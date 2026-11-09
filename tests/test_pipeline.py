"""End-to-end tests against a FAKE exchange. All prices are SYNTHETIC test data."""
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetcher  # noqa: E402
import run  # noqa: E402

NO_SLEEP = lambda seconds: None  # noqa: E731
NOW = 1_700_000_000 + 120
CFG = {
    "exchange": "tokocrypto",
    "pair": "BTC_USDT",
    "timeframe": "1h",
    "lookback_days": 30,
    "mode": "read_only",
    "max_missing_ratio": 0.02,
    "max_spike_pct": 10,
    "http_timeout_seconds": 5,
    "http_retries": 2,
    "sources": [{"name": "tokocrypto-mbx", "provider_id": "tokocrypto"}],
}


def fake_exchange(now_s, blocked=False):
    """Synthetic Tokocrypto-compatible responses for the two approved public routes."""
    calls = []

    def opener(url, timeout):
        calls.append(url)
        parsed = urllib.parse.urlparse(url)
        if blocked:
            return 403, b"unavailable"
        query = urllib.parse.parse_qs(parsed.query)
        if parsed.hostname != "www.tokocrypto.site":
            raise AssertionError("unexpected provider host")
        if parsed.path == "/api/v3/time":
            return 200, json.dumps({"serverTime": now_s * 1000}).encode()
        if parsed.path == "/api/v3/klines":
            step = fetcher.TF_SECONDS[query["interval"][0]]
            start = int(query["startTime"][0]) // 1000
            end = int(query["endTime"][0]) // 1000
            first = -(-start // step) * step
            rows = [
                [t * 1000, str(60000 + t % 97), str(60100 + t % 97),
                 str(59900 + t % 97), str(60001 + t % 97), "5.0",
                 t * 1000 + step * 1000 - 1, "300000", 10]
                for t in range(first, end + 1, step)
            ][:int(query["limit"][0])]
            return 200, json.dumps(rows).encode()
        raise AssertionError("probe attempted an unapproved path")

    opener.calls = calls
    return opener


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def python_source_files(root):
    """Yield root modules and Python files under explicitly approved source trees."""
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if name.endswith(".py") and os.path.isfile(path) and not os.path.islink(path):
            yield path

    for relative_dir in ("markets", "pipeline", "research", "tools"):
        start = os.path.join(root, relative_dir)
        if not os.path.isdir(start) or os.path.islink(start):
            continue

        for current, dirs, files in os.walk(start, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs
                if name != "__pycache__"
                and not os.path.islink(os.path.join(current, name))
            )
            for name in sorted(files):
                if (
                    name.endswith(".py")
                    and not name.startswith("test_")
                    and not name.endswith("_test.py")
                    and not os.path.islink(os.path.join(current, name))
                ):
                    yield os.path.join(current, name)


def source_scan_findings(root, forbidden):
    """Return scanner findings for every file in the approved source set."""
    findings = []
    for path in python_source_files(root):
        name = os.path.relpath(path, root)
        text = read(path).lower()
        for word in forbidden:
            if word in text:
                findings.append((name, f"forbidden text {word!r}"))
        if re.search(r"(?<![.\w])pass" + r"word(?!\w)", text):
            findings.append((name, "forbidden credential identifier"))
        password_attributes = re.findall(r"\b([a-z_]\w*)\.password\b", text)
        allowed_attributes = ["parts"] if name == "transport_policy.py" else []
        if password_attributes != allowed_attributes:
            findings.append((name, "unapproved password attribute reference"))
    return findings


class PipelineTests(unittest.TestCase):
    def test_full_run_uses_only_approved_tokocrypto_source(self):
        opener = fake_exchange(NOW)
        with tempfile.TemporaryDirectory() as out:
            code = run.run_pipeline(CFG, out, opener, NO_SLEEP, NOW)
            self.assertEqual(code, 0)
            result = json.loads(read(out, "report.json"))
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["source"], "tokocrypto-mbx")
            self.assertEqual(result["requests_made"], 2)
            self.assertEqual(result["stats"]["forming_dropped"], 1)
            self.assertEqual(len(opener.calls), 3)  # time + two candle pages
            self.assertTrue(all(urllib.parse.urlparse(url).hostname == "www.tokocrypto.site"
                                for url in opener.calls))
            self.assertTrue(all(urllib.parse.urlparse(url).path in
                                ("/api/v3/time", "/api/v3/klines") for url in opener.calls))
            lines = read(out, "candles.csv").strip().splitlines()
            self.assertEqual(len(lines) - 1, result["stats"]["closed_candles"])
            self.assertIn("READ-ONLY", read(out, "report.md"))

    def test_unapproved_provider_is_rejected_before_any_request(self):
        opener = fake_exchange(NOW)
        bad_cfg = dict(CFG, sources=[{"name": "bad", "provider_id": "coinbase-research"}])
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(ValueError):
                run.run_pipeline(bad_cfg, out, opener, NO_SLEEP, NOW)
        self.assertEqual(opener.calls, [])

    def test_blocked_source_gives_error_report_and_no_data(self):
        with tempfile.TemporaryDirectory() as out:
            code = run.run_pipeline(CFG, out, fake_exchange(NOW, blocked=True), NO_SLEEP, NOW)
            self.assertEqual(code, 1)
            text = read(out, "report.md")
            self.assertIn("API ERROR", text)
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
    FORBIDDEN = ["/open/v1/orders", "/open/v1/account", "/open/v1/withdraws",
                 "user-data-stream", "listenkey", "x-mbx-apikey", "signature",
                 "hmac", "api_key", "apikey", "secret", "withdraw"]

    def test_scanner_finds_nested_source_and_stays_in_approved_trees(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "markets", "providers"))
            os.makedirs(os.path.join(root, "P1"))
            os.makedirs(os.path.join(root, "signal", "data"))
            os.makedirs(os.path.join(root, "tests", "fixtures"))
            nested = os.path.join(root, "markets", "providers", "nested.py")
            with open(nested, "w", encoding="utf-8") as f:
                f.write("client.password = value\n")
            with open(os.path.join(root, "P1", "untouched.py"), "w",
                      encoding="utf-8") as f:
                f.write("must_not_be_opened = True\n")
            with open(os.path.join(root, "signal", "data", "untouched.py"), "w",
                      encoding="utf-8") as f:
                f.write("must_not_be_opened = True\n")
            with open(os.path.join(root, "tests", "fixtures", "test_fixture.py"), "w",
                      encoding="utf-8") as f:
                f.write("test_only = True\n")

            scanned = list(python_source_files(root))
            self.assertIn(nested, scanned)
            self.assertFalse(any(os.sep + "P1" + os.sep in path for path in scanned))
            self.assertFalse(any(
                os.sep + "signal" + os.sep in path for path in scanned
            ))
            self.assertFalse(any(
                os.sep + "tests" + os.sep in path for path in scanned
            ))

            findings = source_scan_findings(root, self.FORBIDDEN)
            self.assertIn(
                ("markets/providers/nested.py", "unapproved password attribute reference"),
                findings,
            )

    def test_no_trading_or_credential_code(self):
        self.assertEqual(source_scan_findings(ROOT, self.FORBIDDEN), [])
        transport_policy = read(ROOT, "transport_policy.py").lower()
        self.assertIn("parts.password is not none", transport_policy)

    def test_only_approved_public_market_paths_are_used(self):
        text = read(ROOT, "fetcher.py")
        self.assertIn("/api/v3/time", text)
        self.assertIn("/api/v3/klines", text)
        self.assertNotIn("/open/v1/", text)


if __name__ == "__main__":
    unittest.main()
