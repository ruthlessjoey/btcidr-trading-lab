import json
import unittest
from urllib.parse import parse_qs, urlsplit

import fetcher
from tokocrypto_fixed_window import (
    fetch_tokocrypto_fixed_window,
    validate_fixed_window,
)


START = 1_700_000_000 - (1_700_000_000 % 3600) - 24 * 3600
END = START + 24 * 3600


def complete_rows():
    return [
        [(START + i * 3600) * 1000, "100", "102", "99", "101", "12"]
        for i in range(24)
    ]


class FakeOpener:
    def __init__(self, rows=None):
        self.rows = complete_rows() if rows is None else rows
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        return 200, json.dumps(self.rows).encode("utf-8")


class FixedWindowTests(unittest.TestCase):
    def test_fixed_window_does_not_require_a_now_argument(self):
        window = validate_fixed_window(
            pair="BTC_USDT", timeframe="1h",
            start_epoch_utc=START, end_epoch_utc_exclusive=END,
        )
        self.assertEqual(window["window_mode"], "fixed_utc_preregistered")
        self.assertEqual(window["clock_source"], "fixed_utc_boundaries")
        self.assertEqual(window["provider_clock_skew"], "NOT_VERIFIED")
        self.assertEqual(window["temporal_past_assertion"], "NOT_PERFORMED")

    def test_valid_fixed_window_fetch_uses_only_approved_endpoint(self):
        opener = FakeOpener()
        result = fetch_tokocrypto_fixed_window(
            pair="BTC_USDT", timeframe="1h",
            start_epoch_utc=START, end_epoch_utc_exclusive=END,
            opener=opener, sleep=lambda _: None,
        )
        self.assertEqual(len(result["candles"]), 24)
        self.assertEqual(result["expected_candles"], 24)
        self.assertEqual(result["received_candles"], 24)
        self.assertEqual(result["data_quality_status"], "COMPLETE_CONTIGUOUS_CLOSED_GRID")
        self.assertEqual(len(opener.calls), 1)
        parsed = urlsplit(opener.calls[0][0])
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.tokocrypto.site")
        self.assertEqual(parsed.path, "/api/v3/klines")
        params = parse_qs(parsed.query)
        self.assertEqual(set(params), {"symbol", "interval", "startTime", "endTime", "limit"})
        self.assertEqual(params["symbol"], ["BTCUSDT"])
        self.assertEqual(int(params["startTime"][0]), START * 1000)
        self.assertEqual(int(params["endTime"][0]), (END - 1) * 1000)

    def test_invalid_boundaries_are_rejected_before_request(self):
        invalid = (
            (START + 1, END),
            (START, END - 1),
            (END, START),
            (START, START),
            (START, END + 15 * 86400),
            (True, END),
            (START, False),
        )
        opener = FakeOpener()
        for start, end in invalid:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                fetch_tokocrypto_fixed_window(
                    pair="BTC_USDT", timeframe="1h",
                    start_epoch_utc=start, end_epoch_utc_exclusive=end,
                    opener=opener, sleep=lambda _: None,
                )
        self.assertEqual(opener.calls, [])

    def test_wrong_pair_or_timeframe_is_rejected_before_request(self):
        opener = FakeOpener()
        with self.assertRaises(ValueError):
            fetch_tokocrypto_fixed_window(
                pair="BTC/USDT", timeframe="1h",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                opener=opener, sleep=lambda _: None,
            )
        with self.assertRaises(ValueError):
            fetch_tokocrypto_fixed_window(
                pair="BTC_USDT", timeframe="7m",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                opener=opener, sleep=lambda _: None,
            )
        self.assertEqual(opener.calls, [])

    def test_incomplete_middle_or_trailing_grid_fails_closed(self):
        cases = [
            ("middle", complete_rows()[:10] + complete_rows()[11:]),
            ("trailing", complete_rows()[:-1]),
            ("first", complete_rows()[1:]),
        ]
        for label, rows in cases:
            with self.subTest(label=label):
                opener = FakeOpener(rows)
                with self.assertRaises(fetcher.ApiError):
                    fetch_tokocrypto_fixed_window(
                        pair="BTC_USDT", timeframe="1h",
                        start_epoch_utc=START, end_epoch_utc_exclusive=END,
                        opener=opener, sleep=lambda _: None,
                    )

    def test_duplicate_or_out_of_order_rows_fail_closed(self):
        rows = complete_rows()
        rows[10] = rows[9]
        opener = FakeOpener(rows)
        with self.assertRaises(fetcher.ApiError):
            fetch_tokocrypto_fixed_window(
                pair="BTC_USDT", timeframe="1h",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                opener=opener, sleep=lambda _: None,
            )

    def test_invalid_ohlcv_fails_closed(self):
        rows = complete_rows()
        rows[3] = [START * 1000 + 3 * 3600 * 1000, "NaN", "102", "99", "101", "12"]
        opener = FakeOpener(rows)
        with self.assertRaises(fetcher.ApiError):
            fetch_tokocrypto_fixed_window(
                pair="BTC_USDT", timeframe="1h",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                opener=opener, sleep=lambda _: None,
            )

    def test_invalid_timeout_or_retries_rejected_before_request(self):
        opener = FakeOpener()
        with self.assertRaises(ValueError):
            fetch_tokocrypto_fixed_window(
                pair="BTC_USDT", timeframe="1h",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                timeout=0, opener=opener,
            )
        with self.assertRaises(ValueError):
            fetch_tokocrypto_fixed_window(
                pair="BTC_USDT", timeframe="1h",
                start_epoch_utc=START, end_epoch_utc_exclusive=END,
                retries=6, opener=opener,
            )
        self.assertEqual(opener.calls, [])


if __name__ == "__main__":
    unittest.main()
