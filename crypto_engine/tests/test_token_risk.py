import unittest
from dataclasses import replace

from tmm_core.token_risk import (
    TokenRiskEvidence, TokenRiskError, TokenRiskPolicy, evaluate_token_eligibility,
)


class TokenRiskGateTests(unittest.TestCase):
    NOW = 1_800_000_000
    HASH = "a" * 64

    def evidence(self):
        return TokenRiskEvidence(
            token_id="chain:synthetic-token", source_id="synthetic-fixture",
            source_sha256=self.HASH, source_timestamp=self.NOW - 60,
            observed_at=self.NOW - 30, contract_verified=True,
            mint_authority_disabled=True, freeze_authority_disabled=True,
            upgrade_authority_disabled=True, honeypot_check_passed=True,
            market_active=True, liquidity_usd="250000", top_holder_share=".12",
            lp_lock_ratio=".95", buy_tax_bps="0", sell_tax_bps="25",
            holder_count=5000,
        )

    def policy(self):
        return TokenRiskPolicy(
            required_checks=("contract_verified", "mint_authority_disabled",
                             "freeze_authority_disabled", "upgrade_authority_disabled",
                             "honeypot_check_passed", "market_active"),
            min_liquidity_usd="50000", max_top_holder_share=".20",
            min_lp_lock_ratio=".80", max_buy_tax_bps="100",
            max_sell_tax_bps="100", min_holder_count=1000,
            max_evidence_age_seconds=3600,
        )

    def test_passing_synthetic_evidence_is_only_eligible_for_human_review(self):
        result = evaluate_token_eligibility(evidence=self.evidence(), policy=self.policy(),
                                            decision_time=self.NOW)
        self.assertEqual(result["status"], "ELIGIBLE_FOR_HUMAN_REVIEW")
        self.assertFalse(result["order_authorized"])
        self.assertFalse(result["evidence_truth_independently_verified"])

    def test_missing_or_failed_security_check_blocks_token(self):
        evidence = replace(self.evidence(), freeze_authority_disabled=None,
                           honeypot_check_passed=False)
        result = evaluate_token_eligibility(evidence=evidence, policy=self.policy(),
                                            decision_time=self.NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("MISSING_CHECK:freeze_authority_disabled", result["reasons"])
        self.assertIn("CHECK_FAILED:honeypot_check_passed", result["reasons"])

    def test_stale_or_future_evidence_is_rejected_or_blocked(self):
        stale = replace(self.evidence(), source_timestamp=self.NOW - 10000,
                        observed_at=self.NOW - 9990)
        result = evaluate_token_eligibility(evidence=stale, policy=self.policy(),
                                            decision_time=self.NOW)
        self.assertIn("STALE_SOURCE_EVIDENCE", result["reasons"])
        future = replace(self.evidence(), observed_at=self.NOW + 1)
        with self.assertRaises(TokenRiskError):
            evaluate_token_eligibility(evidence=future, policy=self.policy(),
                                      decision_time=self.NOW)

    def test_liquidity_concentration_lp_lock_tax_and_holder_limits_block(self):
        evidence = replace(self.evidence(), liquidity_usd="1000",
                           top_holder_share=".45", lp_lock_ratio=".1",
                           buy_tax_bps="500", sell_tax_bps="700", holder_count=10)
        result = evaluate_token_eligibility(evidence=evidence, policy=self.policy(),
                                            decision_time=self.NOW)
        self.assertEqual(result["status"], "BLOCKED")
        for reason in ("MIN_LIQUIDITY_NOT_MET", "TOP_HOLDER_CONCENTRATION_TOO_HIGH",
                       "LP_LOCK_RATIO_TOO_LOW", "BUY_TAX_TOO_HIGH",
                       "SELL_TAX_TOO_HIGH", "HOLDER_COUNT_TOO_LOW"):
            self.assertIn(reason, result["reasons"])

    def test_missing_numeric_evidence_fails_closed(self):
        evidence = replace(self.evidence(), liquidity_usd=None, top_holder_share=None)
        result = evaluate_token_eligibility(evidence=evidence, policy=self.policy(),
                                            decision_time=self.NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("MISSING_VALUE:liquidity_usd", result["reasons"])
        self.assertIn("MISSING_VALUE:top_holder_share", result["reasons"])

    def test_bad_hash_or_invalid_policy_is_rejected(self):
        with self.assertRaises(TokenRiskError):
            evaluate_token_eligibility(evidence=replace(self.evidence(), source_sha256="bad"),
                                       policy=self.policy(), decision_time=self.NOW)
        with self.assertRaises(TokenRiskError):
            evaluate_token_eligibility(evidence=self.evidence(),
                                       policy=replace(self.policy(), required_checks=("unknown",)),
                                       decision_time=self.NOW)
        with self.assertRaises(TokenRiskError):
            evaluate_token_eligibility(evidence=self.evidence(),
                                       policy=replace(self.policy(), required_checks=({},)),
                                       decision_time=self.NOW)


if __name__ == "__main__":
    unittest.main()
