"""Protected-path-safe tests for the generic M5 strategy contract and engine.

This suite intentionally uses only synthetic fixtures. It never calls default_registry(),
imports btc_s1, reads signal/, opens a provider, or accesses the network.
"""
import json
import sys
import unittest
from types import SimpleNamespace

from markets.strategies import contract as C
from markets.strategies.decision import canonical_json, config_fingerprint
from markets.strategies.engine import evaluate_report
from markets.strategies.registry import StrategyRegistry


LISTING = "tokocrypto-spot-btc-idr"
DAY = 86_400
NOW = 1_700_000_000


def make_listing(*, canonical=LISTING, market_type="spot", asset_class="crypto",
                 base="BTC", quote="IDR"):
    instrument = SimpleNamespace(asset_class=asset_class, base=base, quote=quote)
    return SimpleNamespace(canonical=canonical, market_type=market_type, instrument=instrument)


def make_candles(count=2):
    return [SimpleNamespace(open_time_s=NOW - (count - index) * DAY)
            for index in range(count)]


def make_report(*, status="COMPLETE", timeframe_s=DAY, listing=LISTING,
                canonical_candles="default", error=None):
    if canonical_candles == "default":
        canonical_candles = make_candles()
    return {
        "timeframe_s": timeframe_s,
        "reference_time": {"now_s": NOW + DAY, "source": "synthetic-fixture"},
        "status": status,
        "stage": "synthetic-validation",
        "data_source": "synthetic-fixture",
        "provider": {"name": "offline-fixture", "venue": "offline"},
        "pipeline_version": "test-only",
        "freshness": {"state": "FRESH"},
        "candles": {"dataset_sha256": "a" * 64, "raw_sha256": "b" * 64},
        "error": error,
        "listing": {"canonical": listing},
        "reasons": ["synthetic fixture"],
        "canonical_candles": canonical_candles,
    }


class RecordingStrategy(C.Strategy):
    strategy_id = "synthetic-test"
    version = "v1"
    description = "offline synthetic strategy"
    asset_classes = ("crypto",)
    market_types = ("spot",)
    base_assets = ("BTC",)
    quote_assets = ("IDR",)
    intervals_s = (DAY,)
    CONFIG_SCHEMA = {"window": C.ParamSpec("int", 2, 1, 10)}
    reason_codes = ("SYNTHETIC_SIGNAL",)

    def __init__(self, raw_result=None):
        self.calls = 0
        self.seen_candles = None
        self.raw_result = raw_result

    def required_history(self, config):
        return config["window"]

    def evaluate(self, config, candles):
        self.calls += 1
        self.seen_candles = candles
        if self.raw_result is not None:
            return self.raw_result
        return {
            "decision": C.BUY,
            "reason_codes": ["SYNTHETIC_SIGNAL"],
            "reasons": ["synthetic complete-data decision"],
            "indicators": {"score": 1.123456789},
        }


class M5IsolatedStrategyTests(unittest.TestCase):
    def setUp(self):
        self.strategy = RecordingStrategy()
        self.listing = make_listing()
        self.report = make_report()

    def assert_no_protected_strategy_import(self):
        self.assertNotIn("markets.strategies.btc_s1", sys.modules)
        self.assertNotIn("signal.btc_signal", sys.modules)

    def test_complete_report_calls_strategy_once_after_history_and_serializes(self):
        decision = evaluate_report(self.strategy, self.listing, self.report)

        self.assertEqual(self.strategy.calls, 1)
        self.assertEqual(len(self.strategy.seen_candles), 2)
        self.assertEqual(decision.decision, C.BUY)
        self.assertEqual(decision.reason_codes, ("SYNTHETIC_SIGNAL",))
        self.assertEqual(decision.evaluation_now_s, NOW + DAY)
        self.assertEqual(decision.reference_open_s, self.report["canonical_candles"][-1].open_time_s)
        self.assertEqual(decision.reference_close_s, decision.reference_open_s + DAY)
        self.assertEqual(decision.indicators["score"], 1.12345679)

        encoded = decision.to_json()
        self.assertEqual(json.loads(encoded)["schema"], "strategy-decision-m5-v1")
        self.assertEqual(encoded, canonical_json(json.loads(encoded)))
        self.assertIn("not an order", encoded.lower())
        self.assert_no_protected_strategy_import()

    def test_unsupported_interval_refuses_before_strategy_evaluation(self):
        report = make_report(timeframe_s=3_600)
        decision = evaluate_report(self.strategy, self.listing, report)

        self.assertEqual(decision.decision, C.INVALID)
        self.assertIn("UNSUPPORTED_INTERVAL", decision.reason_codes)
        self.assertEqual(self.strategy.calls, 0)

    def test_unsupported_listing_refuses_before_strategy_evaluation(self):
        listing = make_listing(base="ETH")
        decision = evaluate_report(self.strategy, listing, self.report)

        self.assertEqual(decision.decision, C.INVALID)
        self.assertIn("UNSUPPORTED_LISTING", decision.reason_codes)
        self.assertEqual(self.strategy.calls, 0)

    def test_report_listing_mismatch_refuses_before_strategy_evaluation(self):
        report = make_report(listing="different-listing")
        decision = evaluate_report(self.strategy, self.listing, report)

        self.assertEqual(decision.decision, C.INVALID)
        self.assertIn("LISTING_MISMATCH", decision.reason_codes)
        self.assertEqual(self.strategy.calls, 0)

    def test_refused_partial_and_unavailable_never_reach_strategy(self):
        cases = (
            ("REFUSED", C.INVALID, "DATA_REFUSED",
             {"code": "SYNTHETIC_REFUSAL", "detail": "fixture only"}),
            ("PARTIAL", C.NO_DATA, "DATA_INCOMPLETE", None),
            ("UNAVAILABLE", C.NO_DATA, "DATA_UNAVAILABLE", None),
        )
        for status, expected_decision, expected_code, error in cases:
            with self.subTest(status=status):
                strategy = RecordingStrategy()
                decision = evaluate_report(
                    strategy, self.listing,
                    make_report(status=status, error=error, canonical_candles=None),
                )
                self.assertEqual(decision.decision, expected_decision)
                self.assertIn(expected_code, decision.reason_codes)
                self.assertEqual(strategy.calls, 0)
                if status == "REFUSED":
                    self.assertEqual(decision.to_dict()["provenance"]["provider_error"], error)
        self.assert_no_protected_strategy_import()

    def test_complete_report_without_candles_is_invalid(self):
        decision = evaluate_report(
            self.strategy, self.listing,
            make_report(canonical_candles=None),
        )
        self.assertEqual(decision.decision, C.INVALID)
        self.assertIn("INPUT_MISSING", decision.reason_codes)
        self.assertEqual(self.strategy.calls, 0)

    def test_insufficient_history_returns_no_data_without_evaluation(self):
        decision = evaluate_report(
            self.strategy, self.listing,
            make_report(canonical_candles=make_candles(1)),
        )
        self.assertEqual(decision.decision, C.NO_DATA)
        self.assertIn("INSUFFICIENT_HISTORY", decision.reason_codes)
        self.assertEqual(self.strategy.calls, 0)

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(C.StrategyError):
            evaluate_report(self.strategy, self.listing, make_report(status="UNKNOWN"))
        self.assertEqual(self.strategy.calls, 0)

    def test_strategy_configuration_rejects_unknown_keys_and_boolean_numbers(self):
        with self.assertRaises(C.StrategyConfigError):
            evaluate_report(self.strategy, self.listing, self.report, {"unknown": 1})
        with self.assertRaises(C.StrategyConfigError):
            evaluate_report(self.strategy, self.listing, self.report, {"window": True})
        self.assertEqual(self.strategy.calls, 0)

    def test_required_history_must_be_a_positive_plain_integer(self):
        for value in (True, 0, -1, 1.5, "2", None):
            with self.subTest(value=value):
                strategy = RecordingStrategy()
                strategy.required_history = lambda config, result=value: result
                with self.assertRaises(C.StrategyError):
                    evaluate_report(strategy, self.listing, self.report)
                self.assertEqual(strategy.calls, 0)

    def test_strategy_result_must_match_contract(self):
        invalid_results = (
            {"decision": C.BUY},
            {"decision": C.NO_DATA, "reason_codes": [], "reasons": [], "indicators": {}},
            {"decision": C.BUY, "reason_codes": ["UNDECLARED"], "reasons": [], "indicators": {}},
            {"decision": C.BUY, "reason_codes": None, "reasons": [], "indicators": {}},
            {"decision": C.BUY, "reason_codes": "SYNTHETIC_SIGNAL", "reasons": [], "indicators": {}},
            {"decision": C.BUY, "reason_codes": ["SYNTHETIC_SIGNAL"], "reasons": None, "indicators": {}},
            {"decision": C.BUY, "reason_codes": ["SYNTHETIC_SIGNAL"], "reasons": ["ok", 1], "indicators": {}},
            {"decision": C.BUY, "reason_codes": ["SYNTHETIC_SIGNAL"], "reasons": [], "indicators": []},
            {"decision": C.BUY, "reason_codes": ["SYNTHETIC_SIGNAL"], "reasons": [], "indicators": {1: 1.0}},
            {"decision": C.BUY, "reason_codes": ["SYNTHETIC_SIGNAL"], "reasons": [], "indicators": {"score": float("nan")}},
        )
        for raw in invalid_results:
            with self.subTest(raw=raw):
                strategy = RecordingStrategy(raw_result=raw)
                with self.assertRaises(C.StrategyError):
                    evaluate_report(strategy, self.listing, self.report)

    def test_registry_requires_explicit_identity_and_exact_version(self):
        registry = StrategyRegistry()
        strategy = RecordingStrategy()
        registry.register(strategy)
        self.assertIs(registry.lookup("synthetic-test", "v1"), strategy)
        self.assertEqual(registry.ids(), ("synthetic-test",))
        with self.assertRaises(C.DuplicateStrategyError):
            registry.register(RecordingStrategy())
        other_version = RecordingStrategy()
        other_version.version = "v2"
        with self.assertRaises(C.VersionConflictError):
            registry.register(other_version)
        with self.assertRaises(C.VersionConflictError):
            registry.lookup("synthetic-test", "v2")
        with self.assertRaises(C.UnknownStrategyError):
            registry.lookup("not-registered", "v1")

    def test_configuration_fingerprint_is_deterministic(self):
        first = config_fingerprint("synthetic-test", "v1", {"window": 2})
        second = config_fingerprint("synthetic-test", "v1", {"window": 2})
        other_version = config_fingerprint("synthetic-test", "v2", {"window": 2})
        self.assertEqual(first, second)
        self.assertNotEqual(first, other_version)
        self.assertEqual(len(first), 64)
        self.assert_no_protected_strategy_import()


if __name__ == "__main__":
    unittest.main()
