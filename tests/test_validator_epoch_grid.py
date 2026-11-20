"""Regression tests for the root candle validator's Unix-epoch timeframe alignment."""
import unittest
from types import SimpleNamespace

from validator import FAIL, PASS, validate


def candle(open_time):
    return SimpleNamespace(time=open_time, open=100.0, high=101.0, low=99.0, close=100.0, volume=1.0)


class TestAbsoluteEpochGrid(unittest.TestCase):
    def test_epoch_aligned_closed_candles_pass_the_grid_check(self):
        candles = [candle(86400), candle(172800), candle(259200)]
        result = validate(candles, 86400, 345600, 345600, 86400, 259200, {})
        grid = next(check for check in result.checks if check.name == "timestamp_grid")
        self.assertEqual(grid.status, PASS)

    def test_uniformly_offset_candles_fail_even_when_spacing_matches(self):
        # Relative spacing is exactly one day, but every open time is one second off the epoch grid.
        candles = [candle(86401), candle(172801), candle(259201)]
        result = validate(candles, 86400, 345601, 345601, 86400, 259200, {})
        grid = next(check for check in result.checks if check.name == "timestamp_grid")
        self.assertEqual(grid.status, FAIL)
        self.assertIn("3 candle(s) not on the 86400s grid", grid.detail)


if __name__ == "__main__":
    unittest.main()
