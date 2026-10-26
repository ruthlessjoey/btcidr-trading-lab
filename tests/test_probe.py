"""Tests for probe.py. All data here is SYNTHETIC test data."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import probe  # noqa: E402

CFG = {"exchange": "tokocrypto", "pair": "BTC_USDT", "timeframe": "1h", "mode": "read_only",
       "http_timeout_seconds": 5,
       "sources": [{"name": "s1", "style": "binance_style", "base_url": "https://one.test"},
                   {"name": "s2", "style": "open_v1", "base_url": "https://two.test"}]}


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class FindSymbolTests(unittest.TestCase):
    def test_finds_entry_in_nested_json(self):
        data = {"code": 0, "data": {"list": [{"symbol": "ETH_USDT"},
                                              {"symbol": "BTC_USDT", "minQty": "0.0001"}]}}
        self.assertEqual(probe.find_symbol_entry(data)["minQty"], "0.0001")

    def test_finds_concatenated_form_case_insensitive(self):
        self.assertIsNotNone(probe.find_symbol_entry({"symbols": [{"symbol": "btcusdt"}]}))

    def test_returns_none_when_absent(self):
        self.assertIsNone(probe.find_symbol_entry({"symbols": [{"symbol": "ETH_USDT"}]}))


class ProbeRunTests(unittest.TestCase):
    def test_probe_records_success_and_failure_without_raising(self):
        def opener(url, timeout):
            if "one.test" in url:
                raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
            if url.endswith("/open/v1/common/time"):
                return 200, json.dumps({"code": 0, "data": 1_700_000_000_000}).encode()
            if "/open/v1/market/klines" in url:
                return 200, json.dumps({"code": 0, "data": [
                    [1_700_000_000_000, "1", "2", "0.5", "1.5", "3"]]}).encode()
            return 200, json.dumps({"code": 0, "data": [{"symbol": "BTC_USDT",
                                                          "minQty": "0.0001"}]}).encode()
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(probe.run_probe(CFG, out, opener), 0)
            text = read(out, "probe.md")
        self.assertIn("HTTP 403", text)                       # blocked source is reported
        self.assertIn("Parsed 1 candle", text)                # working source is parsed
        self.assertIn('"minQty": "0.0001"', text)             # raw symbol entry is shown

    def test_network_failure_is_reported(self):
        def opener(url, timeout):
            raise urllib.error.URLError("no route")
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(probe.run_probe(CFG, out, opener), 0)
            self.assertIn("network error", read(out, "probe.md"))

    def test_probe_refuses_non_read_only_mode(self):
        with self.assertRaises(SystemExit):
            probe.run_probe(dict(CFG, mode="live"), tempfile.gettempdir(), lambda u, t: (200, b""))


if __name__ == "__main__":
    unittest.main()
