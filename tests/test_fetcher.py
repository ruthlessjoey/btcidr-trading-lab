"""Tests for fetcher.py. All data here is SYNTHETIC test data, not market prices."""
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetcher  # noqa: E402

NO_SLEEP = lambda seconds: None  # noqa: E731
MS = 1_700_000_000_000


def scripted(*answers):
    """Fake network: each call returns the next answer (status, body) or raises it."""
    calls = []

    def opener(url, timeout):
        calls.append(url)
        a = answers[min(len(calls) - 1, len(answers) - 1)]
        if isinstance(a, Exception):
            raise a
        return a
    opener.calls = calls
    return opener


def row(t_ms=MS, o="10", h="12", low="9", c="11", v="5"):
    return [t_ms, o, h, low, c, v, t_ms + 3_599_999, "55", 7, "2", "1", "0"]


class SourceTests(unittest.TestCase):
    def test_urls_and_symbols(self):
        a = fetcher.Source("a", "binance_style", "https://x.test")
        b = fetcher.Source("b", "open_v1", "https://y.test")
        self.assertEqual(a.klines_url(), "https://x.test/api/v3/klines")
        self.assertEqual(a.time_url(), "https://x.test/api/v3/time")
        self.assertEqual(a.symbol("BTC_USDT"), "BTCUSDT")
        self.assertEqual(b.klines_url(), "https://y.test/open/v1/market/klines")
        self.assertEqual(b.time_url(), "https://y.test/open/v1/common/time")
        self.assertEqual(b.symbol("BTC_USDT"), "BTC_USDT")

    def test_unknown_style_is_rejected(self):
        with self.assertRaises(ValueError):
            fetcher.Source("z", "mystery", "https://z.test")


class ParseTests(unittest.TestCase):
    def test_parses_candle_rows_and_converts_ms(self):
        c = fetcher.parse_klines([row()])[0]
        self.assertEqual((c.time, c.open, c.high, c.low, c.close, c.volume),
                         (1_700_000_000, 10.0, 12.0, 9.0, 11.0, 5.0))

    def test_open_v1_wrapper_is_unwrapped(self):
        wrapped = {"code": 0, "msg": "success", "data": [row()]}
        self.assertEqual(len(fetcher.parse_klines(wrapped)), 1)

    def test_nested_data_list_is_unwrapped(self):
        self.assertEqual(len(fetcher.parse_klines({"code": 0, "data": {"list": [row()]}})), 1)

    def test_exchange_error_code_is_an_error(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.parse_klines({"code": -1121, "msg": "Invalid symbol."})
        self.assertIn("Invalid symbol", str(ctx.exception))

    def test_not_a_list_is_an_error(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines({"something": "else"})

    def test_short_row_is_an_error(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines([[MS, "1", "2"]])

    def test_non_numeric_is_an_error(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines([row(o="abc")])

    def test_row_must_be_a_list(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.parse_klines([{"Time": 1}])

    def test_server_time_shapes(self):
        self.assertEqual(fetcher.extract_server_time({"serverTime": MS}), 1_700_000_000)
        self.assertEqual(fetcher.extract_server_time({"code": 0, "data": MS}), 1_700_000_000)
        self.assertEqual(fetcher.extract_server_time({"data": {"serverTime": MS}}), 1_700_000_000)
        self.assertEqual(fetcher.extract_server_time(MS), 1_700_000_000)

    def test_bad_server_time_is_an_error(self):
        with self.assertRaises(fetcher.ApiError):
            fetcher.extract_server_time({"nothing": 1})
        with self.assertRaises(fetcher.ApiError):
            fetcher.extract_server_time({"serverTime": "soon"})


class HttpTests(unittest.TestCase):
    def test_success_returns_json(self):
        op = scripted((200, b'{"ok": 1}'))
        self.assertEqual(fetcher.http_get_json("u", 5, 3, op, NO_SLEEP), {"ok": 1})

    def test_retries_server_error_then_succeeds(self):
        op = scripted((500, b""), (200, b'[1]'))
        self.assertEqual(fetcher.http_get_json("u", 5, 3, op, NO_SLEEP), [1])
        self.assertEqual(len(op.calls), 2)

    def test_429_is_retried(self):
        op = scripted((429, b""), (200, b'[1]'))
        self.assertEqual(fetcher.http_get_json("u", 5, 3, op, NO_SLEEP), [1])

    def test_403_is_not_retried_and_shows_the_body(self):
        op = scripted((403, b"<html>Access denied by firewall</html>"))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json("u", 5, 3, op, NO_SLEEP)
        self.assertIn("403", str(ctx.exception))
        self.assertIn("Access denied", str(ctx.exception))
        self.assertEqual(len(op.calls), 1)

    def test_451_region_block_is_not_retried(self):
        op = scripted((451, b"unavailable for legal reasons"))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json("u", 5, 3, op, NO_SLEEP)
        self.assertIn("451", str(ctx.exception))
        self.assertEqual(len(op.calls), 1)

    def test_http_error_exception_is_handled(self):
        op = scripted(urllib.error.HTTPError("u", 404, "Not Found", {}, None))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json("u", 5, 3, op, NO_SLEEP)
        self.assertEqual(len(op.calls), 1)

    def test_network_errors_exhaust_retries(self):
        op = scripted(urllib.error.URLError("boom"))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json("u", 5, 3, op, NO_SLEEP)
        self.assertIn("failed after 3 attempts", str(ctx.exception))
        self.assertEqual(len(op.calls), 3)

    def test_timeout_is_handled(self):
        op = scripted(TimeoutError("slow"))
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json("u", 5, 2, op, NO_SLEEP)

    def test_invalid_json_is_an_error(self):
        op = scripted((200, b"<html>challenge page</html>"))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json("u", 5, 3, op, NO_SLEEP)
        self.assertIn("challenge page", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
