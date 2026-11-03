"""Offline tests for the M5 strategy engine. Fixtures and injected transports only. No network, no machine clock.

Every time is explicit: NOW and the window are constants, and reports carry their own reference time.
"""
import ast
import json
import math
import os
import socket
import sys
import unittest
import urllib.request
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markets import data_pipeline as dp  # noqa: E402
from markets.candles import Candle  # noqa: E402
from markets.identity import parse_listing  # noqa: E402
from markets.providers import MarketDataProvider, ProviderInfo  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers.binance_vision import BinanceVision  # noqa: E402
from markets.providers.kraken import Kraken  # noqa: E402
from markets.providers.transport import TransportFailure  # noqa: E402
from markets.strategies import (  # noqa: E402
    BUY, HOLD, INVALID, NO_DATA, SELL, DuplicateStrategyError, ParamSpec, Strategy, StrategyConfigError,
    StrategyDecision, StrategyError, StrategyRegistry, UnknownStrategyError, VersionConflictError, canonical_json,
    config_fingerprint, default_registry, evaluate_report,
)
from markets.strategies import btc_s1  # noqa: E402
from markets.strategies import contract as C  # noqa: E402

import btc_signal as bs  # noqa: E402  (committed S1, read only: the golden reference for compatibility)

DAY = 86400
T0 = 1609459200
NOW = T0 + 400 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
LOOKBACK = 200
START = END - (LOOKBACK - 1) * DAY
BTC = parse_listing("crypto:binance-spot:BTC-USDT")
S1 = btc_s1.BtcS1DailyTrend()
REF_LISTING = "crypto:binance-spot:BTC-USDT"


def trend_candles(count, start=START):
    """Deterministic daily OHLC with a visible oscillation, so S1 produces BUY, SELL and HOLD over the series."""
    out = []
    prev = None
    for i in range(count):
        close = 100 + 10 * math.sin(i / 6) + 0.05 * i
        opened = close if prev is None else prev
        out.append(Candle(start + i * DAY, opened, max(opened, close) + 1, min(opened, close) - 1, close, 1.0))
        prev = close
    return out


def rows_for(end_s, count=LOOKBACK, drop=()):
    """Completed rows for the window ending at end_s (minus the offsets in drop), plus a forming candle."""
    candles = trend_candles(count, start=end_s - (count - 1) * DAY)
    dropped = {end_s - k * DAY for k in drop}
    rows = [(c.open_time_s, c.open, c.high, c.low, c.close, c.volume) for c in candles
            if c.open_time_s not in dropped]
    rows.append((end_s + DAY, 1.0, 2.0, 0.5, 1.5, 1.0))
    return rows


class _Transport:
    def __init__(self, body_or_error):
        self.value = body_or_error
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


def report_for(provider=None, listing=BTC, rows=None, now=NOW, lookback=LOOKBACK, transport=None):
    provider = provider or BinanceVision()
    if transport is None:
        transport = _Transport(syn.binance_body(rows if rows is not None else rows_for(END), DAY))
    return dp.fetch_market_data(provider, listing, DAY, now, data_source="synthetic", time_source="explicit-caller",
                                transport=transport, lookback=lookback)


def s1_reference(candles, k):
    """S1's own decision for index k, mapped the way the adapter maps it. The golden reference."""
    s1 = [bs.Candle(c.open_time_s, c.open, c.high, c.low, c.close, c.volume) for c in candles]
    result = bs.signal_at(s1, k)
    mapped = {"BUY": BUY, "SELL": SELL, "WAIT": HOLD}[result["decision"]]
    return mapped, result


# ---------------------------------------------------------------------------------------------------------------------
class ContractTests(unittest.TestCase):
    def test_valid_identity_is_accepted(self):
        C.validate_identity(S1)

    def test_malformed_identity_is_refused(self):
        class Bad(Strategy):
            strategy_id = "Bad_ID"
            version = "1"
            asset_classes = ("crypto",)
            intervals_s = (DAY,)
            reason_codes = ("X",)

            def required_history(self, config):
                return 1

            def evaluate(self, config, candles):
                return {}
        with self.assertRaises(StrategyError):
            C.validate_identity(Bad())

    def test_engine_owned_reason_code_cannot_be_declared_by_a_strategy(self):
        class Owns(Strategy):
            strategy_id = "owns-codes"
            version = "1"
            asset_classes = ("crypto",)
            intervals_s = (DAY,)
            reason_codes = ("DATA_REFUSED",)

            def required_history(self, config):
                return 1

            def evaluate(self, config, candles):
                return {}
        with self.assertRaises(StrategyError):
            C.validate_identity(Owns())

    def test_defaults_are_filled_and_unknown_keys_refused(self):
        schema = {"fast": ParamSpec("int", 20, 1, 500), "scale": ParamSpec("float", 1.5, 0.0, 10.0)}
        self.assertEqual(C.normalize_config(schema, None), {"fast": 20, "scale": 1.5})
        self.assertEqual(C.normalize_config(schema, {"fast": 5}), {"fast": 5, "scale": 1.5})
        with self.assertRaises(StrategyConfigError):
            C.normalize_config(schema, {"slow": 50})

    def test_wrong_types_booleans_nonfinite_and_out_of_range_are_refused(self):
        schema = {"fast": ParamSpec("int", 20, 1, 500), "scale": ParamSpec("float", 1.5, 0.0, 10.0)}
        for bad in ({"fast": True}, {"fast": 2.5}, {"fast": "20"}, {"fast": 0}, {"fast": 501},
                    {"scale": float("nan")}, {"scale": float("inf")}, {"scale": -0.1}, {"scale": 11}, {"scale": "1"}):
            with self.subTest(bad=bad):
                with self.assertRaises(StrategyConfigError):
                    C.normalize_config(schema, bad)
        with self.assertRaises(StrategyConfigError):
            C.normalize_config(schema, ["not", "a", "mapping"])

    def test_rounding_is_fixed_and_negative_zero_is_normalized(self):
        self.assertEqual(C.round_value(0.1 + 0.2), round(0.1 + 0.2, 8))
        self.assertEqual(C.round_value(-0.0), 0.0)
        self.assertEqual(math.copysign(1.0, C.round_value(-0.0)), 1.0)
        for bad in (float("nan"), float("inf"), [1], {"a": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(StrategyError):
                    C.round_value(bad)

    def test_s1_declares_no_tunable_parameters_and_frozen_s1_constants(self):
        self.assertEqual(S1.CONFIG_SCHEMA, {})
        self.assertEqual((bs.SMA_FAST, bs.SMA_SLOW, bs.RSI_N, bs.RSI_OVERBOUGHT, bs.STEP),
                         (20, 50, 14, 70.0, 86400))
        self.assertEqual(S1.version, bs.RULE_VERSION)
        self.assertEqual(S1.required_history({}), 50)

    def test_describe_is_plain_json(self):
        json.dumps(S1.describe(), sort_keys=True)


class RegistryTests(unittest.TestCase):
    def test_register_and_lookup_return_the_same_strategy(self):
        reg = StrategyRegistry()
        reg.register(S1)
        self.assertIs(reg.lookup(S1.strategy_id, S1.version), S1)
        self.assertEqual(reg.ids(), (S1.strategy_id,))

    def test_duplicate_registration_is_refused_and_leaves_the_original(self):
        reg = StrategyRegistry()
        reg.register(S1)
        with self.assertRaises(DuplicateStrategyError):
            reg.register(btc_s1.BtcS1DailyTrend())
        self.assertIs(reg.lookup(S1.strategy_id, S1.version), S1)

    def test_same_id_at_another_version_is_a_refused_conflict(self):
        class Other(btc_s1.BtcS1DailyTrend):
            version = "btc-rules-v2"
        reg = StrategyRegistry()
        reg.register(S1)
        with self.assertRaises(VersionConflictError):
            reg.register(Other())
        with self.assertRaises(VersionConflictError):
            reg.lookup(S1.strategy_id, "btc-rules-v2")

    def test_unknown_id_is_refused_with_no_fallback(self):
        reg = default_registry()
        with self.assertRaises(UnknownStrategyError):
            reg.lookup("no-such-strategy", S1.version)
        with self.assertRaises(UnknownStrategyError):
            StrategyRegistry().lookup(S1.strategy_id, S1.version)

    def test_registry_metadata_is_inspectable_and_plain(self):
        rows = default_registry().describe()
        self.assertEqual([r["strategy_id"] for r in rows], [S1.strategy_id])
        self.assertEqual(rows[0]["version"], "btc-rules-v1")
        json.dumps(rows, sort_keys=True)

    def test_each_default_registry_is_independent(self):
        a = default_registry()
        b = default_registry()
        self.assertIsNot(a, b)
        self.assertIsNot(a.lookup(S1.strategy_id, S1.version), b.lookup(S1.strategy_id, S1.version))


class CompatibilityTests(unittest.TestCase):
    def assertRefusedBy(self, listing_text, timeframe=DAY, code="UNSUPPORTED_LISTING"):
        listing = parse_listing(listing_text)
        codes = [c for c, _ in S1.compatibility_problems(listing, timeframe)]
        self.assertIn(code, codes, listing_text)

    def test_exact_binance_btc_usdt_daily_is_the_only_compatible_listing(self):
        self.assertEqual(S1.compatibility_problems(parse_listing("crypto:binance-spot:BTC-USDT"), DAY), [])
        for text in ("crypto:fixture-spot:BTC-USDT", "crypto:kraken-spot:BTC-USDT"):
            with self.subTest(listing=text):
                codes = [c for c, _ in S1.compatibility_problems(parse_listing(text), DAY)]
                self.assertIn("UNSUPPORTED_LISTING", codes)

    def test_other_quotes_bases_market_types_asset_classes_and_intervals_are_refused(self):
        self.assertRefusedBy("crypto:kraken-spot:BTC-USD")
        self.assertRefusedBy("crypto:binance-spot:ETH-USDT")
        self.assertRefusedBy("crypto:binance-perp:BTC-USDT")
        self.assertRefusedBy("equity:kraken-cash:AAPL-USD")
        self.assertRefusedBy("fx:fixture-spot:EUR-USD")
        self.assertRefusedBy("crypto:binance-spot:BTC-USDT", timeframe=3600, code="UNSUPPORTED_INTERVAL")


class AssetClassGuardTests(unittest.TestCase):
    """A strategy that restricts only the asset class must still be refused for other asset classes, on that reason."""

    class _CryptoAny(Strategy):
        strategy_id = "crypto-any-daily"
        version = "1"
        asset_classes = ("crypto",)
        intervals_s = (DAY,)
        reason_codes = ("NONE_DECLARED",)

        def required_history(self, config):
            return 1

        def evaluate(self, config, candles):
            return {"decision": HOLD, "reason_codes": ["NONE_DECLARED"], "reasons": [], "indicators": {}}

    def test_other_asset_classes_are_refused_on_the_asset_class_reason(self):
        for text in ("equity:kraken-cash:AAPL-USD", "fx:fixture-spot:EUR-USD"):
            with self.subTest(listing=text):
                problems = self._CryptoAny().compatibility_problems(parse_listing(text), DAY)
                self.assertTrue(any("asset class" in t for _, t in problems), problems)

    def test_crypto_of_any_base_is_accepted_by_this_strategy(self):
        self.assertEqual(self._CryptoAny().compatibility_problems(parse_listing("crypto:kraken-spot:ETH-USD"), DAY),
                         [])


class S1CompatibilityTests(unittest.TestCase):
    """The S1 golden check: for every index, the strategy's decision, reasons and indicators equal S1's own output."""

    @classmethod
    def setUpClass(cls):
        cls.candles = trend_candles(220)

    def test_every_index_matches_s1_exactly(self):
        seen = set()
        for k in range(bs.SMA_SLOW - 1, len(self.candles)):
            window = self.candles[:k + 1]
            got = S1.evaluate({}, tuple(window))
            want_decision, want = s1_reference(self.candles, k)
            with self.subTest(index=k):
                self.assertEqual(got["decision"], want_decision)
                self.assertEqual(got["reasons"], want["reasons"])
                self.assertEqual(got["indicators"], want["values"])
                self.assertEqual(got["reason_codes"], [{"BUY": "S1_BUY_RULES_MET", "SELL": "S1_SELL_RULES_MET",
                                                        "WAIT": "S1_NO_RULE_MET"}[want["decision"]]])
            seen.add(got["decision"])
        self.assertEqual(seen, {BUY, SELL, HOLD}, "the fixture must exercise every decision")


class EngineStatusTests(unittest.TestCase):
    """Each data status maps to one engine decision. Only COMPLETE data with enough history is evaluated."""

    class _Spy(btc_s1.BtcS1DailyTrend):
        def evaluate(self, config, candles):
            raise AssertionError("strategy must not be evaluated on this data")

    def test_complete_data_produces_a_strategy_decision(self):
        d = evaluate_report(S1, BTC, report_for(), None)
        self.assertIn(d.decision, (BUY, SELL, HOLD))
        self.assertEqual(d.reference_open_s, END)
        self.assertEqual(d.reference_close_s, END + DAY)
        self.assertEqual(d.evaluation_now_s, NOW)
        self.assertEqual(d.listing, REF_LISTING)
        self.assertEqual(d.provenance["data_status"], "COMPLETE")
        self.assertIsNone(d.provenance["provider_error"])

    def test_partial_data_is_no_data_and_never_a_signal(self):
        report = report_for(rows=rows_for(END, drop=(40,)))
        self.assertEqual(report["status"], dp.PARTIAL)
        d = evaluate_report(self._Spy(), BTC, report, None)
        self.assertEqual((d.decision, d.reason_codes), (NO_DATA, ("DATA_INCOMPLETE",)))
        self.assertIsNone(d.reference_open_s)

    def test_unavailable_data_is_no_data_with_the_provider_error_kept(self):
        report = report_for(transport=_Transport(b"[]"))
        self.assertEqual(report["status"], dp.UNAVAILABLE)
        d = evaluate_report(self._Spy(), BTC, report, None)
        self.assertEqual((d.decision, d.reason_codes), (NO_DATA, ("DATA_UNAVAILABLE",)))
        self.assertEqual(d.provenance["provider_error"]["kind"], "empty")

    def test_refused_data_is_invalid_and_keeps_the_structured_provider_error(self):
        report = report_for(transport=_Transport(TransportFailure("rate_limited", "HTTP 429", 429)))
        self.assertEqual(report["status"], dp.REFUSED)
        d = evaluate_report(self._Spy(), BTC, report, None)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("DATA_REFUSED",)))
        self.assertEqual(d.provenance["provider_error"]["kind"], "rate_limited")
        self.assertEqual(d.provenance["provider_error"]["http_status"], 429)

    def test_overdue_provider_is_refused_and_not_evaluated(self):
        report = report_for(now=NOW + 5 * DAY)
        self.assertEqual(report["status"], dp.REFUSED)
        d = evaluate_report(self._Spy(), BTC, report, None)
        self.assertEqual(d.decision, INVALID)

    def test_complete_but_short_history_is_no_data(self):
        report = report_for(lookback=30, rows=rows_for(END, count=30))
        self.assertEqual(report["status"], dp.COMPLETE, report["reasons"])
        d = evaluate_report(self._Spy(), BTC, report, None)
        self.assertEqual((d.decision, d.reason_codes), (NO_DATA, ("INSUFFICIENT_HISTORY",)))

    def test_listing_mismatch_is_invalid(self):
        other = parse_listing("crypto:binance-spot:BTC-USDT")
        mismatched = report_for(listing=BTC)
        mismatched["listing"]["canonical"] = "crypto:binance-spot:ETH-USDT"
        d = evaluate_report(S1, other, mismatched, None)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("LISTING_MISMATCH",)))

    def test_unsupported_listing_and_interval_are_invalid_before_data_is_judged(self):
        kraken = parse_listing("crypto:kraken-spot:BTC-USD")
        d = evaluate_report(S1, kraken, report_for(), None)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("UNSUPPORTED_LISTING",)))
        weekly = dict(report_for())
        weekly["timeframe_s"] = 3600
        d = evaluate_report(S1, BTC, weekly, None)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("UNSUPPORTED_INTERVAL",)))

    def test_no_data_path_is_refused_when_the_candles_are_missing(self):
        report = dict(report_for())
        report["canonical_candles"] = None
        d = evaluate_report(S1, BTC, report, None)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("INPUT_MISSING",)))


class StrategyContractEnforcementTests(unittest.TestCase):
    def test_a_strategy_returning_no_data_is_refused(self):
        class Bad(btc_s1.BtcS1DailyTrend):
            def evaluate(self, config, candles):
                return {"decision": NO_DATA, "reason_codes": ["S1_NO_RULE_MET"], "reasons": [], "indicators": {}}
        with self.assertRaises(StrategyError):
            evaluate_report(Bad(), BTC, report_for(), None)

    def test_a_strategy_attaching_an_undeclared_reason_code_is_refused(self):
        class Bad(btc_s1.BtcS1DailyTrend):
            def evaluate(self, config, candles):
                return {"decision": HOLD, "reason_codes": ["MADE_UP"], "reasons": [], "indicators": {}}
        with self.assertRaises(StrategyError):
            evaluate_report(Bad(), BTC, report_for(), None)

    def test_a_strategy_result_with_extra_fields_is_refused(self):
        class Bad(btc_s1.BtcS1DailyTrend):
            def evaluate(self, config, candles):
                return {"decision": HOLD, "reason_codes": ["S1_NO_RULE_MET"], "reasons": [], "indicators": {},
                        "order_size": 1}
        with self.assertRaises(StrategyError):
            evaluate_report(Bad(), BTC, report_for(), None)

    def test_a_bad_configuration_is_a_caller_error_not_a_decision(self):
        with self.assertRaises(StrategyConfigError):
            evaluate_report(S1, BTC, report_for(), {"threshold": 70})


class DecisionSerializationTests(unittest.TestCase):
    def test_identical_inputs_give_byte_identical_json(self):
        a = evaluate_report(S1, BTC, report_for(), None).to_json()
        b = evaluate_report(S1, BTC, report_for(), None).to_json()
        self.assertEqual(a, b)

    def test_json_is_canonical_sorted_compact_and_round_trips(self):
        d = evaluate_report(S1, BTC, report_for(), None)
        text = d.to_json()
        self.assertEqual(text, canonical_json(json.loads(text)))
        self.assertEqual(json.loads(text)["decision"], d.decision)

    def test_keys_are_sorted_at_every_level(self):
        text = evaluate_report(S1, BTC, report_for(), None).to_json()

        def check(obj):
            if isinstance(obj, dict):
                self.assertEqual(list(obj), sorted(obj))
                for value in obj.values():
                    check(value)
            elif isinstance(obj, list):
                for value in obj:
                    check(value)
        check(json.loads(text))

    def test_fingerprint_depends_on_strategy_version_and_config_only(self):
        f1 = config_fingerprint("s", "1", {"a": 1.0})
        self.assertEqual(f1, config_fingerprint("s", "1", {"a": 1.0}))
        self.assertNotEqual(f1, config_fingerprint("s", "2", {"a": 1.0}))
        self.assertNotEqual(f1, config_fingerprint("s", "1", {"a": 2.0}))
        self.assertNotEqual(f1, config_fingerprint("t", "1", {"a": 1.0}))

    def test_decision_floats_are_rounded_before_storage_and_nonfinite_is_refused(self):
        d = StrategyDecision("s", "1", REF_LISTING, DAY, NOW, END, END + DAY, HOLD, ("X",), (),
                             indicators={"v": 0.1 + 0.2}, provenance={}, config={}, config_fingerprint="f")
        self.assertEqual(d.indicators["v"], round(0.1 + 0.2, 8))
        with self.assertRaises(StrategyError):
            StrategyDecision("s", "1", REF_LISTING, DAY, NOW, None, None, HOLD, (), (),
                             indicators={"v": float("nan")}, provenance={}, config={}, config_fingerprint="f")

    def test_decision_rejects_unknown_decision_values(self):
        with self.assertRaises(StrategyError):
            StrategyDecision("s", "1", REF_LISTING, DAY, NOW, None, None, "SHORT", (), (),
                             provenance={}, config={}, config_fingerprint="f")

    def test_decision_has_no_order_or_size_fields(self):
        keys = set(evaluate_report(S1, BTC, report_for(), None).to_dict())
        self.assertFalse(keys & {"order", "size", "quantity", "leverage", "account", "exposure", "broker"}, keys)


class DeterminismTests(unittest.TestCase):
    def test_same_report_twice_gives_the_same_decision_and_indicators(self):
        report = report_for()
        d1 = evaluate_report(S1, BTC, report, None)
        d2 = evaluate_report(S1, BTC, report, None)
        self.assertEqual((d1.decision, d1.reasons, d1.indicators), (d2.decision, d2.reasons, d2.indicators))

    def test_explicit_empty_and_omitted_config_are_identical(self):
        a = evaluate_report(S1, BTC, report_for(), None)
        b = evaluate_report(S1, BTC, report_for(), {})
        self.assertEqual(a.to_json(), b.to_json())


class _FixtureVenueProvider(MarketDataProvider):
    """A provider on another venue, serving BTC-USDT. Used to show that the S1 adapter refuses non-Binance venues."""

    info = ProviderInfo(name="fixture-feed", venue="fixture", docs_url="https://fixture.invalid/docs",
                        terms_source="test fixture only; no real terms")
    SYMBOLS = {"crypto:fixture-spot:BTC-USDT": "BTCUSDT"}
    INTERVALS = {DAY: "daily"}
    MAX_CANDLES_PER_REQUEST = 1000

    def build_url(self, symbol, timeframe_s, start_s, end_s):
        return f"https://fixture.invalid/ohlc?pair={symbol}&since={start_s}&until={end_s}"

    def parse_chunk(self, body, timeframe_s):
        return [(int(t), float(o), float(h), float(lo), float(c), None if v is None else float(v))
                for t, o, h, lo, c, v in json.loads(body.decode("utf-8"))]


class _SameListingProvider(_FixtureVenueProvider):
    """A different provider implementation serving the SAME canonical listing as Binance does."""

    info = ProviderInfo(name="fixture-mirror", venue="binance", docs_url="https://fixture.invalid/docs",
                        terms_source="test fixture only; no real terms")
    SYMBOLS = {"crypto:binance-spot:BTC-USDT": "BTCUSDT"}


def fixture_body(rows):
    return json.dumps([[t, o, h, lo, c, v] for t, o, h, lo, c, v in rows]).encode("utf-8")


class S1ScopeTests(unittest.TestCase):
    """The S1 adapter accepts exactly crypto:binance-spot:BTC-USDT at 86400 s under btc-rules-v1. Every other request
    is INVALID from the engine, and S1's signal_at is never called for it."""

    def _decide(self, report, listing):
        with mock.patch.object(btc_s1.bs, "signal_at", wraps=btc_s1.bs.signal_at) as spy:
            d = evaluate_report(S1, listing, report, None)
        return d, spy

    def test_1_binance_btc_usdt_daily_is_accepted_and_reaches_s1(self):
        d, spy = self._decide(report_for(), BTC)
        self.assertIn(d.decision, (BUY, SELL, HOLD))
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(d.strategy_version, "btc-rules-v1")
        self.assertEqual(d.listing, "crypto:binance-spot:BTC-USDT")
        self.assertEqual(d.timeframe_s, 86400)

    def test_2_kraken_btc_usd_daily_is_rejected(self):
        kraken = parse_listing("crypto:kraken-spot:BTC-USD")
        report = report_for(provider=Kraken(), listing=kraken, transport=_Transport(syn.kraken_body(rows_for(END))))
        self.assertEqual(report["status"], dp.COMPLETE, "the rejection must not depend on the data")
        d, spy = self._decide(report, kraken)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("UNSUPPORTED_LISTING",)))
        self.assertEqual(spy.call_count, 0)
        self.assertIn("crypto:binance-spot:BTC-USDT", " ".join(d.reasons))

    def test_3_btc_usdt_on_another_venue_is_rejected(self):
        other = parse_listing("crypto:fixture-spot:BTC-USDT")
        report = report_for(provider=_FixtureVenueProvider(), listing=other,
                            transport=_Transport(fixture_body(rows_for(END))))
        self.assertEqual(report["status"], dp.COMPLETE, "the rejection must not depend on the data")
        d, spy = self._decide(report, other)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("UNSUPPORTED_LISTING",)))
        self.assertEqual(spy.call_count, 0)

    def test_4_binance_btc_usdt_on_a_non_daily_interval_is_rejected(self):
        report = dict(report_for())
        report["timeframe_s"] = 3600
        d, spy = self._decide(report, BTC)
        self.assertEqual((d.decision, d.reason_codes), (INVALID, ("UNSUPPORTED_INTERVAL",)))
        self.assertEqual(spy.call_count, 0)

    def test_5_rejected_requests_never_invoke_s1_signal_at(self):
        kraken = parse_listing("crypto:kraken-spot:BTC-USD")
        other = parse_listing("crypto:fixture-spot:BTC-USDT")
        weekly = dict(report_for())
        weekly["timeframe_s"] = 3600
        cases = [
            (report_for(provider=Kraken(), listing=kraken, transport=_Transport(syn.kraken_body(rows_for(END)))),
             kraken),
            (report_for(provider=_FixtureVenueProvider(), listing=other,
                        transport=_Transport(fixture_body(rows_for(END)))), other),
            (weekly, BTC),
        ]
        for report, listing in cases:
            with self.subTest(listing=listing.canonical, interval=report["timeframe_s"]):
                d, spy = self._decide(report, listing)
                self.assertEqual(d.decision, INVALID)
                self.assertEqual(spy.call_count, 0)

    def test_rule_version_is_pinned_and_a_different_s1_version_is_refused(self):
        self.assertEqual(bs.RULE_VERSION, "btc-rules-v1")
        self.assertEqual((bs.STEP, S1.version), (86400, "btc-rules-v1"))
        drifted = {"decision": "BUY", "rule_version": "btc-rules-v2", "reasons": [], "values": {}}
        with mock.patch.object(btc_s1.bs, "signal_at", return_value=drifted):
            with self.assertRaises(StrategyError):
                S1.evaluate({}, tuple(trend_candles(60)))

    def test_describe_states_the_exact_scope(self):
        described = S1.describe()
        self.assertEqual(described["canonical_listings"], ["crypto:binance-spot:BTC-USDT"])
        self.assertEqual(described["intervals_s"], [86400])
        self.assertEqual(described["version"], "btc-rules-v1")


class ProviderIndependenceTests(unittest.TestCase):
    def test_the_same_canonical_listing_from_two_providers_gives_the_same_decision(self):
        rows = rows_for(END)
        a = evaluate_report(S1, BTC, report_for(rows=rows), None)
        b = evaluate_report(S1, BTC, report_for(provider=_SameListingProvider(), listing=BTC,
                                                transport=_Transport(fixture_body(rows))), None)
        self.assertEqual(a.listing, b.listing)
        self.assertEqual(a.decision, b.decision)
        self.assertEqual(a.reason_codes, b.reason_codes)
        self.assertEqual(a.reasons, b.reasons)
        self.assertEqual(a.indicators, b.indicators)
        self.assertEqual(a.reference_open_s, b.reference_open_s)
        self.assertEqual(a.provenance["dataset_sha256"], b.provenance["dataset_sha256"])
        self.assertNotEqual(a.provenance["provider"], b.provenance["provider"])


class NoNetworkNoOrderTests(unittest.TestCase):
    STRATEGY_FILES = ("contract.py", "decision.py", "registry.py", "engine.py", "btc_s1.py", "__init__.py")
    FORBIDDEN_IMPORTS = {"urllib", "socket", "http", "ssl", "subprocess", "requests", "urllib3", "time", "datetime",
                         "random", "uuid", "secrets", "markets.providers", "pipeline", "research", "tests"}
    FORBIDDEN_IDENTIFIERS = ("order", "broker", "exchange", "credential", "api_key", "secret", "account",
                             "leverage", "exposure")

    def _tree(self, name):
        with open(os.path.join(_HERE, name), encoding="utf-8") as f:
            return ast.parse(f.read())

    def test_strategy_modules_import_no_network_clock_provider_or_execution_code(self):
        for name in self.STRATEGY_FILES:
            with self.subTest(file=name):
                imported = set()
                for node in ast.walk(self._tree(name)):
                    if isinstance(node, ast.Import):
                        imported.update(a.name for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
                roots = {m for m in imported}
                for bad in self.FORBIDDEN_IMPORTS:
                    self.assertFalse(any(r == bad or r.startswith(bad + ".") for r in roots),
                                     f"{name} imports {bad}: {sorted(roots)}")

    def test_strategy_modules_name_no_order_broker_exchange_or_account_identifiers(self):
        for name in self.STRATEGY_FILES:
            with self.subTest(file=name):
                for node in ast.walk(self._tree(name)):
                    idents = []
                    if isinstance(node, ast.Name):
                        idents.append(node.id)
                    elif isinstance(node, ast.Attribute):
                        idents.append(node.attr)
                    elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        idents.append(node.name)
                    elif isinstance(node, ast.arg):
                        idents.append(node.arg)
                    for ident in idents:
                        low = ident.lower()
                        for bad in self.FORBIDDEN_IDENTIFIERS:
                            self.assertNotIn(bad, low, f"{name} uses identifier {ident!r}")

    def test_evaluation_makes_no_network_call(self):
        def refuse(*args, **kwargs):
            raise AssertionError("network used during strategy evaluation")
        report = report_for()
        with mock.patch.object(socket, "socket", side_effect=refuse), \
                mock.patch.object(urllib.request, "urlopen", side_effect=refuse):
            d = evaluate_report(S1, BTC, report, None)
        self.assertIn(d.decision, (BUY, SELL, HOLD))


if __name__ == "__main__":
    unittest.main()
