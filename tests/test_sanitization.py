"""Safe regression tests for provider-controlled errors and report sinks.

This module imports only fetcher and providers. It does not import research,
live_check, validator, report, dataset, or any protected module.
"""
import io
import os
import unittest
import urllib.error

import fetcher
import providers

MARKER = "UNTRUSTED_PROVIDER_MARKER_7f3a9c"
CANDLE_URL = ("https://www.tokocrypto.site/api/v3/klines?"
              "symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")
NO_SLEEP = lambda seconds: None


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


class UntrustedInt(int):
    def __str__(self):
        return MARKER


class TrackedHTTPError(urllib.error.HTTPError):
    def __init__(self, code=404):
        super().__init__(CANDLE_URL, code, "Not Found", {}, io.BytesIO(MARKER.encode()))
        self.closed_by_test = False
        self.read_called = False

    def read(self, *args, **kwargs):
        self.read_called = True
        raise AssertionError("HTTP error body must never be read")

    def close(self):
        self.closed_by_test = True
        super().close()


class FetcherSanitizationTests(unittest.TestCase):
    def test_transport_errors_never_echo_provider_text_or_url(self):
        cases = (
            (scripted((451, MARKER.encode())), 1),
            (scripted((500, MARKER.encode()), (500, MARKER.encode())), 2),
            (scripted(urllib.error.URLError(MARKER)), 2),
            (scripted(RuntimeError(MARKER)), 1),
        )
        for opener, retries in cases:
            with self.subTest(retries=retries), self.assertRaises(fetcher.ApiError) as ctx:
                fetcher.http_get_json(CANDLE_URL, 5, retries, opener, NO_SLEEP)
            self.assertNotIn(MARKER, str(ctx.exception))
            self.assertNotIn(CANDLE_URL, str(ctx.exception))

    def test_http_error_is_closed_without_reading_provider_body(self):
        error = TrackedHTTPError(404)
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted(error), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "HTTP 404 (not retried)")
        self.assertTrue(error.closed_by_test)
        self.assertFalse(error.read_called)
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_invalid_http_status_types_and_ranges_are_rejected(self):
        for status in (True, 99, 600, 200.0, UntrustedInt(451)):
            with self.subTest(status_type=type(status).__name__), self.assertRaises(fetcher.ApiError) as ctx:
                fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((status, b"{}")), NO_SLEEP)
            self.assertEqual(str(ctx.exception), "transport returned an invalid HTTP status")
            self.assertNotIn(MARKER, str(ctx.exception))

    def test_missing_status_and_non_bytes_body_are_rejected(self):
        with self.assertRaisesRegex(fetcher.ApiError, "no HTTP status"):
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((None, b"{}")), NO_SLEEP)
        with self.assertRaisesRegex(fetcher.ApiError, "invalid response body"):
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, MARKER)), NO_SLEEP)

    def test_oversized_body_is_rejected_without_echoing_body(self):
        body = MARKER.encode() + b"x" * fetcher.MAX_RESPONSE_BYTES
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, body)), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "response exceeded the 1 MiB public-data limit")
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_nonstandard_json_constants_are_rejected(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.http_get_json(CANDLE_URL, 5, 1, scripted((200, b'{"price":NaN}')), NO_SLEEP)
        self.assertEqual(str(ctx.exception), "HTTP 200 response was not valid JSON")

    def test_parser_errors_never_echo_provider_values(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.unwrap({"code": -1, "msg": MARKER})
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.parse_klines([[1_700_000_000_000, MARKER, "2", "1", "1", "1"]])
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.parse_klines({"message": MARKER})
        self.assertNotIn(MARKER, str(ctx.exception))
        with self.assertRaises(fetcher.ApiError) as ctx:
            fetcher.extract_server_time(MARKER)
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_timestamp_and_response_code_booleans_are_not_accepted(self):
        for value in (True, False, 1.0, "not-a-timestamp", "-1"):
            with self.subTest(value=repr(value)), self.assertRaises((TypeError, ValueError)):
                fetcher.to_seconds(value)
        with self.assertRaises(fetcher.ApiError):
            fetcher.unwrap({"code": False, "data": [1]})
        self.assertEqual(fetcher.to_seconds("1700000000000"), 1_700_000_000)

    def test_nonfinite_and_boolean_candle_values_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), True):
            row = [1_700_000_000_000, value, "2", "1", "1", "1"]
            with self.subTest(value=repr(value)), self.assertRaises(fetcher.ApiError):
                fetcher.parse_klines([row])


class ProviderSanitizationTests(unittest.TestCase):
    def test_provider_http_log_rejects_untrusted_status_subclasses(self):
        http = providers.Http(5, 1, lambda url, timeout: (UntrustedInt(451), b""), NO_SLEEP)
        with self.assertRaises(fetcher.ApiError):
            http.get(CANDLE_URL)
        self.assertEqual(http.log, [("/api/v3/klines", "invalid HTTP status")])
        self.assertNotIn(MARKER, repr(http.log))

    def test_provider_http_log_sanitizes_http_error_code(self):
        error = TrackedHTTPError(MARKER)
        http = providers.Http(5, 1, lambda url, timeout: (_ for _ in ()).throw(error), NO_SLEEP)
        with self.assertRaises(fetcher.ApiError):
            http.get(CANDLE_URL)
        self.assertEqual(http.log, [("/api/v3/klines", "invalid HTTP status")])
        self.assertTrue(error.closed_by_test)
        self.assertFalse(error.read_called)
        self.assertNotIn(MARKER, repr(http.log))

    def test_legacy_adapter_errors_are_fixed_safe_messages(self):
        with self.assertRaises(fetcher.ApiError) as ctx:
            providers.Kraken._result({"result": {}, "error": [MARKER]})
        self.assertEqual(str(ctx.exception), "Kraken returned an error response")

        class FakeHttp:
            def __init__(self, response):
                self.response = response

            def get(self, url):
                return self.response

        with self.assertRaises(fetcher.ApiError) as ctx:
            providers.Coinbase().server_time(FakeHttp({"epoch": MARKER}))
        self.assertEqual(str(ctx.exception), "Coinbase server-time response is invalid")

        with self.assertRaises(fetcher.ApiError) as ctx:
            providers.Kraken().server_time(FakeHttp({"error": [], "result": {"unixtime": MARKER}}))
        self.assertEqual(str(ctx.exception), "Kraken server-time response is invalid")

        with self.assertRaises(fetcher.ApiError) as ctx:
            providers.Coinbase().candles("1h", 1, 3600, FakeHttp([[MARKER, "1", "2", "1", "1", "1"]]))
        self.assertNotIn(MARKER, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
