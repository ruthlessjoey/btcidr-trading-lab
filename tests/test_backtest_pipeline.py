"""Offline tests for the Step 2 pipeline and the cross-check.

ALL DATA HERE IS SYNTHETIC (seeded toy series or hand-made numbers), not market data.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fetcher import Candle  # noqa: E402
from research import crosscheck, dataset, engine, pipeline, selection, toy  # noqa: E402

DAY = 86400
MARKET = {"provider": toy.TOY_PROVIDER, "host": "none", "symbol": "TOYUSDT", "base_asset": "TOY",
          "quote_asset": "USDT", "pair_label": "TOY/USDT", "timeframe": "1d", "market_type": "spot"}
CFG = {"provider": toy.TOY_PROVIDER, "symbol": "TOYUSDT", "quote_asset": "USDT", "timeframe": "1d",
       "warmup": 200, "flagged_dates": [], "evaluate_test": True}


def write_toy(root, candles=None, fetched_after=2, market=None):
    candles = candles or toy.toy_candles(1000)
    fetched = candles[-1].time + fetched_after * DAY
    _, man = dataset.write_version(root, market or MARKET, candles, fetched)
    return os.path.basename(man).replace(".manifest.json", ""), man


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "datasets")
        self.version, self.manifest = write_toy(self.root)
        self.cfg = dict(CFG, dataset_version=self.version)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_bt(self, cfg=None, out=None, **kw):
        out = out or os.path.join(self.tmp, "out")
        code = pipeline.run_backtest(cfg or self.cfg, self.root, out, run_id="r1", **kw)
        with open(os.path.join(out, "backtest_report.json"), encoding="utf-8") as f:
            data = json.load(f)
        with open(os.path.join(out, "backtest_report.md"), encoding="utf-8") as f:
            md = f.read()
        return code, data, md, out

    def test_full_run_on_toy_data_produces_all_sections_and_logs(self):
        code, data, md, out = self.run_bt()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "OK")
        for part in ("TRAIN (in-sample)", "VALIDATION", "TEST (final, evaluated once)", "Assumptions (ALL UNVERIFIED",
                     "Buy and hold", "Cash", "Metric limitations", "Frozen choice"):
            if data["selection"]["selected_n"] is None and part in ("TRAIN (in-sample)", "TEST (final, evaluated once)"):
                continue
            self.assertIn(part, md)
        self.assertIn("does not show that the strategy is profitable", md)
        self.assertNotIn("will be profitable", md)
        self.assertEqual(len(data["cost_grid"]), 4)
        self.assertTrue(os.path.exists(os.path.join(out, "frozen_choice.json")))
        if data["selection"]["selected_n"] is not None:
            for f in ("trades.csv", "orders.csv", "equity.csv"):
                self.assertTrue(os.path.exists(os.path.join(out, f)))
            self.assertEqual(data["test"]["status"], "evaluated")

    def test_dry_run_never_computes_the_test_window(self):
        code, data, md, out = self.run_bt(dict(self.cfg, evaluate_test=False))
        self.assertEqual(code, 0)
        self.assertEqual(data["test"]["status"], "skipped")
        self.assertNotIn("test", data["shown"])
        self.assertFalse(os.path.exists(os.path.join(out, "test_evaluations")))
        self.assertIn("DRY RUN", md)
        with open(os.path.join(out, "equity.csv"), encoding="utf-8") as f:
            self.assertNotIn("test,", f.read())
        with open(os.path.join(out, "trades.csv"), encoding="utf-8") as f:
            self.assertNotIn("test,", f.read())

    def test_dry_run_then_final_run_gives_the_same_frozen_choice(self):
        _, a, _, _ = self.run_bt(dict(self.cfg, evaluate_test=False), out=os.path.join(self.tmp, "d1"))
        _, b, _, _ = self.run_bt(out=os.path.join(self.tmp, "d2"))
        self.assertEqual(a["frozen"]["frozen_hash"], b["frozen"]["frozen_hash"])

    def test_changed_selection_since_the_recorded_choice_stops_before_the_test(self):
        _, a, _, _ = self.run_bt(dict(self.cfg, evaluate_test=False), out=os.path.join(self.tmp, "e1"))
        n = a["selection"]["selected_n"]
        wrong = 50 if n != 50 else 200
        code, data, md, out = self.run_bt(dict(self.cfg, expected_selected_n=wrong), out=os.path.join(self.tmp, "e2"))
        self.assertEqual(code, 1)
        self.assertIn("test window was NOT evaluated", data["error"])
        self.assertFalse(os.path.exists(os.path.join(out, "test_evaluations")))
        code, data, md, out = self.run_bt(dict(self.cfg, expected_selected_n=n), out=os.path.join(self.tmp, "e3"))
        self.assertEqual(code, 0)
        self.assertIn("recorded in the config before the final run", md)

    def test_split_sizes_match_sixty_twenty_twenty(self):
        _, data, _, _ = self.run_bt()
        bars = {k: v["bars"] for k, v in data["splits"].items()}
        self.assertEqual(data["splits"]["train"]["end_index"], 600)
        self.assertEqual(data["splits"]["validation"]["end_index"], 800)
        self.assertEqual(bars["test"], 200)

    def test_frozen_record_is_written_and_matches_report(self):
        _, data, _, out = self.run_bt()
        with open(os.path.join(out, "frozen_choice.json"), encoding="utf-8") as f:
            frozen = json.load(f)
        selection.verify_frozen(frozen)
        self.assertEqual(frozen["frozen_hash"], data["frozen"]["frozen_hash"])
        self.assertEqual(frozen["selected_n"], data["selection"]["selected_n"])

    def test_source_dataset_is_not_modified(self):
        csv_path = self.manifest.replace(".manifest.json", ".csv")
        before = (dataset.sha256_file(csv_path), os.listdir(os.path.dirname(csv_path)))
        self.run_bt()
        self.assertEqual(before, (dataset.sha256_file(csv_path), os.listdir(os.path.dirname(csv_path))))

    def test_run_is_reproducible(self):
        _, a, _, _ = self.run_bt(out=os.path.join(self.tmp, "o1"))
        _, b, _, _ = self.run_bt(out=os.path.join(self.tmp, "o2"))
        self.assertEqual(a["selection"], b["selection"])
        self.assertEqual(a["frozen"]["frozen_hash"], b["frozen"]["frozen_hash"])
        self.assertEqual(a["shown"], b["shown"])

    def stopped(self, md, data, code):
        self.assertEqual(code, 1)
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("STOPPED", md)
        self.assertIn("no results are shown", md)

    def test_market_identity_mismatch_stops_the_run(self):
        for key, val in (("quote_asset", "USD"), ("symbol", "BTCUSDT"), ("provider", "binance-vision")):
            code, data, md, out = self.run_bt(dict(self.cfg, **{key: val}), out=os.path.join(self.tmp, "o" + key))
            if key == "quote_asset":
                self.stopped(md, data, code)
                self.assertIn("never mixed", data["error"])
            else:
                self.stopped(md, data, code)          # also: dataset folder for that market does not exist
            self.assertFalse(os.path.exists(os.path.join(out, "frozen_choice.json")))

    def test_toy_dataset_cannot_be_used_as_the_real_market(self):
        # same folder, but the config asks for the real provider: refused, not silently used
        real = dict(self.cfg, provider="binance-vision", symbol="BTCUSDT")
        os.makedirs(os.path.join(self.root, "binance-vision_BTCUSDT_1d"))
        shutil.copy(self.manifest, os.path.join(self.root, "binance-vision_BTCUSDT_1d", self.version + ".manifest.json"))
        shutil.copy(self.manifest.replace(".manifest.json", ".csv"),
                    os.path.join(self.root, "binance-vision_BTCUSDT_1d", self.version + ".csv"))
        code, data, md, _ = self.run_bt(real)
        self.stopped(md, data, code)
        self.assertIn("market mismatch", data["error"])

    def test_tampered_csv_stops_the_run(self):
        with open(self.manifest.replace(".manifest.json", ".csv"), "a", encoding="utf-8") as f:
            f.write("x\n")
        code, data, md, _ = self.run_bt()
        self.stopped(md, data, code)
        self.assertIn("hash", data["error"])

    def test_missing_day_duplicate_and_unsorted_data_stop_the_run(self):
        c = toy.toy_candles(1000)
        for bad in (c[:400] + c[401:], c[:400] + [c[399]] + c[400:], [c[1], c[0]] + c[2:]):
            root = tempfile.mkdtemp(dir=self.tmp)
            version, _ = write_toy(root, bad)
            code = pipeline.run_backtest(dict(CFG, dataset_version=version), root, os.path.join(root, "o"))
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(os.path.join(root, "o", "frozen_choice.json")))

    def test_incomplete_final_candle_stops_the_run(self):
        root = tempfile.mkdtemp(dir=self.tmp)
        c = toy.toy_candles(1000)
        _, man = dataset.write_version(root, MARKET, c, c[-1].time + DAY // 2)   # fetched mid-candle
        version = os.path.basename(man).replace(".manifest.json", "")
        code = pipeline.run_backtest(dict(CFG, dataset_version=version), root, os.path.join(root, "o"))
        with open(os.path.join(root, "o", "backtest_report.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(code, 1)
        self.assertIn("incomplete", data["error"])

    def test_test_window_is_only_evaluated_once_across_runs(self):
        _, a, _, out1 = self.run_bt(out=os.path.join(self.tmp, "r1"))
        if a["selection"]["selected_n"] is None:
            self.skipTest("toy data produced no eligible candidate")
        self.assertEqual(a["test"]["status"], "evaluated")
        _, b, md2, _ = self.run_bt(out=os.path.join(self.tmp, "r2"), prev_results_root=out1)
        self.assertEqual(b["test"]["status"], "already_evaluated")
        self.assertIn("Refused", md2)
        _, c, md3, _ = self.run_bt(out=os.path.join(self.tmp, "r3"), prev_results_root=out1, allow_reeval=True)
        self.assertTrue(c["test"]["re_evaluation"])
        self.assertIn("re-evaluation", md3)

    def test_sensitivity_removes_the_flagged_candle_but_keeps_the_original(self):
        c = toy.toy_candles(1000)
        flagged = pipeline.utc_day(c[300].time)
        _, data, md, _ = self.run_bt(dict(self.cfg, flagged_dates=[flagged]))
        sv = data["sensitivity"]
        self.assertEqual(sv["removed"], [flagged])
        self.assertTrue(sv["test_signals_identical_for_original_choice"] in (True, None))
        self.assertIn("removed", md)
        self.assertIn("NOT verified", md)         # no cross-check file was given
        self.assertEqual(data["dataset"]["rows"], 1000)    # original data untouched

    def test_remap_keeps_calendar_boundaries(self):
        c = toy.toy_candles(1000)
        sp = {"train": (200, 600), "validation": (600, 800), "test": (800, 1000)}
        reduced = c[:300] + c[301:]
        sp2 = pipeline.remap_splits(sp, c, reduced)
        for k in sp:
            self.assertEqual(reduced[sp2[k][0]].time, c[sp[k][0]].time)
        self.assertEqual(sp2["test"][1], 999)

    def test_no_eligible_candidate_report_says_nothing_selected(self):
        falling = [Candle(toy.START + i * DAY, 1000.0 - i / 2, 1001.0 - i / 2, 998.0 - i / 2, 999.0 - i / 2, 1.0) for i in range(1000)]
        root = tempfile.mkdtemp(dir=self.tmp)
        version, _ = write_toy(root, falling)
        code = pipeline.run_backtest(dict(CFG, dataset_version=version), root, os.path.join(root, "o"))
        with open(os.path.join(root, "o", "backtest_report.md"), encoding="utf-8") as f:
            md = f.read()
        self.assertEqual(code, 0)
        self.assertIn("No candidate passed the training screen", md)
        self.assertNotIn("TEST (final, evaluated once):", md)


def coinbase_candles(binance, scale=1.0, drop=()):
    return {c.time: Candle(c.time, c.open * scale, c.high * scale, c.low * scale, c.close * scale, 1.0)
            for c in binance if c.time not in drop}


class CrossCheckTests(unittest.TestCase):
    def setUp(self):
        self.b = toy.toy_candles(60)
        self.fd = pipeline.utc_day(self.b[30].time)

    def test_matching_sources_confirm_the_day(self):
        r = crosscheck.compare(self.b, coinbase_candles(self.b, 1.002), coinbase_candles(self.b, 0.999), [self.fd])
        self.assertTrue(r["flagged"][0]["verdict"].startswith("CONFIRMED"))
        self.assertEqual(r["common_days"], 60)

    def test_a_day_that_disagrees_is_not_confirmed(self):
        cb = coinbase_candles(self.b)
        t = self.b[30].time
        cb[t] = Candle(t, cb[t].open, cb[t].high, cb[t].low, cb[t].close * 1.25, 1.0)
        r = crosscheck.compare(self.b, cb, {}, [self.fd])
        self.assertEqual(r["flagged"][0]["verdict"], "NOT CONFIRMED")
        self.assertEqual(r["worst_days"][0]["date"], self.fd)

    def test_other_source_disagreeing_blocks_confirmation(self):
        bs = coinbase_candles(self.b)
        t = self.b[30].time
        bs[t] = Candle(t, bs[t].open * 1.3, bs[t].high, bs[t].low, bs[t].close, 1.0)
        r = crosscheck.compare(self.b, coinbase_candles(self.b), bs, [self.fd])
        self.assertEqual(r["flagged"][0]["verdict"], "NOT CONFIRMED")

    def test_missing_second_source_data_is_unavailable_not_confirmed(self):
        r = crosscheck.compare(self.b, coinbase_candles(self.b, drop={self.b[30].time}), {}, [self.fd])
        self.assertEqual(r["flagged"][0]["verdict"], "UNAVAILABLE")

    def test_binance_candles_are_never_modified(self):
        before = list(self.b)
        crosscheck.compare(self.b, coinbase_candles(self.b, 1.5), {}, [self.fd])
        self.assertEqual(before, self.b)

    def test_coinbase_paging_respects_the_300_candle_limit_and_parses_fields(self):
        calls = []

        def opener(url, timeout):
            u = urllib.parse.urlparse(url)
            q = urllib.parse.parse_qs(u.query)
            calls.append(q)
            from datetime import datetime, timezone
            f = lambda s: int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())  # noqa: E731
            lo, hi = f(q["start"][0]), f(q["end"][0])
            assert (hi - lo) // DAY <= 300
            rows = [[t, 90.0, 110.0, 100.0, 105.0, 1.0] for t in range(lo, hi, DAY)]     # [time, low, high, open, close, vol]
            return 200, json.dumps(rows[::-1]).encode()
        import providers
        http = providers.Http(5, 1, opener, lambda s: None)
        out = crosscheck.fetch_coinbase_daily(http, toy.START, toy.START + 700 * DAY)
        self.assertGreater(len(calls), 2)
        c = out[toy.START]
        self.assertEqual((c.open, c.high, c.low, c.close), (100.0, 110.0, 90.0, 105.0))

    def test_run_crosscheck_reports_a_fetch_failure_instead_of_crashing(self):
        def blocked(url, timeout):
            return 403, b"denied"
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "ds")
            _, man = write_toy(root, self.b)
            manifest, candles = dataset.load_verified(man)
            res = crosscheck.run_crosscheck(manifest, candles, [self.fd], os.path.join(d, "o"),
                                            opener=blocked, sleep=lambda s: None, retries=1)
            self.assertIn("403", res["coinbase_error"])
            self.assertEqual(res["flagged"][0]["verdict"], "UNAVAILABLE")
            with open(os.path.join(d, "o", "crosscheck.md"), encoding="utf-8") as f:
                self.assertIn("UNAVAILABLE", f.read())


class SafetyTests(unittest.TestCase):
    FORBIDDEN = ["/order", "/account", "/withdraw", "listenkey", "x-mbx-apikey", "signature",
                 "hmac", "api_key", "apikey", "secret", "password", "leverage=", "margin"]

    def test_new_files_have_no_trading_or_credential_code(self):
        names = ["run_backtest.py", "run_crosscheck.py"] + [os.path.join("research", n) for n in
                                                          sorted(os.listdir(os.path.join(ROOT, "research"))) if n.endswith(".py")]
        for name in names:
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                text = f.read().lower()
            for word in self.FORBIDDEN:
                self.assertNotIn(word, text, f"{name} contains {word!r}")

    def test_backtest_modules_make_no_network_calls(self):
        for name in ("engine", "strategy", "splits", "selection", "pipeline", "backtest_report", "dataset"):
            with open(os.path.join(ROOT, "research", name + ".py"), encoding="utf-8") as f:
                text = f.read()
            for word in ("urllib", "http.client", "requests", "socket"):
                self.assertNotIn(word, text, f"{name}.py uses {word}")


if __name__ == "__main__":
    unittest.main()
