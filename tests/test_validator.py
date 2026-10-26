"""Tests for validator.py. All data here is SYNTHETIC test data, not market prices."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import validator  # noqa: E402
from fetcher import Candle  # noqa: E402

BASE = 1_699_999_200      # a multiple of 3600
STEP = 3600
CFG = {"max_missing_ratio": 0.02, "max_spike_pct": 20}


def make(n, skip=(), base=BASE):
    """n synthetic hourly candles; indexes in `skip` are left out (gaps)."""
    out = []
    for i in range(n):
        if i in skip:
            continue
        o = 1000.0 + i
        out.append(Candle(base + i * STEP, o, o + 5, o - 5, o + 1, 10.0))
    return out


def run(candles, n_closed=None, server_offset=60, start=None):
    n = n_closed if n_closed is not None else len(candles)
    server_now = BASE + n * STEP + server_offset
    return validator.validate(candles, STEP, server_now, server_now, start or BASE,
                              server_now, CFG)


def status(result, name):
    return next(c.status for c in result.checks if c.name == name)


class ValidatorTests(unittest.TestCase):
    def test_clean_series_passes(self):
        r = run(make(100))
        self.assertEqual(r.status, "PASS", [c for c in r.checks if c.status != "PASS"])
        self.assertEqual(len(r.clean), 100)

    def test_empty_fails(self):
        self.assertEqual(run([], n_closed=0).status, "FAIL")

    def test_gap_is_detected(self):
        r = run(make(100, skip={50, 51}), n_closed=100)
        self.assertEqual(r.stats["missing_candles"], 2)
        self.assertIn(status(r, "missing_candles"), ("WARN", "FAIL"))

    def test_big_gap_fails(self):
        r = run(make(100, skip=set(range(40, 60))), n_closed=100)
        self.assertEqual(status(r, "missing_candles"), "FAIL")

    def test_exact_duplicate_warns_and_is_removed(self):
        c = make(10)
        r = run(c + [c[3]], n_closed=10)
        self.assertEqual(status(r, "order_and_duplicates"), "WARN")
        self.assertEqual(len(r.clean), 10)

    def test_conflicting_duplicate_fails(self):
        c = make(10)
        other = Candle(c[3].time, 5.0, 6.0, 4.0, 5.5, 1.0)
        self.assertEqual(status(run(c + [other], n_closed=10), "order_and_duplicates"), "FAIL")

    def test_unsorted_input_warns_and_is_sorted(self):
        c = make(10)
        r = run(list(reversed(c)), n_closed=10)
        self.assertEqual(status(r, "order_and_duplicates"), "WARN")
        self.assertEqual([x.time for x in r.clean], [x.time for x in c])

    def test_impossible_ohlc_fails(self):
        c = make(10)
        c[4] = Candle(c[4].time, 10.0, 5.0, 8.0, 9.0, 1.0)   # high below open
        self.assertEqual(status(run(c), "ohlc_sanity"), "FAIL")

    def test_nan_and_zero_prices_fail(self):
        c = make(10)
        c[2] = Candle(c[2].time, float("nan"), 1.0, 1.0, 1.0, 1.0)
        self.assertEqual(status(run(c), "ohlc_sanity"), "FAIL")
        c = make(10)
        c[2] = Candle(c[2].time, 0.0, 0.0, 0.0, 0.0, 1.0)
        self.assertEqual(status(run(c), "ohlc_sanity"), "FAIL")

    def test_negative_volume_fails(self):
        c = make(10)
        c[1] = Candle(c[1].time, 10, 11, 9, 10, -1.0)
        self.assertEqual(status(run(c), "volume_sanity"), "FAIL")

    def test_many_zero_volume_candles_warn(self):
        c = [Candle(x.time, x.open, x.high, x.low, x.close, 0.0) for x in make(20)]
        self.assertEqual(status(run(c), "volume_sanity"), "WARN")

    def test_price_spike_warns(self):
        c = make(10)
        c[5] = Candle(c[5].time, 2000, 2100, 1900, 2000, 1.0)  # ~+100%
        self.assertEqual(status(run(c), "price_spikes"), "WARN")

    def test_stale_data_fails(self):
        r = run(make(50), server_offset=3 * STEP)
        self.assertEqual(status(r, "freshness"), "FAIL")
        self.assertEqual(r.status, "FAIL")

    def test_forming_candle_is_excluded(self):
        c = make(51)                                   # 51st candle is still forming
        r = run(c, n_closed=50)
        self.assertEqual(r.stats["forming_dropped"], 1)
        self.assertEqual(len(r.clean), 50)

    def test_late_history_start_warns(self):
        r = run(make(50), start=BASE - 10 * STEP)
        self.assertEqual(status(r, "history_coverage"), "WARN")

    def test_misaligned_timestamp_fails(self):
        c = make(10)
        c[5] = Candle(c[5].time + 7, 1, 2, 0.5, 1, 1.0)
        self.assertEqual(status(run(c), "timestamp_grid"), "FAIL")

    def test_clock_skew_warns(self):
        server_now = BASE + 50 * STEP + 60
        r = validator.validate(make(50), STEP, server_now, server_now + 600,
                               BASE, server_now, CFG)
        self.assertEqual(status(r, "clock_skew"), "WARN")


if __name__ == "__main__":
    unittest.main()
