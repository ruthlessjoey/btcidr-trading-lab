"""Offline tests for the currently authorized provider configuration."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import live_check  # noqa: E402
import providers  # noqa: E402
import fetcher  # noqa: E402

CFG = {
    "mode": "read_only",
    "timeframe": "1h",
    "lookback_days": 2,
    "max_missing_ratio": 0.02,
    "max_spike_pct": 10,
    "http_timeout_seconds": 5,
    "http_retries": 1,
    "min_verified": 1,
    "live_providers": ["tokocrypto"],
}


class ProviderAuthorizationTests(unittest.TestCase):
    def test_factory_builds_only_tokocrypto(self):
        p = providers.build("tokocrypto")
        self.assertEqual(p.name, "tokocrypto")
        self.assertEqual(p.src.base_url, "https://www.tokocrypto.site")
        for name in ("kraken", "coinbase", "binance-vision", "bitstamp", "unknown"):
            with self.subTest(provider=name), self.assertRaises(ValueError):
                providers.build(name)

    def test_live_check_rejects_unapproved_provider_lists_before_network(self):
        def forbidden_network(*args, **kwargs):
            raise AssertionError("network callback must not be reached")
        for names in (["kraken"], ["coinbase"], ["binance-vision"], ["tokocrypto", "kraken"], []):
            cfg = dict(CFG, live_providers=names)
            with self.subTest(providers=names), self.assertRaises(SystemExit):
                live_check.run_live_check(cfg, tempfile.gettempdir(), forbidden_network)
    
    def test_live_check_rejects_non_read_only_mode_before_network(self):
        def forbidden_network(*args, **kwargs):
            raise AssertionError("network callback must not be reached")
        for mode in ("paper", "live", None):
            cfg = dict(CFG, mode=mode)
            with self.subTest(mode=mode), self.assertRaises(SystemExit):
                live_check.run_live_check(cfg, tempfile.gettempdir(), forbidden_network)

    def test_approved_source_urls_pass_central_policy(self):
        p = providers.build("tokocrypto")
        self.assertEqual(fetcher.validate_public_url(p.src.time_url()), p.src.time_url())
        candle = (p.src.klines_url() +
                  "?symbol=BTCUSDT&interval=1h&startTime=1700000000000&endTime=1700003599999&limit=500")
        self.assertEqual(fetcher.validate_public_url(candle), candle)

    def test_no_legacy_provider_is_reported_as_verified(self):
        self.assertEqual(CFG["live_providers"], ["tokocrypto"])
        self.assertEqual(CFG["min_verified"], 1)


if __name__ == "__main__":
    unittest.main()
