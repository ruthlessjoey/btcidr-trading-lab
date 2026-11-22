"""Fail-closed publication checks for durable holdout reservations.

This module is called by the research-backtest workflow after it copies completed
records into its research-data checkout and before it removes pending markers.
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path

MAX_JSON_BYTES = 1024 * 1024
MAX_COMPLETED_FILES = 1000


IDENTITY_FIELDS = (
    "key", "frozen_hash", "run_id", "run_attempt", "workflow_ref", "repository"
)


def _reject_symlink_components(path, description):
    absolute = Path(os.path.abspath(os.fspath(path)))
    for component in (absolute, *absolute.parents):
        if component.is_symlink():
            raise RuntimeError(f"{description} must not traverse a symlinked path component")


def _regular_file(path, description):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{description} must be a regular non-symlink file")


def _reject_json_constant(value):
    raise ValueError("non-standard JSON constant")


def _finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


def _same_json_value(left, right):
    """Compare parsed JSON values without Python bool/int equality coercion."""
    try:
        return json.dumps(
            left, sort_keys=True, separators=(",", ":"), allow_nan=False
        ) == json.dumps(
            right, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError, OverflowError):
        return False


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _read_object(path, description, return_identity=False):
    _regular_file(path, description)
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        path_metadata = os.lstat(path)
        if not stat.S_ISREG(path_metadata.st_mode):
            raise RuntimeError(f"{description} must be a regular file")
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise RuntimeError(f"{description} must be a regular file")
            if not os.path.samestat(path_metadata, metadata):
                raise RuntimeError(f"{description} changed during open")
            current_path_metadata = os.lstat(path)
            if (not stat.S_ISREG(current_path_metadata.st_mode)
                    or not os.path.samestat(current_path_metadata, metadata)):
                raise RuntimeError(f"{description} path changed during open")
            raw = stream.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise RuntimeError(f"{description} exceeds the {MAX_JSON_BYTES}-byte JSON limit")
        value = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_json_constant,
            parse_float=_finite_json_float, object_pairs_hook=_unique_object)
    except RuntimeError:
        raise
    except (OSError, ValueError, RecursionError) as exc:
        raise RuntimeError(f"{description} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{description} must contain a JSON object")
    if return_identity:
        return value, (metadata.st_dev, metadata.st_ino, hashlib.sha256(raw).hexdigest())
    return value


def _remove_exact_reservation(path, expected_identity):
    """Atomically stage, verify, then remove only the reservation inode we read."""
    quarantine = Path(tempfile.mkdtemp(prefix=".holdout-publish-", dir=path.parent))
    staged = quarantine / path.name
    try:
        os.rename(path, staged)
        try:
            _, actual_identity = _read_object(
                staged, "staged durable reservation", return_identity=True
            )
        except RuntimeError:
            actual_identity = None
        if actual_identity != expected_identity:
            # The path was replaced after validation. Restore the replacement when
            # possible; never delete it merely because it occupied the old path.
            try:
                if not os.path.lexists(path):
                    os.rename(staged, path)
                    quarantine.rmdir()
            except OSError:
                # Preserve the staged entry in its quarantine directory for recovery.
                pass
            raise RuntimeError(
                "durable reservation changed before cleanup; replacement was preserved"
            )
        staged.unlink()
        quarantine.rmdir()
    except RuntimeError:
        try:
            if os.path.lexists(staged) and not os.path.lexists(path):
                os.rename(staged, path)
            if quarantine.is_dir() and not any(quarantine.iterdir()):
                quarantine.rmdir()
        except OSError:
            pass
        raise
    except OSError as exc:
        try:
            if os.path.lexists(staged) and not os.path.lexists(path):
                os.rename(staged, path)
            if quarantine.is_dir() and not any(quarantine.iterdir()):
                quarantine.rmdir()
        except OSError:
            pass
        raise RuntimeError(
            f"durable reservation cleanup failed safely: {type(exc).__name__}"
        ) from exc


def publish_completed_reservations(registry_dir, output_dir, report_path):
    """Validate every result first, then remove only its exact matching reservation."""
    root = Path(registry_dir)
    output = Path(output_dir)
    _reject_symlink_components(root, "research-data test registry")
    _reject_symlink_components(output, "run output test registry")
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("research-data test registry must be a real directory")
    if not output.exists() and not output.is_symlink():
        return 0
    if output.is_symlink() or not output.is_dir():
        raise RuntimeError("run output test registry must be a real directory")

    candidate_files = list(itertools.islice(
        output.glob("*.json"), MAX_COMPLETED_FILES + 1
    ))
    if len(candidate_files) > MAX_COMPLETED_FILES:
        raise RuntimeError(f"run output contains more than {MAX_COMPLETED_FILES} completed records")
    completed_files = sorted(candidate_files)
    if not completed_files:
        return 0

    report_path = Path(report_path)
    _reject_symlink_components(report_path, "backtest report")
    report = _read_object(report_path, "backtest report")
    report_test = report.get("test")
    if (report.get("status") not in ("OK", "POST_EVALUATION_FAILED")
            or not isinstance(report_test, dict)
            or report_test.get("status") != "evaluated"):
        raise RuntimeError("backtest report does not confirm a completed TEST evaluation")

    pending_to_remove = []
    reservation_identities = {}
    for completed in completed_files:
        _regular_file(completed, "local completed record")
        pending = root / (completed.stem + ".pending")
        if not os.path.lexists(pending):
            raise RuntimeError("durable reservation is missing; refusing to publish completion")
        reservation_record, reservation_identity = _read_object(
            pending, "durable reservation", return_identity=True
        )
        completed_record = _read_object(completed, "local completed record")
        branch_completed = root / completed.name
        branch_record = _read_object(branch_completed, "branch completed record")

        if not _same_json_value(branch_record, completed_record):
            raise RuntimeError("branch completed record differs from this run's result")
        reservation_fields = {"status", *IDENTITY_FIELDS}
        completion_fields = reservation_fields | {"evaluation_number", "re_evaluation", "results"}
        if set(reservation_record) != reservation_fields or set(completed_record) != completion_fields:
            raise RuntimeError("reservation/completion record has unexpected or missing fields")
        if (reservation_record.get("status") != "reserved"
                or completed_record.get("status") != "evaluated"
                or type(completed_record.get("evaluation_number")) is not int
                or completed_record.get("evaluation_number") != 1
                or completed_record.get("re_evaluation") is not False
                or not isinstance(completed_record.get("results"), dict)
                or not completed_record.get("results")):
            raise RuntimeError("reservation/completion status or shape mismatch")
        if reservation_record.get("key") != completed.stem or completed_record.get("key") != completed.stem:
            raise RuntimeError("reservation/completion filename does not match its key")
        if any(
            type(record.get(field)) is not str or not record[field]
            for record in (reservation_record, completed_record)
            for field in IDENTITY_FIELDS
        ) or not re.fullmatch(r"[0-9a-f]{64}", completed_record["frozen_hash"]):
            raise RuntimeError("reservation/completion identity fields are invalid")
        if any(reservation_record[field] != completed_record[field]
               for field in IDENTITY_FIELDS):
            raise RuntimeError("completed record does not match its durable reservation")
        if not _same_json_value(report_test, completed_record):
            raise RuntimeError("report does not match completed TEST record")
        pending_to_remove.append(pending)
        reservation_identities[pending] = reservation_identity

    # Do not mutate even the temporary publisher checkout until every result validates.
    for pending in pending_to_remove:
        # A validated path may be replaced before cleanup. The staging rename is
        # atomic within the registry directory; its inode must still match the
        # descriptor opened and checked during validation.
        _remove_exact_reservation(pending, reservation_identities[pending])
    return len(pending_to_remove)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    publish_completed_reservations(args.registry, args.output, args.report)


if __name__ == "__main__":
    main()
