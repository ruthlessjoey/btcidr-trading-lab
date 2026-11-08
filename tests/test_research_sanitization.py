"""Regression tests for provider-response sanitization.

All responses and marker strings are synthetic. No network requests are made.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fetcher import ApiError, Candle
from research import crosscheck, history


MARKER = "UNIQUE_PROVIDER_SECRET_MARKER"


class StubHttp:
    def __init__(self, payload):
        self.payload = payload

    def get(self, url):
        return self.payload


class ResearchSanitizationTests(unittest.TestCase):
    def test_crosscheck_rejects_out_of_range_coinbase_and_bitstamp_timestamps(self):
        bad_ts = 4_102_444_801
        coinbase = StubHttp([[bad_ts, 9, 12, 10, 11, 3.5]])
        with self.assertRaisesRegex(ApiError, "Coinbase response contains an invalid candle row"):
            crosscheck.fetch_coinbase_daily(coinbase, 1_700_000_000, 1_700_000_000)

        bitstamp = StubHttp({"data": {"ohlc": [{
            "timestamp": str(bad_ts), "open": "10", "high": "12", "low": "9",
            "close": "11", "volume": "3.5",
        }]}})
        with self.assertRaisesRegex(ApiError, "Bitstamp response contains an invalid candle row"):
            crosscheck.fetch_bitstamp_window(bitstamp, 1_700_000_000, 1)

    def test_crosscheck_coinbase_body_and_network_errors_are_sanitized(self):
        manifest = {"version_id": "synthetic-v1", "csv_sha256": "a" * 64}
        candles = [Candle(1_700_000_000, 10.0, 11.0, 9.0, 10.5, 1.0)]

        def body_opener(url, timeout):
            return 200, json.dumps({"message": MARKER}).encode()

        with tempfile.TemporaryDirectory() as out:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = crosscheck.run_crosscheck(
                    manifest, candles, [], out, opener=body_opener, sleep=lambda _: None,
                    timeout=1, retries=1)
            with open(os.path.join(out, "crosscheck.json"), encoding="utf-8") as f:
                json_text = f.read()
            with open(os.path.join(out, "crosscheck.md"), encoding="utf-8") as f:
                markdown = f.read()
            self.assertIsNotNone(result["coinbase_error"])
            self.assertNotIn(MARKER, json_text + markdown + stdout.getvalue())

        def network_opener(url, timeout):
            raise OSError(MARKER)

        with tempfile.TemporaryDirectory() as out:
            result = crosscheck.run_crosscheck(
                manifest, candles, [], out, opener=network_opener, sleep=lambda _: None,
                timeout=1, retries=1)
            self.assertNotIn(MARKER, json.dumps(result))

    def test_bitstamp_crosscheck_error_is_sanitized(self):
        manifest = {"version_id": "synthetic-v1", "csv_sha256": "a" * 64}
        candles = [Candle(1_700_000_000, 10.0, 11.0, 9.0, 10.5, 1.0)]

        def opener(url, timeout):
            if "coinbase" in url:
                return 200, b"[]"
            return 200, json.dumps({"error": MARKER}).encode()

        with tempfile.TemporaryDirectory() as out:
            result = crosscheck.run_crosscheck(
                manifest, candles, ["2023-11-14"], out, opener=opener, sleep=lambda _: None,
                timeout=1, retries=1)
            self.assertIsNotNone(result["bitstamp_error"])
            self.assertNotIn(MARKER, json.dumps(result))
            with open(os.path.join(out, "crosscheck.md"), encoding="utf-8") as f:
                self.assertNotIn(MARKER, f.read())

    def test_history_report_and_step_summary_do_not_leak_exchange_identity(self):
        cfg = {
            "mode": "read_only",
            "timeframe": "1h",
            "http_timeout_seconds": 1,
            "http_retries": 1,
            "provider": "binance-vision",
            "host": "https://data-api.binance.vision",
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "fetch_from_utc_date": "2023-01-01",
            "require_first_candle_on_or_before": "2023-01-01",
            "min_rows": 1,
            "page_limit": 500,
            "max_pages": 2,
            "max_spike_pct": 20,
        }

        def opener(url, timeout):
            payload = {"symbols": [{
                "symbol": MARKER, "baseAsset": "BTC", "quoteAsset": "USDT",
                "status": "TRADING", "isSpotTradingAllowed": True,
            }]}
            return 200, json.dumps(payload).encode()

        with tempfile.TemporaryDirectory() as out:
            summary_path = os.path.join(out, "step-summary.md")
            stdout = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": summary_path}):
                with contextlib.redirect_stdout(stdout):
                    code = history.run_step1(
                        cfg, out_dir=out, opener=opener, sleep=lambda _: None,
                        local_now=1_700_000_000)
            self.assertEqual(code, 1)
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                report_json = f.read()
            with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
                report_md = f.read()
            with open(summary_path, encoding="utf-8") as f:
                summary = f.read()
            self.assertNotIn(MARKER, report_json + report_md + summary + stdout.getvalue())
            data = json.loads(report_json)
            self.assertFalse(data["exchange_info"]["validated"])
            self.assertIn("symbol", data["exchange_info"]["mismatch_fields"])
            self.assertIsNone(data["exchange_info"]["symbol"])


if __name__ == "__main__":
    unittest.main()
