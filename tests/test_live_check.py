"""Offline static and provider-factory checks; do not import protected validator.py."""
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

    def test_approved_source_urls_pass_central_policy(self):
        p = providers.build("tokocrypto")
        self.assertEqual(fetcher.validate_public_url(p.src.time_url()), p.src.time_url())
        candle = (p.src.klines_url() +
                  "?symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")
        self.assertEqual(fetcher.validate_public_url(candle), candle)

    def test_live_check_provider_guard_precedes_filesystem_and_network(self):
        with open(os.path.join(ROOT, "live_check.py"), encoding="utf-8") as f:
            source = f.read()
        provider_guard = 'if cfg.get("live_providers") != ["tokocrypto"]:'
        self.assertIn(provider_guard, source)
        self.assertLess(source.index(provider_guard), source.index('os.makedirs(out_dir, exist_ok=True)'))
        self.assertLess(source.index(provider_guard), source.index('for name in cfg["live_providers"]'))

    def test_live_check_rejects_non_read_only_before_filesystem_and_network(self):
        with open(os.path.join(ROOT, "live_check.py"), encoding="utf-8") as f:
            source = f.read()
        read_only_guard = 'if cfg.get("mode") != "read_only":'
        self.assertIn(read_only_guard, source)
        self.assertLess(source.index(read_only_guard), source.index('os.makedirs(out_dir, exist_ok=True)'))

    def test_default_configuration_authorizes_only_tokocrypto(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["live_providers"], ["tokocrypto"])
        self.assertEqual(cfg["min_verified"], 1)


if __name__ == "__main__":
    unittest.main()
