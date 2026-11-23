"""Unit tests for the fail-closed profitability evidence gate."""
import unittest

from tmm_core.profitability_gate import evaluate_profitability_evidence


def valid_evidence():
    return {
        "dataset_sha256": "a" * 64,
        "result_sha256": "b" * 64,
        "strategy_config_sha256": "c" * 64,
        "holdout_id": "holdout-2026-v1",
        "holdout_sealed": True,
        "holdout_used_for_tuning": False,
        "source_license_approved": True,
        "point_in_time_verified": True,
        "coverage_complete": True,
        "no_lookahead_verified": True,
        "execution_costs_included": True,
        "two_x_costs_positive": True,
        "all_trials_registered": True,
        "spot_long_only_verified": True,
        "paper_only_verified": True,
        "live_trading_enabled": False,
        "venue_rules_verified": True,
        "independent_review_passed": True,
        "trial_count": 46,
        "observations": 500,
        "closed_trades": 120,
        "net_cagr": 0.18,
        "net_expectancy": 0.002,
        "win_rate": 0.61,
        "profit_factor": 1.55,
        "max_drawdown": 0.19,
        "sharpe_annualized": 1.25,
        "deflated_sharpe_probability": 0.97,
        "bootstrap_excess_lower_bound": 0.0001,
        "net_return": 0.35,
        "buy_hold_return": 0.20,
        "two_x_cost_net_return": 0.12,
        "walk_forward_folds": [
            {"fold_id": "f1", "test_start": "2022-01-01", "test_end": "2022-06-30", "net_return": 0.04, "max_drawdown": 0.12, "closed_trades": 25},
            {"fold_id": "f2", "test_start": "2022-07-01", "test_end": "2022-12-31", "net_return": 0.03, "max_drawdown": 0.15, "closed_trades": 27},
            {"fold_id": "f3", "test_start": "2023-01-01", "test_end": "2023-06-30", "net_return": -0.01, "max_drawdown": 0.18, "closed_trades": 22},
            {"fold_id": "f4", "test_start": "2023-07-01", "test_end": "2023-12-31", "net_return": 0.06, "max_drawdown": 0.10, "closed_trades": 29},
        ],
    }


class ProfitabilityEvidenceGateTests(unittest.TestCase):
    def test_complete_evidence_is_only_eligible_for_independent_review(self):
        result = evaluate_profitability_evidence(valid_evidence())
        self.assertEqual(result["promotion_status"], "READY_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(result["order_authorized"])
        self.assertFalse(result["paper_execution_authorized"])
        self.assertFalse(result["profitability_claim_authorized"])

    def test_missing_fields_fail_closed(self):
        evidence = valid_evidence()
        del evidence["dataset_sha256"]
        result = evaluate_profitability_evidence(evidence)
        self.assertEqual(result["promotion_status"], "BLOCKED")
        self.assertTrue(any("missing required fields" in x for x in result["reasons"]))

    def test_unknown_fields_fail_closed(self):
        evidence = valid_evidence()
        evidence["secret"] = "never accepted"
        result = evaluate_profitability_evidence(evidence)
        self.assertEqual(result["promotion_status"], "BLOCKED")
        self.assertTrue(any("unknown fields" in x for x in result["reasons"]))

    def test_holdout_must_be_sealed_and_untouched(self):
        for field, value in (("holdout_sealed", False), ("holdout_used_for_tuning", True)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_license_and_point_in_time_controls_are_mandatory(self):
        for field in ("source_license_approved", "point_in_time_verified", "coverage_complete", "no_lookahead_verified"):
            evidence = valid_evidence()
            evidence[field] = False
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_spot_paper_and_live_disabled_controls_are_mandatory(self):
        for field, value in (("spot_long_only_verified", False), ("paper_only_verified", False), ("live_trading_enabled", True)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_high_win_rate_alone_cannot_pass_negative_expectancy(self):
        evidence = valid_evidence()
        evidence["net_expectancy"] = -0.001
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_high_win_rate_alone_cannot_pass_negative_profit_factor(self):
        evidence = valid_evidence()
        evidence["profit_factor"] = 1.0
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_low_win_rate_blocks(self):
        evidence = valid_evidence()
        evidence["win_rate"] = 0.54
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_drawdown_and_sharpe_thresholds_block(self):
        for field, value in (("max_drawdown", 0.26), ("sharpe_annualized", 0.99)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_deflated_sharpe_and_bootstrap_must_pass(self):
        for field, value in (("deflated_sharpe_probability", 0.94), ("bootstrap_excess_lower_bound", 0.0)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_must_beat_benchmark_and_survive_double_costs(self):
        for field, value in (("net_return", 0.20), ("two_x_cost_net_return", 0.0)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_minimum_trials_observations_and_trades(self):
        for field, value in (("trial_count", 29), ("observations", 249), ("closed_trades", 99)):
            evidence = valid_evidence()
            evidence[field] = value
            self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_walk_forward_folds_must_be_sufficient_and_profitable(self):
        evidence = valid_evidence()
        evidence["walk_forward_folds"] = evidence["walk_forward_folds"][:3]
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")
        evidence = valid_evidence()
        evidence["walk_forward_folds"][1]["net_return"] = -0.03
        evidence["walk_forward_folds"][2]["net_return"] = -0.01
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_overlapping_or_out_of_order_folds_block(self):
        evidence = valid_evidence()
        evidence["walk_forward_folds"][1]["test_start"] = "2022-06-01"
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_bad_hashes_and_nonfinite_values_block(self):
        evidence = valid_evidence()
        evidence["dataset_sha256"] = "BAD"
        evidence["net_cagr"] = float("nan")
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_boolean_is_not_a_number(self):
        evidence = valid_evidence()
        evidence["net_cagr"] = True
        self.assertEqual(evaluate_profitability_evidence(evidence)["promotion_status"], "BLOCKED")

    def test_non_mapping_input_is_rejected(self):
        with self.assertRaises(TypeError):
            evaluate_profitability_evidence([])


if __name__ == "__main__":
    unittest.main()
