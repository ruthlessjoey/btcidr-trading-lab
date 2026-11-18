"""Offline tests for the approved public transport boundary; no sockets are used."""
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetcher  # noqa: E402

NO_SLEEP = lambda seconds: None  # noqa: E731
TIME_URL = "https://www.tokocrypto.site/api/v3/time"
CANDLE_URL = ("https://www.tokocrypto.site/api/v3/klines?"
              "symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")


def scripted(*answers):
    calls = []
    def opener(url, timeout):
        calls.append((url, timeout))
        answer = answers[min(len(calls) - 1, len(answers) - 1)]
        if isinstance(answer, Exception):
            raise answer
        return answer
    opener.calls = calls
    return opener


def row(t_ms=1_700_000_000_000):
    return [t_ms, "10", "12", "9", "11", "5", t_ms + 3_599_999]


class UrlPolicyTests(unittest.TestCase):
    def test_only_exact_approved_time_route_is_allowed(self):
        self.assertEqual(fetcher.validate_public_url(TIME_URL), TIME_URL)

    def test_only_btcusdt_candle_route_is_allowed(self):
        self.assertEqual(fetcher.validate_public_url(CANDLE_URL), CANDLE_URL)

    def test_rejects_unapproved_schemes_hosts_paths_ports_and_userinfo(self):
        bad = [
            "http://www.tokocrypto.site/api/v3/time",
            "https://www.tokocrypto.com/api/v3/time",
            "https://data-api.binance.vision/api/v3/time",
            "https://api.kraken.com/api/v3/time",
            "https://www.tokocrypto.site:444/api/v3/time",
            "https://user:pass@www.tokocrypto.site/api/v3/time",
            "https://www.tokocrypto.site/api/v3/exchangeInfo?symbol=BTCUSDT",
            "https://www.tokocrypto.site/open/v1/common/time",
            "https://www.tokocrypto.site/api/v3/time#fragment",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(fetcher.DisallowedRequestError):
                fetcher.validate_public_url(url)

    def test_rejects_wrong_market_interval_unknown_and_duplicate_query_keys(self):
        bad = [
            "https://www.tokocrypto.site/api/v3/klines?symbol=ETHUSDT&interval=1h",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=2h",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&foo=bar",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&symbol=ETHUSDT&interval=1h",
            "https://www.tokocrypto.site/api/v3/time?x=1",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=9&endTime=8&limit=500",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1&endTime=2&limit=501",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=%D9%A1&endTime=2&limit=1",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1&endTime=2&limit=1&",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=0&endTime=2&limit=1",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1&endTime=10000000000001&limit=1",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=" + "9" * 5000 + "&endTime=2&limit=1",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1&endTime=2&limit=1" + "&x=1" * 50,
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(fetcher.DisallowedRequestError):
                fetcher.validate_public_url(url)

    def test_invalid_url_is_rejected_before_fake_network_call(self):
        op = scripted((200, b'{"ok":true}'))
        with self.assertRaises(fetcher.DisallowedRequestError):
            fetcher.http_get_json("https://www.tokocrypto.com/api/v3/time", 5, 1, op, NO_SLEEP)
        self.assertEqual(op.calls, [])

    def test_open_v1_style_is_rejected(self):
        with self.assertRaises(fetcher.DisallowedRequestError):
            fetcher.Source("tokocrypto", "open_v1", "https://www.tokocrypto.site")

    def test_symbol_metadata_route_is_unconditionally_rejected(self):
        src = fetcher.Source("tokocrypto", "binance_style", "https://www.tokocrypto.site")
        with self.assertRaises(fetcher.DisallowedRequestError):
            src.symbols_url("BTC_USDT")


class HttpTests(unittest.TestCase):
    def test_success_returns_json_for_approved_url(self):
        op = scripted((200, b'{"ok": 1}'))
        self.assertEqual(fetcher.http_get_json(TIME_URL, 5, 1, op, NO_SLEEP), {"ok": 1})
        self.assertEqual(len(op.calls), 1)

    def test_429_is_not_retried_without_retry_after_support(self):
        op = scripted((429, b""), (200, b'[1]'))
        with self.assertRaisesRegex(fetcher.ApiError, "HTTP 429 rate limit; automatic retry disabled"):
            fetcher.http_get_json(TIME_URL, 5, 2, op, NO_SLEEP)
        self.assertEqual(len(op.calls), 1)

    def test_retries_5xx_then_succeeds(self):
        op = scripted((503, b""), (200, b'[1]'))
        self.assertEqual(fetcher.http_get_json(TIME_URL, 5, 2, op, NO_SLEEP), [1])
        self.assertEqual(len(op.calls), 2)

    def test_403_is_not_retried(self):
        op = scripted((403, b"forbidden"))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 3, op, NO_SLEEP)
        self.assertEqual(len(op.calls), 1)

    def test_redirect_http_error_is_not_followed_or_retried(self):
        op = scripted(urllib.error.HTTPError(TIME_URL, 302, "Found", {}, io.BytesIO(b"redirect")))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 3, op, NO_SLEEP)
        self.assertEqual(len(op.calls), 1)

    def test_http_error_body_is_closed(self):
        body = io.BytesIO(b"missing")
        err = urllib.error.HTTPError(TIME_URL, 404, "Not Found", {}, body)
        op = scripted(err)
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 1, op, NO_SLEEP)
        self.assertTrue(body.closed)

    def test_oversized_success_body_is_rejected(self):
        op = scripted((200, b"x" * (fetcher.MAX_RESPONSE_BYTES + 1)))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 1, op, NO_SLEEP)

    def test_oversized_http_error_body_is_rejected_and_closed(self):
        body = io.BytesIO(b"x" * (fetcher.MAX_RESPONSE_BYTES + 1))
        err = urllib.error.HTTPError(TIME_URL, 404, "Not Found", {}, body)
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 1, scripted(err), NO_SLEEP)
        self.assertTrue(body.closed)

    def test_invalid_json_is_an_error(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 1, scripted((200, b"<html>")), NO_SLEEP)

    def test_network_errors_exhaust_retries(self):
        op = scripted(urllib.error.URLError("offline"))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(TIME_URL, 5, 3, op, NO_SLEEP)
        self.assertEqual(len(op.calls), 3)


class ParseRegressionTests(unittest.TestCase):
    def test_parses_candle_rows_and_converts_milliseconds(self):
        c = fetcher.parse_klines([row()])[0]
        self.assertEqual((c.time, c.open, c.high, c.low, c.close, c.volume),
                         (1_700_000_000, 10.0, 12.0, 9.0, 11.0, 5.0))

    def test_rejects_non_list_and_short_rows(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines({"bad": True})
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines([[1, "2"]])

    def test_rejects_non_numeric_prices(self):
        bad = row()
        bad[1] = "not-a-price"
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines([bad])

    def test_server_time_shapes_remain_supported(self):
        self.assertEqual(fetcher.extract_server_time({"serverTime": 1_700_000_000_000}),
                         1_700_000_000)


if __name__ == "__main__":
    unittest.main()
