import unittest
from decimal import Decimal as D

from tmm_core.risk_overlay import (
    CovarianceRiskPolicy, RiskOverlayError, apply_covariance_risk_overlay,
)


class CovarianceRiskOverlayTests(unittest.TestCase):
    NOW = 1_800_000_000

    def series(self, values):
        return [(self.NOW - (len(values) - i) * 60, value) for i, value in enumerate(values)]

    def test_correlated_assets_are_scaled_to_period_volatility_cap(self):
        returns = [".1", "-.1"] * 10
        result = apply_covariance_risk_overlay(
            target_weights={"BTC/USDT": ".5", "ETH/USDT": ".5"},
            returns={"BTC/USDT": self.series(returns), "ETH/USDT": self.series(returns)},
            decision_time=self.NOW,
            policy=CovarianceRiskPolicy(max_period_volatility=".05", min_observations=20),
        )
        self.assertEqual(result["risk_status"], "SCALED_DOWN")
        self.assertLess(result["scale_factor"], 1)
        self.assertLessEqual(result["volatility_after"], D(".05"))
        self.assertLess(sum(result["weights"].values()), D("1"))

    def test_negative_correlation_can_reduce_risk_without_forcing_scale(self):
        values = [".1", "-.1"] * 10
        inverse = [str(-D(x)) for x in values]
        result = apply_covariance_risk_overlay(
            target_weights={"A/USDT": ".5", "B/USDT": ".5"},
            returns={"A/USDT": self.series(values), "B/USDT": self.series(inverse)},
            decision_time=self.NOW,
            policy=CovarianceRiskPolicy(max_period_volatility=".01", min_observations=20),
        )
        self.assertEqual(result["risk_status"], "WITHIN_LIMIT")
        self.assertEqual(result["scale_factor"], D("1"))
        self.assertEqual(result["volatility_after"], D("0"))

    def test_already_low_volatility_weights_are_unchanged(self):
        values = [".001", "-.001"] * 10
        result = apply_covariance_risk_overlay(
            target_weights={"BTC/USDT": ".3"},
            returns={"BTC/USDT": self.series(values)}, decision_time=self.NOW,
            policy=CovarianceRiskPolicy(max_period_volatility=".1"),
        )
        self.assertEqual(result["weights"]["BTC/USDT"], D(".3"))
        self.assertEqual(result["scale_factor"], D("1"))

    def test_misaligned_missing_stale_and_future_returns_fail_closed(self):
        values = [".01", "-.01"] * 10
        a = self.series(values)
        b = list(self.series(values))
        b[-1] = (b[-1][0] - 1, b[-1][1])
        base = dict(target_weights={"A/USDT": ".5", "B/USDT": ".5"},
                    decision_time=self.NOW,
                    policy=CovarianceRiskPolicy(max_period_volatility=".1"))
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(returns={"A/USDT": a, "B/USDT": b}, **base)
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(returns={"A/USDT": a}, **base)
        future = list(a)
        future[-1] = (self.NOW + 1, future[-1][1])
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(
                target_weights={"A/USDT": ".5"}, returns={"A/USDT": future},
                decision_time=self.NOW, policy=CovarianceRiskPolicy(".1"))
        stale = [(stamp - 100000, value) for stamp, value in a]
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(
                target_weights={"A/USDT": ".5"}, returns={"A/USDT": stale},
                decision_time=self.NOW, policy=CovarianceRiskPolicy(".1", max_return_age_seconds=10))

    def test_invalid_weights_and_insufficient_observations_are_rejected(self):
        values = [".01", "-.01"] * 10
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(
                target_weights={"A/USDT": "-.1"}, returns={"A/USDT": self.series(values)},
                decision_time=self.NOW, policy=CovarianceRiskPolicy(".1"))
        with self.assertRaises(RiskOverlayError):
            apply_covariance_risk_overlay(
                target_weights={"A/USDT": ".5"}, returns={"A/USDT": self.series(values[:5])},
                decision_time=self.NOW, policy=CovarianceRiskPolicy(".1", min_observations=20))


if __name__ == "__main__":
    unittest.main()
