import unittest
from decimal import Decimal

from research_runner import (
    backtest,
    evaluate_market,
    make_signals,
    split_ranges,
)


def candle(open_price="100", close_price="100", volume="10000"):
    return {
        "open": open_price,
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


if __name__ == "__main__":
    unittest.main()
