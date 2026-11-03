"""Kraken boundary and overlap-accounting tests. Offline fixtures only. No network.

Models two documented facts: a call returns up to 720 of the most recent entries (the forming candle is one of them),
and older data cannot be retrieved regardless of 'since'. Also models a forward-paging server with full history, to
check overlap accounting when data exists before the requested window.
"""
import os
import sys
import unittest

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

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY           # last completed daily candle
FORMING_T = (NOW // DAY) * DAY           # still forming at NOW
LISTING = parse_listing("crypto:kraken-spot:BTC-USD")
MAX = 720


def completed(count, last=END):
    """`count` completed daily candles ending at `last`."""
    return syn.series(last - (count - 1) * DAY, count, DAY)


def forming():
    return (FORMING_T, 1.0, 2.0, 0.5, 1.5, 1.0)


def latest_only(data):
    """Documented behaviour: ignores 'since' and returns the most recent 720 entries of `data`."""
    return lambda url: syn.kraken_body(data[-MAX:])


def inclusive(data):
    """Forward paging with inclusive 'since': up to 720 rows starting at since."""
    def respond(url):
        since = int(syn.query_value(url, "since"))
        return syn.kraken_body([r for r in data if r[0] >= since][:MAX])
    return respond


def grid(start, n):
    return [start + i * DAY for i in range(n)]


class BoundaryTests(unittest.TestCase):
    """The latest-720 limit. Only 719 completed candles fit beside the forming candle in one response."""

    def test_719_completed_candles_are_retrievable_and_pass(self):
        data = completed(1500) + [forming()]              # plenty of history; latest 720 = 719 completed + forming
        start = END - 718 * DAY
        t = syn.ScriptedTransport(latest_only(data))
        r = Kraken().fetch_candles(LISTING, DAY, start, END, NOW, transport=t)
        self.assertEqual(r.requests_made, 1)
        self.assertEqual(len(r.candles), 719)
        self.assertEqual([c.open_time_s for c in r.candles], grid(start, 719))
        self.assertEqual((r.forming_dropped, r.duplicates_removed, r.out_of_window_dropped), (1, 0, 0))

    def test_719_completed_candles_pass_the_pipeline_gates(self):
        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(latest_only(completed(1500) + [forming()])),
                                        lookback=719)
        self.assertEqual(report["gate"]["status"], "PASSED", report["gate"]["reasons"])
        self.assertEqual(report["candles"]["completed_count"], 719)

    def test_720_completed_candles_are_refused_under_the_latest_720_limit(self):
        data = completed(1500) + [forming()]              # history exists; 720 completed cannot fit with forming
        start = END - 719 * DAY
        t = syn.ScriptedTransport(latest_only(data))
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, start, END, NOW, transport=t)
        self.assertEqual(cm.exception.kind, "history_unavailable")
        self.assertEqual(len(t.urls), 1, "refused on the first request; no further requests")

    def test_the_720_refusal_is_the_history_limit_not_pagination_or_validation(self):
        data = completed(1500) + [forming()]
        start_720 = END - 719 * DAY
        # Control 1: the same 720-candle window succeeds when the server has full history (inclusive paging).
        full = completed(3000) + [forming()]
        control = Kraken().fetch_candles(LISTING, DAY, start_720, END, NOW,
                                         transport=syn.ScriptedTransport(inclusive(full)))
        self.assertEqual((control.requests_made, len(control.candles)), (2, 720))
        # Control 2: the largest window that fits (719) succeeds on the same latest-720 server.
        self.assertEqual(len(Kraken().fetch_candles(LISTING, DAY, END - 718 * DAY, END, NOW,
                                                    transport=syn.ScriptedTransport(latest_only(data))).candles), 719)
        # The refusal names an earliest returned candle exactly one interval after the requested start.
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, start_720, END, NOW, transport=syn.ScriptedTransport(latest_only(data)))
        self.assertIn(f"the earliest candle returned is {END - 718 * DAY}", cm.exception.detail)
        self.assertIn(f"Requested start {start_720}", cm.exception.detail)
        self.assertEqual(END - 718 * DAY - start_720, DAY)

    def test_only_719_completed_entries_available_refuses_720_with_the_same_signature_as_a_late_listing(self):
        # Only 719 completed candles exist. A 720-candle request is refused. Under this response the cause is missing
        # entries; a listing that began late would look identical, so the test asserts the refusal and nothing more.
        data = completed(719) + [forming()]
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, END - 719 * DAY, END, NOW,
                                   transport=syn.ScriptedTransport(latest_only(data)))
        self.assertEqual(cm.exception.kind, "history_unavailable")
        # Control: the 719-candle window over the same entries passes.
        r = Kraken().fetch_candles(LISTING, DAY, END - 718 * DAY, END, NOW,
                                   transport=syn.ScriptedTransport(latest_only(data)))
        self.assertEqual(len(r.candles), 719)


class OverlapAccountingTests(unittest.TestCase):
    """Window of 1439 completed candles with data before the window: 3 pages, 2 overlap rows, 1 pre-window row."""

    N = 1439
    START = END - (N - 1) * DAY            # first requested candle
    FULL = completed(3000) + [forming()]   # history begins well before START

    def fetch(self, responder):
        t = syn.ScriptedTransport(responder)
        return Kraken().fetch_candles(LISTING, DAY, self.START, END, NOW, transport=t), t

    def test_final_series_has_exactly_the_requested_timestamps(self):
        r, _ = self.fetch(inclusive(self.FULL))
        self.assertEqual([c.open_time_s for c in r.candles], grid(self.START, self.N))
        self.assertNotIn(self.START - DAY, [c.open_time_s for c in r.candles])   # the pre-window overlap candle

    def test_request_counts_and_request_starts(self):
        r, t = self.fetch(inclusive(self.FULL))
        self.assertEqual(r.requests_made, 3)
        self.assertEqual([(int(syn.query_value(u, "since")) - self.START) // DAY for u in t.urls], [-1, 718, 1437])

    def test_overlap_and_pre_window_counts(self):
        r, _ = self.fetch(inclusive(self.FULL))
        self.assertEqual(r.out_of_window_dropped, 1, "exactly the candle one interval before the window")
        self.assertEqual(r.duplicates_removed, 2, "one identical row at each of the two page boundaries")
        self.assertEqual(r.forming_dropped, 1)
        self.assertEqual(len(r.candles), self.N)

    def test_pipeline_reports_the_same_accounting_and_passes(self):
        report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                        time_source="explicit-caller",
                                        transport=syn.ScriptedTransport(inclusive(self.FULL)), lookback=self.N)
        self.assertEqual(report["gate"]["status"], "PASSED", report["gate"]["reasons"])
        self.assertEqual(report["candles"]["completed_count"], self.N)
        self.assertEqual(report["candles"]["duplicates_removed"], 2)
        self.assertEqual(report["candles"]["out_of_window_dropped"], 1)
        self.assertEqual(report["requests_made"], 3)

    def test_conflicting_duplicate_across_pages_fails_closed(self):
        # Each overlap row is served by two pages. Change it in the later page only.
        for label, overlap_day, page_since_day in (("page 1-2 overlap", 718, 718), ("page 2-3 overlap", 1437, 1437)):
            with self.subTest(label):
                target = self.START + overlap_day * DAY
                base = inclusive(self.FULL)

                def altered(url, base=base, target=target, page_since=self.START + page_since_day * DAY):
                    body = base(url)
                    if int(syn.query_value(url, "since")) != page_since:
                        return body
                    import json
                    obj = json.loads(body)
                    rows = obj["result"]["XXBTZUSD"]
                    for row in rows:
                        if row[0] == target:
                            row[4] = str(float(row[4]) + 1.0)     # different close for the same open time
                    return json.dumps(obj).encode()

                with self.assertRaises(ProviderError) as cm:
                    self.fetch(altered)
                self.assertEqual(cm.exception.kind, "conflicting_duplicate")
                report = cp.run_candle_pipeline(Kraken(), LISTING, DAY, NOW, data_source="synthetic",
                                                time_source="explicit-caller",
                                                transport=syn.ScriptedTransport(altered), lookback=self.N)
                self.assertEqual(report["gate"]["status"], "REFUSED")
                self.assertEqual(report["error"]["kind"], "conflicting_duplicate")
                self.assertIsNone(report["candles"])


class HistoryMessageTests(unittest.TestCase):
    def test_refusal_leads_with_the_neutral_fact_and_lists_both_causes_without_claiming_either(self):
        data = completed(1500) + [forming()]
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, END - 719 * DAY, END, NOW,
                                   transport=syn.ScriptedTransport(latest_only(data)))
        detail = cm.exception.detail
        self.assertTrue(detail.startswith("Requested window start is not available from this response."), detail)
        self.assertIn("older than Kraken's retrievable history", detail)
        self.assertIn("listing began after the requested start", detail)
        self.assertIn("cannot distinguish these causes", detail)


if __name__ == "__main__":
    unittest.main()
