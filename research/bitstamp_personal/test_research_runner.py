import unittest
from decimal import Decimal, getcontext

from research_runner import (
    backtest,
    evaluate_market,
    make_signals,
    split_ranges,
    validate_preregistered_run,
    _epoch,
)


def candle(open_price="100", close_price="100", volume="10000", low_price=None):
    low = min(Decimal(open_price), Decimal(close_price)) if low_price is None else Decimal(low_price)
    return {
        "open": open_price,
        "high": str(max(Decimal(open_price), Decimal(close_price))),
        "low": str(low),
        "close": close_price,
        "volume": volume,
    }


class ResearchRunnerTests(unittest.TestCase):
    def test_sma_signals_are_causal_and_long_only(self):
        closes_a = [str(100 + index) for index in range(60)]
        closes_b = closes_a[:51] + [str(1000 - index) for index in range(51, 60)]
        candles_a = [{"close": value} for value in closes_a]
        candles_b = [{"close": value} for value in closes_b]

        signals_a = make_signals("SMA20_50_LONG_ONLY", candles_a)
        signals_b = make_signals("SMA20_50_LONG_ONLY", candles_b)

        self.assertEqual(signals_a[:51], signals_b[:51])
        self.assertEqual(signals_a[49], 1)
        self.assertTrue(set(signals_a).issubset({0, 1}))

    def test_sma_threshold_uses_fixed_precision_independent_of_global_context(self):
        previous_precision = getcontext().prec
        try:
            getcontext().prec = 8
            closes = ["100"] * 49 + ["100.000000000000000000000000000000000001"]
            candles = [{"close": value} for value in closes]
            signals = make_signals("SMA20_50_LONG_ONLY", candles)
            self.assertEqual(signals[-1], 1)
            self.assertEqual(getcontext().prec, 8)
        finally:
            getcontext().prec = previous_precision

    def test_backtest_uses_and_restores_fixed_decimal_context(self):
        previous_precision = getcontext().prec
        try:
            getcontext().prec = 7
            result = backtest(
                [candle(), candle("100", "101")],
                [1, 0],
                fee_bps=Decimal("16"),
                half_spread_bps=Decimal("5"),
                slippage_bps=Decimal("10"),
            )
            self.assertTrue(result["final_equity"])
            self.assertEqual(getcontext().prec, 7)
        finally:
            getcontext().prec = previous_precision

    def test_rsi_strategy_enters_after_decline_and_exits_after_reversal(self):
        closes = [str(100 - index) for index in range(20)]
        closes.extend(str(value) for value in (120, 130, 140, 150, 160, 170))
        candles = [{"close": value} for value in closes]

        signals = make_signals("RSI14_MEAN_REVERSION_LONG_ONLY", candles)

        self.assertEqual(signals[14], 1)
        self.assertEqual(signals[-1], 0)
        self.assertTrue(set(signals).issubset({0, 1}))

    def test_backtest_executes_at_next_open_and_accounts_for_costs(self):
        candles = [
            candle("100", "100"),
            candle("100", "105"),
            candle("110", "110"),
            candle("110", "110"),
        ]
        signals = [1, 0, 0, 0]

        result = backtest(
            candles, signals,
            fee_bps=Decimal("16"),
            half_spread_bps=Decimal("5"),
            slippage_bps=Decimal("10"),
        )
        free_cost_result = backtest(
            candles, signals,
            fee_bps=Decimal("0"),
            half_spread_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
        )

        self.assertEqual(result["fill_count"], 2)
        self.assertEqual(result["closed_cycles"], 1)
        self.assertEqual(result["sample_status"], "INSUFFICIENT_CLOSED_CYCLES")
        self.assertGreater(Decimal(result["fees_paid"]), Decimal("0"))
        self.assertGreater(Decimal(result["final_equity"]), Decimal("10000"))
        self.assertLess(
            Decimal(result["final_equity"]),
            Decimal(free_cost_result["final_equity"]),
        )

    def test_intrabar_low_drawdown_is_not_hidden_by_candle_close(self):
        candles = [
            candle("100", "100"),
            candle("100", "105", low_price="70"),
            candle("110", "110"),
            candle("110", "110"),
        ]
        result = backtest(
            candles, [1, 0, 0, 0],
            fee_bps=Decimal("16"),
            half_spread_bps=Decimal("5"),
            slippage_bps=Decimal("10"),
        )
        self.assertGreater(Decimal(result["max_drawdown_intrabar_pct"]), Decimal("20"))
        self.assertLess(
            Decimal(result["max_drawdown_close_pct"]),
            Decimal(result["max_drawdown_intrabar_pct"]),
        )
        self.assertEqual(
            result["max_drawdown_pct"],
            result["max_drawdown_intrabar_pct"],
        )

    def test_backtest_rejects_invalid_candle_low(self):
        candles = [candle(), candle("100", "105", low_price="101")]
        with self.assertRaisesRegex(ValueError, "candle low"):
            backtest(
                candles, [1, 0],
                fee_bps=Decimal("16"),
                half_spread_bps=Decimal("5"),
                slippage_bps=Decimal("10"),
            )

    def test_zero_prior_volume_prevents_entry(self):
        candles = [candle(volume="0"), candle("100", "101", volume="10000")]
        result = backtest(
            candles, [1, 1],
            fee_bps=Decimal("16"),
            half_spread_bps=Decimal("5"),
            slippage_bps=Decimal("10"),
        )
        self.assertEqual(result["fill_count"], 0)
        self.assertEqual(result["open_position_at_end"], "0E-12")

    def test_preregistered_date_boundaries_map_to_exact_utc_midnight(self):
        # The final requested candle must close exactly at 2026-11-01 00:00 UTC.
        self.assertEqual(_epoch("2024-01-01"), 1704067200)
        self.assertEqual(_epoch("2026-11-01"), 1793491200)

    def test_date_boundary_rejects_non_iso_date(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            _epoch("2026/11/01")

    def test_runner_accepts_only_the_frozen_preregistered_configuration(self):
        symbols = "btcusd,ethusd,xrpusd,dogeusd,shibusd,pepeusd,solusd"
        self.assertEqual(
            validate_preregistered_run("2024-01-01", "2026-11-01", symbols, 3, True),
            ["btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd"],
        )

    def test_runner_rejects_date_range_override(self):
        with self.assertRaisesRegex(ValueError, "date range differs"):
            validate_preregistered_run(
                "2024-01-01", "2026-10-01",
                "btcusd,ethusd,xrpusd,dogeusd,shibusd,pepeusd,solusd", 3, True,
            )

    def test_runner_rejects_unregistered_symbols_and_universe_changes(self):
        with self.assertRaisesRegex(ValueError, "market universe differs"):
            validate_preregistered_run(
                "2024-01-01", "2026-11-01",
                "btcusd,ethusd,xrpusd,dogeusd,shibusd,pepeusd,solusd,bonkusd", 3, True,
            )
        with self.assertRaisesRegex(ValueError, "market universe differs"):
            validate_preregistered_run(
                "2024-01-01", "2026-11-01", "btcusd", 3, True,
            )

    def test_runner_rejects_lower_minimum_or_missing_meme_requirement(self):
        symbols = "btcusd,ethusd,xrpusd,dogeusd,shibusd,pepeusd,solusd"
        with self.assertRaisesRegex(ValueError, "minimum market count differs"):
            validate_preregistered_run("2024-01-01", "2026-11-01", symbols, 1, True)
        with self.assertRaisesRegex(ValueError, "meme-market requirement differs"):
            validate_preregistered_run("2024-01-01", "2026-11-01", symbols, 3, False)

    def test_chronological_splits_have_exact_embargoes(self):
        ranges = split_ranges(10000, embargo_bars=50)
        train_start, train_end = ranges["train"]
        validation_start, validation_end = ranges["validation"]
        holdout_start, holdout_end = ranges["holdout"]

        self.assertEqual(train_start, 0)
        self.assertEqual(validation_start - train_end, 50)
        self.assertEqual(holdout_start - validation_end, 50)
        self.assertEqual(holdout_end, 10000)
        self.assertLess(train_end, validation_start)
        self.assertLess(validation_end, holdout_start)

    def test_market_with_any_coverage_gap_is_not_backtested(self):
        result = evaluate_market(
            {"market_symbol": "btcusd"},
            {
                "market_symbol": "btcusd",
                "pair": "BTC/USD",
                "row_count": 5000,
                "dataset_sha256": "a" * 64,
                "coverage_status": "GAPS_DETECTED_BACKTEST_BLOCKED",
                "gap_count": 1,
                "candles": [],
            },
        )
        self.assertEqual(result["promotion_status"], "BLOCKED_GAPS")
        self.assertEqual(result["results"], {})


    def test_backtest_rejects_nonbinary_and_boolean_signals(self):
        for signals in ([2, 0], [-1, 0], [True, 0], [0.0, 1]):
            with self.subTest(signals=signals), self.assertRaisesRegex(ValueError, "signal"):
                backtest(
                    [candle(), candle()], signals,
                    fee_bps=Decimal("16"), half_spread_bps=Decimal("5"),
                    slippage_bps=Decimal("10"),
                )

    def test_backtest_rejects_nonfinite_and_impossible_ohlcv(self):
        invalid_candles = (
            [{**candle(), "open": "NaN"}, candle()],
            [candle(), {**candle(), "close": "Infinity"}],
            [candle(), {**candle(), "volume": "-1"}],
            [candle(), {**candle(), "high": "99"}],
            [candle(), {**candle(), "low": "101"}],
            [candle(), {**candle(), "open": True}],
        )
        for candles in invalid_candles:
            with self.subTest(candles=candles), self.assertRaises(ValueError):
                backtest(
                    candles, [0, 1],
                    fee_bps=Decimal("16"), half_spread_bps=Decimal("5"),
                    slippage_bps=Decimal("10"),
                )

    def test_backtest_rejects_invalid_execution_cost_assumptions(self):
        invalid_costs = (
            {"fee_bps": Decimal("-1"), "half_spread_bps": Decimal("5"), "slippage_bps": Decimal("10")},
            {"fee_bps": Decimal("NaN"), "half_spread_bps": Decimal("5"), "slippage_bps": Decimal("10")},
            {"fee_bps": Decimal("10000"), "half_spread_bps": Decimal("5"), "slippage_bps": Decimal("10")},
            {"fee_bps": Decimal("16"), "half_spread_bps": Decimal("5000"), "slippage_bps": Decimal("5000")},
            {"fee_bps": Decimal("16"), "half_spread_bps": Decimal("5"), "slippage_bps": Decimal("Infinity")},
        )
        for costs in invalid_costs:
            with self.subTest(costs=costs), self.assertRaises(ValueError):
                backtest([candle(), candle()], [0, 1], **costs)


if __name__ == "__main__":
    unittest.main()
