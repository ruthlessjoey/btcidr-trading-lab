"""Static offline tests for the Step 1 fail-closed gates.

These tests deliberately do not import research.history because that module imports the
protected, not-yet-authorized validator.py dependency.
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

    def test_market_identity_is_a_hard_fail_before_network_access(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        fail_marker = 'add("market_identity", FAIL,'
        refusal = 'raise ApiError("market identity cannot be independently verified'
        first_network = 'server_now = fetcher.extract_server_time(http.get('
        self.assertIn(fail_marker, source)
        self.assertIn(refusal, source)
        self.assertLess(source.index(fail_marker), source.index(first_network))
        self.assertLess(source.index(refusal), source.index(first_network))

    def test_symbol_metadata_route_is_not_requested(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn('"/api/v3/exchangeInfo', source)

    def test_unapproved_provider_and_host_are_refused_before_output_or_network(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        provider_guard = 'if cfg.get("provider") != "tokocrypto"'
        self.assertIn(provider_guard, source)
        self.assertLess(source.index(provider_guard), source.index('os.makedirs(out_dir, exist_ok=True)'))


if __name__ == "__main__":
    unittest.main()
