"""Regression tests for holdout failure reporting. Synthetic data only; no network or workflow."""
import json
import os
import tempfile
import unittest
from unittest import mock

from research import pipeline, toy


class HoldoutFailureReportingTests(unittest.TestCase):
    def test_holdout_exception_writes_failure_report_and_returns_nonzero(self):
        candles = toy.toy_candles(1000)
        splits = {"train": (200, 600), "validation": (600, 800), "test": (800, 1000)}
        manifest = {
            "version_id": "synthetic",
            "csv_sha256": "a" * 64,
            "row_count": len(candles),
            "first_open_utc": "synthetic-first",
            "last_open_utc": "synthetic-last",
            "market": "SYNTHETIC",
        }
        selection_result = {"selected_n": 50, "rows": []}
        frozen = {"frozen_hash": "b" * 64}

        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "out")
            with (
                mock.patch.object(pipeline, "load_pinned", return_value=(manifest, candles)),
                mock.patch.object(pipeline.splits_mod, "make_splits", return_value=splits),
                mock.patch.object(pipeline.strategy, "assert_causal"),
                mock.patch.object(pipeline.selection, "select", return_value=selection_result),
                mock.patch.object(pipeline.selection, "freeze", return_value=frozen),
                mock.patch.object(
                    pipeline.selection, "evaluate_test",
                    side_effect=RuntimeError("synthetic holdout interruption"),
                ),
            ):
                code = pipeline.run_backtest(
                    {"evaluate_test": True}, root, out, prev_results_root=root, run_id="synthetic-run"
                )

            self.assertEqual(code, 1)
            with open(os.path.join(out, "backtest_report.json"), encoding="utf-8") as f:
                report = json.load(f)
            self.assertEqual(report["status"], "FAILED")
            self.assertEqual(
                report["error"], "RuntimeError: synthetic holdout interruption"
            )
            with open(os.path.join(out, "backtest_report.md"), encoding="utf-8") as f:
                markdown = f.read()
            self.assertIn("synthetic holdout interruption", markdown)


if __name__ == "__main__":
    unittest.main()
