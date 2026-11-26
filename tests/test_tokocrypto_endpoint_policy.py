"""Offline tests for the approved Tokocrypto public-klines-only boundary.

All responses are synthetic. No DNS lookup, HTTP request or exchange access occurs.
This test deliberately imports only fetcher.py and providers.py, not the protected
legacy pipeline modules.
"""
import json
import os
import sys
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fetcher  # noqa: E402
import providers  # noqa: E402


NO_SLEEP = lambda seconds: None  # noqa: E731
VALID_URL = (
    "https://www.tokocrypto.site/api/v3/klines?"
    "symbol=BTCUSDT&interval=1h&startTime=1699999200000&"
    "endTime=1700002800000&limit=500"
)


def synthetic_kline(timestamp_ms=1699999200000):
    return [[timestamp_ms, "100", "101", "99", "100.5", "10"]]


class ScriptedOpener:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        return 200, self.body


class TokocryptoSourceTests(unittest.TestCase):
    def test_exact_approved_source_constructs_only_klines_route(self):
        source = fetcher.Source(
            "tokocrypto-mbx",
            "binance_style",
            "https://www.tokocrypto.site",
        )
        self.assertEqual(source.klines_url(), "https://www.tokocrypto.site/api/v3/klines")
        self.assertEqual(source.symbol("BTC_USDT"), "BTCUSDT")

    def test_tokocrypto_time_and_symbol_discovery_are_disabled(self):
        source = fetcher.Source(
            "tokocrypto",
            "binance_style",
            "https://www.tokocrypto.site",
        )
        with self.assertRaisesRegex(fetcher.ApiError, "server-time requests are not approved"):
            source.time_url()
        with self.assertRaisesRegex(fetcher.ApiError, "symbol discovery is not approved"):
            source.symbols_url("BTC_USDT")

    def test_unapproved_tokocrypto_source_variants_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact approved .site"):
            fetcher.Source("tokocrypto", "open_v1", "https://www.tokocrypto.site")
        with self.assertRaisesRegex(ValueError, "exact approved .site"):
            fetcher.Source("tokocrypto", "binance_style", "https://www.tokocrypto.com")
        with self.assertRaisesRegex(ValueError, "exact approved .site"):
            fetcher.Source("market-data", "binance_style", "https://api.tokocrypto.site")

    def test_legacy_config_contains_only_approved_tokocrypto_source(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        self.assertEqual(len(config["sources"]), 1)
        self.assertEqual(config["sources"][0], {
            "name": "tokocrypto-mbx",
            "style": "binance_style",
            "base_url": "https://www.tokocrypto.site",
        })


class TokocryptoUrlPolicyTests(unittest.TestCase):
    def test_exact_public_klines_url_is_allowed(self):
        self.assertIsNone(fetcher.validate_request_url(VALID_URL))

    def test_every_other_tokocrypto_route_or_host_is_blocked(self):
        blocked = (
            "https://www.tokocrypto.site/api/v3/time",
            "https://www.tokocrypto.site/api/v3/exchangeInfo?symbol=BTCUSDT",
            "https://www.tokocrypto.site/open/v1/common/time",
            "https://www.tokocrypto.site/open/v1/market/klines",
            "https://www.tokocrypto.com/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
            "https://api.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
            "https://www.tokocrypto.site.evil.example/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
            "http://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
            "https://user:pass@www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
            "https://www.tokocrypto.site:443/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime=1699999200000&endTime=1700002800000&limit=500",
        )
        for url in blocked:
            with self.subTest(url=url), self.assertRaises(fetcher.ApiError):
                fetcher.validate_request_url(url)

    def test_unexpected_or_duplicate_query_parameters_are_blocked(self):
        additions = (
            "&foo=bar",
            "&limit=500",
            "&symbol=ETHUSDT",
        )
        for suffix in additions:
            with self.subTest(suffix=suffix), self.assertRaises(fetcher.ApiError):
                fetcher.validate_request_url(VALID_URL + suffix)

    def test_invalid_query_values_and_bounds_are_blocked(self):
        invalid_values = (
            ("symbol", "BTC_USDT"),
            ("interval", "7m"),
            ("startTime", "-1"),
            ("endTime", "1699999200000"),
            ("limit", "501"),
            ("limit", "0"),
        )
        for key, value in invalid_values:
            parsed = urllib.parse.urlsplit(VALID_URL)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            query[key] = value
            url = urllib.parse.urlunsplit((
                parsed.scheme, parsed.netloc, parsed.path,
                urllib.parse.urlencode(query), "",
            ))
            with self.subTest(key=key, value=value), self.assertRaises(fetcher.ApiError):
                fetcher.validate_request_url(url)

    def test_encoded_tokocrypto_hostname_is_not_a_bypass(self):
        url = VALID_URL.replace("www.tokocrypto.site", "www.%74okocrypto.site")
        with self.assertRaises(fetcher.ApiError):
            fetcher.validate_request_url(url)

    def test_candle_window_larger_than_limit_is_blocked(self):
        parsed = urllib.parse.urlsplit(VALID_URL)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        query["endTime"] = str(1699999200000 + 501 * 3600 * 1000)
        too_wide = urllib.parse.urlunsplit((
            parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "",
        ))
        with self.assertRaises(fetcher.ApiError):
            fetcher.validate_request_url(too_wide)

    def test_disallowed_url_is_rejected_before_the_opener_is_called(self):
        opener = ScriptedOpener(b"[]")
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(
                "https://www.tokocrypto.site/api/v3/time",
                5, 1, opener, NO_SLEEP,
            )
        self.assertEqual(opener.calls, [])

    def test_redirect_handler_refuses_redirects(self):
        handler = fetcher._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://example.com"))


class TokocryptoKlinesOnlyTests(unittest.TestCase):
    def test_direct_fetch_candles_is_blocked_before_opener(self):
        source = fetcher.Source(
            "tokocrypto-mbx",
            "binance_style",
            "https://www.tokocrypto.site",
        )
        opener = ScriptedOpener(json.dumps(synthetic_kline()).encode("utf-8"))
        with self.assertRaisesRegex(fetcher.ApiError, "Direct Tokocrypto candle retrieval is disabled"):
            fetcher.fetch_candles(
                source, "BTC_USDT", "1h",
                1699999200, 1700002800,
                5, 1, opener, NO_SLEEP,
            )
        self.assertEqual(opener.calls, [])

    def test_low_level_http_get_json_is_blocked_before_opener(self):
        opener = ScriptedOpener(json.dumps(synthetic_kline()).encode("utf-8"))
        with self.assertRaisesRegex(fetcher.ApiError, "Direct Tokocrypto JSON transport is disabled"):
            fetcher.http_get_json(VALID_URL, 5, 1, opener, NO_SLEEP)
        self.assertEqual(opener.calls, [])

    def test_default_opener_blocks_tokocrypto_before_network(self):
        with self.assertRaisesRegex(fetcher.ApiError, "Direct Tokocrypto transport is disabled"):
            fetcher.default_opener(VALID_URL, 5)

    def test_provider_server_time_fails_without_network_access(self):
        provider = providers.build("tokocrypto")
        opener = ScriptedOpener(b"{}")
        http = providers.Http(5, 1, opener, NO_SLEEP)
        with self.assertRaisesRegex(fetcher.ApiError, "Tokocrypto server-time access is not approved"):
            provider.server_time(http)
        self.assertEqual(http.requests, 0)
        self.assertEqual(opener.calls, [])

    def test_direct_provider_candles_is_blocked_before_http(self):
        provider = providers.build("tokocrypto")
        opener = ScriptedOpener(json.dumps(synthetic_kline()).encode("utf-8"))
        http = providers.Http(5, 1, opener, NO_SLEEP)
        with self.assertRaisesRegex(fetcher.ApiError, "Direct Tokocrypto provider-adapter retrieval is disabled"):
            provider.candles("1h", 1699999200, 1700002800, http)
        self.assertEqual(http.requests, 0)
        self.assertEqual(opener.calls, [])

    def test_public_response_size_is_bounded(self):
        opener = ScriptedOpener(b" " * (fetcher.MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(fetcher.ApiError, "4 MiB"):
            fetcher.http_get_json(VALID_URL, 5, 1, opener, NO_SLEEP)


if __name__ == "__main__":
    unittest.main()
