"""Offline tests for the manual-only, exact-route Tokocrypto probe."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import probe  # noqa: E402

CFG = {
    "exchange": "tokocrypto",
    "pair": "BTC_USDT",
    "timeframe": "1h",
    "mode": "read_only",
    "http_timeout_seconds": 5,
    "sources": [{"name": "tokocrypto-mbx", "provider_id": "tokocrypto"}],
}


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class ProbeRunTests(unittest.TestCase):
    def test_probe_uses_only_approved_time_and_klines_routes(self):
        requested = []

        def opener(url, timeout):
            requested.append(url)
            parsed = urllib.parse.urlparse(url)
            if parsed.path == "/api/v3/time":
                return 200, json.dumps({"serverTime": 1_700_000_000_000}).encode()
            if parsed.path == "/api/v3/klines":
                query = urllib.parse.parse_qs(parsed.query)
                self.assertEqual(query["symbol"], ["BTCUSDT"])
                self.assertEqual(query["interval"], ["1h"])
                self.assertEqual(query["limit"], ["3"])
                return 200, json.dumps([
                    [1_700_000_000_000, "1", "2", "0.5", "1.5", "3"]
                ]).encode()
            raise AssertionError("probe attempted an unapproved path")

        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(probe.run_probe(CFG, out, opener), 0)
            report = read(out, "probe.md")

        self.assertEqual(len(requested), 2)
        self.assertTrue(all(urllib.parse.urlparse(url).hostname == "www.tokocrypto.site"
                            for url in requested))
        self.assertEqual({urllib.parse.urlparse(url).path for url in requested},
                         {"/api/v3/time", "/api/v3/klines"})
        self.assertIn("Parsed 1 candle", report)
        self.assertNotIn("minQty", report)
        self.assertNotIn("symbols", report)

    def test_network_failure_is_reported_without_raw_exception_text(self):
        def opener(url, timeout):
            raise urllib.error.URLError("UNIQUE_NETWORK_ERROR_MARKER")
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(probe.run_probe(CFG, out, opener), 0)
            report = read(out, "probe.md")
        self.assertIn("request rejected or unavailable", report)
        self.assertNotIn("UNIQUE_NETWORK_ERROR_MARKER", report)

    def test_probe_refuses_non_read_only_mode(self):
        with self.assertRaises(SystemExit):
            probe.run_probe(dict(CFG, mode="live"), tempfile.gettempdir(), lambda u, t: (200, b""))


if __name__ == "__main__":
    unittest.main()
