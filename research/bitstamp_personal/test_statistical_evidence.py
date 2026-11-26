import unittest
from decimal import Decimal
from statistical_evidence import (
    BOOTSTRAP_RESAMPLES,
    StatisticalEvidenceError,
    deflated_sharpe_probability,
    non_overlapping_24bar_returns,
    paired_block_bootstrap_excess_lower_bound,
)


class StatisticalEvidenceTests(unittest.TestCase):
    def test_non_overlapping_24bar_returns_have_expected_count(self):
        curve = [10000.0 * (1.001 ** index) for index in range(24 * 31 + 1)]
        returns = non_overlapping_24bar_returns(curve)
        self.assertEqual(len(returns), 31)
        self.assertTrue(all(value > 0 for value in returns))

    def test_equity_curve_accepts_internal_decimal_strings(self):
        curve = [str(Decimal("10000") * (Decimal("1.001") ** index)) for index in range(24 * 31 + 1)]
        returns = non_overlapping_24bar_returns(curve)
        self.assertEqual(len(returns), 31)
        self.assertTrue(all(value > 0 for value in returns))

    def test_non_overlapping_returns_ignore_incomplete_trailing_block(self):
        curve = [10000.0 * (1.001 ** index) for index in range(24 * 31 + 12)]
        returns = non_overlapping_24bar_returns(curve)
        self.assertEqual(len(returns), 31)

    def test_equity_curve_rejects_bad_marks_and_short_series(self):
        with self.assertRaises(StatisticalEvidenceError):
            non_overlapping_24bar_returns([10000] * 24)
        bad = [10000.0] * (24 * 31 + 1)
        bad[20] = 0
        with self.assertRaisesRegex(StatisticalEvidenceError, "strictly positive"):
            non_overlapping_24bar_returns(bad)

    def test_dsr_zero_variance_returns_neutral_probability(self):
        self.assertEqual(
            deflated_sharpe_probability([0.0] * 30, registered_trial_count=3),
            0.5,
        )

    def test_dsr_positive_edge_is_finite_and_trial_adjusted(self):
        returns = [0.01 if index % 5 else -0.002 for index in range(100)]
        one = deflated_sharpe_probability(returns, registered_trial_count=2)
        many = deflated_sharpe_probability(returns, registered_trial_count=100)
        self.assertGreaterEqual(one, many)
        self.assertTrue(0 <= many <= one <= 1)

    def test_dsr_rejects_invalid_trial_count_and_return_values(self):
        returns = [0.001] * 30
        for count in (True, 1, 0, 2.5):
            with self.subTest(count=count), self.assertRaises(StatisticalEvidenceError):
                deflated_sharpe_probability(returns, registered_trial_count=count)
        bad = list(returns)
        bad[0] = float("nan")
        with self.assertRaises(StatisticalEvidenceError):
            deflated_sharpe_probability(bad, registered_trial_count=2)

    def test_paired_bootstrap_is_deterministic_and_positive_for_positive_excess(self):
        strategy = [0.01 + (index % 7) * 0.0001 for index in range(100)]
        baseline = [0.002 + (index % 7) * 0.00005 for index in range(100)]
        kwargs = {"dataset_sha256": "a" * 64, "fold_id": "fold-1"}
        first = paired_block_bootstrap_excess_lower_bound(strategy, baseline, **kwargs)
        second = paired_block_bootstrap_excess_lower_bound(strategy, baseline, **kwargs)
        self.assertEqual(first, second)
        self.assertGreater(first, 0)
        self.assertEqual(BOOTSTRAP_RESAMPLES, 10000)

    def test_paired_bootstrap_does_not_claim_positive_edge_when_series_match(self):
        series = [0.001 * (index % 3) for index in range(100)]
        result = paired_block_bootstrap_excess_lower_bound(
            series, series, dataset_sha256="b" * 64, fold_id="fold-2",
        )
        self.assertEqual(result, 0.0)

    def test_paired_bootstrap_rejects_misaligned_or_untrusted_inputs(self):
        series = [0.001] * 100
        with self.assertRaisesRegex(StatisticalEvidenceError, "equal lengths"):
            paired_block_bootstrap_excess_lower_bound(
                series, series[:-1], dataset_sha256="a" * 64, fold_id="fold-1",
            )
        with self.assertRaisesRegex(StatisticalEvidenceError, "SHA-256"):
            paired_block_bootstrap_excess_lower_bound(
                series, series, dataset_sha256="not-a-hash", fold_id="fold-1",
            )
        with self.assertRaisesRegex(StatisticalEvidenceError, "fold_id"):
            paired_block_bootstrap_excess_lower_bound(
                series, series, dataset_sha256="a" * 64, fold_id="",
            )


if __name__ == "__main__":
    unittest.main()
