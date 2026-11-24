import unittest
from decimal import Decimal as D

from tmm_core.exposure_policy import (
    ExposureMark, ExposurePolicy, ExposurePolicyError, authorize_exposure,
)


class ExposurePolicyTests(unittest.TestCase):
    def mark(self, market, base, quote="USDT", unit="100", liquidity="10000", ts=100):
        return ExposureMark(market, base, quote, unit, ts, liquidity)

    def authorize(self, holdings, proposals, marks, **kwargs):
        return authorize_exposure(account_equity="1000", holdings=holdings,
                                  proposals=proposals, marks=marks,
                                  timestamp=100, **kwargs)

    def test_buy_is_capped_by_market_weight(self):
        result = self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "9"},
                                {"BTC/USDT": self.mark("BTC/USDT", "BTC")})
        self.assertLessEqual(result["BTC/USDT"] * D("100"), D("250.00000000000000000001"))

    def test_gross_cap_scales_buys_across_markets(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC"),
                 "ETH/USDT": self.mark("ETH/USDT", "ETH")}
        result = self.authorize({"BTC/USDT": "0", "ETH/USDT": "0"},
                                {"BTC/USDT": "9", "ETH/USDT": "9"}, marks)
        gross = sum((v * D("100") for v in result.values()), D("0"))
        self.assertLessEqual(gross, D("950.00000000000000000001"))
        self.assertGreater(result["BTC/USDT"], 0)
        self.assertGreater(result["ETH/USDT"], 0)

    def test_base_asset_concentration_aggregates_across_quotes(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC", "USDT"),
                 "BTC/USDC": self.mark("BTC/USDC", "BTC", "USDC")}
        result = self.authorize({m: "0" for m in marks}, {m: "9" for m in marks}, marks)
        self.assertLessEqual(sum((v * D("100") for v in result.values()), D("0")),
                             D("350.00000000000000000001"))

    def test_quote_asset_concentration_aggregates_markets(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC", "USDT"),
                 "ETH/USDT": self.mark("ETH/USDT", "ETH", "USDT")}
        result = self.authorize({m: "0" for m in marks}, {m: "9" for m in marks}, marks)
        self.assertLessEqual(sum((v * D("100") for v in result.values()), D("0")),
                             D("600.00000000000000000001"))

    def test_liquidity_capacity_caps_buy_notional(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC", liquidity="50")}
        result = self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "9"}, marks)
        self.assertLessEqual(result["BTC/USDT"] * D("100"), D("50.00000000000000000001"))

    def test_existing_excess_blocks_buys_but_allows_reducing_sell(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC")}
        result = self.authorize({"BTC/USDT": "4"}, {"BTC/USDT": "2"}, marks)
        self.assertEqual(result["BTC/USDT"], 0)
        result = self.authorize({"BTC/USDT": "4"}, {"BTC/USDT": "-9"}, marks)
        self.assertEqual(result["BTC/USDT"], D("-4"))

    def test_sell_never_exceeds_inventory(self):
        marks = {"BTC/USDT": self.mark("BTC/USDT", "BTC")}
        result = self.authorize({"BTC/USDT": "0.5"}, {"BTC/USDT": "-9"}, marks)
        self.assertEqual(result["BTC/USDT"], D("-0.5"))

    def test_stale_or_future_marks_fail_closed(self):
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "1"},
                           {"BTC/USDT": self.mark("BTC/USDT", "BTC", ts=0)},
                           policy=ExposurePolicy(max_mark_age_seconds=30))
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "1"},
                           {"BTC/USDT": self.mark("BTC/USDT", "BTC", ts=101)})

    def test_missing_mark_or_inventory_market_fails_closed(self):
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "1"}, {})
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0", "ETH/USDT": "0"},
                           {"BTC/USDT": "1"},
                           {"BTC/USDT": self.mark("BTC/USDT", "BTC")})

    def test_invalid_short_inventory_and_nonfinite_inputs_fail_closed(self):
        mark = {"BTC/USDT": self.mark("BTC/USDT", "BTC")}
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "-1"}, {"BTC/USDT": "0"}, mark)
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "NaN"}, mark)

    def test_invalid_policy_caps_rejected(self):
        with self.assertRaises(ExposurePolicyError):
            self.authorize({"BTC/USDT": "0"}, {"BTC/USDT": "1"},
                           {"BTC/USDT": self.mark("BTC/USDT", "BTC")},
                           policy=ExposurePolicy(max_gross_exposure="1.1"))

    def test_empty_proposal_set_rejected(self):
        with self.assertRaises(ExposurePolicyError):
            self.authorize({}, {}, {})


if __name__ == "__main__":
    unittest.main()
