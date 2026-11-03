"""Offline tests for pipeline/candle_pipeline.py. Fixture transports only. No network.

Run from the repository root with:
    python3 -B -m unittest discover -s pipeline -p "test_*.py"
"""
import json
import os
import sys
import unittest
from unittest import mock

import candle_pipeline as cp
from s1_bridge import s1_daily_signal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markets.identity import parse_listing  # noqa: E402
from markets.providers import ProviderInfo  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers import transport as tr  # noqa: E402
from markets.providers.binance_vision import BinanceVision  # noqa: E402
from markets.providers.kraken import Kraken  # noqa: E402

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
START = END - 118 * DAY
KRAKEN = parse_listing("crypto:kraken-spot:BTC-USD")
BINANCE = parse_listing("crypto:binance-spot:BTC-USDT")


def completed_plus_forming(start=START, count=119, now=NOW):
    rows = syn.series(start, count, DAY)
    rows.append(((now // DAY) * DAY, 1.0, 2.0, 0.5, 1.5, 1.0))
    return rows


def kraken_run(rows=None, **kw):
    rows = rows if rows is not None else completed_plus_forming()
    t = syn.ScriptedTransport(lambda url: syn.kraken_body(rows))
    kw.setdefault("data_source", "synthetic")
    kw.setdefault("time_source", "explicit-caller")
    return cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, transport=t, lookback=119, **kw), t


class SecondProviderScenarioTests(unittest.TestCase):
    """The M4a demonstration: a second provider, offline, through the same shared pipeline."""

    def test_kraken_fixture_passes_the_shared_pipeline(self):
        r, t = kraken_run()
        self.assertEqual(r["gate"]["status"], "PASSED", r["gate"])
        self.assertEqual(r["provider"]["name"], "kraken")
        self.assertEqual(r["listing"]["canonical"], "crypto:kraken-spot:BTC-USD")
        self.assertEqual(r["candles"]["completed_count"], 119)
        self.assertEqual(r["candles"]["forming_dropped"], 1)
        self.assertEqual(r["candles"]["validation"]["coverage"], "complete")
        self.assertEqual(r["requests_made"], 1)
        self.assertEqual(len(t.urls), 1)
        self.assertIsNone(r["signal"])      # no signal function configured: validation only
        self.assertIsNone(r["error"])

    def test_kraken_fixture_with_the_s1_bridge_produces_a_signal(self):
        r, _ = kraken_run(signal_fn=s1_daily_signal)
        self.assertEqual(r["gate"]["status"], "PASSED")
        self.assertIn(r["signal"]["decision"], ("BUY", "SELL", "WAIT"))
        self.assertEqual(r["explanation"][0], r["signal"]["decision_meaning"])

    def test_report_is_json_serializable_and_renders_markdown(self):
        r, _ = kraken_run()
        json.dumps(r, sort_keys=True)
        md = cp.render_markdown(r)
        self.assertIn("Gate: PASSED", md)
        self.assertIn("**Data source: synthetic**", md)
        self.assertIn("kraken", md)

    def test_the_720_limit_passes_end_to_end_for_a_longer_lookback(self):
        lookback = 1500
        first = END - (lookback - 1) * DAY
        all_rows = completed_plus_forming(first, lookback)

        def paged(url):
            since = int(syn.query_value(url, "since"))
            return syn.kraken_body([r for r in all_rows if r[0] >= since][:720])

        t = syn.ScriptedTransport(paged)
        r = cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="synthetic",
                                   time_source="explicit-caller", transport=t, lookback=lookback)
        self.assertEqual(r["gate"]["status"], "PASSED", r["gate"])
        self.assertEqual(r["requests_made"], 3)
        self.assertEqual(r["candles"]["completed_count"], lookback)


class ProvenanceTests(unittest.TestCase):
    def test_live_label_is_only_valid_without_an_injected_transport(self):
        with self.assertRaises(cp.PipelineError):
            cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="live", time_source="explicit-caller",
                                   transport=syn.ScriptedTransport(lambda u: b""))

    def test_live_run_uses_the_real_transport_and_is_labeled_live(self):
        body = syn.kraken_body(completed_plus_forming())
        with mock.patch.object(cp, "live_transport", return_value=body) as live:
            r = cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="live",
                                       time_source="runtime-clock", lookback=119)
        self.assertEqual(live.call_count, 1)
        self.assertEqual(r["data_source"], "live")
        self.assertEqual(r["gate"]["status"], "PASSED")

    def test_synthetic_and_replay_need_a_caller_transport_and_never_fall_back_to_the_network(self):
        with mock.patch.object(cp, "live_transport", side_effect=AssertionError("network fallback")):
            for src in ("synthetic", "replay"):
                with self.subTest(source=src):
                    with self.assertRaises(cp.PipelineError):
                        cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source=src,
                                               time_source="explicit-caller", transport=None)

    def test_replay_and_synthetic_need_an_explicit_reference_time(self):
        with self.assertRaises(cp.PipelineError):
            cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="replay",
                                   time_source="runtime-clock",
                                   transport=syn.ScriptedTransport(lambda u: syn.kraken_body([])))

    def test_invalid_values_are_rejected(self):
        t = syn.ScriptedTransport(lambda u: b"")
        for bad_source in ("LIVE", "", None):
            with self.subTest(data_source=bad_source):
                with self.assertRaises(cp.PipelineError):
                    cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source=bad_source,
                                           time_source="explicit-caller", transport=t)
        with self.assertRaises(cp.PipelineError):
            cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="synthetic", time_source="clock",
                                   transport=t)
        with self.assertRaises(cp.PipelineError):
            cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, -1, data_source="synthetic",
                                   time_source="explicit-caller", transport=t)

    def test_data_source_and_time_source_are_required_keywords(self):
        with self.assertRaises(TypeError):
            cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, transport=syn.ScriptedTransport(lambda u: b""))


class RefusalTests(unittest.TestCase):
    """Every refusal stops the run, produces no signal, and records a structured reason."""

    def assertRefused(self, r, stage):
        self.assertEqual(r["gate"]["status"], "REFUSED")
        self.assertEqual(r["gate"]["stage"], stage)
        self.assertIsNone(r["signal"])
        self.assertIn("Signal NOT produced", r["explanation"][0])
        self.assertIn("**Gate: REFUSED**", cp.render_markdown(r))

    def test_unsupported_listing_refuses_before_any_transport_call(self):
        t = syn.ScriptedTransport(lambda u: b"")
        r = cp.run_candle_pipeline(Kraken(), parse_listing("crypto:kraken-spot:ETH-USD"), DAY, NOW,
                                   data_source="synthetic", time_source="explicit-caller", transport=t)
        self.assertRefused(r, "request")
        self.assertEqual(r["error"]["kind"], "unsupported_listing")
        self.assertEqual(t.urls, [])
        self.assertEqual(r["requests_made"], 0)

    def test_unsupported_interval_refuses_before_any_transport_call(self):
        t = syn.ScriptedTransport(lambda u: b"")
        r = cp.run_candle_pipeline(Kraken(), KRAKEN, 3600, NOW, data_source="synthetic",
                                   time_source="explicit-caller", transport=t)
        self.assertRefused(r, "request")
        self.assertEqual(r["error"]["kind"], "unsupported_interval")
        self.assertEqual(t.urls, [])

    def test_non_crypto_listing_refuses_at_the_calendar_stage_with_no_request(self):
        class EquityFake(Kraken):
            info = ProviderInfo(name="fake-equity", venue="kraken", docs_url="https://example.org/x",
                                terms_source="unverified")
            SYMBOLS = {"equity:kraken-cash:AAPL-USD": "AAPL"}
        equity = parse_listing("equity:kraken-cash:AAPL-USD")
        t = syn.ScriptedTransport(lambda u: b"")
        r = cp.run_candle_pipeline(EquityFake(), equity, DAY, NOW, data_source="synthetic",
                                   time_source="explicit-caller", transport=t)
        self.assertRefused(r, "calendar")
        self.assertEqual(t.urls, [])

    def test_rate_limit_is_a_structured_fetch_refusal_with_one_request(self):
        def limited(url):
            raise tr.TransportFailure("rate_limited", "HTTP 429", 429)
        r = cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="synthetic",
                                   time_source="explicit-caller", transport=syn.ScriptedTransport(limited))
        self.assertRefused(r, "fetch")
        self.assertEqual(r["error"], {"kind": "rate_limited", "provider": "kraken", "detail": "HTTP 429",
                                      "http_status": 429, "retriable": True})
        self.assertEqual(r["requests_made"], 1)

    def test_timeout_and_unavailable_are_structured_fetch_refusals(self):
        for kind in ("timeout", "unavailable"):
            def fail(url, kind=kind):
                raise tr.TransportFailure(kind, kind)
            with self.subTest(kind=kind):
                r = cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="synthetic",
                                           time_source="explicit-caller",
                                           transport=syn.ScriptedTransport(fail))
                self.assertRefused(r, "fetch")
                self.assertEqual(r["error"]["kind"], kind)

    def test_conflicting_duplicate_refuses_at_fetch(self):
        rows = completed_plus_forming()
        rows.append((rows[5][0], 1.0, 2.0, 0.5, 1.5, 1.0))
        r, _ = kraken_run(rows=rows)
        self.assertRefused(r, "fetch")
        self.assertEqual(r["error"]["kind"], "conflicting_duplicate")

    def test_a_missing_interval_is_refused_by_validation_and_never_filled(self):
        rows = completed_plus_forming()
        del rows[40]
        r, _ = kraken_run(rows=rows)
        self.assertRefused(r, "gates")
        self.assertEqual(r["candles"]["completed_count"], 118)
        self.assertIn("expected_missing", " ".join(r["gate"]["reasons"]))

    def test_stale_data_is_refused_by_the_gates(self):
        # A series that ends ten days before the window: no collision with the window, so the gates must refuse.
        old_rows = completed_plus_forming(start=START - 10 * DAY, now=NOW - 10 * DAY)
        r, _ = kraken_run(rows=old_rows)
        self.assertRefused(r, "gates")

    def test_empty_provider_response_is_refused_at_fetch(self):
        body = json.dumps({"error": [], "result": {"XXBTZUSD": [], "last": 0}}).encode()
        r = cp.run_candle_pipeline(Kraken(), KRAKEN, DAY, NOW, data_source="synthetic",
                                   time_source="explicit-caller",
                                   transport=syn.ScriptedTransport(lambda u: body))
        self.assertRefused(r, "fetch")
        self.assertEqual(r["error"]["kind"], "empty")


class ParityWithM3Tests(unittest.TestCase):
    """The M4a Binance adapter, fed the same bytes as the committed M3 pipeline, must reach the same dataset
    fingerprint and the same S1 decision. M3 itself is not modified."""

    class _Resp:
        status = 200

        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def test_binance_adapter_matches_m3_on_identical_bytes(self):
        import btc_pipeline as bp
        now = NOW
        day_start = (now // DAY) * DAY
        first = day_start - 119 * DAY
        body = syn.binance_body(syn.series(first, 120, DAY), DAY)      # 119 completed + 1 forming

        m3 = bp.run(now, data_source="synthetic", time_source="explicit-caller",
                    opener=lambda req, timeout=None: self._Resp(body))
        m4 = cp.run_candle_pipeline(BinanceVision(), BINANCE, DAY, now, data_source="synthetic",
                                    time_source="explicit-caller",
                                    transport=syn.ScriptedTransport(lambda u: body),
                                    lookback=119, signal_fn=s1_daily_signal)

        self.assertEqual(m3["gate"]["status"], "PASSED", m3["gate"])
        self.assertEqual(m4["gate"]["status"], "PASSED", m4["gate"])
        self.assertEqual(m3["candles"]["dataset_sha256"], m4["candles"]["dataset_sha256"])
        self.assertEqual(m3["signal"]["decision"], m4["signal"]["decision"])
        self.assertEqual(m3["signal"]["values"], m4["signal"]["values"])
        self.assertEqual(m3["candles"]["completed_count"], m4["candles"]["completed_count"])


class NoNetworkTests(unittest.TestCase):
    def test_a_full_synthetic_run_never_touches_urlopen(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
            r, _ = kraken_run(signal_fn=s1_daily_signal)
        self.assertEqual(r["gate"]["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
