import unittest
from decimal import Decimal as D

from tmm_core.portfolio import (
    MarketIntent, PortfolioError, PortfolioPolicy, allocate_long_only_portfolio,
)
from tmm_core.market_rules import MarketRules, MarketRulesError
from tmm_core.multi_market_backtest import (
    MultiMarketBacktestError, run_multi_market_backtest,
)


class CryptoSpotCoreTests(unittest.TestCase):
    NOW = 1800000000

    def test_allocator_enforces_shared_gross_and_asset_caps(self):
        intents = [
            MarketIntent("BTC/USDT", "BTC", "USDT", ".7", "60000", "1", self.NOW, self.NOW),
            MarketIntent("BTC/IDR", "BTC", "IDR", ".7", "1500000000", "0.000067", self.NOW, self.NOW),
            MarketIntent("ETH/USDT", "ETH", "USDT", ".5", "3000", "1", self.NOW, self.NOW),
        ]
        rows = allocate_long_only_portfolio(
            account_equity="10000", account_currency="USD", decision_time=self.NOW,
            intents=intents,
            policy=PortfolioPolicy(max_gross_exposure=".8", max_market_weight=".7",
                                   max_base_asset_weight=".5", max_quote_asset_weight=".8"),
        )
        self.assertLessEqual(sum((r.weight for r in rows), D("0")), D(".8"))
        btc = sum((r.weight for r in rows if r.base_asset == "BTC"), D("0"))
        self.assertLessEqual(btc, D(".5"))

    def test_allocator_rejects_stale_future_and_short_inputs(self):
        for weight, price_time in (("-.1", self.NOW), (".2", self.NOW + 1), (".2", self.NOW - 1000)):
            with self.subTest(weight=weight, price_time=price_time), self.assertRaises(PortfolioError):
                allocate_long_only_portfolio(
                    account_equity=1000, account_currency="USD", decision_time=self.NOW,
                    intents=[MarketIntent("BTC/USD", "BTC", "USD", weight, 100, 1,
                                          price_time, price_time)],
                )

    def test_quote_equal_to_account_currency_requires_identity_fx(self):
        with self.assertRaises(PortfolioError):
            allocate_long_only_portfolio(
                account_equity=1000, account_currency="USD", decision_time=self.NOW,
                intents=[MarketIntent("BTC/USD", "BTC", "USD", ".2", 100, "1.01",
                                      self.NOW, self.NOW)],
            )

    def test_market_rules_round_buy_up_sell_down_and_quantity_down(self):
        rules = MarketRules(".05", ".005").validated()
        self.assertEqual(rules.round_price(D("1.021"), "BUY"), D("1.05"))
        self.assertEqual(rules.round_price(D("1.029"), "SELL"), D("1.00"))
        self.assertEqual(rules.round_quantity(D("1.019")), D("1.015"))

    def test_market_rules_reject_invalid_and_enforce_minimums(self):
        with self.assertRaises(MarketRulesError):
            MarketRules("0", ".1").validated()
        rules = MarketRules(".01", ".1", ".5", "10").validated()
        self.assertFalse(rules.meets_minimums(D(".4"), D("100")))
        self.assertFalse(rules.meets_minimums(D(".5"), D("19")))
        self.assertTrue(rules.meets_minimums(D(".5"), D("20")))

    def make_bars(self, prices=(10, 10, 10, 10), volumes=(1000, 1000, 1000, 1000)):
        bars = []
        for i, (price, volume) in enumerate(zip(prices, volumes)):
            op = i * 60
            close = op + 59
            markets = {
                "BTC/IDR": {"open_quote": str(price), "close_quote": str(price),
                            "open_fx": "1", "close_fx": "1", "volume_base": str(volume),
                            "open_fx_timestamp": op, "close_fx_timestamp": close},
                "ETH/USDT": {"open_quote": str(price), "close_quote": str(price),
                             "open_fx": "1", "close_fx": "1", "volume_base": str(volume),
                             "open_fx_timestamp": op, "close_fx_timestamp": close},
            }
            bars.append({"timestamp": close, "open_timestamp": op, "markets": markets})
        return bars

    def make_signals(self, weights=None):
        weights = weights or {"BTC/IDR": ".4", "ETH/USDT": ".4"}
        return [{"timestamp": i * 60 + 59, "data_cutoff_timestamp": i * 60 + 59,
                 "target_weights": dict(weights)} for i in range(4)]

    def costs(self, participation="1", fee="0", spread="0", slippage="0"):
        return {m: {"fee_bps": fee, "half_spread_bps": spread,
                    "slippage_bps": slippage, "max_volume_participation": participation}
                for m in ("BTC/IDR", "ETH/USDT")}

    def rules(self, *, tick=".000000000001", step=".000000000001",
              min_qty="0", min_notional="0"):
        return {m: MarketRules(tick, step, min_qty, min_notional)
                for m in ("BTC/IDR", "ETH/USDT")}

    def run_bt(self, bars=None, signals=None, costs=None, rules=None, **kwargs):
        return run_multi_market_backtest(
            bars=bars or self.make_bars(), signals=signals or self.make_signals(),
            market_costs=costs or self.costs(), market_rules=rules or self.rules(),
            initial_cash="1000", **kwargs,
        )

    def test_backtest_uses_one_shared_cash_pool_and_next_bar_open(self):
        result = self.run_bt()
        self.assertEqual(D(result["final_cash"]), D("200"))
        self.assertEqual(D(result["final_holdings"]["BTC/IDR"]), D("40"))
        self.assertEqual(D(result["final_holdings"]["ETH/USDT"]), D("40"))
        self.assertTrue(all(fill["timestamp"] > fill["signal_timestamp"] for fill in result["fills"]))

    def test_backtest_requires_complete_market_rules(self):
        with self.assertRaises(MultiMarketBacktestError):
            self.run_bt(rules={"BTC/IDR": MarketRules(".01", ".001")})

    def test_backtest_respects_minimum_order_and_tick_rules(self):
        bars = self.make_bars()
        bars[1]["markets"]["BTC/IDR"]["open_quote"] = "10.2"
        weights = {"BTC/IDR": ".001", "ETH/USDT": "0"}
        signals = self.make_signals(weights)
        rules = self.rules(tick="1", step=".1", min_qty=".5", min_notional="5")
        result = self.run_bt(bars=bars, signals=signals, rules=rules)
        self.assertFalse(any(f["side"] == "BUY" for f in result["fills"]))
        self.assertEqual(D(result["final_cash"]), D("1000"))

    def test_drawdown_stop_latches_and_liquidates_on_next_open(self):
        bars = self.make_bars(prices=(10, 10, 10, 5))
        bars[2]["markets"]["BTC/IDR"]["close_quote"] = "5"
        bars[2]["markets"]["ETH/USDT"]["close_quote"] = "5"
        result = self.run_bt(bars=bars, max_portfolio_drawdown=".2")
        self.assertTrue(result["risk_halted"])
        self.assertEqual(result["risk_halt_timestamp"], 179)
        self.assertEqual(result["risk_halt_reason"], "MAX_PORTFOLIO_DRAWDOWN")
        self.assertTrue(result["liquidation_complete"])
        self.assertTrue(all(D(q) == 0 for q in result["final_holdings"].values()))
        self.assertEqual([f["side"] for f in result["fills"][-2:]], ["SELL", "SELL"])

    def test_partial_liquidation_keeps_risk_halt_latched(self):
        bars = self.make_bars(prices=(10, 10, 10, 5), volumes=(1000, 1000, 10, 10))
        bars[2]["markets"]["BTC/IDR"]["close_quote"] = "5"
        bars[2]["markets"]["ETH/USDT"]["close_quote"] = "5"
        result = self.run_bt(bars=bars, costs=self.costs(participation=".1"),
                             max_portfolio_drawdown=".2")
        self.assertTrue(result["risk_halted"])
        self.assertFalse(result["liquidation_complete"])
        self.assertTrue(all(f["side"] == "SELL" for f in result["fills"][-2:]))
        self.assertTrue(all(D(q) > 0 for q in result["final_holdings"].values()))


if __name__ == "__main__":
    unittest.main()
