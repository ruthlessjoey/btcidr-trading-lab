import hashlib
import json
import unittest
from pathlib import Path

from promotion_gate import (
    FROZEN_REGISTERED_TRIAL_COUNT, FROZEN_TRIAL_REGISTRY_SHA256,
    MAXIMUM_FOLD_DRAWDOWN, MINIMUM_DSR_PROBABILITY, MINIMUM_FOLDS,
    MINIMUM_FOLD_EMBARGO_BARS, MINIMUM_POSITIVE_RATIO,
    MINIMUM_PROFIT_FACTOR, PromotionError,
    evaluate_promotion_gate as _evaluate_promotion_gate,
)

REGISTRY_RAW = Path(__file__).with_name("trial_registry.jsonl").read_bytes()
REGISTRY_SHA256 = hashlib.sha256(REGISTRY_RAW).hexdigest()


def evaluate_promotion_gate(*, folds, trial_registry_raw=REGISTRY_RAW):
    return _evaluate_promotion_gate(
        folds=folds, trial_registry_raw=trial_registry_raw,
    )

def valid_folds():
    return [{
        "fold_id": f"fold-{i}", "test_start": i * 1000,
        "test_end": i * 1000 + 900, "dataset_sha256": "a" * 64,
        "trial_registry_sha256": REGISTRY_SHA256,
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
        self.assertTrue(result["trial_registry_verified"])
        self.assertEqual(result["trial_registry_sha256"], FROZEN_TRIAL_REGISTRY_SHA256)
        self.assertEqual(result["registered_trial_count"], FROZEN_REGISTERED_TRIAL_COUNT)
        self.assertEqual(FROZEN_REGISTERED_TRIAL_COUNT, 2)

    def test_requires_five_folds(self):
        with self.assertRaisesRegex(PromotionError, "at least 5"):
            evaluate_promotion_gate(folds=valid_folds()[:4])

    def test_overlapping_ranges_rejected(self):
        rows = valid_folds()
        rows[1]["test_start"] = 800
        with self.assertRaisesRegex(PromotionError, "50 embargo bars"):
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
        with self.assertRaisesRegex(PromotionError, "does not match the verified frozen registry bytes"):
            evaluate_promotion_gate(folds=rows)

    def test_registered_trial_count_must_match(self):
        rows = valid_folds()
        rows[2]["registered_trial_count"] = 4
        with self.assertRaisesRegex(PromotionError, "independently verified number"):
            evaluate_promotion_gate(folds=rows)

    def test_trial_registry_raw_bytes_are_hash_chain_verified(self):
        tampered = REGISTRY_RAW.replace(b"TRIAL_STARTED", b"TRIAL_TAMPERED", 1)
        with self.assertRaisesRegex(PromotionError, "trial registry failed verification"):
            evaluate_promotion_gate(
                folds=valid_folds(), trial_registry_raw=tampered,
            )

    def test_valid_but_unpinned_registry_extension_is_rejected(self):
        last = json.loads(REGISTRY_RAW.splitlines()[-1])
        core = {
            "seq": 3,
            "event": "TRIAL_STARTED",
            "payload": {
                "trial_id": "BITSTAMP_V2_TEST_EXTRA",
                "research_family": "BITSTAMP_PERSONAL_SPOT_V2",
                "strategy_id": "EXTRA_CANDIDATE",
                "config_sha256": "b" * 64,
            },
            "previous_hash": last["record_hash"],
        }
        canonical = json.dumps(
            core, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        core["record_hash"] = hashlib.sha256(canonical).hexdigest()
        extension = REGISTRY_RAW + json.dumps(
            core, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8") + b"\\n"
        with self.assertRaisesRegex(PromotionError, "digest does not match"):
            evaluate_promotion_gate(
                folds=valid_folds(), trial_registry_raw=extension,
            )

    def test_exact_verified_trial_count_is_required_in_every_fold(self):
        rows = valid_folds()
        rows[1]["registered_trial_count"] = 3
        with self.assertRaisesRegex(PromotionError, "independently verified number"):
            evaluate_promotion_gate(folds=rows)

    def test_exact_50_bar_embargo_is_required_between_folds(self):
        rows = valid_folds()
        rows[1]["test_start"] = rows[0]["test_end"] + 49
        with self.assertRaisesRegex(PromotionError, "50 embargo bars"):
            evaluate_promotion_gate(folds=rows)
        rows = valid_folds()
        rows[1]["test_start"] = rows[0]["test_end"] + 50
        result = evaluate_promotion_gate(folds=rows)
        self.assertTrue(result["frozen_policy"]["ordered_test_ranges_with_embargo"])

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
        self.assertEqual(MINIMUM_FOLD_EMBARGO_BARS, 50)
        self.assertEqual(hashlib.sha256(REGISTRY_RAW).hexdigest(), FROZEN_TRIAL_REGISTRY_SHA256)
        with self.assertRaises(TypeError):
            evaluate_promotion_gate(folds=valid_folds(), minimum_folds=3)

if __name__ == "__main__":
    unittest.main()
