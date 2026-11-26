import json
import unittest
from urllib.parse import parse_qs, urlsplit

import fetcher
from tokocrypto_public_window import (\n    build_window, fetch_tokocrypto_candles, validate_complete_candle_grid,\n)


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

    def test_current_window_fetch_is_blocked_before_network(self):
        opener = FakeOpener()
        with self.assertRaisesRegex(fetcher.ApiError, "current-window collection is blocked"):
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
            )
        self.assertEqual(opener.urls, [])

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
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
            )

    def test_duplicate_or_out_of_order_candle_timestamps_are_rejected(self):
        rows = complete_1h_rows()
        opener = FakeOpener(rows=rows + [rows[-1]])
        with self.assertRaisesRegex(fetcher.ApiError, "duplicate or out-of-order"):
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
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
                    validate_complete_candle_grid(
                        fetcher.parse_klines(opener.rows),
                        start_epoch_utc=START_INCLUSIVE,
                        end_epoch_utc_exclusive=END_EXCLUSIVE,
                        timeframe="1h",
                    )

    def test_missing_middle_candle_is_rejected(self):
        rows = complete_1h_rows()
        del rows[10]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "candle grid is incomplete: 1 missing interval"):
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
            )

    def test_missing_first_candle_is_rejected(self):
        rows = complete_1h_rows()[1:]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "candle grid is incomplete: 1 missing interval"):
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
            )

    def test_missing_trailing_candle_is_rejected(self):
        rows = complete_1h_rows()[:-1]
        opener = FakeOpener(rows=rows)
        with self.assertRaisesRegex(fetcher.ApiError, "1 trailing interval"):
            validate_complete_candle_grid(
                fetcher.parse_klines(opener.rows),
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
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
            validate_complete_candle_grid(
                [],
                start_epoch_utc=START_INCLUSIVE,
                end_epoch_utc_exclusive=END_EXCLUSIVE,
                timeframe="1h",
            )

    def test_complete_grid_rejects_unaligned_or_reversed_windows(self):
        rows = fetcher.parse_klines(complete_1h_rows())
        for start, end in ((START_INCLUSIVE + 1, END_EXCLUSIVE),
                           (START_INCLUSIVE, END_EXCLUSIVE - 1),
                           (END_EXCLUSIVE, START_INCLUSIVE)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                validate_complete_candle_grid(
                    rows, start_epoch_utc=start,
                    end_epoch_utc_exclusive=end, timeframe="1h",
                )



if __name__ == "__main__":
    unittest.main()
