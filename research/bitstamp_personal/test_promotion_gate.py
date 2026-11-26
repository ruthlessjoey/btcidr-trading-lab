import unittest
from promotion_gate import (
    MAXIMUM_FOLD_DRAWDOWN, MINIMUM_DSR_PROBABILITY, MINIMUM_FOLDS,
    MINIMUM_POSITIVE_RATIO, MINIMUM_PROFIT_FACTOR, PromotionError,
    evaluate_promotion_gate,
)

def valid_folds():
    return [{
        "fold_id": f"fold-{i}", "test_start": i * 1000,
        "test_end": i * 1000 + 900, "dataset_sha256": "a" * 64,
        "trial_registry_sha256": "c" * 64,
        "registered_trial_count": 2, "strategy_net_return": 0.05,
        "buy_hold_net_return": 0.02, "two_x_cost_net_return": 0.01,
        "max_drawdown": 0.10, "profit_factor": 1.5,
        "closed_trade_count": 8, "observations": 500,
        "deflated_sharpe_probability": 0.97, "bootstrap_excess_ci_lower": 0.005,
    } for i in range(5)]

class PromotionGateTests(unittest.TestCase):
    def test_strong_synthetic_evidence_only_qualifies_for_human_review(self):
        result = evaluate_promotion_gate(folds=valid_folds())
        self.assertEqual(result["status"], "ELIGIBLE_FOR_INDEPENDENT_HUMAN_REVIEW_NOT_PROVEN_PROFITABLE")
        self.assertEqual(result["profitability_status"], "NOT_VERIFIED")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["total_closed_trades"], 40)

    def test_requires_five_folds(self):
        with self.assertRaisesRegex(PromotionError, "at least 5"):
            evaluate_promotion_gate(folds=valid_folds()[:4])

    def test_overlapping_ranges_rejected(self):
        rows = valid_folds()
        rows[1]["test_start"] = 800
        with self.assertRaisesRegex(PromotionError, "non-overlapping"):
            evaluate_promotion_gate(folds=rows)

    def test_duplicate_fold_ids_rejected(self):
        rows = valid_folds()
        rows[1]["fold_id"] = rows[0]["fold_id"]
        with self.assertRaisesRegex(PromotionError, "unique"):
            evaluate_promotion_gate(folds=rows)

    def test_dataset_hash_must_match(self):
        rows = valid_folds()
        rows[2]["dataset_sha256"] = "b" * 64
        with self.assertRaisesRegex(PromotionError, "same immutable dataset hash"):
            evaluate_promotion_gate(folds=rows)

    def test_trial_registry_hash_must_match_across_folds(self):
        rows = valid_folds()
        rows[3]["trial_registry_sha256"] = "d" * 64
        with self.assertRaisesRegex(PromotionError, "same immutable trial registry hash"):
            evaluate_promotion_gate(folds=rows)

    def test_registered_trial_count_must_match(self):
        rows = valid_folds()
        rows[2]["registered_trial_count"] = 4
        with self.assertRaisesRegex(PromotionError, "same complete registered trial count"):
            evaluate_promotion_gate(folds=rows)

    def test_exact_schema_required(self):
        rows = valid_folds()
        del rows[0]["bootstrap_excess_ci_lower"]
        with self.assertRaisesRegex(PromotionError, "contain exactly"):
            evaluate_promotion_gate(folds=rows)
        rows = valid_folds()
        rows[0]["extra"] = "ignored?"
        with self.assertRaisesRegex(PromotionError, "contain exactly"):
            evaluate_promotion_gate(folds=rows)

    def test_boolean_and_numeric_strings_rejected(self):
        for value in (True, "0.12"):
            rows = valid_folds()
            rows[0]["strategy_net_return"] = value
            with self.subTest(value=value), self.assertRaises(PromotionError):
                evaluate_promotion_gate(folds=rows)

    def test_nonfinite_metrics_rejected(self):
        rows = valid_folds()
        rows[0]["profit_factor"] = float("inf")
        with self.assertRaisesRegex(PromotionError, "finite"):
            evaluate_promotion_gate(folds=rows)

    def test_invalid_return_drawdown_and_dsr_ranges_rejected(self):
        rows = valid_folds()
        rows[0]["strategy_net_return"] = -1.0
        with self.assertRaisesRegex(PromotionError, "greater than -100%"):
            evaluate_promotion_gate(folds=rows)
        rows = valid_folds()
        rows[0]["max_drawdown"] = 1.0
        with self.assertRaisesRegex(PromotionError, "max_drawdown"):
            evaluate_promotion_gate(folds=rows)
        rows = valid_folds()
        rows[0]["deflated_sharpe_probability"] = 1.1
        with self.assertRaisesRegex(PromotionError, "deflated_sharpe_probability"):
            evaluate_promotion_gate(folds=rows)

    def test_weak_evidence_returns_reject_status(self):
        rows = valid_folds()
        rows[0].update({
            "strategy_net_return": -0.01, "buy_hold_net_return": 0.01,
            "two_x_cost_net_return": -0.02, "max_drawdown": 0.21,
            "profit_factor": 1.19, "deflated_sharpe_probability": 0.94,
            "bootstrap_excess_ci_lower": -0.001,
        })
        result = evaluate_promotion_gate(folds=rows)
        self.assertEqual(result["status"], "REJECT_OR_RESEARCH_MORE")
        self.assertFalse(all(result["checks"].values()))

    def test_two_x_cost_and_baseline_are_independent_checks(self):
        rows = valid_folds()
        for row in rows:
            row["two_x_cost_net_return"] = -0.001
        result = evaluate_promotion_gate(folds=rows)
        self.assertFalse(result["checks"]["positive_mean_two_x_cost_return"])
        rows = valid_folds()
        for row in rows:
            row["buy_hold_net_return"] = 0.06
        result = evaluate_promotion_gate(folds=rows)
        self.assertFalse(result["checks"]["positive_mean_excess_vs_buy_hold"])

    def test_policy_is_fixed_and_not_caller_overridable(self):
        self.assertEqual(MINIMUM_FOLDS, 5)
        self.assertEqual(MINIMUM_POSITIVE_RATIO, 0.60)
        self.assertEqual(MAXIMUM_FOLD_DRAWDOWN, 0.20)
        self.assertEqual(MINIMUM_PROFIT_FACTOR, 1.20)
        self.assertEqual(MINIMUM_DSR_PROBABILITY, 0.95)
        with self.assertRaises(TypeError):
            evaluate_promotion_gate(folds=valid_folds(), minimum_folds=3)

if __name__ == "__main__":
    unittest.main()
