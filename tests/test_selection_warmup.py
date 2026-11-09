"""Synthetic offline regression tests for strategy warm-up and frozen metadata."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from research import selection, splits, toy  # noqa: E402
from research.engine import EngineError  # noqa: E402


class CandidateLookbackTests(unittest.TestCase):
    def setUp(self):
        self.candles = toy.toy_candles(1000)

    def test_selection_requires_training_to_cover_longest_candidate(self):
        short = splits.make_splits(1000, warmup=199)
        with self.assertRaisesRegex(EngineError, "longest candidate lookback"):
            selection.select(self.candles, short)

    def test_custom_candidates_use_their_own_maximum_lookback(self):
        windows = splits.make_splits(1000, warmup=50)
        result = selection.select(self.candles, windows, candidates=(20, 50))
        self.assertEqual([row["n"] for row in result["rows"]], [20, 50])

    def test_candidate_periods_must_be_unique_positive_integers(self):
        windows = splits.make_splits(1000, warmup=200)
        for candidates in ((20, 20), (20, True), (1, 20), ()):
            with self.subTest(candidates=candidates), self.assertRaises(EngineError):
                selection.select(self.candles, windows, candidates=candidates)

    def test_freeze_rejects_training_window_shorter_than_selected_candidates(self):
        windows = splits.make_splits(1000, warmup=200)
        result = selection.select(self.candles, windows)
        short = splits.make_splits(1000, warmup=199)
        with self.assertRaisesRegex(EngineError, "longest candidate lookback"):
            selection.freeze(result, short, {"sha256": "a" * 64}, self.candles)

    def test_custom_candidate_freeze_records_its_actual_lookback(self):
        windows = splits.make_splits(1000, warmup=50)
        result = selection.select(self.candles, windows, candidates=(20, 50))
        frozen = selection.freeze(result, windows, {"sha256": "c" * 64}, self.candles)
        self.assertIn("Candidates: 20, 50", frozen["rule_text"])
        self.assertIn("starts at index 50", frozen["rule_text"])

    def test_evaluation_rejects_boolean_frozen_boundary_timestamps(self):
        windows = splits.make_splits(1000, warmup=200)
        result = selection.select(self.candles, windows)
        frozen = selection.freeze(result, windows, {"sha256": "b" * 64}, self.candles)
        frozen["splits"]["train"]["first_open_unix"] = True
        body = {key: value for key, value in frozen.items() if key != "frozen_hash"}
        frozen["frozen_hash"] = selection.hashlib.sha256(
            selection._canon(body).encode()
        ).hexdigest()
        with self.assertRaisesRegex(EngineError, "timestamps must be non-negative integers"):
            selection.evaluate_test(self.candles, frozen, windows)


if __name__ == "__main__":
    unittest.main()
