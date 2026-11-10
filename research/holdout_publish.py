"""Fail-closed publication checks for durable holdout reservations.

This module is called by the research-backtest workflow after it copies completed
records into its research-data checkout and before it removes pending markers.
"""
import argparse
import json
import os
from pathlib import Path


IDENTITY_FIELDS = (
    "key", "frozen_hash", "run_id", "run_attempt", "workflow_ref", "repository"
)


def _regular_file(path, description):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{description} must be a regular non-symlink file")


def _read_object(path, description):
    _regular_file(path, description)
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"{description} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{description} must contain a JSON object")
    return value


def publish_completed_reservations(registry_dir, output_dir, report_path):
    """Validate every result first, then remove only its exact matching reservation."""
    root = Path(registry_dir)
    output = Path(output_dir)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("research-data test registry must be a real directory")
    if not output.exists() and not output.is_symlink():
        return 0
    if output.is_symlink() or not output.is_dir():
        raise RuntimeError("run output test registry must be a real directory")

    report = _read_object(Path(report_path), "backtest report")
    report_test = report.get("test")
    if (report.get("status") not in ("OK", "POST_EVALUATION_FAILED")
            or not isinstance(report_test, dict)
            or report_test.get("status") != "evaluated"):
        raise RuntimeError("backtest report does not confirm a completed TEST evaluation")

    pending_to_remove = []
    for completed in sorted(output.glob("*.json")):
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
                or not isinstance(completed_record.get("results"), dict)):
            raise RuntimeError("reservation/completion status or shape mismatch")
        if reservation_record.get("key") != completed.stem or completed_record.get("key") != completed.stem:
            raise RuntimeError("reservation/completion filename does not match its key")
        if any(reservation_record.get(field) != completed_record.get(field)
               for field in IDENTITY_FIELDS):
            raise RuntimeError("completed record does not match its durable reservation")
        if any(report_test.get(field) != completed_record.get(field)
               for field in IDENTITY_FIELDS):
            raise RuntimeError("backtest report does not match the completed TEST record")
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
