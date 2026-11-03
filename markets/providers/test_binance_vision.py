"""Offline tests for the Binance public market-data adapter. Fixture transports only. No network."""
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
from markets.providers.binance_vision import BinanceVision  # noqa: E402

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
START = END - 118 * DAY
LISTING = parse_listing("crypto:binance-spot:BTC-USDT")


def completed_plus_forming():
    rows = syn.series(START, 119, DAY)
    rows.append(((NOW // DAY) * DAY, 1.0, 2.0, 0.5, 1.5, 1.0))     # still forming at NOW
    return rows


class RequestTests(unittest.TestCase):
    def test_url_uses_the_listing_symbol_interval_and_inclusive_window(self):
        url = BinanceVision().build_url("BTCUSDT", DAY, START, END)
        parsed = urllib.parse.urlparse(url)
        self.assertEqual(parsed.netloc, "data-api.binance.vision")
        self.assertEqual(parsed.path, "/api/v3/klines")
        q = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(q["symbol"], ["BTCUSDT"])
        self.assertEqual(q["interval"], ["1d"])
        self.assertEqual(q["startTime"], [str(START * 1000)])
        self.assertEqual(q["endTime"], [str((END + DAY) * 1000 - 1)])
        self.assertEqual(q["limit"], ["1000"])

    def test_symbol_mapping_is_explicit(self):
        self.assertEqual(BinanceVision().provider_symbol(LISTING), "BTCUSDT")
        with self.assertRaises(ProviderError) as cm:
            BinanceVision().provider_symbol(parse_listing("crypto:binance-spot:ETH-USDT"))
        self.assertEqual(cm.exception.kind, "unsupported_listing")

    def test_support_matrix(self):
        b = BinanceVision()
        self.assertTrue(b.supports(LISTING, DAY))
        self.assertFalse(b.supports(LISTING, 3600))
        self.assertFalse(b.supports(parse_listing("crypto:kraken-spot:BTC-USD"), DAY))


class FetchTests(unittest.TestCase):
    def fetch(self, rows, body=None):
        t = syn.ScriptedTransport(lambda url: body if body is not None else syn.binance_body(rows, DAY))
        r = BinanceVision().fetch_candles(LISTING, DAY, START, END, NOW, transport=t)
        return r, t

    def test_completed_candles_are_returned_and_the_forming_row_is_dropped(self):
        r, t = self.fetch(completed_plus_forming())
        self.assertEqual(len(r.candles), 119)
        self.assertEqual(r.forming_dropped, 1)
        self.assertEqual(r.requests_made, 1)
        self.assertEqual(r.candles[-1].open_time_s, END)
        self.assertEqual(len(t.urls), 1)

    def test_a_row_before_the_window_is_trimmed_and_counted(self):
        rows = [(START - DAY, 19990.0, 20000.0, 19980.0, 19995.0, 10.0)] + completed_plus_forming()
        r, _ = self.fetch(rows)
        self.assertEqual(r.out_of_window_dropped, 1)
        self.assertEqual(len(r.candles), 119)

    def test_an_exact_duplicate_row_is_removed_and_counted(self):
        rows = completed_plus_forming()
        rows.insert(10, rows[9])
        r, _ = self.fetch(rows)
        self.assertEqual(r.duplicates_removed, 1)
        self.assertEqual(len(r.candles), 119)

    def test_a_conflicting_duplicate_refuses(self):
        rows = completed_plus_forming()
        rows.insert(10, (rows[9][0], 1.0, 2.0, 0.5, 1.5, 1.0))
        with self.assertRaises(ProviderError) as cm:
            self.fetch(rows)
        self.assertEqual(cm.exception.kind, "conflicting_duplicate")

    def test_a_missing_interval_is_never_filled(self):
        rows = completed_plus_forming()
        del rows[40]
        r, _ = self.fetch(rows)
        self.assertEqual(len(r.candles), 118)
        self.assertNotIn(START + 40 * DAY, [c.open_time_s for c in r.candles])

    def test_close_time_mismatch_is_bad_payload(self):
        data = json.loads(syn.binance_body(completed_plus_forming(), DAY))
        data[5][6] = data[5][6] + 1
        with self.assertRaises(ProviderError) as cm:
            self.fetch(None, body=json.dumps(data).encode())
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_open_time_in_milliseconds_not_whole_seconds_is_bad_payload(self):
        data = json.loads(syn.binance_body(completed_plus_forming(), DAY))
        data[3][0] = data[3][0] + 1
        with self.assertRaises(ProviderError) as cm:
            self.fetch(None, body=json.dumps(data).encode())
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_non_json_and_error_objects_are_bad_payload(self):
        for body in (b"<html>nope</html>", b'{"code": -1121, "msg": "Invalid symbol."}'):
            with self.subTest(body=body[:20]):
                with self.assertRaises(ProviderError) as cm:
                    self.fetch(None, body=body)
                self.assertEqual(cm.exception.kind, "bad_payload")

    def test_empty_list_is_structured_empty(self):
        with self.assertRaises(ProviderError) as cm:
            self.fetch(None, body=b"[]")
        self.assertEqual(cm.exception.kind, "empty")

    def test_provenance_fields_are_present(self):
        r, _ = self.fetch(completed_plus_forming())
        self.assertEqual(r.provider.name, "binance-vision")
        self.assertEqual(r.provider.venue, "binance")
        self.assertIn("unverified", r.provider.terms_source)


if __name__ == "__main__":
    unittest.main()
