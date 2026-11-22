"""Fail-closed publication checks for durable holdout reservations.

This module is called by the research-backtest workflow after it copies completed
records into its research-data checkout and before it removes pending markers.
"""
import argparse
import itertools
import json
import math
import os
import stat
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


def _read_object(path, description):
    _regular_file(path, description)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise RuntimeError(f"{description} must be a regular file")
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
    return value


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
    for completed in completed_files:
        _regular_file(completed, "local completed record")
        pending = root / (completed.stem + ".pending")
        if not os.path.lexists(pending):
            raise RuntimeError("durable reservation is missing; refusing to publish completion")
        reservation_record = _read_object(pending, "durable reservation")
        completed_record = _read_object(completed, "local completed record")
        branch_completed = root / completed.name
        branch_record = _read_object(branch_completed, "branch completed record")

        if branch_record != completed_record:
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
        if any(reservation_record.get(field) != completed_record.get(field)
               for field in IDENTITY_FIELDS):
            raise RuntimeError("completed record does not match its durable reservation")
        if not _same_json_value(report_test, completed_record):
            raise RuntimeError("report does not match completed TEST record")
        pending_to_remove.append(pending)

    # Do not mutate even the temporary publisher checkout until every result validates.
    for pending in pending_to_remove:
        pending.unlink()
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
