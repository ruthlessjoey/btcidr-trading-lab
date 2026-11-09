"""End-to-end tests against a FAKE exchange. All prices are SYNTHETIC test data."""
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock
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


SOURCE_DIRS = ("markets", "research", "signal")
PRUNED_DIRS = {"data", "P1", "tests", ".git", "__pycache__"}


def iter_production_python_files(root):
    """Yield approved Python source files without entering protected/test trees."""
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if name.endswith(".py") and os.path.isfile(path) and not os.path.islink(path):
            yield name, path

    for relative_dir in SOURCE_DIRS:
        start = os.path.join(root, relative_dir)
        if not os.path.isdir(start) or os.path.islink(start):
            continue
        def raise_walk_error(error):
            raise error

        for current, dirs, files in os.walk(
            start, topdown=True, followlinks=False, onerror=raise_walk_error
        ):
            dirs[:] = sorted(
                name for name in dirs
                if name not in PRUNED_DIRS
                and not os.path.islink(os.path.join(current, name))
            )
            for name in sorted(files):
                path = os.path.join(current, name)
                if (
                    name.endswith(".py")
                    and not name.startswith("test_")
                    and not name.endswith("_test.py")
                    and not os.path.islink(path)
                ):
                    yield os.path.relpath(path, root), path


def scan_forbidden_source(root):
    """Return scanner findings from root modules and explicitly approved source trees."""
    forbidden = [
        "/open/v1/orders", "/open/v1/account", "/open/v1/withdraws",
        "user-data-stream", "listenkey", "x-mbx-apikey", "signature",
        "hmac", "api_key", "apikey", "secret", "withdraw",
    ]
    findings = []
    for relative_path, path in iter_production_python_files(root):
        with open(path, encoding="utf-8") as source:
            content = source.read().lower()
        for word in forbidden:
            if word in content:
                findings.append(f"{relative_path} contains forbidden text {word!r}")
        if re.search(r"(?<![.\w])password(?!\w)", content):
            findings.append(f"{relative_path} contains a forbidden credential identifier")
        password_attributes = re.findall(r"\b([a-z_]\w*)\.password\b", content)
        allowed_attributes = ["parts"] if relative_path == "transport_policy.py" else []
        if password_attributes != allowed_attributes:
            findings.append(f"{relative_path} contains an unapproved password attribute reference")
    return findings


class SafetyScanTests(unittest.TestCase):
    def test_no_trading_or_credential_code(self):
        self.assertEqual(scan_forbidden_source(ROOT), [])
        transport_policy = read(ROOT, "transport_policy.py").lower()
        self.assertIn("parts.password is not none", transport_policy)

    def test_nested_production_module_is_scanned(self):
        with tempfile.TemporaryDirectory() as root:
            nested = os.path.join(root, "markets", "providers", "nested.py")
            os.makedirs(os.path.dirname(nested))
            with open(nested, "w", encoding="utf-8") as source:
                source.write("client.password = value\n")
            findings = scan_forbidden_source(root)
            self.assertTrue(any("markets/providers/nested.py" in item for item in findings))
            self.assertTrue(any("password attribute" in item for item in findings))

    def test_scanner_fails_closed_on_walk_error(self):
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "markets"))

            def walk_with_error(*args, **kwargs):
                kwargs["onerror"](PermissionError("simulated traversal failure"))
                return iter(())

            with mock.patch("os.walk", side_effect=walk_with_error):
                with self.assertRaisesRegex(PermissionError, "simulated traversal failure"):
                    list(iter_production_python_files(root))

    def test_protected_signal_data_tree_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as root:
            protected = os.path.join(root, "signal", "data", "must_not_read.py")
            os.makedirs(os.path.dirname(protected))
            with open(protected, "w", encoding="utf-8") as source:
                source.write("client.password = value\n")
            self.assertEqual(scan_forbidden_source(root), [])

    def test_only_approved_public_market_paths_are_used(self):
        text = read(ROOT, "fetcher.py")
        self.assertIn("/api/v3/time", text)
        self.assertIn("/api/v3/klines", text)
        self.assertNotIn("/open/v1/", text)


if __name__ == "__main__":
    unittest.main()
