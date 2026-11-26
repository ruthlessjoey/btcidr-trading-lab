import json
import unittest
from urllib.parse import parse_qs, urlsplit

import fetcher
from tokocrypto_public_window import build_window, fetch_tokocrypto_candles


class FakeOpener:
    def __init__(self, rows=None):
        self.urls = []
        self.rows = rows if rows is not None else [
            [1699999200000, "100", "102", "99", "101", "12"]
        ]

    def __call__(self, url, timeout):
        self.urls.append(url)
        return 200, json.dumps(self.rows).encode("utf-8")


class TokocryptoCallerClockWindowTests(unittest.TestCase):
    def test_window_ends_before_current_open_candle(self):
        now = 1_700_000_000
        window = build_window(
            pair="BTC_USDT", timeframe="1h", lookback_days=2,
            now_epoch_utc=now,
        )
        self.assertEqual(window["end_exclusive_timestamp"] % 3600, 0)
        self.assertEqual(
            window["end_timestamp_inclusive"] + 1,
            window["end_exclusive_timestamp"],
        )
        self.assertEqual(
            window["end_exclusive_timestamp"] - window["start_timestamp"],
            2 * 86400,
        )
        self.assertEqual(window["provider_clock_skew"], "NOT_VERIFIED")

    def test_fetch_uses_only_exact_approved_klines_endpoint(self):
        opener = FakeOpener()
        result = fetch_tokocrypto_candles(
            pair="BTC_USDT", timeframe="1h", lookback_days=1,
            now_epoch_utc=1_700_000_000, opener=opener,
            sleep=lambda _: None,
        )
        self.assertEqual(len(opener.urls), result["requests_made"])
        self.assertTrue(opener.urls)
        for url in opener.urls:
            parsed = urlsplit(url)
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "www.tokocrypto.site")
            self.assertEqual(parsed.path, "/api/v3/klines")
            params = parse_qs(parsed.query)
            self.assertEqual(
                set(params),
                {"symbol", "interval", "startTime", "endTime", "limit"},
            )
            self.assertEqual(params["symbol"], ["BTCUSDT"])
            self.assertEqual(params["interval"], ["1h"])
            self.assertLessEqual(
                int(params["endTime"][0]) - int(params["startTime"][0]),
                500 * 3600 * 1000,
            )
        self.assertEqual(result["clock_source"], "caller_supplied_utc_epoch")
        self.assertEqual(result["endpoint"], fetcher.TOKOCRYPTO_KLINES_PATH)

    def test_no_request_is_made_for_invalid_window_inputs(self):
        opener = FakeOpener()
        bad = (
            {"pair": "BTC/USDT", "timeframe": "1h", "lookback_days": 1, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1s", "lookback_days": 1, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": 15, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": True, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": 1, "now_epoch_utc": True},
        )
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_window(**args)
        self.assertEqual(opener.urls, [])

    def test_empty_provider_response_fails_closed(self):
        opener = FakeOpener(rows=[])
        with self.assertRaisesRegex(fetcher.ApiError, "zero candles"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=1_700_000_000, opener=opener,
                sleep=lambda _: None,
            )

    def test_retries_and_timeout_are_bounded_before_network(self):
        opener = FakeOpener()
        with self.assertRaises(ValueError):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=1_700_000_000, timeout=0, opener=opener,
            )
        with self.assertRaises(ValueError):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=1_700_000_000, retries=6, opener=opener,
            )
        self.assertEqual(opener.urls, [])


if __name__ == "__main__":
    unittest.main()
