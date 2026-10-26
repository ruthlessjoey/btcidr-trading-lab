"""End-to-end tests against a FAKE exchange. All prices are SYNTHETIC test data.

These prove the pipeline logic works. They do NOT prove Tokocrypto is reachable
from GitHub; only a real run of the workflow can show that.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetcher  # noqa: E402
import run  # noqa: E402

NO_SLEEP = lambda seconds: None  # noqa: E731
NOW = 1_700_000_000 + 120        # arbitrary fixed "exchange time"
CFG = {"exchange": "tokocrypto", "pair": "BTC_USDT", "timeframe": "1h", "lookback_days": 30,
       "mode": "read_only", "max_missing_ratio": 0.02, "max_spike_pct": 10,
       "http_timeout_seconds": 5, "http_retries": 2,
       "sources": [{"name": "src-a", "style": "binance_style", "base_url": "https://a.test"},
                   {"name": "src-b", "style": "open_v1", "base_url": "https://b.test"}]}


def fake_exchange(now_s, blocked_hosts=()):
    """Pretends to be both endpoint styles. Hosts in blocked_hosts answer 403."""
    def opener(url, timeout):
        p = urllib.parse.urlparse(url)
        if p.hostname in blocked_hosts:
            return 403, b"<html>Access denied</html>"
        q = urllib.parse.parse_qs(p.query)
        if p.path == "/api/v3/time":
            return 200, json.dumps({"serverTime": now_s * 1000}).encode()
        if p.path == "/open/v1/common/time":
            return 200, json.dumps({"code": 0, "msg": "success", "data": now_s * 1000}).encode()
        if p.path in ("/api/v3/klines", "/open/v1/market/klines"):
            step = fetcher.TF_SECONDS[q["interval"][0]]
            start, end = int(q["startTime"][0]) // 1000, int(q["endTime"][0]) // 1000
            first = -(-start // step) * step
            rows = [[t * 1000, str(60000 + t % 97), str(60100 + t % 97), str(59900 + t % 97),
                     str(60001 + t % 97), "5.0", t * 1000 + step * 1000 - 1, "300000", 10]
                    for t in range(first, end + 1, step)][:int(q["limit"][0])]
            if p.path == "/open/v1/market/klines":
                return 200, json.dumps({"code": 0, "msg": "success", "data": rows}).encode()
            return 200, json.dumps(rows).encode()
        return 404, b""
    return opener


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class PipelineTests(unittest.TestCase):
    def test_full_run_uses_first_source(self):
        with tempfile.TemporaryDirectory() as out:
            code = run.run_pipeline(CFG, out, fake_exchange(NOW), NO_SLEEP, NOW)
            self.assertEqual(code, 0)
            result = json.loads(read(out, "report.json"))
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["source"], "src-a")
            self.assertEqual(result["requests_made"], 2)          # 720 candles / 500 per request
            self.assertEqual(result["stats"]["forming_dropped"], 1)
            lines = read(out, "candles.csv").strip().splitlines()
            self.assertEqual(len(lines) - 1, result["stats"]["closed_candles"])
            self.assertIn("READ-ONLY", read(out, "report.md"))

    def test_falls_back_to_second_source_and_says_so(self):
        with tempfile.TemporaryDirectory() as out:
            code = run.run_pipeline(CFG, out, fake_exchange(NOW, {"a.test"}), NO_SLEEP, NOW)
            self.assertEqual(code, 0)
            result = json.loads(read(out, "report.json"))
            self.assertEqual(result["source"], "src-b")
            self.assertFalse(result["attempts"][0]["ok"])
            self.assertIn("403", result["attempts"][0]["detail"])
            self.assertTrue(result["attempts"][1]["ok"])
            self.assertIn("src-a", read(out, "report.md"))

    def test_all_sources_blocked_gives_error_report_and_no_data(self):
        with tempfile.TemporaryDirectory() as out:
            code = run.run_pipeline(CFG, out, fake_exchange(NOW, {"a.test", "b.test"}),
                                    NO_SLEEP, NOW)
            self.assertEqual(code, 1)
            text = read(out, "report.md")
            self.assertIn("API ERROR", text)
            self.assertIn("src-a", text)
            self.assertIn("src-b", text)
            self.assertIn("Nothing is made up", text)
            self.assertFalse(os.path.exists(os.path.join(out, "candles.csv")))

    def test_refuses_any_mode_except_read_only(self):
        for mode in ("paper", "live", "", None):
            with self.assertRaises(SystemExit):
                run.run_pipeline(dict(CFG, mode=mode), tempfile.gettempdir(),
                                 fake_exchange(NOW), NO_SLEEP, NOW)

    def test_unknown_timeframe_is_rejected(self):
        with self.assertRaises(SystemExit):
            run.run_pipeline(dict(CFG, timeframe="7m"), tempfile.gettempdir(),
                             fake_exchange(NOW), NO_SLEEP, NOW)


class SafetyScanTests(unittest.TestCase):
    """The program files must contain nothing that can trade or hold credentials."""
    FORBIDDEN = ["/open/v1/orders", "/open/v1/account", "/open/v1/withdraws",
                 "user-data-stream", "listenkey", "x-mbx-apikey", "signature",
                 "hmac", "api_key", "apikey", "secret", "withdraw", "password"]

    def test_no_trading_or_credential_code(self):
        for name in sorted(os.listdir(ROOT)):
            if name.endswith(".py"):
                text = read(ROOT, name).lower()
                for word in self.FORBIDDEN:
                    self.assertNotIn(word, text, f"{name} contains forbidden text {word!r}")

    def test_only_public_market_urls_are_used(self):
        text = read(ROOT, "fetcher.py")
        for allowed in ("/api/v3/time", "/api/v3/klines", "/open/v1/common/time",
                        "/open/v1/market/klines", "/open/v1/common/symbols"):
            self.assertIn(allowed, text)


if __name__ == "__main__":
    unittest.main()
