"""Regression tests for provider-controlled text reaching report sinks."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import fetcher
import providers
from research import crosscheck, history, dataset

MARKER = "UNTRUSTED_PROVIDER_MARKER_7f3a9c"
NOW = 1_700_003_700


class SanitizationSinkTests(unittest.TestCase):
    def test_coinbase_and_bitstamp_parser_errors_are_sanitized(self):
        class FakeHttp:
            def __init__(self, value):
                self.value = value
            def get(self, url):
                return self.value

        with self.assertRaises(fetcher.ApiError) as ctx:
            crosscheck.fetch_coinbase_daily(FakeHttp([[MARKER, "1", "2", "1", "1", "1"]]),
                                            NOW - 86400, NOW)
        self.assertNotIn(MARKER, str(ctx.exception))

        malformed_bitstamp = {"data": {"ohlc": [{
            "timestamp": MARKER, "open": "1", "high": "2",
            "low": "1", "close": "1", "volume": "1",
        }]}}
        with self.assertRaises(fetcher.ApiError) as ctx:
            crosscheck.fetch_bitstamp_window(FakeHttp(malformed_bitstamp), NOW - 86400, 1)
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_crosscheck_marker_does_not_reach_json_markdown_or_stdout(self):
        candle = fetcher.Candle(NOW - 86400, 100.0, 101.0, 99.0, 100.0, 1.0)

        def opener(url, timeout):
            return 451, MARKER.encode("utf-8")

        with tempfile.TemporaryDirectory() as out:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = crosscheck.run_crosscheck(
                    {"version_id": "synthetic-v1", "csv_sha256": "a" * 64},
                    [candle], ["2023-11-15"], out, opener=opener,
                    sleep=lambda _: None, timeout=1, retries=1)
            with open(os.path.join(out, "crosscheck.json"), encoding="utf-8") as f:
                json_text = f.read()
            with open(os.path.join(out, "crosscheck.md"), encoding="utf-8") as f:
                markdown = f.read()

        self.assertEqual(result["coinbase_error"], "HTTP 451 (not retried)")
        self.assertEqual(result["bitstamp_error"], "HTTP 451 (not retried)")
        for output in (json_text, markdown, stdout.getvalue()):
            self.assertNotIn(MARKER, output)
            self.assertIn("HTTP 451", output)

    def test_exchange_identity_marker_is_absent_from_history_reports(self):
        cfg = {
            "mode": "read_only", "timeframe": "1h", "http_timeout_seconds": 1,
            "http_retries": 1, "provider": "tokocrypto", "host": "https://example.test",
            "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT",
            "fetch_from_utc_date": "2023-11-14",
            "require_first_candle_on_or_before": "2023-11-14",
            "min_rows": 1, "page_limit": 10, "max_pages": 2, "max_spike_pct": 10,
        }

        def opener(url, timeout):
            if url.endswith("/api/v3/exchangeInfo?symbol=BTCUSDT"):
                body = {"symbols": [{
                    "symbol": MARKER, "baseAsset": "BTC", "quoteAsset": "USDT",
                    "status": "TRADING", "isSpotTradingAllowed": True,
                }]}
                return 200, json.dumps(body).encode()
            return 404, b""

        with tempfile.TemporaryDirectory() as out:
            summary = os.path.join(out, "step-summary.md")
            stdout = io.StringIO()
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary}):
                with contextlib.redirect_stdout(stdout):
                    history.run_step1(cfg, out_dir=out, opener=opener,
                                       sleep=lambda _: None, local_now=NOW)
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                json_text = f.read()
            with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
                markdown = f.read()
            with open(summary, encoding="utf-8") as f:
                step_summary = f.read()

        self.assertIn('"symbol_matches": false', json_text)
        for output in (json_text, markdown, stdout.getvalue(), step_summary):
            self.assertNotIn(MARKER, output)

    def test_non_object_exchange_identity_is_a_safe_error(self):
        cfg = {
            "mode": "read_only", "timeframe": "1h", "http_timeout_seconds": 1,
            "http_retries": 1, "provider": "tokocrypto", "host": "https://example.test",
            "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT",
            "fetch_from_utc_date": "2023-11-14",
            "require_first_candle_on_or_before": "2023-11-14",
            "min_rows": 1, "page_limit": 10, "max_pages": 2, "max_spike_pct": 10,
        }

        def opener(url, timeout):
            if url.endswith("/api/v3/exchangeInfo?symbol=BTCUSDT"):
                return 200, json.dumps({"symbols": [MARKER]}).encode()
            return 404, b""

        with tempfile.TemporaryDirectory() as out:
            summary = os.path.join(out, "step-summary.md")
            stdout = io.StringIO()
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary}):
                with contextlib.redirect_stdout(stdout):
                    history.run_step1(cfg, out_dir=out, opener=opener,
                                       sleep=lambda _: None, local_now=NOW)
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                json_text = f.read()
            with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
                markdown = f.read()
            with open(summary, encoding="utf-8") as f:
                step_summary = f.read()

        self.assertIn("exactly one symbol object", json_text)
        for output in (json_text, markdown, stdout.getvalue(), step_summary):
            self.assertNotIn(MARKER, output)


    def test_previous_dataset_error_marker_is_removed_from_all_history_sinks(self):
        start = int(datetime(2023, 11, 14, tzinfo=timezone.utc).timestamp())
        cfg = {
            "mode": "read_only", "timeframe": "1h", "http_timeout_seconds": 1,
            "http_retries": 1, "provider": "tokocrypto", "host": "https://example.test",
            "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT",
            "fetch_from_utc_date": "2023-11-14",
            "require_first_candle_on_or_before": "2023-11-14",
            "min_rows": 1, "page_limit": 10, "max_pages": 2, "max_spike_pct": 10,
        }

        def opener(url, timeout):
            if url.endswith("/api/v3/exchangeInfo?symbol=BTCUSDT"):
                body = {"symbols": [{
                    "symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
                    "status": "TRADING", "isSpotTradingAllowed": True,
                }]}
                return 200, json.dumps(body).encode()
            if url.endswith("/api/v3/time"):
                return 200, json.dumps({"serverTime": NOW * 1000}).encode()
            if "/api/v3/klines?" in url:
                row = [start * 1000, "100", "101", "99", "100", "1"]
                return 200, json.dumps([row]).encode()
            return 404, b""

        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as previous:
            market_folder = os.path.join(previous, "tokocrypto_BTCUSDT_1h")
            os.makedirs(market_folder)
            with open(os.path.join(market_folder, "v0001.manifest.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            summary = os.path.join(out, "step-summary.md")
            stdout = io.StringIO()
            with mock.patch.object(dataset, "load_verified",
                                   side_effect=dataset.DatasetError(MARKER)):
                with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary}):
                    with contextlib.redirect_stdout(stdout):
                        history.run_step1(cfg, out_dir=out, opener=opener,
                                           sleep=lambda _: None, local_now=NOW,
                                           previous_root=previous)
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                json_text = f.read()
            with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
                markdown = f.read()
            with open(summary, encoding="utf-8") as f:
                step_summary = f.read()

        self.assertEqual(json.loads(json_text)["previous"]["error"],
                         "previous dataset failed verification")
        for output in (json_text, markdown, stdout.getvalue(), step_summary):
            self.assertNotIn(MARKER, output)
            self.assertIn("failed", output.lower())


    def test_provider_row_objects_are_wrapped_in_safe_api_errors(self):
        class FakeHttp:
            def __init__(self, value):
                self.value = value

            def get(self, url):
                return self.value

        malformed_row = {"time": MARKER}
        cases = (
            (
                "Kraken",
                lambda: providers.Kraken().candles(
                    "1h", NOW - 7200, NOW,
                    FakeHttp({"error": [], "result": {"XXBTZUSD": [malformed_row], "last": NOW}}),
                ),
                "Kraken candle row 0 has an unexpected format",
            ),
            (
                "Coinbase",
                lambda: providers.Coinbase().candles(
                    "1h", NOW - 7200, NOW, FakeHttp([malformed_row])
                ),
                "Coinbase candle row 0 has an unexpected format",
            ),
            (
                "Coinbase cross-check",
                lambda: crosscheck.fetch_coinbase_daily(
                    FakeHttp([malformed_row]), NOW - 86400, NOW
                ),
                "Coinbase daily-candle row has an unexpected format",
            ),
        )
        for label, call, expected in cases:
            with self.subTest(adapter=label), self.assertRaises(fetcher.ApiError) as ctx:
                call()
            self.assertEqual(str(ctx.exception), expected)
            self.assertNotIn(MARKER, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
