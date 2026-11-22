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
        class FakeHttp:
            def get(self, url):
                calls.append(url)
                raise AssertionError("unverified server-time route must not reach HTTP adapter")
        with self.assertRaisesRegex(fetcher.DisallowedRequestError, "server-time route is unverified"):
            p.server_time(FakeHttp())
        self.assertEqual(calls, [])

    def test_default_configuration_authorizes_only_tokocrypto(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["live_providers"], ["tokocrypto"])
        self.assertEqual(cfg["min_verified"], 1)


    def test_legacy_adapters_and_custom_sources_cannot_bypass_central_allowlist(self):
        attempted = []

        def opener(url, timeout):
            attempted.append(url)
            raise AssertionError("unapproved provider URL reached the opener")

        class GuardedHttp:
            def get(self, url):
                return fetcher.http_get_json(url, 5, 1, opener, lambda seconds: None)

        http = GuardedHttp()
        for adapter_type in (providers.Kraken, providers.Coinbase):
            with self.subTest(adapter=adapter_type.__name__):
                with self.assertRaises(fetcher.DisallowedRequestError):
                    adapter_type()
                adapter = object.__new__(adapter_type)
                with self.assertRaises(fetcher.DisallowedRequestError):
                    adapter.server_time(http)
                with self.assertRaises(fetcher.DisallowedRequestError):
                    adapter.candles("1h", 0, 3_600, http)

        custom = providers.BinanceStyle(
            "unapproved", "BTC/USDT", "USDT", "BTCUSDT",
            "https://api.kraken.com", "synthetic test only",
        )
        with self.assertRaises(fetcher.DisallowedRequestError):
            custom.candles("1h", 0, 3_600, http)

        self.assertEqual(attempted, [])


if __name__ == "__main__":
    unittest.main()
