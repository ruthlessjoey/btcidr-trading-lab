"""Safe cross-check gate tests using only the unprotected research.crosscheck module.

The production pipeline adapts CrosscheckError to its protected engine error type,
but these tests exercise the same dataset-evidence validation without importing or
executing research.pipeline, research.engine, validator.py, or report.py.
"""
import ast
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import research.crosscheck as crosscheck
from research.crosscheck import (
    CrosscheckError, AUTHORIZED_CROSSCHECK_PROVIDERS,
    CROSSCHECK_ARTIFACT_PRODUCER, CROSSCHECK_ARTIFACT_SCHEMA,
    CONFIRMED_VERDICT, compare, is_confirmed_verdict, load_required_crosscheck,
    to_ts, validate_crosscheck_artifact,
)

MANIFEST = {"version_id": "v-test", "csv_sha256": "abc123"}
CFG = {"flagged_dates": ["2020-03-12"]}
TEST_APPROVED = frozenset({"coinbase", "bitstamp"})


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def payload(self, verdict=CONFIRMED_VERDICT, providers=("coinbase", "bitstamp"),
                agreements=None):
        agreements = agreements or {}
        entry = {"date": "2020-03-12", "verdict": verdict}
        for provider in providers:
            entry[provider] = {"agrees": agreements.get(provider, True)}
        return {
            "schema": CROSSCHECK_ARTIFACT_SCHEMA,
            "producer": CROSSCHECK_ARTIFACT_PRODUCER,
            "dataset_version": "v-test",
            "dataset_sha256": "abc123",
            "providers": list(providers),
            "flagged": [entry],
        }

    def test_production_crosscheck_loader_stays_disabled_even_if_module_constant_is_reassigned(self):
        original = crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS
        try:
            crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = TEST_APPROVED
            with self.assertRaisesRegex(CrosscheckError, "at least two distinct authorized providers"):
                load_required_crosscheck(CFG, MANIFEST, None)
        finally:
            crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = original

    def test_validator_requires_two_authorized_providers(self):
        with self.assertRaisesRegex(CrosscheckError, "at least two distinct authorized providers"):
            validate_crosscheck_artifact(CFG, MANIFEST, None, frozenset({"coinbase"}))

    def test_missing_artifact_is_blocked_when_two_providers_are_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CrosscheckError, "no artifact"):
                validate_crosscheck_artifact(
                    CFG, MANIFEST, os.path.join(d, "missing.json"), TEST_APPROVED
                )

    def test_dataset_version_and_hash_must_match(self):
        for field, value in (("dataset_version", "wrong-version"),
                             ("dataset_sha256", "wrong-hash")):
            with tempfile.TemporaryDirectory() as d:
                payload = self.payload()
                payload[field] = value
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "does not match"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_artifact_requires_exact_schema_and_producer_identity(self):
        for field, value in (("schema", "twin-money-maker.crosscheck/v999"),
                             ("producer", "untrusted.producer")):
            with tempfile.TemporaryDirectory() as d:
                payload = self.payload()
                payload[field] = value
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "schema or producer"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_provider_must_be_explicitly_authorized_and_distinct(self):
        payloads = (
            self.payload(providers=("coinbase", "kraken")),
            self.payload(providers=("coinbase", "coinbase")),
            self.payload(providers=("coinbase",)),
        )
        for payload in payloads:
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(providers=payload["providers"]), self.assertRaises(CrosscheckError):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_malformed_or_duplicate_flagged_entries_are_rejected(self):
        malformed = []
        missing_list = self.payload()
        missing_list["flagged"] = None
        malformed.append(missing_list)
        non_object = self.payload()
        non_object["flagged"] = ["not-an-object"]
        malformed.append(non_object)
        duplicate_date = self.payload()
        duplicate_date["flagged"].append(dict(duplicate_date["flagged"][0]))
        malformed.append(duplicate_date)
        extra_date = self.payload()
        extra_date["flagged"].append({
            "date": "2020-03-13", "verdict": CONFIRMED_VERDICT,
            "coinbase": {"agrees": True}, "bitstamp": {"agrees": True},
        })
        malformed.append(extra_date)
        for payload in malformed:
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(payload=payload), self.assertRaises(CrosscheckError):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_each_flagged_date_requires_affirmative_evidence_from_both_providers(self):
        for agreements in (
            {"coinbase": False, "bitstamp": True},
            {"coinbase": True, "bitstamp": False},
            {"coinbase": True, "bitstamp": None},
            {"coinbase": True, "bitstamp": 1},
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(agreements=agreements))
                with self.subTest(agreements=agreements), self.assertRaisesRegex(
                        CrosscheckError, "lacks affirmative agreement"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

        payload = self.payload()
        del payload["flagged"][0]["bitstamp"]
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, payload)
            with self.assertRaisesRegex(CrosscheckError, "lacks affirmative agreement"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_only_exact_confirmed_verdict_is_accepted(self):
        self.assertTrue(is_confirmed_verdict(CONFIRMED_VERDICT))
        for verdict in (
            "CONFIRMED",
            "CONFIRMED_UNTRUSTED",
            "CONFIRMED-malformed",
            "CONFIRMED but not actually confirmed",
            "NOT CONFIRMED",
            "UNAVAILABLE",
            "",
            None,
            {"verdict": CONFIRMED_VERDICT},
        ):
            with self.subTest(verdict=verdict):
                self.assertFalse(is_confirmed_verdict(verdict))
        for verdict in (
            "CONFIRMED_UNTRUSTED",
            "CONFIRMED-malformed",
            "NOT CONFIRMED",
            "UNAVAILABLE",
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(verdict=verdict))
                with self.subTest(verdict=verdict), self.assertRaisesRegex(
                        CrosscheckError, "exact confirmed verdict"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_flagged_date_must_have_two_source_confirmation(self):
        cfg = {"flagged_dates": ["2020-03-12", "2020-03-13"]}
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload())
            with self.assertRaisesRegex(CrosscheckError, "flagged dates do not exactly match"):
                validate_crosscheck_artifact(cfg, MANIFEST, path, TEST_APPROVED)

    def test_valid_dataset_bound_two_provider_evidence_is_accepted_by_validator(self):
        with tempfile.TemporaryDirectory() as d:
            payload = self.payload()
            path = self.write_evidence(d, payload)
            self.assertEqual(
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED), payload
            )

    def test_comparison_never_confirms_when_either_independent_source_is_missing_or_disagrees(self):
        previous = to_ts("2020-03-11")
        target = to_ts("2020-03-12")

        def candle(timestamp, price):
            return SimpleNamespace(
                time=timestamp, open=price, high=price, low=price, close=price
            )

        binance = [candle(previous, 100), candle(target, 110)]
        coinbase = {previous: candle(previous, 100), target: candle(target, 110)}
        bitstamp = {previous: candle(previous, 100), target: candle(target, 110)}

        result = compare(binance, coinbase, {}, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], "UNAVAILABLE")

        result = compare(binance, coinbase, bitstamp, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], CONFIRMED_VERDICT)

        disagreeing = {
            previous: candle(previous, 100),
            target: candle(target, 200),
        }
        result = compare(binance, coinbase, disagreeing, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], "NOT CONFIRMED")

    def test_no_flagged_dates_does_not_require_crosscheck(self):
        self.assertIsNone(load_required_crosscheck(
            {"flagged_dates": []}, MANIFEST, None
        ))


class CrosscheckPipelineBoundaryTests(unittest.TestCase):
    def test_backtest_loader_passes_a_fresh_empty_authorization_set(self):
        path = os.path.join(ROOT, "research", "pipeline.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)

        assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if any(isinstance(target, ast.Name)
                   and target.id == "AUTHORIZED_CROSSCHECK_PROVIDERS"
                   for target in targets):
                assignments.append(node)
        self.assertEqual(assignments, [])

        loader = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "load_required_crosscheck")
        calls = [node for node in ast.walk(loader)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "validate_crosscheck_artifact"]
        self.assertEqual(len(calls), 1)
        authorization = calls[0].args[-1]
        self.assertIsInstance(authorization, ast.Call)
        self.assertIsInstance(authorization.func, ast.Name)
        self.assertEqual(authorization.func.id, "frozenset")
        self.assertEqual(authorization.args, [])
        self.assertEqual(authorization.keywords, [])


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
