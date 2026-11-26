import json
import unittest
from urllib.parse import parse_qs, urlsplit

import fetcher
from tokocrypto_public_window import build_window, fetch_tokocrypto_candles


NOW_UTC = 1_700_000_000
INTERVAL_SECONDS = 3600
END_EXCLUSIVE = (NOW_UTC // INTERVAL_SECONDS) * INTERVAL_SECONDS
START_INCLUSIVE = END_EXCLUSIVE - 86400


def complete_1h_rows():
    return [
        [(START_INCLUSIVE + index * INTERVAL_SECONDS) * 1000,
         "100", "102", "99", "101", "12"]
        for index in range(24)
    ]


class FakeOpener:
    def __init__(self, rows=None):
        self.urls = []
        self.rows = rows if rows is not None else complete_1h_rows()

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
        self.assertEqual(result["expected_candles"], 24)
        self.assertEqual(result["received_candles"], 24)
        self.assertEqual(result["data_quality_status"], "COMPLETE_CONTIGUOUS_CLOSED_GRID")

    def test_no_request_is_made_for_invalid_window_inputs(self):
        opener = FakeOpener()
        bad = (
            {"pair": "BTC/USDT", "timeframe": "1h", "lookback_days": 1, "now_epoch_utc": 1_700_000_000},
            {"pair": "ETH_USDT", "timeframe": "1h", "lookback_days": 1, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1s", "lookback_days": 1, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": 15, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": True, "now_epoch_utc": 1_700_000_000},
            {"pair": "BTC_USDT", "timeframe": "1h", "lookback_days": 1, "now_epoch_utc": True},
        )
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_window(**args)
        self.assertEqual(opener.urls, [])

    def test_open_or_out_of_window_candle_is_rejected(self):
        opener = FakeOpener(rows=[
            [1699999200000, "100", "102", "99", "101", "12"]
        ])
        with self.assertRaisesRegex(fetcher.ApiError, "outside the requested closed UTC window"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=1_700_000_000, opener=opener,
                sleep=lambda _: None,
            )

    def test_duplicate_or_out_of_order_candle_timestamps_are_rejected(self):
        rows = complete_1h_rows()
        opener = FakeOpener(rows=rows + [rows[-1]])
        with self.assertRaisesRegex(fetcher.ApiError, "duplicate or out-of-order"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=1_700_000_000, opener=opener,
                sleep=lambda _: None,
            )

    def test_nonfinite_or_invalid_ohlcv_is_rejected(self):
        invalid_rows = (
            [1699995600000, "NaN", "102", "99", "101", "12"],
            [1699995600000, "100", "102", "99", "101", "-1"],
            [1699995600000, "100", "99", "98", "101", "12"],
            [1699995600000, "100", "102", "101", "101", "12"],
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                rows = complete_1h_rows()
                rows[-1] = row
                opener = FakeOpener(rows=rows)
                with self.assertRaises(fetcher.ApiError):
                    fetch_tokocrypto_candles(
                        pair="BTC_USDT", timeframe="1h", lookback_days=1,
                        now_epoch_utc=1_700_000_000, opener=opener,
                        sleep=lambda _: None,
                    )

    def test_missing_middle_candle_is_rejected(self):
        rows = complete_1h_rows()
        del rows[10]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "candle grid is incomplete: 1 missing interval"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=NOW_UTC, opener=opener, sleep=lambda _: None,
            )

    def test_missing_first_candle_is_rejected(self):
        rows = complete_1h_rows()[1:]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "candle grid is incomplete: 1 missing interval"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=NOW_UTC, opener=opener, sleep=lambda _: None,
            )

    def test_missing_trailing_candle_is_rejected(self):
        rows = complete_1h_rows()[:-1]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "1 trailing interval"):
            fetch_tokocrypto_candles(
                pair="BTC_USDT", timeframe="1h", lookback_days=1,
                now_epoch_utc=NOW_UTC, opener=opener, sleep=lambda _: None,
            )

    def test_parser_rejects_fractional_boolean_and_malformed_timestamps(self):
        bad_rows = (
            [1699995600.5, "100", "102", "99", "101", "12"],
            [True, "100", "102", "99", "101", "12"],
            ["16999956.00", "100", "102", "99", "101", "12"],
            ["-1699995600", "100", "102", "99", "101", "12"],
        )
        for row in bad_rows:
            with self.subTest(row=row), self.assertRaises(fetcher.ApiError):
                fetcher.parse_klines([row])

    def test_parser_rejects_boolean_price_and_volume_values(self):
        for index in range(1, 6):
            row = [1699995600000, "100", "102", "99", "101", "12"]
            row[index] = True
            with self.subTest(index=index), self.assertRaises(fetcher.ApiError):
                fetcher.parse_klines([row])

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
