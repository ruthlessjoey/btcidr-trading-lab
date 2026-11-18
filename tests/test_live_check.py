"""Offline provider-factory and configuration checks; no protected live-check imports."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import providers  # noqa: E402
import fetcher  # noqa: E402


class ProviderAuthorizationTests(unittest.TestCase):
    def test_factory_builds_only_tokocrypto(self):
        p = providers.build("tokocrypto")
        self.assertEqual(p.name, "tokocrypto")
        self.assertEqual(p.src.base_url, "https://www.tokocrypto.site")
        for name in ("kraken", "coinbase", "binance-vision", "bitstamp", "unknown"):
            with self.subTest(provider=name), self.assertRaises(ValueError):
                providers.build(name)

    def test_only_documented_candle_route_passes_central_policy(self):
        p = providers.build("tokocrypto")
        with self.assertRaises(fetcher.DisallowedRequestError):
            fetcher.validate_public_url(p.src.time_url())
        candle = (p.src.klines_url() +
                  "?symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")
        self.assertEqual(fetcher.validate_public_url(candle), candle)

    def test_server_time_fetch_fails_before_network_until_route_is_verified(self):
        p = providers.build("tokocrypto")
        calls = []
        def opener(url, timeout):
            calls.append(url)
            raise AssertionError("unverified server-time route must not reach transport")
        with self.assertRaisesRegex(fetcher.DisallowedRequestError, "server-time route is unverified"):
            fetcher.fetch_server_time(p.src, 5, 1, opener, lambda seconds: None)
        self.assertEqual(calls, [])

    def test_default_configuration_authorizes_only_tokocrypto(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["live_providers"], ["tokocrypto"])
        self.assertEqual(cfg["min_verified"], 1)


if __name__ == "__main__":
    unittest.main()
