"""Offline tests for the Kraken public OHLC adapter. Fixture transports only. No network.

The adapter asserts Kraken's documented 720-candle limit and its row layout. The layout is confirmed against the
live API only in a later, separately approved milestone.
"""
import json
import os
import sys
import unittest
import urllib.parse

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markets.identity import parse_listing  # noqa: E402
from markets.providers import ProviderError  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers.kraken import Kraken  # noqa: E402

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
START = END - 118 * DAY
LISTING = parse_listing("crypto:kraken-spot:BTC-USD")


def completed_plus_forming(start=START, count=119):
    rows = syn.series(start, count, DAY)
    rows.append(((NOW // DAY) * DAY, 1.0, 2.0, 0.5, 1.5, 1.0))     # still forming at NOW
    return rows


def paged_responder(all_rows, limit=720):
    """Kraken-style paging: returns up to `limit` rows whose open time is at or after `since`."""
    def respond(url):
        since = int(syn.query_value(url, "since"))
        chosen = [r for r in all_rows if r[0] >= since][:limit]
        return syn.kraken_body(chosen)
    return respond


class RequestTests(unittest.TestCase):
    def test_url_uses_the_pair_minutes_interval_and_since(self):
        url = Kraken().build_url("XBTUSD", DAY, START, END)
        parsed = urllib.parse.urlparse(url)
        self.assertEqual(parsed.netloc, "api.kraken.com")
        self.assertEqual(parsed.path, "/0/public/OHLC")
        q = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(q["pair"], ["XBTUSD"])
        self.assertEqual(q["interval"], ["1440"])
        self.assertEqual(q["since"], [str(START)])

    def test_bitcoin_is_mapped_to_xbt_by_table_not_by_string_rule(self):
        self.assertEqual(Kraken().provider_symbol(LISTING), "XBTUSD")
        with self.assertRaises(ProviderError):
            Kraken().provider_symbol(parse_listing("crypto:kraken-spot:ETH-USD"))

    def test_support_matrix(self):
        k = Kraken()
        self.assertTrue(k.supports(LISTING, DAY))
        self.assertFalse(k.supports(LISTING, 3600))
        self.assertFalse(k.supports(parse_listing("crypto:binance-spot:BTC-USDT"), DAY))


class FetchTests(unittest.TestCase):
    def test_single_request_returns_completed_candles_and_drops_the_forming_one(self):
        rows = completed_plus_forming()
        t = syn.ScriptedTransport(lambda url: syn.kraken_body(rows))
        r = Kraken().fetch_candles(LISTING, DAY, START, END, NOW, transport=t)
        self.assertEqual(len(r.candles), 119)
        self.assertEqual(r.forming_dropped, 1)
        self.assertEqual(r.requests_made, 1)
        self.assertEqual(r.candles[-1].open_time_s, END)

    def test_720_candle_limit_is_respected_across_three_requests(self):
        lookback = 1500
        first = END - (lookback - 1) * DAY
        all_rows = completed_plus_forming(first, lookback)
        t = syn.ScriptedTransport(paged_responder(all_rows))
        r = Kraken().fetch_candles(LISTING, DAY, first, END, NOW, transport=t)
        self.assertEqual(r.requests_made, 3)
        self.assertEqual(len(r.candles), lookback)
        self.assertEqual(r.forming_dropped, 1)
        # Overlap rows served by two pages are identical and removed: page 1 and page 2 share 2 rows (days 718-719),
        # page 2 and page 3 share 1 row (day 1437). Each request reaches one interval back, so the count is 3.
        self.assertEqual(r.duplicates_removed, 3)
        self.assertEqual(len({c.open_time_s for c in r.candles}), lookback)      # no duplicates across pages
        self.assertEqual([c.open_time_s for c in r.candles], sorted(c.open_time_s for c in r.candles))

    def test_each_request_asks_for_a_window_of_at_most_720_candles(self):
        lookback = 1500
        first = END - (lookback - 1) * DAY
        t = syn.ScriptedTransport(paged_responder(completed_plus_forming(first, lookback)))
        Kraken().fetch_candles(LISTING, DAY, first, END, NOW, transport=t)
        sinces = [int(syn.query_value(u, "since")) for u in t.urls]
        # 719 slots per page plus one overlapping candle: each request reaches one interval before its window.
        self.assertEqual(sinces, [first - DAY, first + 718 * DAY, first + 1437 * DAY])

    def test_a_response_larger_than_720_candles_is_bad_payload(self):
        big = syn.kraken_body(syn.series(START, 721, DAY))
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, START, START + 720 * DAY, NOW,
                                   transport=lambda url: big)
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_rows_after_the_requested_end_are_trimmed_and_counted(self):
        early_end = END - 10 * DAY
        rows = completed_plus_forming()
        t = syn.ScriptedTransport(lambda url: syn.kraken_body(rows))
        r = Kraken().fetch_candles(LISTING, DAY, START, early_end, NOW, transport=t)
        self.assertEqual(r.out_of_window_dropped, 10)
        self.assertEqual(r.candles[-1].open_time_s, early_end)

    def test_exact_duplicate_is_removed_and_conflicting_duplicate_refuses(self):
        rows = completed_plus_forming()
        same = Kraken().fetch_candles(LISTING, DAY, START, END, NOW,
                                      transport=syn.ScriptedTransport(
                                          lambda url: syn.kraken_body(rows + [rows[5]])))
        self.assertEqual(same.duplicates_removed, 1)
        conflicting = rows + [(rows[5][0], 1.0, 2.0, 0.5, 1.5, 1.0)]
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, START, END, NOW,
                                   transport=syn.ScriptedTransport(lambda url: syn.kraken_body(conflicting)))
        self.assertEqual(cm.exception.kind, "conflicting_duplicate")

    def test_two_forming_candles_are_bad_payload(self):
        rows = completed_plus_forming()
        rows.append(((NOW // DAY) * DAY + DAY, 1.0, 2.0, 0.5, 1.5, 1.0))
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, START, END, NOW,
                                   transport=lambda url: syn.kraken_body(rows))
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_a_missing_interval_is_never_filled(self):
        rows = completed_plus_forming()
        del rows[40]
        r = Kraken().fetch_candles(LISTING, DAY, START, END, NOW, transport=lambda url: syn.kraken_body(rows))
        self.assertEqual(len(r.candles), 118)
        self.assertNotIn(START + 40 * DAY, [c.open_time_s for c in r.candles])

    def test_empty_result_is_structured_empty(self):
        body = json.dumps({"error": [], "result": {"XXBTZUSD": [], "last": 0}}).encode()
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(LISTING, DAY, START, END, NOW, transport=lambda url: body)
        self.assertEqual(cm.exception.kind, "empty")


class ErrorBodyTests(unittest.TestCase):
    def call(self, body):
        return Kraken().fetch_candles(LISTING, DAY, START, END, NOW, transport=lambda url: body)

    def test_rate_limit_error_body_is_rate_limited(self):
        with self.assertRaises(ProviderError) as cm:
            self.call(syn.kraken_error_body(["EAPI:Rate limit exceeded"]))
        self.assertEqual(cm.exception.kind, "rate_limited")
        self.assertTrue(cm.exception.retriable)

    def test_other_error_body_is_unavailable(self):
        with self.assertRaises(ProviderError) as cm:
            self.call(syn.kraken_error_body(["EService:Unavailable"]))
        self.assertEqual(cm.exception.kind, "unavailable")

    def test_two_candle_lists_are_bad_payload(self):
        body = json.dumps({"error": [], "result": {"A": [[START, "1", "2", "0.5", "1.5", "1.5", "1", 1]],
                                                   "B": [], "last": 0}}).encode()
        with self.assertRaises(ProviderError) as cm:
            self.call(body)
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_missing_error_list_or_non_json_is_bad_payload(self):
        for body in (b'{"result": {}}', b"not json", b"[]"):
            with self.subTest(body=body[:15]):
                with self.assertRaises(ProviderError) as cm:
                    self.call(body)
                self.assertEqual(cm.exception.kind, "bad_payload")

    def test_non_integer_time_is_bad_payload(self):
        body = json.dumps({"error": [], "result": {"X": [["1609459200", "1", "2", "0.5", "1.5", "1.5", "1", 1]],
                                                   "last": 0}}).encode()
        with self.assertRaises(ProviderError) as cm:
            self.call(body)
        self.assertEqual(cm.exception.kind, "bad_payload")


if __name__ == "__main__":
    unittest.main()
