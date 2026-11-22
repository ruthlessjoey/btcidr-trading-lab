import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from research.holdout_publish import _read_object, publish_completed_reservations


class HoldoutPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "research-data"
        self.output = Path(self.temp.name) / "out" / "test_evaluations"
        self.root.mkdir(parents=True)
        self.output.mkdir(parents=True)
        self.report = Path(self.temp.name) / "backtest_report.json"
        self.key = "a" * 25
        self.reservation = {
            "status": "reserved",
            "key": self.key,
            "frozen_hash": "b" * 64,
            "run_id": "123456",
            "run_attempt": "2",
            "workflow_ref": "owner/repo/.github/workflows/research-backtest.yml@refs/heads/main",
            "repository": "owner/repo",
        }
        self.completed = {
            **self.reservation,
            "status": "evaluated",
            "evaluation_number": 1,
            "re_evaluation": False,
            "results": {"BASE": {}},
        }

    def write_json(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def install_pair(self):
        self.write_json(self.root / (self.key + ".pending"), self.reservation)
        self.write_json(self.output / (self.key + ".json"), self.completed)
        self.write_json(self.root / (self.key + ".json"), self.completed)
        self.write_json(self.report, {"status": "OK", "test": self.completed})

    def publish(self):
        return publish_completed_reservations(self.root, self.output, self.report)

    def test_read_object_opens_in_nonblocking_mode(self):
        self.install_pair()
        original_open = os.open
        observed_flags = []

        def record_flags(path, flags, *args, **kwargs):
            if os.fspath(path) == os.fspath(self.report):
                observed_flags.append(flags)
            return original_open(path, flags, *args, **kwargs)

        with mock.patch("research.holdout_publish.os.open", side_effect=record_flags):
            _read_object(self.report, "backtest report")

        self.assertEqual(len(observed_flags), 1)
        self.assertTrue(observed_flags[0] & getattr(os, "O_NONBLOCK", 0))

    def test_read_object_rejects_path_replaced_between_check_and_open(self):
        self.report.write_text('{"status":"OK"}', encoding="utf-8")
        original_open = os.open
        moved = self.report.with_name("original-report.json")

        def replace_then_open(path, flags, *args, **kwargs):
            if os.fspath(path) == os.fspath(self.report):
                os.replace(self.report, moved)
                self.report.write_text('{"status":"REPLACED"}', encoding="utf-8")
            return original_open(path, flags, *args, **kwargs)

        with mock.patch("research.holdout_publish.os.open", side_effect=replace_then_open):
            with self.assertRaisesRegex(RuntimeError, "changed during open"):
                _read_object(self.report, "backtest report")

        self.assertTrue(moved.is_file())
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))["status"], "REPLACED")

    def test_failed_run_with_only_pending_marker_keeps_it_without_completion_report(self):
        pending = self.root / (self.key + ".pending")
        self.write_json(pending, self.reservation)
        self.write_json(self.report, {"status": "FAILED", "error": "synthetic failure"})
        self.assertEqual(self.publish(), 0)
        self.assertTrue(pending.is_file())

    def test_removes_only_exact_matching_durable_reservation(self):
        self.install_pair()
        self.assertEqual(self.publish(), 1)
        self.assertFalse((self.root / (self.key + ".pending")).exists())
        self.assertTrue((self.root / (self.key + ".json")).is_file())

    def test_missing_durable_reservation_refuses_publication(self):
        self.write_json(self.output / (self.key + ".json"), self.completed)
        self.write_json(self.root / (self.key + ".json"), self.completed)
        self.write_json(self.report, {"status": "OK", "test": self.completed})
        with self.assertRaisesRegex(RuntimeError, "reservation is missing"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".json")).is_file())

    def test_conflicting_existing_branch_completion_refuses_cleanup(self):
        self.install_pair()
        conflict = dict(self.completed, run_attempt="3")
        self.write_json(self.root / (self.key + ".json"), conflict)
        with self.assertRaisesRegex(RuntimeError, "differs from this run"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_identity_mismatch_refuses_cleanup(self):
        self.install_pair()
        mismatched = dict(self.completed, run_attempt="3")
        self.write_json(self.output / (self.key + ".json"), mismatched)
        self.write_json(self.root / (self.key + ".json"), mismatched)
        self.write_json(self.report, {"status": "OK", "test": mismatched})
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_preparation_report_cannot_clear_completed_reservation(self):
        self.install_pair()
        self.write_json(self.report, {"status": "RESERVATION_PREPARED", "test": {"status": "reserved"}})
        with self.assertRaisesRegex(RuntimeError, "does not confirm a completed TEST"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_unexpected_reservation_fields_refuse_cleanup(self):
        self.install_pair()
        self.write_json(self.root / (self.key + ".pending"), dict(self.reservation, unexpected="extra"))
        with self.assertRaisesRegex(RuntimeError, "unexpected or missing fields"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_empty_completed_results_refuse_cleanup(self):
        self.install_pair()
        empty = dict(self.completed, results={})
        self.write_json(self.output / (self.key + ".json"), empty)
        self.write_json(self.root / (self.key + ".json"), empty)
        self.write_json(self.report, {"status": "OK", "test": empty})
        with self.assertRaisesRegex(RuntimeError, "status or shape mismatch"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_dangling_pending_symlink_fails_closed(self):
        self.write_json(self.output / (self.key + ".json"), self.completed)
        self.write_json(self.root / (self.key + ".json"), self.completed)
        self.write_json(self.report, {"status": "OK", "test": self.completed})
        os.symlink(self.root / "missing-target", self.root / (self.key + ".pending"))
        with self.assertRaisesRegex(RuntimeError, "regular non-symlink"):
            self.publish()

    def test_report_result_mismatch_refuses_cleanup(self):
        self.install_pair()
        mismatched_report = dict(
            self.completed,
            results={"BASE": {"strategy": {"total_return": -0.75}}},
        )
        self.write_json(self.report, {"status": "OK", "test": mismatched_report})
        with self.assertRaisesRegex(RuntimeError, "report does not match completed TEST record"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_identity_fields_reject_type_coercion_and_malformed_hash(self):
        cases = ("boolean_integer_collision", "non_string_run_id", "malformed_frozen_hash")
        for case in cases:
            with self.subTest(case=case):
                self.install_pair()
                bad_reservation = dict(self.reservation)
                bad_completed = dict(self.completed)
                if case == "boolean_integer_collision":
                    bad_reservation["run_attempt"] = True
                    bad_completed["run_attempt"] = 1
                elif case == "non_string_run_id":
                    bad_reservation["run_id"] = 123456
                    bad_completed["run_id"] = 123456
                else:
                    bad_reservation["frozen_hash"] = "not-a-sha256"
                    bad_completed["frozen_hash"] = "not-a-sha256"
                self.write_json(self.root / (self.key + ".pending"), bad_reservation)
                self.write_json(self.output / (self.key + ".json"), bad_completed)
                self.write_json(self.root / (self.key + ".json"), bad_completed)
                self.write_json(self.report, {"status": "OK", "test": bad_completed})
                with self.assertRaisesRegex(RuntimeError, "identity fields are invalid"):
                    self.publish()
                self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_replacement_reservation_is_preserved_during_cleanup(self):
        self.install_pair()
        pending = self.root / (self.key + ".pending")
        replacement = dict(self.reservation, run_attempt="99")
        backup = self.root / "replaced-pending.json"
        original_rename = os.rename
        replaced = False

        def replace_before_stage(source, destination):
            nonlocal replaced
            if not replaced and os.fspath(source) == os.fspath(pending):
                replaced = True
                os.replace(pending, backup)
                self.write_json(pending, replacement)
            return original_rename(source, destination)

        with mock.patch("research.holdout_publish.os.rename", side_effect=replace_before_stage):
            with self.assertRaisesRegex(
                    RuntimeError, "durable reservation changed before cleanup"):
                self.publish()

        self.assertTrue(replaced)
        self.assertTrue(pending.is_file())
        self.assertEqual(json.loads(pending.read_text(encoding="utf-8")), replacement)
        self.assertTrue(backup.is_file())
        self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), self.reservation)
        self.assertFalse(any(self.root.glob(".holdout-publish-*")))

    def test_report_boolean_does_not_match_integer_evaluation_number(self):
        self.install_pair()
        mismatched_report = dict(self.completed, evaluation_number=True)
        self.write_json(self.report, {"status": "OK", "test": mismatched_report})
        with self.assertRaisesRegex(RuntimeError, "report does not match completed TEST record"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_branch_record_boolean_does_not_match_integer_evaluation_number(self):
        self.install_pair()
        mismatched_branch_record = dict(self.completed, evaluation_number=True)
        self.write_json(self.root / (self.key + ".json"), mismatched_branch_record)
        with self.assertRaisesRegex(RuntimeError, "branch completed record differs from this run's result"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_overflowing_json_float_refuses_cleanup(self):
        self.install_pair()
        raw = json.dumps({"status": "OK", "test": self.completed}, sort_keys=True)
        needle = '"results": {"BASE": {}}'
        self.assertIn(needle, raw)
        raw = raw.replace(needle, '"results": {"BASE": {"metric": 1e999}}')
        self.report.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreadable: ValueError"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_valid_first_record_is_not_removed_if_later_record_is_invalid(self):
        self.install_pair()
        other_key = "c" * 25
        other_reservation = dict(self.reservation, key=other_key)
        other_completed = dict(self.completed, key=other_key)
        self.write_json(self.root / (other_key + ".pending"), other_reservation)
        self.write_json(self.output / (other_key + ".json"), other_completed)
        self.write_json(self.root / (other_key + ".json"), dict(other_completed, run_attempt="9"))
        self.write_json(self.report, {"status": "OK", "test": self.completed})
        with self.assertRaisesRegex(RuntimeError, "differs from this run"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())
        self.assertTrue((self.root / (other_key + ".pending")).is_file())


    def test_duplicate_json_keys_refuse_cleanup(self):
        self.install_pair()
        pending = self.root / (self.key + ".pending")
        pending.write_text(
            json.dumps(self.reservation, sort_keys=True).replace(
                '"status": "reserved"', '"status": "reserved", "status": "evaluated"'),
            encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreadable: ValueError"):
            self.publish()
        self.assertTrue(pending.is_file())

    def test_nonstandard_json_constant_refuses_cleanup(self):
        self.install_pair()
        completed = self.output / (self.key + ".json")
        raw = json.dumps(self.completed, sort_keys=True)
        raw = raw.replace('"results": {"BASE": {}}', '"results": {"BASE": {"metric": NaN}}')
        completed.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "unreadable: ValueError"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())


    def test_symlinked_registry_parent_refuses_cleanup(self):
        self.install_pair()
        alias = self.root.parent / "registry-parent-alias"
        os.symlink(self.root.parent, alias, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinked path component"):
            publish_completed_reservations(alias / self.root.name, self.output, self.report)
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_symlinked_output_parent_refuses_cleanup(self):
        self.install_pair()
        alias = self.output.parent.parent / "output-parent-alias"
        os.symlink(self.output.parent, alias, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinked path component"):
            publish_completed_reservations(self.root, alias / self.output.name, self.report)
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_oversized_completed_record_refuses_cleanup(self):
        self.install_pair()
        completed = self.output / (self.key + ".json")
        completed.write_text('{"payload":"' + ("x" * (1024 * 1024)) + '"}', encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "exceeds the 1048576-byte JSON limit"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())


    def test_completed_record_count_limit_refuses_publication(self):
        self.install_pair()
        for index in range(1000):
            (self.output / f"extra-{index}.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "more than 1000 completed records"):
            self.publish()
        self.assertTrue((self.root / (self.key + ".pending")).is_file())

    def test_completed_file_enumeration_stops_at_limit_plus_one(self):
        yielded = 0

        def many_json_files(path, pattern):
            nonlocal yielded
            for index in range(10000):
                yielded += 1
                yield path / f"record-{index}.json"

        with mock.patch.object(Path, "glob", new=many_json_files):
            with self.assertRaisesRegex(RuntimeError, "more than 1000 completed records"):
                self.publish()

        self.assertEqual(yielded, 1001)

    def test_symlinked_report_parent_refuses_cleanup(self):
        self.install_pair()
        alias = self.report.parent / "report-parent-alias"
        os.symlink(self.report.parent, alias, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlinked path component"):
            publish_completed_reservations(self.root, self.output, alias / self.report.name)
        self.assertTrue((self.root / (self.key + ".pending")).is_file())



if __name__ == "__main__":
    unittest.main()
