"""Deterministic offline tests for the research engine.

ALL DATA IN THIS FILE IS SYNTHETIC (made-up numbers or the seeded toy series). Nothing here
is market data, and a pass here says nothing about any strategy or exchange.
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fetcher import Candle  # noqa: E402
from research import engine, selection, splits as splits_mod, strategy, toy  # noqa: E402
from research.engine import Costs, EngineError, Rules  # noqa: E402

DAY = 86400
T0 = toy.START
ZERO = Costs("zero", 0.0, 0.0)
EXACT = Rules(capital=1000.0, fraction=1.0, min_notional=0.0, qty_step=1e-8)


def gappy(n=12):
    """open_i = 100 + 10 i, close_i = open_i + 1: the next open never equals the last close,
    so a fill at the wrong price is visible."""
    out = []
    for i in range(n):
        o = 100.0 + 10 * i
        out.append(Candle(T0 + i * DAY, o, o + 5, o - 5, o + 1, 10.0))
    return out


def sig(n, ones):
    s = [0] * n
    for i in ones:
        s[i] = 1
    return s


class ExecutionTests(unittest.TestCase):
    def test_fill_is_next_bars_open_not_the_signal_bars_close(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2]), 1, 12, ZERO, EXACT)    # long signal at close of bar 2
        buy = run["orders"][0]
        self.assertEqual(buy["time"], c[3].time)          # filled during bar 3
        self.assertEqual(buy["fill"], c[3].open)          # at bar 3's open (130)
        self.assertNotEqual(buy["fill"], c[2].close)      # not at bar 2's close (121)
        sell = run["orders"][1]
        self.assertEqual((sell["time"], sell["fill"]), (c[4].time, c[4].open))

    def test_bar_never_trades_on_its_own_signal(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [5]), 1, 12, ZERO, EXACT)
        self.assertEqual(run["orders"][0]["time"], c[6].time)

    def test_last_bars_signal_is_never_executed(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [11]), 1, 12, ZERO, EXACT)
        self.assertEqual(run["orders"], [])

    def test_first_bar_of_a_segment_uses_the_previous_bars_signal(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [5, 6, 7]), 6, 12, ZERO, EXACT)   # segment starts at bar 6
        self.assertEqual(run["orders"][0]["time"], c[6].time)              # signal from bar 5
        self.assertEqual(run["orders"][0]["fill"], c[6].open)

    def test_round_trip_with_fee_and_slippage_matches_hand_calculation(self):
        c = gappy()
        costs = Costs("t", 0.004, 0.0005)
        run = engine.simulate(c, sig(12, [2]), 1, 12, costs, EXACT)
        buy_fill, sell_fill = 130 * 1.0005, 140 * 0.9995
        q = int(1000 / (buy_fill * 1.004) * 1e8) / 1e8
        t = run["trades"][0]
        self.assertAlmostEqual(t["entry_price"], buy_fill, 9)
        self.assertAlmostEqual(t["exit_price"], sell_fill, 9)
        self.assertAlmostEqual(t["qty"], q, 8)
        cost = q * buy_fill * 1.004
        proceeds = q * sell_fill * (1 - 0.004)
        self.assertAlmostEqual(t["pnl"], proceeds - cost, 6)
        self.assertAlmostEqual(t["fees"], q * buy_fill * 0.004 + q * sell_fill * 0.004, 6)
        self.assertLess(t["pnl"], q * (140 - 130))          # costs always reduce the result

    def test_zero_cost_round_trip_equals_price_difference(self):
        c = gappy()
        t = engine.simulate(c, sig(12, [2]), 1, 12, ZERO, EXACT)["trades"][0]
        self.assertAlmostEqual(t["pnl"], t["qty"] * 10.0, 6)

    def test_slippage_is_adverse_on_both_sides(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2]), 1, 12, Costs("s", 0.0, 0.01), EXACT)
        b, s = run["orders"]
        self.assertGreater(b["fill"], b["ref_open"])
        self.assertLess(s["fill"], s["ref_open"])

    def test_higher_costs_never_improve_results(self):
        c = toy.toy_candles(600)
        s = strategy.ma_trend(20)(c)
        rets = [engine.metrics(engine.simulate(c, s, 50, 600, k, Rules()))["total_return"]
                for k in (ZERO, Costs("a", 0.001, 0.0005), Costs("b", 0.004, 0.0005),
                          Costs("c", 0.004, 0.002))]
        self.assertEqual(rets, sorted(rets, reverse=True))


class SizingTests(unittest.TestCase):
    def test_fraction_limits_the_amount_invested(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2]), 1, 12, ZERO, Rules(fraction=0.5, min_notional=0, qty_step=1e-8))
        b = run["orders"][0]
        self.assertAlmostEqual(b["qty"] * b["fill"], 500.0, 4)

    def test_no_leverage_fraction_above_one_is_refused(self):
        with self.assertRaises(EngineError):
            engine.simulate(gappy(), sig(12, [2]), 1, 12, ZERO, Rules(fraction=1.5))

    def test_spend_including_fee_never_exceeds_cash(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2]), 1, 12, Costs("t", 0.004, 0.0005), EXACT)
        b = run["orders"][0]
        self.assertLessEqual(b["qty"] * b["fill"] + b["fee"], 1000.0 + 1e-9)

    def test_quantity_is_rounded_down_to_the_step(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2]), 1, 12, ZERO, Rules(min_notional=0, qty_step=0.01))
        q = run["orders"][0]["qty"]
        self.assertAlmostEqual(q / 0.01, round(q / 0.01), 6)
        self.assertLessEqual(q * 130.0, 1000.0 + 1e-9)

    def test_order_below_minimum_is_rejected_and_logged(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2, 3, 4]), 1, 12, ZERO, Rules(capital=5.0, min_notional=10.0))
        self.assertTrue(run["orders"])
        self.assertTrue(all(o["status"] == "rejected" for o in run["orders"]))
        self.assertEqual(run["trades"], [])
        self.assertEqual(run["equity"][-1], 5.0)
        self.assertEqual(engine.metrics(run)["rejected_orders"], len(run["orders"]))

    def test_cash_never_negative_over_a_toy_series(self):
        c = toy.toy_candles(800)
        run = engine.simulate(c, strategy.ma_trend(30)(c), 40, 800, Costs("t", 0.004, 0.002), Rules())
        self.assertTrue(all(v > 0 for v in run["equity"]))


class MetricTests(unittest.TestCase):
    def fake(self, equity, pnls=(), held=0, capital=100.0):
        return {"rules": Rules(capital=capital), "equity": equity, "orders": [],
                "trades": [{"pnl": p} for p in pnls], "open_position": None, "held_bars": held}

    def test_max_drawdown_total_return_and_exposure(self):
        m = engine.metrics(self.fake([110, 99, 121, 60.5], held=2))
        self.assertAlmostEqual(m["max_drawdown"], 0.5)
        self.assertAlmostEqual(m["total_return"], 60.5 / 100 - 1)
        self.assertAlmostEqual(m["exposure"], 0.5)

    def test_drawdown_counts_the_starting_equity_as_a_peak(self):
        self.assertAlmostEqual(engine.metrics(self.fake([90, 95]))["max_drawdown"], 0.10)

    def test_win_rate_and_profit_factor(self):
        m = engine.metrics(self.fake([100, 100], pnls=[10, -5, 20, -5]))
        self.assertEqual((m["closed_trades"], m["win_rate"]), (4, 0.5))
        self.assertAlmostEqual(m["profit_factor"], 3.0)

    def test_profit_factor_undefined_without_losses_or_trades(self):
        self.assertIsNone(engine.metrics(self.fake([100], pnls=[5, 6]))["profit_factor"])
        m = engine.metrics(self.fake([100]))
        self.assertIsNone(m["profit_factor"])
        self.assertIsNone(m["win_rate"])
        self.assertEqual(m["closed_trades"], 0)

    def test_open_position_is_marked_not_liquidated_and_not_counted_as_a_trade(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2, 3, 4, 5, 6, 7, 8, 9, 10]), 1, 12, ZERO, EXACT)
        m = engine.metrics(run)
        self.assertTrue(m["open_position"])
        self.assertEqual(m["closed_trades"], 0)
        self.assertAlmostEqual(run["equity"][-1], run["open_position"]["qty"] * c[11].close, 4)

    def test_exposure_counts_bars_held(self):
        c = gappy()
        run = engine.simulate(c, sig(12, [2, 3, 4]), 1, 12, ZERO, EXACT)     # held bars 3,4,5
        self.assertEqual(run["held_bars"], 3)
        self.assertAlmostEqual(engine.metrics(run)["exposure"], 3 / 11)


class BenchmarkTests(unittest.TestCase):
    def test_cash_benchmark_is_flat_and_never_trades(self):
        c = gappy()
        run = engine.cash_only(c, 1, 12, Costs("t", 0.004, 0.002), EXACT)
        self.assertEqual(run["orders"], [])
        m = engine.metrics(run)
        self.assertEqual((m["total_return"], m["max_drawdown"], m["exposure"]), (0.0, 0.0, 0.0))

    def test_buy_and_hold_pays_the_same_costs_once_and_is_fully_exposed(self):
        c = gappy()
        costs = Costs("t", 0.004, 0.0005)
        run = engine.buy_and_hold(c, 1, 12, costs, EXACT)
        self.assertEqual([o["side"] for o in run["orders"]], ["buy"])
        self.assertAlmostEqual(run["orders"][0]["fill"], c[1].open * 1.0005, 9)
        self.assertEqual(engine.metrics(run)["exposure"], 1.0)
        self.assertLess(engine.metrics(run)["total_return"],
                        c[11].close / c[1].open - 1)                  # entry costs reduce it

    def test_strategy_that_is_always_long_equals_buy_and_hold(self):
        c = toy.toy_candles(300)
        a = engine.metrics(engine.simulate(c, [1] * 300, 10, 300, Costs("t", 0.004, 0.0005), Rules()))
        b = engine.metrics(engine.buy_and_hold(c, 10, 300, Costs("t", 0.004, 0.0005), Rules()))
        self.assertEqual(a, b)


class DataChecksTests(unittest.TestCase):
    def test_good_series_passes(self):
        engine.check_series(gappy())

    def test_duplicate_candle_is_rejected(self):
        c = gappy()
        with self.assertRaises(EngineError) as ctx:
            engine.check_series(c[:3] + [c[2]] + c[3:])
        self.assertIn("duplicate", str(ctx.exception))

    def test_unsorted_is_rejected(self):
        c = gappy()
        with self.assertRaises(EngineError) as ctx:
            engine.check_series([c[1], c[0]] + c[2:])
        self.assertIn("chronological", str(ctx.exception))

    def test_missing_day_is_rejected(self):
        c = gappy()
        with self.assertRaises(EngineError) as ctx:
            engine.check_series(c[:4] + c[5:])
        self.assertIn("missing", str(ctx.exception))

    def test_deliberately_skipped_day_is_allowed_only_when_listed(self):
        c = gappy()
        engine.check_series(c[:4] + c[5:], skipped_times=[c[4].time])
        with self.assertRaises(EngineError):
            engine.check_series(c[:4] + c[6:], skipped_times=[c[4].time])

    def test_off_grid_and_impossible_prices_are_rejected(self):
        c = gappy()
        with self.assertRaises(EngineError):
            engine.check_series(c[:2] + [Candle(c[2].time + 60, 1, 2, 0.5, 1.5, 1)])
        with self.assertRaises(EngineError):
            engine.check_series([Candle(T0, 10.0, 8.0, 9.0, 11.0, 1.0)])

    def test_incomplete_candle_is_rejected(self):
        c = gappy()
        engine.assert_completed(c, c[-1].time + DAY)
        with self.assertRaises(EngineError) as ctx:
            engine.assert_completed(c, c[-1].time + DAY - 1)
        self.assertIn("incomplete", str(ctx.exception))

    def test_simulate_rejects_bad_ranges_and_signals(self):
        c = gappy()
        for a, b in ((0, 5), (5, 5), (3, 99)):
            with self.assertRaises(EngineError):
                engine.simulate(c, sig(12, []), a, b, ZERO, EXACT)
        with self.assertRaises(EngineError):
            engine.simulate(c, [2] * 12, 1, 5, ZERO, EXACT)


class StrategyTests(unittest.TestCase):
    def closes(self, values):
        return [Candle(T0 + i * DAY, v, v + 1, v - 0.5, v, 1.0) for i, v in enumerate(values)]

    def test_ma_trend_by_hand(self):
        self.assertEqual(strategy.ma_trend(3)(self.closes([1, 2, 3, 4, 5])), [0, 0, 1, 1, 1])
        self.assertEqual(strategy.ma_trend(3)(self.closes([5, 4, 3, 2, 1])), [0, 0, 0, 0, 0])

    def test_close_equal_to_average_is_not_long(self):
        self.assertEqual(strategy.ma_trend(3)(self.closes([2, 2, 2, 2])), [0, 0, 0, 0])

    def test_matches_a_naive_recomputation_on_the_toy_series(self):
        c = toy.toy_candles(400)
        for n in (2, 5, 50, 200):
            naive = [1 if i >= n - 1 and c[i].close > sum(x.close for x in c[i - n + 1:i + 1]) / n else 0
                     for i in range(len(c))]
            self.assertEqual(strategy.ma_trend(n)(c), naive)

    def test_average_includes_the_current_completed_close_and_nothing_later(self):
        s = strategy.ma_trend(2)(self.closes([10, 10, 11]))      # avg(10, 11) = 10.5 < 11
        self.assertEqual(s, [0, 0, 1])


class LookAheadTests(unittest.TestCase):
    def test_every_prefix_gives_the_same_signal_as_the_full_series(self):
        c = toy.toy_candles(260)
        for n in (5, 20, 50):
            full = strategy.ma_trend(n)(c)
            for k in range(len(c)):
                self.assertEqual(strategy.ma_trend(n)(c[:k + 1])[k], full[k])

    def test_rewriting_the_future_does_not_change_past_signals(self):
        c = toy.toy_candles(300)
        s = strategy.ma_trend(20)
        self.assertTrue(strategy.assert_causal(s, c, points=range(len(c))))

    def test_guard_catches_a_strategy_that_peeks_at_the_next_close(self):
        def peeker(candles):
            return [1 if i + 1 < len(candles) and candles[i + 1].close > candles[i].close else 0
                    for i in range(len(candles))]
        with self.assertRaises(EngineError) as ctx:
            strategy.assert_causal(peeker, toy.toy_candles(120), points=range(120))
        self.assertIn("look-ahead", str(ctx.exception))

    def test_guard_catches_a_centered_moving_average(self):
        def centered(candles, w=5):
            h = w // 2
            out = []
            for i in range(len(candles)):
                lo, hi = max(0, i - h), min(len(candles), i + h + 1)
                avg = sum(x.close for x in candles[lo:hi]) / (hi - lo)
                out.append(1 if candles[i].close > avg else 0)
            return out
        with self.assertRaises(EngineError):
            strategy.assert_causal(centered, toy.toy_candles(120), points=range(120))

    def test_guard_catches_whole_series_normalisation(self):
        def normalised(candles):
            top = max(x.close for x in candles)
            return [1 if x.close / top > 0.5 else 0 for x in candles]
        with self.assertRaises(EngineError):
            strategy.assert_causal(normalised, toy.toy_candles(200), points=range(200))

    def test_simulation_up_to_bar_k_ignores_all_later_candles(self):
        c = toy.toy_candles(400)
        k = 250
        s = strategy.ma_trend(25)
        base = engine.simulate(c, s(c), 30, k + 1, Costs("t", 0.004, 0.0005), Rules())
        wild = c[:k + 1] + [Candle(x.time, 5.0, 9.0, 1.0, 7.0, 1.0) for x in c[k + 1:]]
        other = engine.simulate(wild, s(wild), 30, k + 1, Costs("t", 0.004, 0.0005), Rules())
        self.assertEqual(base["equity"], other["equity"])
        self.assertEqual(base["trades"], other["trades"])
        self.assertEqual(base["orders"], other["orders"])

    def test_full_run_prefix_is_unchanged_by_future_changes(self):
        c = toy.toy_candles(400)
        s = strategy.ma_trend(25)
        full = engine.simulate(c, s(c), 30, 400, Costs("t", 0.004, 0.0005), Rules())
        wild = c[:301] + [Candle(x.time, 3.0, 4.0, 2.0, 3.5, 1.0) for x in c[301:]]
        alt = engine.simulate(wild, s(wild), 30, 400, Costs("t", 0.004, 0.0005), Rules())
        cut = 300 - 30 + 1                                   # equity points for bars 30..300
        self.assertEqual(full["equity"][:cut], alt["equity"][:cut])


class SplitTests(unittest.TestCase):
    def test_sixty_twenty_twenty_split_is_chronological_and_complete(self):
        sp = splits_mod.make_splits(3358)
        self.assertEqual(sp["train"], (200, 2014))
        self.assertEqual(sp["validation"], (2014, 2685))
        self.assertEqual(sp["test"], (2685, 3358))
        self.assertEqual(sp["train"][1], sp["validation"][0])        # no gap, no overlap
        self.assertEqual(sp["validation"][1], sp["test"][0])
        self.assertEqual(sp["test"][1], 3358)
        self.assertAlmostEqual(2014 / 3358, 0.6, 2)

    def test_split_depends_only_on_row_count(self):
        self.assertEqual(splits_mod.make_splits(1000), splits_mod.make_splits(1000))

    def test_too_short_series_is_refused(self):
        with self.assertRaises(EngineError):
            splits_mod.make_splits(300)

    def test_validation_run_ignores_the_test_window(self):
        c = toy.toy_candles(1000)
        sp = splits_mod.make_splits(1000, warmup=60)
        s = strategy.ma_trend(50)
        a = engine.simulate(c, s(c), *sp["validation"], Costs("t", 0.004, 0.0005), Rules())
        wild = c[:sp["test"][0]] + [Candle(x.time, 2.0, 3.0, 1.0, 2.5, 1.0) for x in c[sp["test"][0]:]]
        b = engine.simulate(wild, s(wild), *sp["validation"], Costs("t", 0.004, 0.0005), Rules())
        self.assertEqual(a["equity"], b["equity"])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.c = toy.toy_candles(1000)
        self.sp = splits_mod.make_splits(1000, warmup=200)

    def test_selection_never_looks_at_the_test_window(self):
        a = selection.select(self.c, self.sp)
        wild = self.c[:self.sp["test"][0]] + [Candle(x.time, 2.0, 3.0, 1.0, 2.5, 1.0)
                                              for x in self.c[self.sp["test"][0]:]]
        b = selection.select(wild, self.sp)
        self.assertEqual(a, b)

    def test_candidates_are_scored_on_identical_training_bars(self):
        res = selection.select(self.c, self.sp)
        self.assertEqual({r["train"]["bars"] for r in res["rows"]}, {self.sp["train"][1] - 200})
        self.assertEqual([r["n"] for r in res["rows"]], [50, 100, 150, 200])

    def test_selected_period_is_eligible_and_has_the_best_validation_score(self):
        res = selection.select(self.c, self.sp)
        if res["selected_n"] is None:
            self.skipTest("toy series produced no eligible candidate")
        ok = [r for r in res["rows"] if r["eligible"]]
        best = max(r["score"] for r in ok)
        self.assertEqual(next(r for r in ok if r["n"] == res["selected_n"])["score"], best)

    def test_no_eligible_candidate_means_nothing_selected_and_no_test(self):
        falling = [Candle(T0 + i * DAY, 1000.0 - i / 2, 1001.0 - i / 2, 998.0 - i / 2, 999.0 - i / 2, 1.0)
                   for i in range(1000)]
        res = selection.select(falling, self.sp)
        self.assertIsNone(res["selected_n"])
        frozen = selection.freeze(res, self.sp, {"sha256": "a" * 64}, falling)
        self.assertEqual(selection.evaluate_test(falling, frozen, self.sp)["status"], "not_evaluated")

    def freeze(self):
        res = selection.select(self.c, self.sp)
        if res["selected_n"] is None:
            res["selected_n"] = 100          # force a choice so the registry can be tested
        return selection.freeze(res, self.sp, {"sha256": "b" * 64}, self.c)

    def test_frozen_choice_cannot_be_altered(self):
        f = self.freeze()
        selection.verify_frozen(f)
        f["selected_n"] = 50 if f["selected_n"] != 50 else 200
        with self.assertRaises(EngineError):
            selection.verify_frozen(f)
        with self.assertRaises(EngineError):
            selection.evaluate_test(self.c, f, self.sp)

    def test_test_window_is_evaluated_once_and_a_second_look_is_refused(self):
        f = self.freeze()
        with tempfile.TemporaryDirectory() as reg, tempfile.TemporaryDirectory() as out:
            first = selection.evaluate_test(self.c, f, self.sp, registry_dir=reg, out_registry_dir=out, run_id="1")
            self.assertEqual(first["status"], "evaluated")
            self.assertEqual(first["evaluation_number"], 1)
            self.assertEqual(len(first["results"]), 4)
            # the published record from run 1 becomes the registry of run 2
            second = selection.evaluate_test(self.c, f, self.sp, registry_dir=out, run_id="2")
            self.assertEqual(second["status"], "already_evaluated")
            self.assertNotIn("results", second)
            third = selection.evaluate_test(self.c, f, self.sp, registry_dir=out,
                                            out_registry_dir=out, allow_reeval=True, run_id="3")
            self.assertTrue(third["re_evaluation"])
            self.assertEqual(third["evaluation_number"], 2)
            with open(os.path.join(out, selection.test_key(f) + ".json"), encoding="utf-8") as fh:
                kept = json.load(fh)
            self.assertEqual(kept["run_id"], "1")                       # original record not overwritten

    def test_all_four_cost_scenarios_are_present_with_benchmarks(self):
        f = self.freeze()
        r = selection.evaluate_test(self.c, f, self.sp)["results"]
        self.assertEqual(len(r), 4)
        for name, block in r.items():
            self.assertEqual(set(block), {"strategy", "buy_and_hold", "cash"})
            self.assertEqual(block["cash"]["total_return"], 0.0)
        self.assertEqual([k.fee for k in selection.COST_GRID], [0.004, 0.004, 0.001, 0.001])
        self.assertEqual([k.slip for k in selection.COST_GRID], [0.0005, 0.002, 0.0005, 0.002])


class ToyTests(unittest.TestCase):
    def test_toy_series_is_deterministic_and_labelled(self):
        self.assertEqual(toy.toy_candles(50), toy.toy_candles(50))
        self.assertIn("NOT MARKET DATA", toy.TOY_LABEL)
        engine.check_series(toy.toy_candles(500))


if __name__ == "__main__":
    unittest.main()
