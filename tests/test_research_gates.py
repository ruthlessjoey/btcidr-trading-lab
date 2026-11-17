"""Offline tests for fail-closed research evidence gates; no network or protected modules."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from research.pipeline import load_required_crosscheck
from research.engine import EngineError

MANIFEST = {"version_id": "v-test", "csv_sha256": "abc123"}
CFG = {"flagged_dates": ["2020-03-12"]}


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def test_flagged_backtest_without_artifact_is_blocked(self):
        with self.assertRaises(EngineError):
            load_required_crosscheck(CFG, MANIFEST, None)

    def test_missing_file_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(EngineError):
                load_required_crosscheck(CFG, MANIFEST, os.path.join(d, "missing.json"))

    def test_mismatched_dataset_version_or_hash_is_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            payload = {"dataset_version": "other", "dataset_sha256": "abc123",
                       "flagged": [{"date": "2020-03-12", "verdict": "CONFIRMED"}]}
            path = self.write_evidence(d, payload)
            with self.assertRaises(EngineError):
                load_required_crosscheck(CFG, MANIFEST, path)

    def test_unavailable_or_not_confirmed_flagged_day_is_blocked(self):
        for verdict in ("UNAVAILABLE", "NOT CONFIRMED", "MISSING"):
            with tempfile.TemporaryDirectory() as d:
                payload = {"dataset_version": "v-test", "dataset_sha256": "abc123",
                           "flagged": [{"date": "2020-03-12", "verdict": verdict}]}
                path = self.write_evidence(d, payload)
                with self.subTest(verdict=verdict), self.assertRaises(EngineError):
                    load_required_crosscheck(CFG, MANIFEST, path)

    def test_confirmed_dataset_bound_evidence_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            payload = {"dataset_version": "v-test", "dataset_sha256": "abc123",
                       "flagged": [{"date": "2020-03-12",
                                    "verdict": "CONFIRMED (approximate: USD is not USDT)"}]}
            path = self.write_evidence(d, payload)
            self.assertEqual(load_required_crosscheck(CFG, MANIFEST, path), payload)

    def test_every_flagged_date_must_be_confirmed(self):
        cfg = {"flagged_dates": ["2020-03-12", "2020-03-13"]}
        with tempfile.TemporaryDirectory() as d:
            payload = {"dataset_version": "v-test", "dataset_sha256": "abc123",
                       "flagged": [{"date": "2020-03-12", "verdict": "CONFIRMED"}]}
            path = self.write_evidence(d, payload)
            with self.assertRaises(EngineError):
                load_required_crosscheck(cfg, MANIFEST, path)

    def test_no_flagged_dates_does_not_require_crosscheck(self):
        self.assertIsNone(load_required_crosscheck({"flagged_dates": []}, MANIFEST, None))


if __name__ == "__main__":
    unittest.main()
