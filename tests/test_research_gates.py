"""Offline tests for fail-closed research evidence gates; no network or protected modules."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from research.pipeline import (load_required_crosscheck, validate_crosscheck_artifact,
                               AUTHORIZED_CROSSCHECK_PROVIDERS)
from research.engine import EngineError

MANIFEST = {"version_id": "v-test", "csv_sha256": "abc123"}
CFG = {"flagged_dates": ["2020-03-12"]}
TEST_APPROVED = frozenset({"coinbase"})


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def payload(self, verdict="CONFIRMED", provider="coinbase"):
        return {"dataset_version": "v-test", "dataset_sha256": "abc123",
                "providers": [provider],
                "flagged": [{"date": "2020-03-12", "verdict": verdict}]}

    def test_no_independent_provider_is_currently_authorized(self):
        self.assertEqual(AUTHORIZED_CROSSCHECK_PROVIDERS, frozenset())
        with self.assertRaisesRegex(EngineError, "no independent cross-check provider"):
            load_required_crosscheck(CFG, MANIFEST, None)

    def test_missing_artifact_is_blocked_when_a_provider_is_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(EngineError, "no artifact"):
                validate_crosscheck_artifact(CFG, MANIFEST, os.path.join(d, "missing.json"),
                                             TEST_APPROVED)

    def test_dataset_version_and_hash_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.payload()
            p["dataset_sha256"] = "wrong"
            path = self.write_evidence(d, p)
            with self.assertRaisesRegex(EngineError, "does not match"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_provider_must_be_explicitly_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload(provider="bitstamp"))
            with self.assertRaisesRegex(EngineError, "authorized independent providers"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_flagged_day_must_be_confirmed(self):
        for verdict in ("UNAVAILABLE", "NOT CONFIRMED", "MISSING"):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(verdict=verdict))
                with self.subTest(verdict=verdict), self.assertRaisesRegex(EngineError, "lacks confirmed"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_flagged_date_must_be_confirmed(self):
        cfg = {"flagged_dates": ["2020-03-12", "2020-03-13"]}
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload())
            with self.assertRaisesRegex(EngineError, "2020-03-13"):
                validate_crosscheck_artifact(cfg, MANIFEST, path, TEST_APPROVED)

    def test_valid_dataset_bound_authorized_evidence_is_accepted_by_validator(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.payload("CONFIRMED (approximate: USD is not USDT)")
            path = self.write_evidence(d, p)
            self.assertEqual(validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED), p)

    def test_no_flagged_dates_does_not_require_crosscheck(self):
        self.assertIsNone(load_required_crosscheck({"flagged_dates": []}, MANIFEST, None))


class HistoryGateStaticTests(unittest.TestCase):
    def test_unverified_market_identity_fails_before_first_network_request(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        fail_marker = 'add("market_identity", FAIL,'
        refusal = 'raise ApiError("market identity cannot be independently verified'
        first_request = 'server_now = fetcher.extract_server_time(http.get('
        self.assertIn(fail_marker, source)
        self.assertIn(refusal, source)
        self.assertLess(source.index(fail_marker), source.index(first_request))
        self.assertLess(source.index(refusal), source.index(first_request))


if __name__ == "__main__":
    unittest.main()
