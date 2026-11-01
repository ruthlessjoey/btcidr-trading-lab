"""Offline tests for signal/btc_signal.py. Run from the repository root with:
    python3 -B -m unittest discover -s signal -p "test_*.py" -v
Datasets are written to a temporary directory outside the repository and removed afterwards.
"""
import ast
import csv
import json
import math
import os
import shutil
import tempfile
import unittest

import btc_signal as bs

START = 1609459200            # 2021-01-01 00:00:00 UTC, on the daily grid
REPO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backtest_config.json")


def candles_from_closes(closes):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        out.append(bs.Candle(START + i * bs.STEP, o, max(o, c) * 1.01, min(o, c) * 0.99, c, 1000.0))
        prev = c
    return out


def wave(i, base, slope, amp=3.0):
    return base + slope * i + amp * (-1) ** i


def write_dataset(root, candles, version="v20260101T000000Z_testtest", fetched_ts=None,
                  extra_checks=()):
    # Fixture now carries the fields real manifests carry: fetched_utc and gate_checks.
    if fetched_ts is None:
        fetched_ts = candles[-1].time + bs.STEP + 3600      # fetched one hour after the close
    csv_name = version + ".csv"
    csv_path = os.path.join(root, csv_name)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(bs.COLUMNS)
        for c in candles:
            w.writerow(["binance-vision", "BTCUSDT", "1d", c.time, bs.utc_text(c.time),
                        repr(c.open), repr(c.high), repr(c.low), repr(c.close), repr(c.volume)])
    manifest = {
        "schema_version": 1, "dataset_name": "binance-vision_BTCUSDT_1d", "version_id": version,
        "market": dict(bs.EXPECTED_MARKET), "price_basis_warning": "proxy",
        "csv_file": csv_name, "csv_sha256": bs.sha256_file(csv_path), "row_count": len(candles),
        "first_open_unix": candles[0].time, "last_open_unix": candles[-1].time,
        "timeframe_seconds": bs.STEP,
        "fetched_utc": bs.utc_text(fetched_ts) + " UTC",
        "gate_checks": [{"name": "validator_freshness", "status": "PASS", "detail": "ok"}]
                       + list(extra_checks),
    }
    mpath = os.path.join(root, version + ".manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return mpath, csv_path


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="btc_signal_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class IndicatorTests(unittest.TestCase):
    def test_sma_uses_last_n_values(self):
        self.assertEqual(bs.sma([1, 2, 3, 4, 5], 3), 4.0)
        self.assertIsNone(bs.sma([1, 2], 3))

    def test_rsi_extremes(self):
        up = [float(i) for i in range(30)]
        down = [float(100 - i) for i in range(30)]
        flat = [5.0] * 30
        self.assertEqual(bs.rsi(up), 100.0)
        self.assertEqual(bs.rsi(down), 0.0)
        self.assertEqual(bs.rsi(flat), 50.0)
        self.assertIsNone(bs.rsi([1.0] * 5))

    def test_rsi_is_bounded(self):
        closes = [wave(i, 100, 0.5) for i in range(80)]
        r = bs.rsi(closes)
        self.assertTrue(0.0 <= r <= 100.0)

    def test_rsi14_wilder_matches_hand_calculation(self):
        # Hand calculation, independent of btc_signal.rsi.
        # 16 closes give 15 changes: the first 14 seed the averages, the 15th applies one Wilder step.
        # Changes:  +1 +2 -1 +3 -2 +1 +1 -1 +2 -3 +1 +2 -1 +1 | -4
        # Seed:     gains sum 14 -> avg gain 14/14 = 1; losses sum 8 -> avg loss 8/14 = 4/7
        # Step (-4): avg gain = (1*13 + 0)/14 = 13/14; avg loss = ((4/7)*13 + 4)/14 = 40/49
        # RS = (13/14)/(40/49) = 91/80; RSI = 100 - 100/(1 + 91/80) = 9100/171 = 53.2163742690...
        closes = [100, 101, 103, 102, 105, 103, 104, 105, 104, 106, 103, 104, 106, 105, 106, 102]
        expected = 9100 / 171
        self.assertTrue(math.isclose(bs.rsi([float(c) for c in closes]), expected, abs_tol=1e-9))
        # The seed-only value (first 15 closes) is 63.6363..., so the smoothing step is observable.
        seed_only = bs.rsi([float(c) for c in closes[:15]])
        self.assertTrue(math.isclose(seed_only, 100 - 100 / (1 + 1.75), abs_tol=1e-9))
        self.assertGreater(abs(seed_only - expected), 10.0)

    def test_rsi14_wilder_two_smoothing_steps_hand_calculation(self):
        # Exact-fraction hand calculation, independent of btc_signal.rsi.
        # 17 closes give 16 changes: 14 seed changes, then two Wilder steps (-4, then +5).
        # Changes: +1 +2 -1 +3 -2 +1 +1 -1 +2 -3 +1 +2 -1 +1 | -4 | +5
        # Seed:    gains sum 14 -> AG = 14/14 = 1; losses sum 8 -> AL = 8/14 = 4/7
        # Step 1 (loss 4): AG = (1*13 + 0)/14 = 13/14; AL = ((4/7)*13 + 4)/14 = 40/49
        # Step 2 (gain 5): AG = ((13/14)*13 + 5)/14 = 239/196; AL = ((40/49)*13 + 0)/14 = 260/343
        # RS = (239/196)/(260/343) = 1673/1040
        # RSI = 100 - 100/(1 + 1673/1040) = 167300/2713 = 61.66605234...
        closes = [100, 101, 103, 102, 105, 103, 104, 105, 104, 106, 103, 104, 106, 105, 106, 102, 107]
        expected = 167300 / 2713
        self.assertTrue(math.isclose(bs.rsi([float(c) for c in closes]), expected, abs_tol=1e-9))


class DecisionTests(unittest.TestCase):
    def test_buy_on_uptrend(self):
        cs = candles_from_closes([wave(i, 100, 0.5) for i in range(120)])
        res = bs.signal_at(cs, len(cs) - 1)
        self.assertEqual(res["decision"], "BUY")
        self.assertEqual(res["basis_candle_open_utc"], bs.utc_text(cs[-1].time))
        self.assertIsNotNone(res["values"]["rsi14"])
        self.assertLess(res["values"]["rsi14"], bs.RSI_OVERBOUGHT)

    def test_sell_on_downtrend(self):
        cs = candles_from_closes([wave(i, 200, -0.5) for i in range(120)])
        res = bs.signal_at(cs, len(cs) - 1)
        self.assertEqual(res["decision"], "SELL")
        self.assertIn("bearish or exit candidate", " ".join(res["reasons"]))

    def test_wait_on_flat_market_with_reason(self):
        cs = candles_from_closes([100.0] * 80)
        res = bs.signal_at(cs, len(cs) - 1)
        self.assertEqual(res["decision"], "WAIT")
        self.assertTrue(any("no trend" in r for r in res["reasons"]))

    def test_wait_on_insufficient_history_with_reason(self):
        cs = candles_from_closes([wave(i, 100, 0.5) for i in range(30)])
        res = bs.signal_at(cs, len(cs) - 1)
        self.assertEqual(res["decision"], "WAIT")
        self.assertIn("insufficient history", res["reasons"][0])

    def test_wait_when_overbought_uptrend(self):
        closes = [100.0 + i for i in range(120)]          # steady rise: RSI 100
        cs = candles_from_closes(closes)
        res = bs.signal_at(cs, len(cs) - 1)
        self.assertEqual(res["decision"], "WAIT")
        self.assertTrue(any("overbought" in r for r in res["reasons"]))

    def test_index_out_of_range_refused(self):
        cs = candles_from_closes([100.0] * 60)
        with self.assertRaises(bs.SignalError):
            bs.signal_at(cs, 60)


class CausalityTests(unittest.TestCase):
    def test_signal_ignores_future_candles(self):
        closes = [wave(i, 100, 0.3, amp=8.0) for i in range(160)]
        cs = candles_from_closes(closes)
        for k in range(bs.SMA_SLOW, len(cs), 9):
            prefix_only = bs.signal_at(cs[:k + 1], k)
            full = bs.signal_at(cs, k)
            wild = cs[:k + 1] + [bs.Candle(c.time, 1e9, 2e9, 1.0, 1.5e9, 1.0)
                                 for c in cs[k + 1:]]
            rewritten = bs.signal_at(wild, k)
            self.assertEqual(prefix_only, full, f"prefix changed result at {k}")
            self.assertEqual(full, rewritten, f"future rewrite changed result at {k}")


class DatasetVerificationTests(Base):
    def test_valid_dataset_loads(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        mpath, _ = write_dataset(self.tmp, cs)
        m, loaded = bs.load_verified(mpath)
        self.assertEqual(len(loaded), 60)
        self.assertEqual(m["version_id"], "v20260101T000000Z_testtest")

    def test_tampered_csv_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        mpath, csv_path = write_dataset(self.tmp, cs)
        with open(csv_path, "rb") as f:
            data = f.read()
        with open(csv_path, "wb") as f:
            f.write(data.replace(b"1000.0", b"1001.0", 1))
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath)
        self.assertIn("hash", str(ctx.exception))

    def test_gap_refused_even_with_valid_hash(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        broken = cs[:30] + cs[31:]            # remove one day; manifest hashes are rebuilt
        mpath, _ = write_dataset(self.tmp, broken)
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath)
        self.assertIn("not consecutive", str(ctx.exception))

    def test_duplicate_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        dup = cs[:30] + [cs[29]] + cs[30:]
        mpath, _ = write_dataset(self.tmp, dup)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)

    def test_impossible_ohlc_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        c = cs[10]
        cs[10] = bs.Candle(c.time, c.open, c.close * 0.5, c.low, c.close, c.volume)  # high < close
        mpath, _ = write_dataset(self.tmp, cs)
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath)
        self.assertIn("impossible OHLC", str(ctx.exception))

    def test_wrong_market_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        mpath, _ = write_dataset(self.tmp, cs)
        with open(mpath, encoding="utf-8") as f:
            m = json.load(f)
        m["market"]["symbol"] = "ETHUSDT"
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)

    def test_unpinned_version_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        mpath, _ = write_dataset(self.tmp, cs)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath, expect_version="v20261027T102241Z_c11776a0")

    def test_path_traversal_in_csv_name_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.2) for i in range(60)])
        mpath, _ = write_dataset(self.tmp, cs)
        with open(mpath, encoding="utf-8") as f:
            m = json.load(f)
        m["csv_file"] = "../" + m["csv_file"]
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)


class ReportTests(Base):
    def test_report_has_disclaimer_identity_and_no_model_score(self):
        cs = candles_from_closes([wave(i, 100, 0.5) for i in range(120)])
        mpath, _ = write_dataset(self.tmp, cs)
        r = bs.build_report(mpath, now_ts=cs[-1].time + bs.STEP + 3600)
        self.assertIn("RESEARCH ONLY", r["disclaimer"])
        self.assertEqual(r["dataset"]["version_id"], "v20260101T000000Z_testtest")
        self.assertEqual(len(r["dataset"]["csv_sha256_verified"]), 64)
        self.assertEqual(r["data_freshness_hours_since_basis_close"], 1.0)
        self.assertIn("no model score", r["model"])
        self.assertNotIn("probability", json.dumps(r).lower().replace("not a probability", ""))
        md = bs.render_markdown(r)
        self.assertIn("Decision: BUY", md)

    def test_config_pin_mismatch_refused(self):
        cs = candles_from_closes([wave(i, 100, 0.5) for i in range(120)])
        mpath, _ = write_dataset(self.tmp, cs)
        cfg = os.path.join(self.tmp, "cfg.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"dataset_version": "v20261027T102241Z_c11776a0", "provider":
                       "binance-vision", "symbol": "BTCUSDT", "timeframe": "1d"}, f)
        with self.assertRaises(bs.SignalError):
            bs.build_report(mpath, config_path=cfg)


class PinnedDatasetTests(unittest.TestCase):
    """Runs only when BTC_SIGNAL_PINNED_MANIFEST points to a local manifest. Never fetches."""

    @unittest.skipUnless(os.environ.get("BTC_SIGNAL_PINNED_MANIFEST"),
                         "set BTC_SIGNAL_PINNED_MANIFEST to a local pinned manifest to run")
    def test_pinned_version_matches_config_and_loads(self):
        mpath = os.environ["BTC_SIGNAL_PINNED_MANIFEST"]
        with open(REPO_CONFIG, encoding="utf-8") as f:
            pinned = json.load(f)["dataset_version"]
        m, candles = bs.load_verified(mpath, expect_version=pinned)
        self.assertEqual(m["version_id"], pinned)
        self.assertGreater(len(candles), 3000)


class BoundaryTests(unittest.TestCase):
    def test_only_standard_library_and_no_network_or_repo_imports(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_signal.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        allowed = {"argparse", "csv", "hashlib", "io", "json", "math", "os", "sys", "time",
                   "collections", "datetime"}
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertTrue(names <= allowed, f"unexpected imports: {names - allowed}")
        for banned in ("urllib", "socket", "http", "requests", "ccxt", "research", "fetcher",
                       "validator", "subprocess"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
