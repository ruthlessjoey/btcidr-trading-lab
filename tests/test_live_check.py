"""Offline provider-construction checks; no URL is authorized by this module.

Endpoint authorization is tested separately by the Q0 transport-policy suite.
This module must not import live_check.py or any protected dependency.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import providers  # noqa: E402


class ProviderFactoryIsolationTests(unittest.TestCase):
    def test_factory_constructs_tokocrypto_adapter_without_network(self):
        provider = providers.build("tokocrypto")
        self.assertEqual(provider.name, "tokocrypto")
        self.assertEqual(provider.src.base_url, "https://www.tokocrypto.site")
        self.assertEqual(provider.pair, "BTC_USDT")

    def test_factory_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            providers.build("unknown-provider")

    def test_default_configuration_is_read_only_and_includes_tokocrypto(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["mode"], "read_only")
        self.assertIn("tokocrypto", cfg["live_providers"])
        self.assertEqual(cfg["min_verified"], 1)


if __name__ == "__main__":
    unittest.main()
