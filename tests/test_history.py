"""Static offline tests for the Step 1 fail-closed gate.

These tests deliberately avoid importing protected validator.py or invoking network code.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HistoryContainmentTests(unittest.TestCase):
    def test_research_config_names_only_the_approved_provider_and_host(self):
        with open(os.path.join(ROOT, "research_config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["provider"], "tokocrypto")
        self.assertEqual(cfg["host"], "https://www.tokocrypto.site")
        self.assertEqual(cfg["symbol"], "BTCUSDT")

    def test_history_gate_fails_without_symbol_metadata_authorization(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"name": "market_identity", "status": "FAIL"', source)
        self.assertIn('"network_requests": 0', source)
        self.assertIn('"backtest_allowed": False', source)
        self.assertIn("server-time route is undocumented", source)
        self.assertIn("Configuration alone is insufficient", source)

    def test_history_module_has_no_network_or_protected_imports(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        for forbidden in ("urllib", "providers.Http", "import validator", "import fetcher"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_only_exact_tokocrypto_scope_is_accepted_as_configuration(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        for literal in ('provider == "tokocrypto"',
                        'host == "https://www.tokocrypto.site"',
                        'symbol == "BTCUSDT"', 'base_asset == "BTC"', 'quote_asset == "USDT"'):
            self.assertIn(literal, source)


if __name__ == "__main__":
    unittest.main()
