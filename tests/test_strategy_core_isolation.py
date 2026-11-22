"""Isolated M5 contract/decision/engine tests.

This harness intentionally bypasses markets/__init__.py and
markets/strategies/__init__.py so it does not load registry/default_registry,
btc_s1, the protected S1 signal code, providers, data pipeline, risk, or validator.
Only the three pure strategy-core modules are imported.
"""
import ast
import json
import os
import sys
import types
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Test-only package shells keep Python from executing the normal package
# initializers, which expose the default registry and its lazy S1 adapter.
markets_package = types.ModuleType("markets")
markets_package.__path__ = [os.path.join(ROOT, "markets")]
sys.modules["markets"] = markets_package

strategies_package = types.ModuleType("markets.strategies")
strategies_package.__path__ = [os.path.join(ROOT, "markets", "strategies")]
sys.modules["markets.strategies"] = strategies_package

from markets.strategies import contract as C  # noqa: E402
from markets.strategies.decision import StrategyDecision, config_fingerprint  # noqa: E402
from markets.strategies.engine import evaluate_report  # noqa: E402


LISTING = SimpleNamespace(
    canonical="crypto:fixture-spot:BTC-USDT",
    market_type="spot",
    instrument=SimpleNamespace(asset_class="crypto", base="BTC", quote="USDT"),
)
OTHER_LISTING = SimpleNamespace(
    canonical="crypto:fixture-spot:ETH-USDT",
    market_type="spot",
    instrument=SimpleNamespace(asset_class="crypto", base="ETH", quote="USDT"),
)
NOW = 1_700_000_000
DAY = 86_400


class FixtureStrategy(C.Strategy):
    strategy_id = "fixture-trend"
    version = "1.0"
    description = "Deterministic offline strategy fixture"
    asset_classes = ("crypto",)
    market_types = ("spot",)
    base_assets = ("BTC",)
    quote_assets = ("USDT",)
    intervals_s = (DAY,)
    reason_codes = ("FIXTURE_SIGNAL",)
    CONFIG_SCHEMA = {
        "length": C.ParamSpec("int", 2, minimum=1, maximum=10),
        "threshold": C.ParamSpec("float", 0.25, minimum=0.0, maximum=1.0),
    }

    def __init__(self, result=None):
        self.calls = 0
        self.result = result or {
            "decision": C.BUY,
            "reason_codes": ["FIXTURE_SIGNAL"],
            "reasons": ["synthetic deterministic fixture"],
            "indicators": {"strength": 0.123456789},
        }

    def required_history(self, config):
        return config["length"]

    def evaluate(self, config, candles):
        self.calls += 1
        return self.result


def candle(open_time_s, close=100.0):
    return SimpleNamespace(open_time_s=open_time_s, close=close)


def report(status="COMPLETE", listing=LISTING, candles=None, reasons=()):
    return {
        "status": status,
        "stage": "offline-validation",
        "data_source": "synthetic-fixture",
        "provider": {"name": "synthetic", "venue": "offline"},
        "pipeline_version": "fixture-v1",
        "reference_time": {"source": "fixed-fixture", "now_s": NOW},
        "timeframe_s": DAY,
        "listing": {"canonical": listing.canonical},
        "freshness": {"state": "FIXTURE"},
        "candles": {"dataset_sha256": "a" * 64, "raw_sha256": "b" * 64},
        "error": {"code": "FIXTURE_REFUSAL"} if status == "REFUSED" else None,
        "reasons": list(reasons),
        "canonical_candles": candles,
    }


class StrategyImportBoundaryTests(unittest.TestCase):
    def test_pure_strategy_core_imports_do_not_reach_protected_or_network_modules(self):
        paths = (
            "markets/strategies/contract.py",
            "markets/strategies/decision.py",
            "markets/strategies/engine.py",
        )
        forbidden = ("signal", "markets.risk", "validator", "report", "urllib",
                     "requests", "socket", "http.client")
        for path in paths:
            with self.subTest(path=path):
                with open(os.path.join(ROOT, path), encoding="utf-8") as stream:
                    tree = ast.parse(stream.read(), filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        modules = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        modules = [node.module or ""]
                    else:
                        continue
                    for module in modules:
                        self.assertFalse(
                            any(module == item or module.startswith(item + ".")
                                for item in forbidden),
                            msg=f"{path} imports forbidden module {module!r}",
                        )

    def test_harness_did_not_load_registry_or_protected_s1_adapter(self):
        self.assertNotIn("markets.strategies.registry", sys.modules)
        self.assertNotIn("markets.strategies.btc_s1", sys.modules)
        self.assertNotIn("btc_signal", sys.modules)


class StrategyContractTests(unittest.TestCase):
    def test_valid_identity_and_normalized_defaults_are_deterministic(self):
        strategy = FixtureStrategy()
        C.validate_identity(strategy)
        normalized = strategy.normalize_config({"threshold": 0.5})
        self.assertEqual(list(normalized), ["length", "threshold"])
        self.assertEqual(normalized, {"length": 2, "threshold": 0.5})
        self.assertEqual(strategy.normalize_config(normalized), normalized)

    def test_unknown_keys_wrong_types_non_finite_and_out_of_range_values_fail_closed(self):
        strategy = FixtureStrategy()
        for supplied in (
            {"unknown": 1},
            {"length": True},
            {"threshold": float("nan")},
            {"threshold": float("inf")},
            {"length": 11},
            {"threshold": -0.01},
        ):
            with self.subTest(supplied=supplied):
                with self.assertRaises(C.StrategyConfigError):
                    strategy.normalize_config(supplied)

    def test_engine_owned_reason_codes_cannot_be_declared_by_a_strategy(self):
        strategy = FixtureStrategy()
        strategy.reason_codes = ("DATA_REFUSED",)
        with self.assertRaises(C.StrategyError):
            C.validate_identity(strategy)

    def test_canonical_fingerprint_is_order_independent_and_config_sensitive(self):
        first = config_fingerprint("fixture-trend", "1.0", {"a": 1, "b": 2})
        second = config_fingerprint("fixture-trend", "1.0", {"b": 2, "a": 1})
        changed = config_fingerprint("fixture-trend", "1.0", {"a": 1, "b": 3})
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first), 64)


class StrategyDecisionTests(unittest.TestCase):
    def test_decision_json_is_canonical_and_rounds_floats(self):
        cfg = {"length": 2, "threshold": 0.25}
        decision = StrategyDecision(
            strategy_id="fixture-trend",
            strategy_version="1.0",
            listing=LISTING.canonical,
            timeframe_s=DAY,
            evaluation_now_s=NOW,
            reference_open_s=NOW - DAY,
            reference_close_s=NOW,
            decision=C.BUY,
            reason_codes=("FIXTURE_SIGNAL",),
            reasons=("synthetic",),
            indicators={"strength": 0.123456789},
            provenance={"provider": "synthetic"},
            config=cfg,
            config_fingerprint=config_fingerprint("fixture-trend", "1.0", cfg),
        )
        rendered = decision.to_json()
        parsed = json.loads(rendered)
        self.assertEqual(parsed["decision"], C.BUY)
        self.assertEqual(parsed["indicators"]["strength"], 0.12345679)
        self.assertIn("not an order", parsed["no_trading"].lower())
        self.assertEqual(rendered, json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True))

    def test_non_finite_decision_values_are_rejected(self):
        with self.assertRaises(C.StrategyError):
            StrategyDecision(
                strategy_id="fixture-trend", strategy_version="1.0",
                listing=LISTING.canonical, timeframe_s=DAY,
                evaluation_now_s=NOW, reference_open_s=None, reference_close_s=None,
                decision=C.HOLD, reason_codes=(), reasons=(),
                indicators={"bad": float("nan")},
            )


class StrategyEngineTests(unittest.TestCase):
    def test_only_complete_compatible_sufficient_data_reaches_strategy(self):
        strategy = FixtureStrategy()
        candles = [candle(NOW - 2 * DAY), candle(NOW - DAY, 101.0)]
        result = evaluate_report(strategy, LISTING, report(candles=candles))
        self.assertEqual(strategy.calls, 1)
        self.assertEqual(result.decision, C.BUY)
        self.assertEqual(result.reason_codes, ("FIXTURE_SIGNAL",))
        self.assertEqual(result.evaluation_now_s, NOW)
        self.assertEqual(result.reference_open_s, NOW - DAY)
        self.assertEqual(result.reference_close_s, NOW)
        self.assertEqual(result.indicators["strength"], 0.12345679)
        self.assertEqual(result.provenance["data_source"], "synthetic-fixture")

    def test_refused_partial_and_unavailable_reports_never_reach_strategy(self):
        cases = (
            ("REFUSED", C.INVALID, "DATA_REFUSED"),
            ("PARTIAL", C.NO_DATA, "DATA_INCOMPLETE"),
            ("UNAVAILABLE", C.NO_DATA, "DATA_UNAVAILABLE"),
        )
        for status, expected, code in cases:
            strategy = FixtureStrategy()
            with self.subTest(status=status):
                result = evaluate_report(
                    strategy, LISTING,
                    report(status=status, reasons=("synthetic reason",)),
                )
                self.assertEqual(result.decision, expected)
                self.assertIn(code, result.reason_codes)
                self.assertEqual(strategy.calls, 0)

    def test_listing_mismatch_and_unsupported_listing_or_interval_never_reach_strategy(self):
        strategy = FixtureStrategy()
        mismatch = evaluate_report(
            strategy, LISTING, report(listing=OTHER_LISTING)
        )
        self.assertEqual(mismatch.decision, C.INVALID)
        self.assertIn("LISTING_MISMATCH", mismatch.reason_codes)
        self.assertEqual(strategy.calls, 0)

        unsupported = evaluate_report(
            strategy, OTHER_LISTING, report(listing=OTHER_LISTING)
        )
        self.assertEqual(unsupported.decision, C.INVALID)
        self.assertIn("UNSUPPORTED_LISTING", unsupported.reason_codes)
        self.assertEqual(strategy.calls, 0)

        wrong_interval = report(candles=[candle(NOW - DAY)] * 2)
        wrong_interval["timeframe_s"] = 3_600
        interval_result = evaluate_report(strategy, LISTING, wrong_interval)
        self.assertEqual(interval_result.decision, C.INVALID)
        self.assertIn("UNSUPPORTED_INTERVAL", interval_result.reason_codes)
        self.assertEqual(strategy.calls, 0)

    def test_complete_report_missing_candles_or_history_returns_no_strategy_call(self):
        strategy = FixtureStrategy()
        missing = evaluate_report(strategy, LISTING, report(candles=None))
        self.assertEqual(missing.decision, C.INVALID)
        self.assertIn("INPUT_MISSING", missing.reason_codes)
        self.assertEqual(strategy.calls, 0)

        short = evaluate_report(
            strategy, LISTING,
            report(candles=[candle(NOW - DAY)]),
        )
        self.assertEqual(short.decision, C.NO_DATA)
        self.assertIn("INSUFFICIENT_HISTORY", short.reason_codes)
        self.assertEqual(strategy.calls, 0)

    def test_strategy_cannot_return_engine_owned_decisions_or_undeclared_reasons(self):
        invalid_decision = FixtureStrategy(result={
            "decision": C.INVALID,
            "reason_codes": ["FIXTURE_SIGNAL"],
            "reasons": ["attempted engine decision"],
            "indicators": {},
        })
        with self.assertRaises(C.StrategyError):
            evaluate_report(invalid_decision, LISTING, report(candles=[candle(NOW - DAY)] * 2))

        invalid_reason = FixtureStrategy(result={
            "decision": C.BUY,
            "reason_codes": ["DATA_REFUSED"],
            "reasons": ["attempted engine reason"],
            "indicators": {},
        })
        with self.assertRaises(C.StrategyError):
            evaluate_report(invalid_reason, LISTING, report(candles=[candle(NOW - DAY)] * 2))


if __name__ == "__main__":
    unittest.main()
