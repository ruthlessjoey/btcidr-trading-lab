import unittest
from decimal import Decimal

from tmm_core.offline_portfolio import MarketSpec, SyntheticMark, SyntheticPortfolioLedger
from tmm_core.offline_settlement import (
    ExecutionRules, OfflineSettlementController, SyntheticBar,
)


class Gateway:
    def __init__(self, permitted):
        self.permitted = permitted
        self.calls = 0
    def propose(self, *, proposals, timestamp):
        self.calls += 1
        return {"permitted_deltas": dict(self.permitted)}


class Settlement:
    def __init__(self):
        self.calls = []
    def settle_sell(self, **kwargs):
        self.calls.append(kwargs)


class OfflineSettlementTests(unittest.TestCase):
    def setUp(self):
        self.ledger = SyntheticPortfolioLedger(
            account_id="a", account_currency="USDT", opening_cash="10000",
            markets={"BTC/USDT": MarketSpec("BTC/USDT", "BTC", "USDT")},
        )
        self.ledger.update_marks(
            {"BTC/USDT": SyntheticMark("BTC/USDT", "100", 100, "5000")},
            timestamp=100,
        )
        self.gateway, self.settlement = Gateway({"BTC/USDT": "1"}), Settlement()
        self.controller = OfflineSettlementController(
            proposal_client=self.gateway, settlement=self.settlement,
            ledger=self.ledger,
            rules={"BTC/USDT": ExecutionRules("0.001", "0.1", fee_bps="10",
                                               half_spread_bps="5", slippage_bps="5",
                                               max_volume_participation="0.05")},
        )
        self.bar = SyntheticBar("BTC/USDT", 101, "100", "105", "95", "102", "10")

    def test_buy_applies_adverse_price_fee_and_volume_cap(self):
        result = self.controller.process(
            proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": self.bar}, timestamp=101
        )[0]
        self.assertEqual(result.filled_quantity, Decimal("0.500"))
        self.assertGreater(result.fill_price, Decimal("100"))
        self.assertGreater(result.fee_quote, 0)
        self.assertEqual(self.ledger.snapshot_holdings("a")["BTC/USDT"], "0.500")

    def test_sell_partial_fill_releases_reservation(self):
        self.gateway.permitted = {"BTC/USDT": "-1"}
        result = self.controller.process(
            proposals={"BTC/USDT": "-1"}, bars={"BTC/USDT": self.bar}, timestamp=101
        )[0]
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(len(self.settlement.calls), 1)
        self.assertEqual(self.settlement.calls[0]["authorized_quantity"], Decimal("1"))
        self.assertEqual(self.settlement.calls[0]["filled_quantity"], Decimal("0.500"))

    def test_gateway_must_authorize_exact_market_set(self):
        self.gateway.permitted = {}
        with self.assertRaises(ValueError):
            self.controller.process(
                proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": self.bar}, timestamp=101
            )

    def test_missing_or_wrong_time_bar_rejected(self):
        bad = SyntheticBar("BTC/USDT", 100, "100", "105", "95", "102", "10")
        with self.assertRaises(ValueError):
            self.controller.process(
                proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": bad}, timestamp=101
            )

    def test_invalid_ohlcv_and_unknown_rules_rejected(self):
        bad = SyntheticBar("BTC/USDT", 101, "100", "90", "95", "102", "10")
        with self.assertRaises(ValueError):
            self.controller.process(
                proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": bad}, timestamp=101
            )

    def test_zero_liquidity_sell_is_settled_unfilled(self):
        self.gateway.permitted = {"BTC/USDT": "-1"}
        no_volume = SyntheticBar("BTC/USDT", 101, "100", "105", "95", "102", "0")
        result = self.controller.process(
            proposals={"BTC/USDT": "-1"}, bars={"BTC/USDT": no_volume}, timestamp=101
        )[0]
        self.assertEqual(result.status, "UNFILLED")
        self.assertEqual(self.settlement.calls[0]["filled_quantity"], Decimal("0"))


if __name__ == "__main__":
    unittest.main()
