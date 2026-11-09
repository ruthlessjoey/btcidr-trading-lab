"""Regression tests for the M4a review fixes. Offline only: fixture responders and a patched urllib opener. No network.

Covers: Kraken since-boundary tolerance, Kraken's 720-most-recent history limit, live-transport connection errors,
and empty intermediate pages.
"""
import http.client
from contextlib import ExitStack, contextmanager
import json
import os
import socket
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for p in (_ROOT, os.path.join(_ROOT, "pipeline")):
    if p not in sys.path:
        sys.path.insert(0, p)

import candle_pipeline as cp  # noqa: E402
from markets.identity import parse_listing  # noqa: E402
from markets.providers import ProviderError  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers.kraken import Kraken  # noqa: E402
from markets.providers.transport import TransportFailure, live_transport  # noqa: E402

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
LOOKBACK = 1500
FIRST = END - (LOOKBACK - 1) * DAY
LISTING = parse_listing("crypto:kraken-spot:BTC-USD")
FORMING_T = (NOW // DAY) * DAY


@contextmanager
def patched_live_opener(exc):
    """Use a deterministic opener and hard-deny every standard socket connection path."""
    opener = mock.Mock()
    opener.open.side_effect = exc
    blocked = AssertionError("network access is forbidden in this offline regression test")
    with ExitStack() as stack:
        stack.enter_context(mock.patch("urllib.request.build_opener", return_value=opener))
        stack.enter_context(mock.patch("urllib.request.urlopen", side_effect=blocked))
        stack.enter_context(mock.patch("socket.create_connection", side_effect=blocked))
        stack.enter_context(mock.patch("socket.socket.connect", side_effect=blocked))
        stack.enter_context(mock.patch("socket.socket.connect_ex", side_effect=blocked))
        try:
            yield opener
        finally:
            # Must run even when the expected mocked transport exception escapes.
            opener.open.assert_called()


def all_rows():
    """1500 completed daily candles ending at END, plus the candle still forming at NOW."""
    return syn.series(FIRST, LOOKBACK, DAY) + [(FORMING_T, 1.0, 2.0, 0.5, 1.5, 1.0)]


def inclusive_responder(rows, limit=720):
    """Returns up to `limit` rows whose open time is >= since."""
    def respond(url):
        since = int(syn.query_value(url, "since"))
        return syn.kraken_body([r for r in rows if r[0] >= since][:limit])
    return respond


def exclusive_responder(rows, limit=720):
    """Returns up to `limit` rows whose open time is strictly after since."""
    def respond(url):
        since = int(syn.query_value(url, "since"))
        return syn.kraken_body([r for r in rows if r[0] > since][:limit])
    return respond


def latest_only_responder(rows, limit=720):
    """Kraken's documented behaviour: ignores 'since' and returns the most recent `limit` entries."""
    def respond(url):
        return syn.kraken_body(rows[-limit:])
    return respond


class SinceBoundaryTests(unittest.TestCase):
    def test_exclusive_since_server_loses_no_candles(self):
        t = syn.ScriptedTransport(exclusive_responder(all_rows()))
        r = Kraken().fetch_candles(LISTING, DAY, FIRST, END, NOW, transport=t)
        self.assertEqual([c.open_time_s for c in r.candles], [FIRST + i * DAY for i in range(LOOKBACK)])
        self.assertEqual(r.forming_dropped, 1)
        self.assertEqual(r.requests_made, 3)

    def test_each_request_reaches_one_interval_before_its_window(self):
        t = syn.ScriptedTransport(inclusive_responder(all_rows()))
        Kraken().fetch_candles(LISTING, DAY, FIRST, END, NOW, transport=t)
        self.assertEqual(int(syn.query_value(t.urls[0], "since")), FIRST - DAY)

    def test_exclusive_pipeline_run_passes_the_gates(self):
        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(exclusive_responder(all_rows())),
                                        lookback=LOOKBACK)
        self.assertEqual(report["gate"]["status"], "PASSED", report["gate"]["reasons"])
        self.assertEqual(report["candles"]["completed_count"], LOOKBACK)


class HistoryLimitTests(unittest.TestCase):
    def test_latest_only_server_is_history_unavailable_on_the_first_page(self):
        t = syn.ScriptedTransport(latest_only_responder(all_rows()))
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, FIRST, END, NOW, transport=t)
        self.assertEqual(cm.exception.kind, "history_unavailable")
        self.assertFalse(cm.exception.retriable)
        self.assertEqual(len(t.urls), 1, "the refusal must come from the first page, not after more requests")

    def test_pipeline_reports_the_provider_limit_not_expected_missing(self):
        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(latest_only_responder(all_rows())),
                                        lookback=LOOKBACK)
        self.assertEqual(report["gate"]["status"], "REFUSED")
        self.assertEqual(report["gate"]["stage"], "fetch")
        self.assertEqual(report["error"]["kind"], "history_unavailable")
        self.assertIsNone(report["candles"])

    def test_a_window_inside_the_latest_720_still_passes(self):
        # The limit is Kraken-specific and applies only when a page cannot reach the window start.
        recent = 700
        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(latest_only_responder(all_rows())),
                                        lookback=recent)
        self.assertEqual(report["gate"]["status"], "PASSED", report["gate"]["reasons"])
        self.assertEqual(report["candles"]["completed_count"], recent)


class EmptyPageTests(unittest.TestCase):
    EMPTY = json.dumps({"error": [], "result": {"XXBTZUSD": [], "last": 0}}).encode()

    def test_empty_intermediate_page_is_structured_empty(self):
        rows = all_rows()
        inclusive = inclusive_responder(rows)
        calls = []

        def second_page_empty(url):
            calls.append(url)
            return inclusive(url) if len(calls) == 1 else self.EMPTY

        t = syn.ScriptedTransport(second_page_empty)
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, FIRST, END, NOW, transport=t)
        self.assertEqual(cm.exception.kind, "empty")
        self.assertIn("page 2 of 3", cm.exception.detail)
        self.assertEqual(len(t.urls), 2, "the run stops at the empty page; it does not continue into the gap")

    def test_empty_first_page_is_structured_empty(self):
        t = syn.ScriptedTransport(lambda url: self.EMPTY)
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, FIRST, END, NOW, transport=t)
        self.assertEqual(cm.exception.kind, "empty")

    def test_empty_intermediate_page_refuses_the_pipeline(self):
        rows = all_rows()
        inclusive = inclusive_responder(rows)
        calls = []

        def second_page_empty(url):
            calls.append(url)
            return inclusive(url) if len(calls) == 1 else self.EMPTY

        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(second_page_empty), lookback=LOOKBACK)
        self.assertEqual(report["gate"]["status"], "REFUSED")
        self.assertEqual(report["error"]["kind"], "empty")


class LiveTransportTests(unittest.TestCase):
    def test_remote_disconnected_becomes_unavailable(self):
        with patched_live_opener(http.client.RemoteDisconnected("closed by peer")):
            with self.assertRaises(TransportFailure) as cm:
                live_transport("https://api.kraken.com/0/public/OHLC?pair=XBTUSD")
        self.assertEqual(cm.exception.kind, "unavailable")

    def test_other_connection_errors_become_unavailable(self):
        for exc in (ConnectionResetError("reset"), http.client.IncompleteRead(b""), OSError("tls failure")):
            with self.subTest(exc=type(exc).__name__):
                with patched_live_opener(exc):
                    with self.assertRaises(TransportFailure) as cm:
                        live_transport("https://api.kraken.com/0/public/OHLC?pair=XBTUSD")
                self.assertEqual(cm.exception.kind, "unavailable")

    def test_timeouts_still_map_to_timeout(self):
        with patched_live_opener(socket.timeout("timed out")):
            with self.assertRaises(TransportFailure) as cm:
                live_transport("https://api.kraken.com/0/public/OHLC?pair=XBTUSD")
        self.assertEqual(cm.exception.kind, "timeout")

    def test_pipeline_refuses_with_a_structured_report_when_the_connection_drops(self):
        # No exception may escape the pipeline. The run is refused with a structured error and no signal.
        with patched_live_opener(http.client.RemoteDisconnected("closed by peer")):
            report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="live",
                                            time_source="runtime-clock", lookback=119)
        self.assertEqual(report["gate"]["status"], "REFUSED")
        self.assertEqual(report["gate"]["stage"], "fetch")
        self.assertEqual(report["error"]["kind"], "unavailable")
        self.assertIsNone(report["signal"])


class OfflineOpenerGuardTests(unittest.TestCase):
    def test_mock_opener_assertion_runs_when_open_raises(self):
        expected = OSError("synthetic connection failure")
        with patched_live_opener(expected) as opener:
            with self.assertRaises(OSError):
                opener.open("https://offline.invalid/")
        opener.open.assert_called_once_with("https://offline.invalid/")


if __name__ == "__main__":
    unittest.main()
