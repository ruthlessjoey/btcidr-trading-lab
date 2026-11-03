"""Tests for the shared provider-neutral market-data pipeline (M4b). Offline only: injected transports, no network.

Covers explicit provider selection, provenance rules, Binance and Kraken adapters through the shared pipeline, a third
fixture venue (generality), coverage classes (complete, partial, unavailable, refused), refusal before transport,
malformed, duplicate, conflicting and misaligned data, provider errors, no silent fallback, deterministic output,
missing volume that is never zero, and M3 dataset parity.
"""
import ast
import dataclasses
import json
import os
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for p in (_ROOT, os.path.join(_ROOT, "pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)

from markets import data_pipeline as dp  # noqa: E402
from markets.identity import parse_listing  # noqa: E402
from markets.providers import MarketDataProvider, ProviderInfo  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers.binance_vision import BinanceVision  # noqa: E402
from markets.providers.registry import UnknownProviderError, provider_names, select_provider  # noqa: E402
from markets.providers.transport import TransportFailure  # noqa: E402
import candle_pipeline as cp  # noqa: E402
import btc_pipeline as bp  # noqa: E402  (M3, read only: parity check)

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
LOOKBACK = 119
START = END - (LOOKBACK - 1) * DAY
FORMING_T = (NOW // DAY) * DAY
BINANCE_LISTING = parse_listing("crypto:binance-spot:BTC-USDT")
KRAKEN_LISTING = parse_listing("crypto:kraken-spot:BTC-USD")


def window_rows(count=LOOKBACK, start=START):
    """Completed daily rows for the window, plus the candle still forming at NOW."""
    return syn.series(start, count, DAY) + [(FORMING_T, 1.0, 2.0, 0.5, 1.5, 1.0)]


def window_fixture(end_s, drop=()):
    """Completed rows for the window that ends at end_s, minus the slots at the given offsets back from end_s
    (offset 0 is the final expected slot), plus the candle still forming one slot after end_s."""
    start = end_s - (LOOKBACK - 1) * DAY
    dropped = {end_s - k * DAY for k in drop}
    rows = [r for r in syn.series(start, LOOKBACK, DAY) if r[0] not in dropped]
    return rows + [(end_s + DAY, 1.0, 2.0, 0.5, 1.5, 1.0)]


def binance_body(rows):
    return syn.binance_body(rows, DAY)


def kraken_body(rows):
    return syn.kraken_body(rows)


def run(provider, listing, transport, *, now=NOW, lookback=LOOKBACK, timeframe=DAY, data_source="synthetic",
        time_source="explicit-caller", grace=dp.DEFAULT_PUBLICATION_GRACE_S):
    return dp.fetch_market_data(provider, listing, timeframe, now, data_source=data_source,
                                time_source=time_source, transport=transport, lookback=lookback,
                                publication_grace_s=grace)


class FixtureVenueProvider(MarketDataProvider):
    """A third provider with its own venue, symbols and JSON layout. Used only to show the core is not tied to the
    two real adapters. Null volume is passed through as None, never converted to zero."""

    info = ProviderInfo(name="fixture-feed", venue="fixture", docs_url="https://fixture.invalid/docs",
                        terms_source="test fixture only; no real terms")
    SYMBOLS = {"crypto:fixture-spot:ABC-USD": "ABCUSD"}
    INTERVALS = {DAY: "daily"}
    MAX_CANDLES_PER_REQUEST = 1000

    def build_url(self, symbol, timeframe_s, start_s, end_s):
        return f"https://fixture.invalid/ohlc?pair={symbol}&since={start_s}&until={end_s}"

    def parse_chunk(self, body, timeframe_s):
        return [(int(t), float(o), float(h), float(lo), float(c), None if v is None else float(v))
                for t, o, h, lo, c, v in json.loads(body.decode("utf-8"))]


def fixture_body(rows):
    return json.dumps([[t, o, h, lo, c, v] for t, o, h, lo, c, v in rows]).encode("utf-8")


class RecordingTransport:
    def __init__(self, responder):
        self.responder = responder
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.responder(url)


class RegistryTests(unittest.TestCase):
    def test_registered_names_are_exactly_the_two_adapters(self):
        self.assertEqual(provider_names(), ("binance-vision", "kraken"))

    def test_selection_returns_the_named_adapter(self):
        self.assertIsInstance(select_provider("binance-vision"), BinanceVision)
        self.assertEqual(select_provider("kraken").info.name, "kraken")

    def test_selection_is_exact_and_never_defaults(self):
        for bad in ("Kraken", "BINANCE-VISION", "", " kraken", None, 0):
            with self.subTest(name=bad):
                with self.assertRaises(UnknownProviderError):
                    select_provider(bad)

    def test_each_selection_is_a_new_instance(self):
        self.assertIsNot(select_provider("kraken"), select_provider("kraken"))


class ProvenanceTests(unittest.TestCase):
    def test_live_data_with_an_injected_transport_is_refused(self):
        with self.assertRaises(dp.PipelineError):
            run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: b"[]"), data_source="live")

    def test_synthetic_data_needs_a_caller_transport(self):
        with self.assertRaises(dp.PipelineError):
            dp.fetch_market_data(BinanceVision(), BINANCE_LISTING, DAY, NOW, data_source="synthetic",
                                 time_source="explicit-caller", transport=None)

    def test_unknown_data_source_and_clock_source_are_refused(self):
        with self.assertRaises(dp.PipelineError):
            run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: b"[]"), data_source="remote")
        with self.assertRaises(dp.PipelineError):
            run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: b"[]"),
                time_source="runtime-clock")


class AdapterIntegrationTests(unittest.TestCase):
    def test_binance_adapter_through_the_shared_pipeline_is_complete(self):
        t = RecordingTransport(lambda u: binance_body(window_rows()))
        r = run(BinanceVision(), BINANCE_LISTING, t)
        self.assertEqual(r["status"], dp.COMPLETE, r["reasons"])
        self.assertTrue(r["coverage"]["complete"])
        self.assertEqual(r["candles"]["completed_count"], LOOKBACK)
        self.assertEqual(r["candles"]["forming_dropped"], 1)
        self.assertEqual(r["requests_made"], 1)
        self.assertEqual(len(r["canonical_candles"]), LOOKBACK)
        self.assertEqual(r["provider"]["name"], "binance-vision")
        self.assertEqual(r["listing"]["canonical"], "crypto:binance-spot:BTC-USDT")

    def test_kraken_adapter_through_the_shared_pipeline_is_complete(self):
        t = RecordingTransport(lambda u: kraken_body(window_rows()))
        r = run(select_provider("kraken"), KRAKEN_LISTING, t)
        self.assertEqual(r["status"], dp.COMPLETE, r["reasons"])
        self.assertEqual(r["candles"]["completed_count"], LOOKBACK)
        self.assertEqual(r["requests_made"], 1)
        self.assertEqual(r["provider"]["name"], "kraken")

    def test_same_canonical_request_shape_across_providers(self):
        rb = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows())))
        rk = run(select_provider("kraken"), KRAKEN_LISTING, RecordingTransport(lambda u: kraken_body(window_rows())))
        self.assertEqual(set(rb), set(rk))
        self.assertEqual(rb["window"], rk["window"])
        self.assertEqual(rb["timeframe_s"], rk["timeframe_s"])
        self.assertEqual(rb["reference_time"], rk["reference_time"])

    def test_same_candles_from_either_provider_give_the_same_dataset_hash(self):
        rb = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows())))
        rk = run(select_provider("kraken"), KRAKEN_LISTING, RecordingTransport(lambda u: kraken_body(window_rows())))
        self.assertEqual(rb["candles"]["dataset_sha256"], rk["candles"]["dataset_sha256"])


class CoverageTests(unittest.TestCase):
    def test_one_missing_interior_candle_is_partial_with_the_gap_listed_and_nothing_filled(self):
        rows = window_rows()
        gap_index = 50
        gap_t = START + gap_index * DAY
        del rows[gap_index]
        t = RecordingTransport(lambda u: binance_body(rows))
        r = run(BinanceVision(), BINANCE_LISTING, t)
        self.assertEqual(r["status"], dp.PARTIAL)
        self.assertFalse(r["coverage"]["complete"])
        self.assertEqual(r["coverage"]["expected_candles"], LOOKBACK)
        self.assertEqual(r["coverage"]["returned_candles"], LOOKBACK - 1)
        self.assertEqual(r["coverage"]["missing_expected_total"], 1)
        self.assertEqual(r["coverage"]["missing_expected_sample"], [dp.utc_text(gap_t)])
        observed = [c.open_time_s for c in r["canonical_candles"]]
        self.assertEqual(observed, [START + i * DAY for i in range(LOOKBACK) if i != gap_index])
        self.assertNotIn(gap_t, observed)
        self.assertIn("validation FAIL: expected_missing", r["reasons"])
        self.assertEqual(r["freshness"]["state"], dp.CURRENT)

    def test_partial_data_never_produces_a_signal_in_the_signal_layer(self):
        rows = window_rows()
        del rows[50]
        r = cp.run_candle_pipeline(BinanceVision(), BINANCE_LISTING, DAY, NOW, data_source="synthetic",
                                   time_source="explicit-caller",
                                   transport=RecordingTransport(lambda u: binance_body(rows)),
                                   lookback=LOOKBACK, signal_fn=lambda canon: self.fail("signal ran on partial data"))
        self.assertEqual(r["gate"]["status"], "REFUSED")
        self.assertIsNone(r["signal"])
        self.assertEqual(r["status"], dp.PARTIAL)

    def test_no_rows_in_the_window_is_unavailable(self):
        t = RecordingTransport(lambda u: b"[]")
        r = run(BinanceVision(), BINANCE_LISTING, t)
        self.assertEqual(r["status"], dp.UNAVAILABLE)
        self.assertEqual(r["error"]["kind"], "empty")
        self.assertIsNone(r["canonical_candles"])
        self.assertFalse(r["coverage"]["complete"])

    def test_only_rows_outside_the_window_is_unavailable(self):
        before = syn.series(START - 200 * DAY, 50, DAY)
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(before)))
        self.assertEqual(r["status"], dp.UNAVAILABLE)
        self.assertEqual(r["stage"], "fetch")
        self.assertIsNone(r["candles"])
        self.assertIsNone(r["canonical_candles"])


class RefusalTests(unittest.TestCase):
    def test_listing_not_supported_by_the_provider_is_refused_before_any_transport_call(self):
        t = RecordingTransport(lambda u: kraken_body(window_rows()))
        r = run(select_provider("kraken"), BINANCE_LISTING, t)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "request"))
        self.assertEqual(t.urls, [])
        self.assertEqual(r["requests_made"], 0)

    def test_unsupported_interval_is_refused_before_any_transport_call(self):
        t = RecordingTransport(lambda u: binance_body(window_rows()))
        r = run(BinanceVision(), BINANCE_LISTING, t, timeframe=3600)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "request"))
        self.assertEqual(t.urls, [])

    def test_non_crypto_asset_class_is_refused_by_the_calendar_gate(self):
        class _Instrument:
            asset_class = "equity"

        class _Listing:
            canonical = "equity:fixture-spot:ABC-USD"
            venue = "fixture"
            market_type = "spot"
            instrument = _Instrument()

        class _Provider(BinanceVision):
            def check_request(self, listing, timeframe_s):
                return "ABC"

        t = RecordingTransport(lambda u: b"[]")
        r = dp.fetch_market_data(_Provider(), _Listing(), DAY, NOW, data_source="synthetic",
                                 time_source="explicit-caller", transport=t, lookback=LOOKBACK)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "calendar"))
        self.assertEqual(t.urls, [])

    def test_malformed_provider_output_is_refused(self):
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: b"<html>503</html>"))
        self.assertEqual((r["status"], r["error"]["kind"]), (dp.REFUSED, "bad_payload"))

    def test_conflicting_duplicate_is_refused(self):
        rows = window_rows()
        rows.insert(10, (rows[9][0], 1.0, 2.0, 0.5, 1.5, 1.0))
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(rows)))
        self.assertEqual((r["status"], r["error"]["kind"]), (dp.REFUSED, "conflicting_duplicate"))
        self.assertIsNone(r["canonical_candles"])

    def test_exact_duplicate_is_accepted_and_counted(self):
        rows = window_rows()
        rows.insert(10, rows[9])
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(rows)))
        self.assertEqual(r["status"], dp.COMPLETE)
        self.assertEqual(r["candles"]["duplicates_removed"], 1)
        self.assertEqual(r["candles"]["completed_count"], LOOKBACK)

    def test_misaligned_timestamp_is_refused(self):
        data = json.loads(binance_body(window_rows()))
        data[5][0] += 3600 * 1000            # an hour off the daily grid, with a matching close time
        data[5][6] += 3600 * 1000
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: json.dumps(data).encode()))
        self.assertEqual((r["status"], r["error"]["kind"]), (dp.REFUSED, "bad_payload"))

    def test_provider_rate_limit_is_refused_with_the_structured_kind(self):
        def limited(url):
            raise TransportFailure("rate_limited", "HTTP 429", 429)
        t = RecordingTransport(limited)
        r = run(BinanceVision(), BINANCE_LISTING, t)
        self.assertEqual((r["status"], r["error"]["kind"], r["error"]["retriable"]), (dp.REFUSED, "rate_limited", True))
        self.assertEqual(r["requests_made"], 1)

    def test_stale_data_is_refused(self):
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows())),
                now=NOW + 5 * DAY)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "gates"))
        self.assertEqual(r["freshness"]["state"], dp.OVERDUE)


class FreshnessTests(unittest.TestCase):
    """Provider freshness is decided by the publication schedule at an explicit now_s (see markets/data_pipeline.py).
    Every test passes now_s and the grace period explicitly. None reads the machine clock."""

    G = dp.DEFAULT_PUBLICATION_GRACE_S

    def _run_rows(self, rows, now=NOW, grace=G, lookback=LOOKBACK):
        return run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(rows)), now=now,
                   grace=grace, lookback=lookback)

    def test_fresh_complete_series_is_complete_and_current(self):
        r = self._run_rows(window_rows())
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.COMPLETE, dp.CURRENT))
        self.assertTrue(r["freshness"]["expected_latest_present"])

    def test_fresh_partial_missing_its_final_slot_within_grace_is_a_gap_not_an_outage(self):
        now = NOW + DAY                       # the window's final slot has just closed, inside the grace period
        end = END + DAY
        r = self._run_rows(window_fixture(end, drop=(0,)), now=now)
        self.assertEqual((r["status"], r["stage"]), (dp.PARTIAL, "gates"), r["reasons"])
        self.assertEqual(r["freshness"]["state"], dp.AWAITING)
        self.assertFalse(r["freshness"]["expected_latest_present"])
        self.assertEqual(r["coverage"]["missing_expected_sample"], [dp.utc_text(end)])
        self.assertTrue(any("publication grace" in x for x in r["reasons"]), r["reasons"])
        self.assertEqual(len(r["canonical_candles"]), LOOKBACK - 1)

    def test_partial_with_an_older_internal_gap_is_current_and_not_a_freshness_failure(self):
        r = self._run_rows(window_fixture(END, drop=(40,)))
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.PARTIAL, dp.CURRENT))
        self.assertTrue(r["freshness"]["expected_latest_present"])
        self.assertFalse(any("grace" in x or "overdue" in x for x in r["reasons"]), r["reasons"])

    def test_genuinely_stale_provider_is_refused_as_overdue(self):
        r = self._run_rows(window_rows(), now=NOW + 5 * DAY)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "gates"))
        self.assertEqual(r["freshness"]["state"], dp.OVERDUE)
        self.assertTrue(any("provider overdue" in x for x in r["reasons"]), r["reasons"])
        self.assertIsNone(r["canonical_candles"])

    def test_a_window_whose_newest_interval_has_not_completed_uses_the_previous_slot_as_its_final_slot(self):
        r = self._run_rows(window_rows())            # NOW is 1 hour into a day; the candle at that day is forming
        self.assertEqual(r["candles"]["forming_dropped"], 1)
        self.assertEqual(r["window"]["end_utc"], dp.utc_text(END))
        self.assertEqual(r["freshness"]["expected_latest_open_utc"], dp.utc_text(END))
        self.assertEqual(r["status"], dp.COMPLETE)

    def test_only_the_forming_interval_in_the_response_is_unavailable(self):
        forming_only = [(FORMING_T, 1.0, 2.0, 0.5, 1.5, 1.0)]
        r = self._run_rows(forming_only)
        self.assertEqual((r["status"], r["stage"]), (dp.UNAVAILABLE, "fetch"))
        self.assertIsNone(r["candles"])
        self.assertIsNone(r["canonical_candles"])
        self.assertFalse(r["coverage"]["complete"])

    def test_grace_minus_one_second_keeps_a_missing_final_slot_awaiting(self):
        now = END + DAY + self.G - 1
        r = self._run_rows(window_fixture(END, drop=(0,)), now=now)
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.PARTIAL, dp.AWAITING))

    def test_grace_exactly_makes_a_missing_final_slot_due_and_so_overdue(self):
        now = END + DAY + self.G
        r = self._run_rows(window_fixture(END, drop=(0,)), now=now)
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.REFUSED, dp.OVERDUE))
        self.assertEqual(r["freshness"]["newest_due_open_utc"], dp.utc_text(END))

    def test_zero_grace_makes_a_missing_final_slot_overdue_one_second_after_it_closes(self):
        r = self._run_rows(window_fixture(END, drop=(0,)), now=END + DAY + 1, grace=0)
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.REFUSED, dp.OVERDUE))

    def test_two_missing_final_slots_are_overdue_not_a_gap(self):
        r = self._run_rows(window_fixture(END, drop=(0, 1)), now=END + DAY + 3600)
        self.assertEqual((r["status"], r["freshness"]["state"]), (dp.REFUSED, dp.OVERDUE))
        self.assertTrue(any("provider overdue" in x for x in r["reasons"]), r["reasons"])

    def test_the_grace_period_is_an_explicit_argument_and_negative_values_are_refused(self):
        for bad in (-1, True, 1.5):
            with self.subTest(grace=bad):
                with self.assertRaises(dp.PipelineError):
                    self._run_rows(window_rows(), grace=bad)

    def test_no_completed_slot_is_an_argument_error_with_no_transport_call(self):
        t = RecordingTransport(lambda u: binance_body(window_rows()))
        with self.assertRaises(dp.PipelineError):
            run(BinanceVision(), BINANCE_LISTING, t, now=DAY - 1)
        self.assertEqual(t.urls, [])

    def test_a_window_before_the_epoch_is_an_argument_error_with_no_transport_call(self):
        t = RecordingTransport(lambda u: binance_body(window_rows()))
        with self.assertRaises(dp.PipelineError):
            run(BinanceVision(), BINANCE_LISTING, t, now=100 * DAY + 3600)
        self.assertEqual(t.urls, [])

    def test_a_lookback_above_the_validation_grid_limit_is_an_argument_error(self):
        # now is far enough out that the window starts after the epoch, so only the grid limit can refuse it.
        far_now = 3_000_000 * DAY + 3600
        t = RecordingTransport(lambda u: binance_body(window_rows()))
        with self.assertRaises(dp.PipelineError) as ctx:
            run(BinanceVision(), BINANCE_LISTING, t, now=far_now, lookback=dp.vd.MAX_GRID_SLOTS + 1)
        self.assertIn("grid limit", str(ctx.exception))
        self.assertEqual(t.urls, [])

    def test_a_non_gap_validation_failure_refuses_even_when_a_gap_is_also_present(self):
        # The real adapters cannot produce a non-gap FAIL here, so the validator's report is extended with one.
        # The refusal rule must hold: only missing expected slots may make a series PARTIAL.
        real = dp.vd.validate_series

        def with_ohlc_fail(*args, **kwargs):
            report = real(*args, **kwargs)
            return dataclasses.replace(report, checks=report.checks + (
                dp.vd.Check("ohlc", dp.vd.FAIL, "forced non-gap failure for the test"),))
        gap = window_fixture(END, drop=(40,))
        with mock.patch.object(dp.vd, "validate_series", side_effect=with_ohlc_fail):
            r = self._run_rows(gap)
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "gates"), r["reasons"])
        self.assertTrue(any("validation FAIL" in x and "ohlc" in x for x in r["reasons"]), r["reasons"])
        self.assertIsNone(r["canonical_candles"])

    def test_a_validator_that_cannot_establish_the_full_window_fails_closed(self):
        real = dp.vd.validate_series

        def coverage_none(*args, **kwargs):
            return dataclasses.replace(real(*args, **kwargs), coverage=dp.vd.COVERAGE_NONE,
                                       coverage_reason="forced for the fail-closed test")
        with mock.patch.object(dp.vd, "validate_series", side_effect=coverage_none):
            r = self._run_rows(window_rows())
        self.assertEqual((r["status"], r["stage"]), (dp.REFUSED, "gates"))
        self.assertTrue(any("could not establish the full window" in x for x in r["reasons"]), r["reasons"])
        self.assertIsNone(r["canonical_candles"])


class StatusContractTests(unittest.TestCase):
    """The public status contract: exactly four statuses, each reached by a real scenario."""

    def test_exactly_four_statuses_and_three_freshness_states(self):
        self.assertEqual(dp.STATUSES, ("COMPLETE", "PARTIAL", "UNAVAILABLE", "REFUSED"))
        self.assertEqual(dp.FRESHNESS_STATES, ("current", "awaiting_publication", "overdue"))

    def test_each_status_is_reached_by_a_real_scenario(self):
        def rate_limited(url):
            raise TransportFailure("rate_limited", "HTTP 429", 429)
        gap = window_fixture(END, drop=(40,))
        scenarios = {
            dp.COMPLETE: run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows()))),
            dp.PARTIAL: run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(gap))),
            dp.UNAVAILABLE: run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: b"[]")),
            dp.REFUSED: run(BinanceVision(), BINANCE_LISTING, RecordingTransport(rate_limited)),
        }
        for status, r in scenarios.items():
            self.assertEqual(r["status"], status, r["reasons"])
        self.assertEqual({r["status"] for r in scenarios.values()}, set(dp.STATUSES))
        self.assertEqual(scenarios[dp.REFUSED]["error"]["kind"], "rate_limited")
        self.assertEqual(scenarios[dp.UNAVAILABLE]["error"]["kind"], "empty")


class NoSilentFallbackTests(unittest.TestCase):
    def test_a_failed_provider_is_never_replaced_by_another(self):
        def failing(url):
            raise TransportFailure("unavailable", "HTTP 503", 503)
        t = RecordingTransport(failing)
        r = run(BinanceVision(), BINANCE_LISTING, t)
        self.assertEqual(r["status"], dp.REFUSED)
        self.assertEqual(r["provider"]["name"], "binance-vision")
        self.assertTrue(all("binance" in u for u in t.urls), t.urls)


class GenericityTests(unittest.TestCase):
    def _fixture_listing(self):
        return parse_listing("crypto:fixture-spot:ABC-USD")

    def test_a_third_venue_runs_through_the_same_pipeline(self):
        rows = window_rows()
        t = RecordingTransport(lambda u: fixture_body(rows))
        r = run(FixtureVenueProvider(), self._fixture_listing(), t)
        self.assertEqual(r["status"], dp.COMPLETE, r["reasons"])
        self.assertEqual(r["provider"]["venue"], "fixture")
        self.assertEqual(r["candles"]["completed_count"], LOOKBACK)

    def test_missing_volume_is_never_converted_to_zero(self):
        rows_null = [(t, o, h, lo, c, None) for t, o, h, lo, c, v in window_rows()]
        rows_zero = [(t, o, h, lo, c, 0.0) for t, o, h, lo, c, v in window_rows()]
        rn = run(FixtureVenueProvider(), self._fixture_listing(), RecordingTransport(lambda u: fixture_body(rows_null)))
        rz = run(FixtureVenueProvider(), self._fixture_listing(), RecordingTransport(lambda u: fixture_body(rows_zero)))
        self.assertEqual(rn["status"], dp.COMPLETE)
        self.assertEqual(rn["candles"]["volume_supplied_count"], 0)
        self.assertEqual(rz["candles"]["volume_supplied_count"], LOOKBACK)
        self.assertNotEqual(rn["candles"]["dataset_sha256"], rz["candles"]["dataset_sha256"])
        volume_check = [c for c in rn["candles"]["validation"]["checks"] if c["name"] == "volume"][0]
        self.assertEqual(volume_check["status"], "PASS")
        self.assertIn("not treated as zero", volume_check["detail"])

    def test_partly_missing_volume_is_a_warning_not_a_zero(self):
        rows = [(t, o, h, lo, c, None if i % 2 else v) for i, (t, o, h, lo, c, v) in enumerate(window_rows())]
        r = run(FixtureVenueProvider(), self._fixture_listing(), RecordingTransport(lambda u: fixture_body(rows)))
        self.assertEqual(r["status"], dp.COMPLETE)
        volume_check = [c for c in r["candles"]["validation"]["checks"] if c["name"] == "volume"][0]
        self.assertEqual(volume_check["status"], "WARN")
        self.assertGreater(r["candles"]["volume_supplied_count"], 0)
        self.assertLess(r["candles"]["volume_supplied_count"], LOOKBACK)

    def test_shared_core_names_no_market_provider_or_asset(self):
        with open(os.path.join(_HERE, "data_pipeline.py"), encoding="utf-8") as f:
            text = f.read().lower()
        for forbidden in ("binance", "kraken", "btc", "usdt", "xbt", "eth", "crypto:"):
            self.assertNotIn(forbidden, text, f"shared core must not name {forbidden!r}")

    def test_shared_core_imports_no_network_modules(self):
        with open(os.path.join(_HERE, "data_pipeline.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & {"urllib", "socket", "http", "ssl"}, names)


class DeterminismTests(unittest.TestCase):
    def test_the_same_inputs_give_byte_identical_reports(self):
        def once():
            r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows())))
            return json.dumps(dp.json_safe(r), sort_keys=True)
        self.assertEqual(once(), once())

    def test_provenance_fields_are_present(self):
        r = run(BinanceVision(), BINANCE_LISTING, RecordingTransport(lambda u: binance_body(window_rows())))
        self.assertEqual(r["data_source"], "synthetic")
        self.assertEqual(r["reference_time"]["source"], "explicit-caller")
        self.assertEqual(r["provider"]["name"], "binance-vision")
        self.assertIsNotNone(r["candles"]["raw_sha256"])
        self.assertIsNotNone(r["candles"]["dataset_sha256"])
        self.assertEqual(r["requests_made"], 1)
        self.assertIn("No order", r["no_trading"])


class M3ParityTests(unittest.TestCase):
    def test_shared_dataset_hash_equals_the_m3_hash_for_the_same_candles(self):
        canon = list(BinanceVision().fetch_candles(
            BINANCE_LISTING, DAY, START, END, NOW,
            transport=lambda u: binance_body(window_rows())).candles)
        self.assertEqual(dp.dataset_sha256(canon), bp.dataset_sha256(canon))


if __name__ == "__main__":
    unittest.main()
