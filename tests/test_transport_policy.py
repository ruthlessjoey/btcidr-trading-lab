"""Offline tests for the exact public transport policy. No sockets or DNS are used."""
import os
import sys
import time
import unittest
import urllib.request
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fetcher
import transport_policy
from markets.providers import transport as market_transport


class FakeResponse:
    def __init__(self, body, headers=None, delay=0):
        self.body = body
        self.headers = headers or {}
        self.delay = delay
        self.read_sizes = []
        self.closed = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.delay:
            time.sleep(self.delay)
        if not self.body:
            return b""
        part, self.body = self.body[:size], self.body[size:]
        return part

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


class TransportPolicyTests(unittest.TestCase):
    def test_exact_approved_routes_are_accepted(self):
        urls = [
            "https://api.kraken.com/0/public/Time",
            "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60",
            "https://data-api.binance.vision/api/v3/time",
            "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5",
            "https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT",
            "https://www.tokocrypto.site/api/v3/time",
            "https://www.tokocrypto.site/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5",
            "https://api.exchange.coinbase.com/time",
            "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertGreater(transport_policy.validate_request(url), 0)

    def test_provider_ids_resolve_only_to_fixed_origins(self):
        self.assertEqual(transport_policy.provider_base_url("kraken"), "https://api.kraken.com")
        self.assertEqual(transport_policy.provider_base_url("binance-vision"),
                         "https://data-api.binance.vision")
        self.assertEqual(transport_policy.provider_base_url("tokocrypto"),
                         "https://www.tokocrypto.site")
        for provider in ("coinbase", "bitstamp", "www.tokocrypto.com", "api.binance.com", "evil"):
            with self.subTest(provider=provider):
                with self.assertRaises(transport_policy.PolicyError):
                    transport_policy.provider_base_url(provider)

    def test_rejects_unsafe_authorities_schemes_paths_and_methods(self):
        rejected = [
            "http://api.kraken.com/0/public/Time",
            "ftp://api.kraken.com/0/public/Time",
            "file:///etc/passwd",
            "https://api.kraken.com.attacker.example/0/public/Time",
            "https://evil.api.kraken.com/0/public/Time",
            "https://api.kraken.com./0/public/Time",
            "https://127.0.0.1/0/public/Time",
            "https://2130706433/0/public/Time",
            "https://localhost/0/public/Time",
            "https://user@api.kraken.com/0/public/Time",
            "https://api.kraken.com:8443/0/public/Time",
            "https://api.kraken.com/0/public/../Time",
            "https://api.kraken.com/0/public/%2e%2e/Time",
            "https://api.kraken.com/0/public%2fTime",
            "https://www.tokocrypto.com/api/v3/time",
            "https://www.tokocrypto.site/open/v1/common/time",
            "https://www.tokocrypto.site/api/v3/exchangeInfo?symbol=BTCUSDT",
            "https://www.bitstamp.net/api/v2/ohlc/btcusd/",
            "https://api.exchange.coinbase.com/products",
            "https://api.kraken.com/0/public/Time#fragment",
            "https://api.kraken.com\\@evil.example/0/public/Time",
            "https://api.kraken.com/0/public/Time\n",
            "https://api.kraken.com/0/public/Time?token=secret",
        ]
        for url in rejected:
            with self.subTest(url=url):
                with self.assertRaises(transport_policy.PolicyError):
                    transport_policy.validate_request(url)
        with self.assertRaises(transport_policy.PolicyError):
            transport_policy.validate_request("https://api.kraken.com/0/public/Time", "POST")

    def test_rejects_duplicate_unknown_and_missing_query_keys(self):
        for url in (
            "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&pair=ETHUSD&interval=60",
            "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60&admin=true",
            "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h",
        ):
            with self.subTest(url=url):
                with self.assertRaises(transport_policy.PolicyError):
                    transport_policy.validate_request(url)

    def test_rejected_url_never_reaches_injected_opener(self):
        calls = []
        def opener(url, timeout):
            calls.append(url)
            return 200, b"{}"
        with self.assertRaises(fetcher.ApiError):
            fetcher.http_get_json(
                "https://www.tokocrypto.site/api/v3/exchangeInfo?symbol=BTCUSDT",
                1, 1, opener, lambda _: None)
        self.assertEqual(calls, [])

    def test_response_exactly_at_limit_is_accepted(self):
        response = FakeResponse(b"12345", {"Content-Length": "5"})
        self.assertEqual(transport_policy.read_bounded(response, 5, 1), b"12345")

    def test_response_limit_plus_one_is_rejected(self):
        response = FakeResponse(b"123456")
        with self.assertRaises(transport_policy.PolicyError):
            transport_policy.read_bounded(response, 5, 1)
        self.assertEqual(sum(response.read_sizes), 6)

    def test_content_length_is_only_an_early_rejection_hint(self):
        response = FakeResponse(b"123456", {"Content-Length": "6"})
        with self.assertRaises(transport_policy.PolicyError):
            transport_policy.read_bounded(response, 5, 1)
        self.assertEqual(response.read_sizes, [])

    def test_malformed_content_length_is_rejected(self):
        response = FakeResponse(b"1", {"Content-Length": "5x"})
        with self.assertRaises(transport_policy.PolicyError):
            transport_policy.read_bounded(response, 5, 1)

    def test_slow_drip_body_cannot_exceed_total_deadline(self):
        response = FakeResponse(b"12", delay=0.02)
        with self.assertRaises(transport_policy.PolicyError):
            transport_policy.read_bounded(response, 10, 0.005)

    def test_default_opener_disables_proxy_and_redirects_and_closes_response(self):
        response = FakeResponse(b'{"ok":true}', {"Content-Length": "11"})
        fake_opener = FakeOpener(response)
        with patch("urllib.request.build_opener", return_value=fake_opener) as build:
            status, body = fetcher.default_opener("https://api.kraken.com/0/public/Time", 1)
        self.assertEqual((status, body), (200, b'{"ok":true}'))
        handlers = build.call_args.args
        self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler)
                            for h in handlers))
        self.assertTrue(any(isinstance(h, fetcher._NoRedirectHandler) for h in handlers))
        self.assertTrue(response.closed)

    def test_redirect_handler_refuses_redirects(self):
        handler = fetcher._NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/"))

    def test_provider_neutral_transport_rejects_unapproved_url_before_opener(self):
        with patch("urllib.request.build_opener") as build:
            with self.assertRaises(market_transport.TransportFailure):
                market_transport.live_transport("https://api.binance.com/api/v3/time")
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
