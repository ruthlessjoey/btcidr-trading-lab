"""Safe cross-check gate tests using only the unprotected research.crosscheck module.

The production pipeline adapts CrosscheckError to its protected engine error type,
but these tests exercise the same dataset-evidence validation without importing or
executing research.pipeline, research.engine, validator.py, or report.py.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from research.crosscheck import (
    CrosscheckError, AUTHORIZED_CROSSCHECK_PROVIDERS,
    load_required_crosscheck, validate_crosscheck_artifact,
)
from research.backtest_report import crosscheck_status_line

MANIFEST = {"version_id": "v-test", "csv_sha256": "abc123"}
CFG = {"flagged_dates": ["2020-03-12"]}
TEST_APPROVED = frozenset({"coinbase", "bitstamp"})


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    @staticmethod
    def comparison():
        return {
            "open_diff_pct": 0.0,
            "close_diff_pct": 0.0,
            "high_diff_pct": 0.0,
            "low_diff_pct": 0.0,
            "binance_return_pct": 0.0,
            "other_return_pct": 0.0,
            "return_gap_pp": 0.0,
            "agrees": True,
        }

    def payload(self, verdict="CONFIRMED (approximate: USD is not USDT)", provider=None):
        providers = ["coinbase", "bitstamp"] if provider is None else ["coinbase", provider]
        return {
            "dataset_version": "v-test",
            "dataset_sha256": "abc123",
            "providers": providers,
            "flagged": [{
                "date": "2020-03-12",
                "verdict": verdict,
                "coinbase": self.comparison(),
                "bitstamp": self.comparison(),
            }],
        }

    def test_no_independent_provider_is_currently_authorized(self):
        self.assertEqual(AUTHORIZED_CROSSCHECK_PROVIDERS, frozenset())
        with self.assertRaisesRegex(CrosscheckError, "no independent cross-check provider"):
            load_required_crosscheck(CFG, MANIFEST, None)

    def test_missing_artifact_is_blocked_when_a_provider_is_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CrosscheckError, "no artifact"):
                validate_crosscheck_artifact(CFG, MANIFEST, os.path.join(d, "missing.json"),
                                             TEST_APPROVED)

    def test_dataset_version_and_hash_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.payload()
            p["dataset_sha256"] = "wrong"
            path = self.write_evidence(d, p)
            with self.assertRaisesRegex(CrosscheckError, "does not match"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_provider_must_be_explicitly_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload(provider="kraken"))
            with self.assertRaisesRegex(CrosscheckError, "authorized independent providers"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_malformed_or_duplicate_flagged_entries_are_rejected(self):
        malformed = [
            {"dataset_version": "v-test", "dataset_sha256": "abc123",
             "providers": ["coinbase"], "flagged": None},
            {"dataset_version": "v-test", "dataset_sha256": "abc123",
             "providers": ["coinbase"], "flagged": ["not-an-object"]},
            {"dataset_version": "v-test", "dataset_sha256": "abc123",
             "providers": ["coinbase"], "flagged": [
                 {"date": "2020-03-12", "verdict": "CONFIRMED"},
                 {"date": "2020-03-12", "verdict": "CONFIRMED"}]},
            {"dataset_version": "v-test", "dataset_sha256": "abc123",
             "providers": ["coinbase", "coinbase"],
             "flagged": [{"date": "2020-03-12", "verdict": "CONFIRMED"}]},
        ]
        for payload in malformed:
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(payload=payload), self.assertRaises(CrosscheckError):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_flagged_day_must_be_confirmed(self):
        for verdict in ("UNAVAILABLE", "NOT CONFIRMED", "MISSING"):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(verdict=verdict))
                with self.subTest(verdict=verdict), self.assertRaisesRegex(CrosscheckError, "lacks confirmed"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_flagged_date_must_be_confirmed(self):
        cfg = {"flagged_dates": ["2020-03-12", "2020-03-13"]}
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload())
            with self.assertRaisesRegex(CrosscheckError, "2020-03-13"):
                validate_crosscheck_artifact(cfg, MANIFEST, path, TEST_APPROVED)

    def test_valid_dataset_bound_authorized_evidence_is_accepted_by_validator(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.payload("CONFIRMED (approximate: USD is not USDT)")
            path = self.write_evidence(d, p)
            self.assertEqual(validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED), p)

    def test_no_flagged_dates_does_not_require_crosscheck(self):
        self.assertIsNone(load_required_crosscheck({"flagged_dates": []}, MANIFEST, None))


class BacktestReportCrosscheckBoundaryTests(unittest.TestCase):
    def test_missing_crosscheck_is_reported_as_unverified(self):
        rendered = crosscheck_status_line(None)
        self.assertIn("No independent cross-check was run", rendered)
        self.assertIn("flagged candle remains unverified", rendered)

    def test_supplied_crosscheck_payload_is_suppressed_without_provider_authorization(self):
        payload = {
            "flagged": [{"date": "2020-03-12", "verdict": "CONFIRMED"}],
            "summary": {"max_abs_close_diff_pct": "UNTRUSTED_PROVIDER_MARKER"},
        }
        rendered = crosscheck_status_line(payload)
        self.assertIn("suppressed", rendered)
        self.assertIn("no independent provider is authorized", rendered)
        self.assertNotIn("CONFIRMED", rendered)
        self.assertNotIn("UNTRUSTED_PROVIDER_MARKER", rendered)


class HistoryGateStaticTests(unittest.TestCase):
    def test_unverified_market_identity_fails_without_any_network_request(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"name": "market_identity", "status": "FAIL"', source)
        self.assertIn('"network_requests": 0', source)
        self.assertIn('"backtest_allowed": False', source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("import validator", source)


if __name__ == "__main__":
    unittest.main()
