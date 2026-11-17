"""Offline tests for fail-closed research evidence gates; no network or protected modules."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from research.pipeline import load_required_crosscheck, AUTHORIZED_CROSSCHECK_PROVIDERS
from research.engine import EngineError

MANIFEST = {"version_id": "v-test", "csv_sha256": "abc123"}
CFG = {"flagged_dates": ["2020-03-12"]}


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def test_no_independent_provider_is_authorized(self):
        self.assertEqual(AUTHORIZED_CROSSCHECK_PROVIDERS, frozenset())
        with self.assertRaisesRegex(EngineError, "no independent cross-check provider"):
            load_required_crosscheck(CFG, MANIFEST, None)

    def test_artifact_cannot_bypass_missing_owner_authorization(self):
        with tempfile.TemporaryDirectory() as d:
            payload = {"dataset_version": "v-test", "dataset_sha256": "abc123",
                       "providers": ["coinbase"],
                       "flagged": [{"date": "2020-03-12", "verdict": "CONFIRMED"}]}
            path = self.write_evidence(d, payload)
            with self.assertRaises(EngineError):
                load_required_crosscheck(CFG, MANIFEST, path)

    def test_missing_or_unreadable_artifact_is_blocked_after_provider_approval(self):
        # Current provider allowlist is empty, so all flagged-date backtests stop even earlier.
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(EngineError):
                load_required_crosscheck(CFG, MANIFEST, os.path.join(d, "missing.json"))

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
