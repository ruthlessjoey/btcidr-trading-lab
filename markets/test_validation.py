"""Offline tests for markets/validation.py. Synthetic fixtures only. No network, no datasets.
Run from the repository root with:
    python3 -B -m unittest discover -s markets -p "test_*.py"
"""
import ast
import os
import unittest
from unittest import mock

from markets import validation as v
from markets import calendars as cal
from markets.candles import Candle

DAY = 86400
T0 = 1609459200          # 2021-01-01T00:00:00Z, on a daily boundary
MIN = 60
CRYPTO = cal.CryptoCalendar24x7()


def bar(t, close=100.0, volume=1.0):
    return Candle(t, close, close * 1.01, close * 0.99, close, volume)


def series(n, start=T0, closes=None, volume=1.0, tf=DAY):
    closes = closes or [100.0 + i for i in range(n)]
    return [bar(start + i * tf, closes[i], volume) for i in range(n)]


def now_after(candles, tf=DAY, slack=3600):
    """A now_s that completes the last candle and is one hour after its close."""
    return max(c.open_time_s for c in candles) + tf + slack


def check(report, name):
    matches = [c for c in report.checks if c.name == name]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one check named {name!r}, got {len(matches)}")
    return matches[0]


class ClosedEveryFourthDay(cal.Calendar):
    """Synthetic test-only calendar. It is not a real market schedule; it exists to exercise closures."""

    name = "test-closed-every-fourth-day"

    def is_expected(self, open_time_s, timeframe_s):
        open_time_s, timeframe_s = self._inputs(open_time_s, timeframe_s)
        return open_time_s % timeframe_s == 0 and (open_time_s // timeframe_s) % 4 != 3


class GenericEveryAlignedSlot(cal.Calendar):
    """Test-only. Same answers as CryptoCalendar24x7, but NOT the exact class, so it takes the generic scan path."""

    name = "test-generic-every-aligned"

    def is_expected(self, open_time_s, timeframe_s):
        open_time_s, timeframe_s = self._inputs(open_time_s, timeframe_s)
        return open_time_s % timeframe_s == 0


class HappyPathTests(unittest.TestCase):
    def test_clean_series_passes(self):
        candles = series(10)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.status, v.PASS)
        self.assertTrue(r.ok)
        self.assertEqual(r.row_count, 10)
        self.assertEqual(r.first_open_s, T0)
        self.assertEqual(r.last_open_s, T0 + 9 * DAY)
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(r.price_spikes, ())

    def test_every_check_is_reported_in_fixed_order(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual([c.name for c in r.checks],
                         ["non_empty", "range", "ordering", "duplicates", "alignment", "ohlc", "volume",
                          "out_of_range", "expected_missing", "unexpected_candles", "expected_closures",
                          "completed", "freshness", "price_spikes"])

    def test_empty_series_fails_without_crashing(self):
        r = v.validate_series([], CRYPTO, DAY, T0)
        self.assertEqual(check(r, "non_empty").status, v.FAIL)
        self.assertFalse(r.ok)
        self.assertIsNone(r.first_open_s)
        self.assertEqual(r.row_count, 0)


class OrderingAndDuplicateTests(unittest.TestCase):
    def test_reversed_order_fails(self):
        candles = list(reversed(series(5)))
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "ordering").status, v.FAIL)
        self.assertFalse(r.ok)

    def test_duplicate_open_time_fails_and_is_listed(self):
        candles = series(5)
        candles.insert(3, bar(T0 + 2 * DAY))
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "duplicates").status, v.FAIL)
        self.assertEqual(r.duplicate_open_s, (T0 + 2 * DAY,))
        self.assertFalse(r.ok)

    def test_duplicate_does_not_create_a_false_missing_candle(self):
        candles = series(5)
        candles.insert(3, bar(T0 + 2 * DAY))
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.missing_expected, ())


class AlignmentTests(unittest.TestCase):
    def test_misaligned_open_time_fails(self):
        candles = series(3)
        candles.append(bar(T0 + 3 * DAY + 3600))
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "alignment").status, v.FAIL)
        self.assertFalse(r.ok)

    def test_misaligned_candle_links_its_expected_slot(self):
        # Slot 2 holds only a misaligned candle. It is reported once, under alignment, not also as missing.
        candles = [bar(T0), bar(T0 + DAY), bar(T0 + 2 * DAY + 3600), bar(T0 + 3 * DAY), bar(T0 + 4 * DAY)]
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "alignment").status, v.FAIL)
        self.assertIn("occupied only by misaligned", check(r, "alignment").detail)
        self.assertEqual(r.misaligned_slots, (T0 + 2 * DAY,))
        self.assertEqual(r.misaligned_slot_total, 1)
        self.assertFalse(r.misaligned_slot_truncated)
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(r.missing_expected_total, 0)

    def test_misaligned_linking_does_not_hide_an_unrelated_gap(self):
        candles = [bar(T0), bar(T0 + DAY), bar(T0 + 2 * DAY + 3600), bar(T0 + 3 * DAY),
                   bar(T0 + 4 * DAY), bar(T0 + 6 * DAY)]
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0)
        self.assertEqual(r.misaligned_slots, (T0 + 2 * DAY,))
        self.assertEqual(r.missing_expected, (T0 + 5 * DAY,))
        self.assertEqual(r.missing_expected_total, 1)

    def test_misaligned_candle_outside_the_range_is_not_linked(self):
        candles = series(5) + [bar(T0 + 9 * DAY + 5)]
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 10 * DAY, start_s=T0, end_s=T0 + 4 * DAY)
        self.assertEqual(check(r, "alignment").status, v.FAIL)
        self.assertEqual(r.misaligned_slots, ())
        self.assertEqual(r.misaligned_slot_total, 0)

    def test_inferred_start_is_the_slot_containing_a_lone_misaligned_first_candle(self):
        # Omitted start_s: the inferred start must be the slot that contains T0+10s, i.e. T0, not T0+60s.
        candles = [bar(T0 + 10)]
        now = T0 + 11 * MIN                                    # last completed slot is T0+10min
        r = v.validate_series(candles, CRYPTO, MIN, now)
        self.assertEqual(r.range_start_s, T0)
        self.assertEqual(r.range_end_s, T0 + 10 * MIN)
        self.assertEqual(check(r, "alignment").status, v.FAIL)
        self.assertEqual(r.misaligned_slots, (T0,))
        self.assertEqual(r.misaligned_slot_total, 1)
        # Accounting: effective slots = aligned present + linked misaligned + absent.
        slots = (r.range_end_s - r.range_start_s) // MIN + 1
        self.assertEqual(slots, 11)
        self.assertEqual(0 + r.misaligned_slot_total + r.missing_expected_total, slots)
        self.assertEqual(r.missing_expected, tuple(T0 + k * MIN for k in range(1, 11)))
        self.assertNotIn(T0, r.missing_expected)               # the containing slot is not reported missing

    def test_inferred_start_is_the_containing_slot_when_aligned_candles_follow(self):
        candles = [bar(T0 + 10), bar(T0 + 1 * MIN), bar(T0 + 2 * MIN), bar(T0 + 3 * MIN), bar(T0 + 4 * MIN)]
        now = T0 + 5 * MIN                                     # last completed slot is T0+4min
        r = v.validate_series(candles, CRYPTO, MIN, now)
        self.assertEqual(r.range_start_s, T0)                  # not T0+60s
        self.assertEqual(r.range_end_s, T0 + 4 * MIN)
        self.assertEqual(check(r, "alignment").status, v.FAIL)
        self.assertEqual(r.misaligned_slots, (T0,))
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(r.missing_expected_total, 0)
        # Accounting: aligned present (4) + linked misaligned (1) + absent (0) = slots (5).
        slots = (r.range_end_s - r.range_start_s) // MIN + 1
        aligned_present = sum(1 for c in candles if c.open_time_s % MIN == 0)
        self.assertEqual(slots, 5)
        self.assertEqual(aligned_present + r.misaligned_slot_total + r.missing_expected_total, slots)


class OhlcAndVolumeTests(unittest.TestCase):
    def test_ohlc_mutated_after_construction_is_caught(self):
        candles = series(4)
        object.__setattr__(candles[2], "high", 1.0)           # high now below open and close
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "ohlc").status, v.FAIL)
        self.assertFalse(r.ok)

    def test_non_positive_price_mutated_after_construction_is_caught(self):
        candles = series(4)
        object.__setattr__(candles[1], "low", -5.0)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "ohlc").status, v.FAIL)

    def test_volume_absent_everywhere_passes_and_is_not_zero(self):
        candles = series(4, volume=None)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "volume").status, v.PASS)
        self.assertIn("not treated as zero", check(r, "volume").detail)

    def test_volume_partly_missing_warns_but_stays_ok(self):
        candles = series(4)
        object.__setattr__(candles[1], "volume", None)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "volume").status, v.WARN)
        self.assertTrue(r.ok)

    def test_invalid_volume_mutated_after_construction_fails(self):
        for bad in (-1.0, float("nan"), float("inf"), True):
            with self.subTest(bad=bad):
                candles = series(4)
                object.__setattr__(candles[0], "volume", bad)
                r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
                self.assertEqual(check(r, "volume").status, v.FAIL)


class RangeBoundaryTests(unittest.TestCase):
    """H1: leading, middle and trailing completeness against an explicit expected range."""

    def test_leading_missing_candles_are_detected_with_explicit_start(self):
        candles = series(5, start=T0 + 2 * DAY)                # days 2..6 observed; days 0 and 1 expected
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.missing_expected, (T0, T0 + DAY))
        self.assertEqual(r.missing_expected_total, 2)
        self.assertEqual(check(r, "range").status, v.PASS)
        self.assertEqual(check(r, "expected_missing").status, v.FAIL)
        self.assertFalse(r.ok)

    def test_middle_missing_candle_is_detected(self):
        candles = [bar(T0 + d * DAY) for d in range(7) if d != 3]
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.missing_expected, (T0 + 3 * DAY,))
        self.assertFalse(r.ok)

    def test_trailing_missing_completed_candles_are_detected(self):
        candles = series(5)                                    # days 0..4 observed
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0)
        # last completed slot at now_s is day 6, so days 5 and 6 are expected and absent
        self.assertEqual(r.range_end_s, T0 + 6 * DAY)
        self.assertEqual(r.missing_expected, (T0 + 5 * DAY, T0 + 6 * DAY))
        self.assertEqual(r.missing_expected_total, 2)

    def test_explicit_start_and_end_detect_both_boundaries(self):
        candles = [bar(T0 + d * DAY) for d in range(1, 6)]     # days 1..5 observed
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 8 * DAY, start_s=T0, end_s=T0 + 6 * DAY)
        self.assertEqual(r.range_start_s, T0)
        self.assertEqual(r.range_end_s, T0 + 6 * DAY)
        self.assertEqual(r.missing_expected, (T0, T0 + 6 * DAY))

    def test_explicit_end_beyond_last_completed_slot_is_partial_and_never_claimed_complete(self):
        # Replaces the old silent-cap test. The effective range is shortened, but the report says so.
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0, end_s=T0 + 10 * DAY)
        self.assertEqual(r.requested_end_s, T0 + 10 * DAY)     # what the caller asked for
        self.assertEqual(r.range_end_s, T0 + 6 * DAY)          # what was actually validated
        self.assertEqual(r.coverage, v.COVERAGE_PARTIAL)
        self.assertFalse(r.fully_validated)
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertIn("extends beyond the last completed slot", r.coverage_reason)
        self.assertIn("NOT validated", check(r, "range").detail)

    def test_end_s_before_the_last_candle_marks_later_candles_out_of_range(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0, end_s=T0 + 2 * DAY)
        self.assertEqual(check(r, "out_of_range").status, v.WARN)
        self.assertIn("2 completed aligned candle(s) outside", check(r, "out_of_range").detail)
        self.assertEqual(check(r, "expected_missing").status, v.PASS)

    def test_omitted_end_s_is_derived_from_now_not_from_the_last_candle(self):
        candles = series(5)                                    # last observed is day 4
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 10 * DAY + 3600, start_s=T0)
        self.assertEqual(r.range_end_s, T0 + 9 * DAY)
        self.assertEqual(r.missing_expected_total, 5)          # days 5..9 are not proof of completeness

    def test_omitted_start_is_a_warn_and_leading_completeness_is_not_claimed(self):
        candles = series(5, start=T0 + 2 * DAY)                # days 0 and 1 are absent but not checked
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles))
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertIn("leading completeness NOT established", check(r, "range").detail)
        self.assertEqual(r.range_start_s, T0 + 2 * DAY)
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(r.status, v.WARN)
        self.assertTrue(r.ok)

    def test_omitted_start_still_detects_a_middle_gap(self):
        candles = [bar(T0 + d * DAY) for d in (2, 3, 5, 6)]    # day 4 absent between observed candles
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles))
        self.assertEqual(r.missing_expected, (T0 + 4 * DAY,))

    def test_range_that_is_empty_is_reported_not_silent(self):
        candles = series(3)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0 + 10 * DAY)
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertIsNone(r.range_start_s)
        self.assertEqual(r.missing_expected_total, 0)

    def test_no_completed_slot_at_now_gives_no_range(self):
        r = v.validate_series([], CRYPTO, DAY, 100, start_s=0)
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertIsNone(r.range_end_s)

    def test_unaligned_or_invalid_bounds_are_refused(self):
        candles = series(3)
        now = now_after(candles)
        cases = [
            dict(start_s=T0 + 1),
            dict(end_s=T0 + DAY + 5),
            dict(start_s=-DAY),
            dict(start_s=True),
            dict(start_s=float(T0)),
            dict(start_s=T0, end_s=T0 - DAY),                  # end before start
            dict(end_s=-1),
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(v.ValidationError):
                    v.validate_series(candles, CRYPTO, DAY, now, **kwargs)


class RequestedVersusEffectiveTests(unittest.TestCase):
    """Requested bounds are kept separately from the effective completed range, and coverage is explicit."""

    def test_explicit_end_beyond_last_completed_slot_is_partial(self):
        candles = series(5)                                    # days 0..4 observed; last completed slot is day 6
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0, end_s=T0 + 10 * DAY)
        self.assertEqual(r.coverage, v.COVERAGE_PARTIAL)
        self.assertFalse(r.fully_validated)
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertNotEqual(r.status, v.PASS)
        self.assertIn("extends beyond the last completed slot", r.coverage_reason)
        self.assertIn(str(T0 + 6 * DAY), r.coverage_reason)

    def test_explicit_end_exactly_at_last_completed_slot_is_complete(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0, end_s=T0 + 6 * DAY)
        self.assertEqual(r.coverage, v.COVERAGE_COMPLETE)
        self.assertTrue(r.fully_validated)
        self.assertIsNone(r.coverage_reason)
        self.assertEqual(r.range_end_s, T0 + 6 * DAY)
        self.assertEqual(r.requested_end_s, T0 + 6 * DAY)
        self.assertEqual(check(r, "range").status, v.PASS)
        self.assertEqual(r.missing_expected_total, 2)          # days 5 and 6 are completed and absent

    def test_incomplete_future_slots_are_not_counted_as_missing(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0, end_s=T0 + 50 * DAY)
        self.assertEqual(r.missing_expected_total, 2)          # only completed days 5 and 6
        self.assertEqual(r.missing_expected, (T0 + 5 * DAY, T0 + 6 * DAY))
        self.assertTrue(all(t <= T0 + 6 * DAY for t in r.missing_expected))
        self.assertEqual(check(r, "expected_missing").status, v.FAIL)

    def test_no_slot_completed_at_now_is_represented_explicitly(self):
        r = v.validate_series([], CRYPTO, DAY, 100, start_s=0, end_s=0)
        self.assertEqual(r.coverage, v.COVERAGE_NONE)
        self.assertFalse(r.fully_validated)
        self.assertIsNone(r.range_start_s)
        self.assertIsNone(r.range_end_s)
        self.assertEqual(r.requested_start_s, 0)
        self.assertEqual(r.requested_end_s, 0)
        self.assertIn("no slot has completed", r.coverage_reason)
        self.assertEqual(check(r, "range").status, v.WARN)
        self.assertEqual(r.missing_expected_total, 0)

    def test_explicit_future_start_yields_no_validated_range(self):
        candles = series(5)                                    # last completed slot at now_s is day 6
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0 + 10 * DAY, end_s=T0 + 12 * DAY)
        self.assertEqual(r.coverage, v.COVERAGE_NONE)
        self.assertIn("future start", r.coverage_reason)
        self.assertIsNone(r.range_start_s)
        self.assertIsNone(r.range_end_s)
        self.assertEqual(r.requested_start_s, T0 + 10 * DAY)
        self.assertEqual(r.missing_expected_total, 0)
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(check(r, "range").status, v.WARN)

    def test_requested_and_effective_bounds_are_distinguishable(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0, end_s=T0 + 10 * DAY)
        self.assertEqual((r.requested_start_s, r.requested_end_s), (T0, T0 + 10 * DAY))
        self.assertEqual((r.range_start_s, r.range_end_s), (T0, T0 + 6 * DAY))
        self.assertNotEqual(r.requested_end_s, r.range_end_s)

    def test_omitted_end_is_derived_and_is_complete(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, start_s=T0)
        self.assertIsNone(r.requested_end_s)
        self.assertEqual(r.range_end_s, T0 + 6 * DAY)
        self.assertEqual(r.coverage, v.COVERAGE_COMPLETE)

    def test_incomplete_requested_range_cannot_pass_as_fully_validated(self):
        candles = series(5)
        cases = [
            dict(start_s=T0, end_s=T0 + 7 * DAY),             # end one slot beyond completed
            dict(start_s=T0, end_s=T0 + 30 * DAY),            # end far beyond completed
            dict(end_s=T0 + 6 * DAY),                         # start omitted: leading not established
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                r = v.validate_series(candles, CRYPTO, DAY, T0 + 7 * DAY, **kwargs)
                self.assertFalse(r.fully_validated)
                self.assertNotEqual(r.coverage, v.COVERAGE_COMPLETE)
                self.assertEqual(check(r, "range").status, v.WARN)
                # The overall status is not PASS. Here it is FAIL because the newest candle is stale at now_s,
                # which is a separate, correct finding and not a reason to hide partial coverage.
                self.assertNotEqual(r.status, v.PASS)
                self.assertTrue(r.coverage_reason)

    def test_grid_limit_applies_to_the_effective_range_not_the_requested_end(self):
        candles = [bar(T0)]
        # A requested end of ten million days is far above max_grid_slots, but only 3 slots are evaluated.
        r = v.validate_series(candles, CRYPTO, DAY, T0 + 3 * DAY, start_s=T0, end_s=T0 + 10_000_000 * DAY)
        self.assertEqual(r.range_end_s, T0 + 2 * DAY)
        self.assertEqual(r.missing_expected_total, 2)          # days 1 and 2 only
        self.assertEqual(r.coverage, v.COVERAGE_PARTIAL)

    def test_grid_limit_still_rejects_an_oversized_effective_range(self):
        candles = [bar(T0)]
        with self.assertRaises(v.ValidationError):
            v.validate_series(candles, CRYPTO, MIN, T0 + 1_000_001 * MIN, start_s=T0, end_s=T0 + 1_000_001 * MIN)


class BoundedReportingTests(unittest.TestCase):
    """H2: exact totals, bounded samples, truncation flags, grid-work limit."""

    def test_totals_are_exact_and_samples_are_bounded_on_the_generic_path(self):
        candles = [bar(T0), bar(T0 + 100 * DAY)]
        r = v.validate_series(candles, GenericEveryAlignedSlot(), DAY, T0 + 101 * DAY + 3600,
                              start_s=T0, sample_limit=5)
        self.assertEqual(r.missing_expected_total, 99)
        self.assertEqual(len(r.missing_expected), 5)
        self.assertTrue(r.missing_expected_truncated)
        self.assertEqual(r.missing_expected, tuple(T0 + d * DAY for d in range(1, 6)))

    def test_no_truncation_when_samples_cover_everything(self):
        candles = [bar(T0), bar(T0 + 2 * DAY)]
        r = v.validate_series(candles, GenericEveryAlignedSlot(), DAY, T0 + 2 * DAY + 3600, start_s=T0)
        self.assertEqual(r.missing_expected, (T0 + DAY,))
        self.assertFalse(r.missing_expected_truncated)

    def test_sample_limit_zero_keeps_totals_and_flags_truncation(self):
        candles = [bar(T0), bar(T0 + 2 * DAY)]
        r = v.validate_series(candles, GenericEveryAlignedSlot(), DAY, T0 + 2 * DAY + 3600,
                              start_s=T0, sample_limit=0)
        self.assertEqual(r.missing_expected, ())
        self.assertEqual(r.missing_expected_total, 1)
        self.assertTrue(r.missing_expected_truncated)

    def test_closure_and_missing_totals_are_separate_and_exact(self):
        # Interior slots 1..35 hold 9 closures (days 3,7,...,35) and 26 expected-absent slots.
        candles = [bar(T0), bar(T0 + 36 * DAY)]
        r = v.validate_series(candles, ClosedEveryFourthDay(), DAY, T0 + 37 * DAY + 3600,
                              start_s=T0, sample_limit=4)
        self.assertEqual(r.missing_expected_total, 26)
        self.assertEqual(r.expected_closures_total, 9)
        self.assertEqual(r.missing_expected, tuple(T0 + d * DAY for d in (1, 2, 4, 5)))
        self.assertEqual(r.expected_closures, tuple(T0 + d * DAY for d in (3, 7, 11, 15)))
        self.assertTrue(r.missing_expected_truncated)
        self.assertTrue(r.expected_closures_truncated)
        self.assertEqual(check(r, "expected_closures").status, v.PASS)

    def test_unexpected_candles_total_and_truncation(self):
        candles = [bar(T0 + d * DAY) for d in range(40)]       # closed days 3,7,...,39 are present
        r = v.validate_series(candles, ClosedEveryFourthDay(), DAY, now_after(candles), start_s=T0,
                              sample_limit=4)
        self.assertEqual(r.unexpected_total, 10)
        self.assertEqual(r.unexpected_candles, tuple(T0 + d * DAY for d in (3, 7, 11, 15)))
        self.assertTrue(r.unexpected_truncated)

    def test_crypto_arithmetic_totals_and_samples_over_a_large_range(self):
        last = T0 + 100000 * MIN
        candles = [bar(T0), bar(last)]
        # Fails if the per-slot scan is ever used for CryptoCalendar24x7.
        with mock.patch.object(v, "_scan_generic", side_effect=AssertionError("per-slot scan used")):
            r = v.validate_series(candles, CRYPTO, MIN, last + MIN, start_s=T0)
        self.assertEqual(r.missing_expected_total, 99999)
        self.assertEqual(r.missing_expected, tuple(T0 + k * MIN for k in range(1, 21)))
        self.assertTrue(r.missing_expected_truncated)
        self.assertEqual(r.expected_closures_total, 0)

    def test_crypto_path_matches_the_generic_path_exactly(self):
        candles = [bar(T0 + d * DAY) for d in (0, 1, 2, 5, 6, 9, 10)]
        candles.append(bar(T0 + 3 * DAY + 60))                 # misaligned, lands in slot 3
        now = T0 + 14 * DAY
        rc = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0)
        rg = v.validate_series(candles, GenericEveryAlignedSlot(), DAY, now, start_s=T0)
        self.assertEqual(rc.checks, rg.checks)
        self.assertEqual(rc.range_start_s, rg.range_start_s)
        self.assertEqual(rc.range_end_s, rg.range_end_s)
        self.assertEqual(rc.missing_expected, rg.missing_expected)
        self.assertEqual(rc.missing_expected_total, rg.missing_expected_total)
        self.assertEqual(rc.misaligned_slots, rg.misaligned_slots)
        self.assertEqual(rc.misaligned_slot_total, rg.misaligned_slot_total)
        self.assertEqual(rc.expected_closures_total, rg.expected_closures_total)
        self.assertEqual(rc.unexpected_total, rg.unexpected_total)
        self.assertEqual(rc.missing_expected_total, 6)
        self.assertEqual(rc.missing_expected, tuple(T0 + d * DAY for d in (4, 7, 8, 11, 12, 13)))

    def test_excessive_grid_range_is_rejected_before_scanning(self):
        candles = [bar(T0)]
        now = T0 + 1_000_001 * MIN                              # 1,000,001 slots at 60 s
        with mock.patch.object(v, "_scan_generic", side_effect=AssertionError("scan ran")):
            with self.assertRaises(v.ValidationError) as ctx:
                v.validate_series(candles, GenericEveryAlignedSlot(), MIN, now, start_s=T0)
        self.assertIn("max_grid_slots", str(ctx.exception))

    def test_excessive_range_is_rejected_for_the_crypto_path_too(self):
        candles = [bar(T0)]
        with self.assertRaises(v.ValidationError):
            v.validate_series(candles, CRYPTO, MIN, T0 + 1_000_001 * MIN, start_s=T0)

    def test_grid_limit_is_inclusive_and_overridable(self):
        candles = series(5)
        now = now_after(candles)
        r = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0, max_grid_slots=5)
        self.assertTrue(r.ok)
        with self.assertRaises(v.ValidationError):
            v.validate_series(candles, CRYPTO, DAY, now, start_s=T0, max_grid_slots=4)

    def test_invalid_limits_are_refused(self):
        candles = series(3)
        now = now_after(candles)
        for kwargs in (dict(sample_limit=-1), dict(sample_limit=True), dict(max_grid_slots=0),
                       dict(max_grid_slots=False)):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(v.ValidationError):
                    v.validate_series(candles, CRYPTO, DAY, now, start_s=T0, **kwargs)


class EmptyInputStubTests(unittest.TestCase):
    """L1: the calendar is probed even when the series is empty."""

    def test_empty_series_with_equity_stub_raises(self):
        with self.assertRaises(cal.CalendarNotImplemented):
            v.validate_series([], cal.EquityCalendarStub(), DAY, T0 + 10 * DAY, start_s=T0, end_s=T0 + 5 * DAY)

    def test_empty_series_with_fx_stub_raises(self):
        with self.assertRaises(cal.CalendarNotImplemented):
            v.validate_series([], cal.FxCalendarStub(), DAY, T0 + 10 * DAY, start_s=T0, end_s=T0 + 5 * DAY)

    def test_empty_series_with_stub_and_no_bounds_still_raises(self):
        with self.assertRaises(cal.CalendarNotImplemented):
            v.validate_series([], cal.EquityCalendarStub(), DAY, T0)


class CompletedAndFreshnessTests(unittest.TestCase):
    def test_candle_still_forming_fails_completed(self):
        candles = series(5)
        now = T0 + 4 * DAY + DAY - 1                         # last candle closes one second after now
        r = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0)
        self.assertEqual(check(r, "completed").status, v.FAIL)
        self.assertFalse(r.ok)

    def test_candle_closing_exactly_at_now_is_completed(self):
        candles = series(5)
        now = T0 + 4 * DAY + DAY                             # close equals now_s: complete
        self.assertEqual(check(v.validate_series(candles, CRYPTO, DAY, now, start_s=T0),
                               "completed").status, v.PASS)

    def test_stale_series_fails_freshness(self):
        candles = series(5)
        now = T0 + 4 * DAY + DAY + v.FRESHNESS_LIMIT_S + 1
        r = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0)
        self.assertEqual(check(r, "freshness").status, v.FAIL)
        self.assertIn("STALE", check(r, "freshness").detail)

    def test_freshness_boundary_is_inclusive(self):
        candles = series(5)
        close = T0 + 4 * DAY + DAY
        r_at = v.validate_series(candles, CRYPTO, DAY, close + v.FRESHNESS_LIMIT_S, start_s=T0)
        r_over = v.validate_series(candles, CRYPTO, DAY, close + v.FRESHNESS_LIMIT_S + 1, start_s=T0)
        self.assertEqual(check(r_at, "freshness").status, v.PASS)
        self.assertEqual(check(r_over, "freshness").status, v.FAIL)

    def test_custom_max_age_is_honoured(self):
        candles = series(5)
        close = T0 + 4 * DAY + DAY
        r = v.validate_series(candles, CRYPTO, DAY, close + 100, max_age_s=50, start_s=T0)
        self.assertEqual(check(r, "freshness").status, v.FAIL)

    def test_now_before_newest_candle_fails_freshness(self):
        candles = series(5)
        r = v.validate_series(candles, CRYPTO, DAY, T0 + DAY)
        self.assertEqual(check(r, "freshness").status, v.FAIL)


class PriceSpikeTests(unittest.TestCase):
    def test_large_move_is_a_warn_only_and_stays_ok(self):
        closes = [100.0, 100.0, 140.0, 141.0]               # +40% between day 1 and day 2
        candles = series(4, closes=closes)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(check(r, "price_spikes").status, v.WARN)
        self.assertEqual(r.status, v.WARN)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.price_spikes), 1)
        self.assertEqual(r.price_spikes[0].open_time_s, T0 + 2 * DAY)
        self.assertAlmostEqual(r.price_spikes[0].change, 0.40)

    def test_spike_threshold_is_exclusive(self):
        closes = [100.0, 125.0]                              # exactly +25%: not above the threshold
        candles = series(2, closes=closes)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.price_spikes, ())

    def test_move_across_a_gap_is_not_compared(self):
        candles = [bar(T0, 100.0), bar(T0 + 3 * DAY, 200.0)]  # days 1 and 2 missing: not consecutive
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.price_spikes, ())

    def test_spike_never_changes_the_ok_flag_on_a_clean_series(self):
        candles = series(3, closes=[100.0, 300.0, 310.0])
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.status, v.WARN)
        self.assertTrue(r.ok)


class ArgumentTests(unittest.TestCase):
    def test_now_s_is_required(self):
        with self.assertRaises(TypeError):
            v.validate_series(series(3), CRYPTO, DAY)

    def test_bad_arguments_raise_validation_error(self):
        candles = series(3)
        cases = [
            dict(calendar="crypto", timeframe_s=DAY, now_s=T0),
            dict(calendar=CRYPTO, timeframe_s=0, now_s=T0),
            dict(calendar=CRYPTO, timeframe_s=True, now_s=T0),
            dict(calendar=CRYPTO, timeframe_s=DAY, now_s=True),
            dict(calendar=CRYPTO, timeframe_s=DAY, now_s=-1),
            dict(calendar=CRYPTO, timeframe_s=DAY, now_s=T0, max_age_s=-1),
            dict(calendar=CRYPTO, timeframe_s=DAY, now_s=T0, spike_threshold=0),
            dict(calendar=CRYPTO, timeframe_s=DAY, now_s=T0, spike_threshold=float("nan")),
        ]
        for kwargs in cases:
            with self.subTest(kwargs={k: type(x).__name__ for k, x in kwargs.items()}):
                with self.assertRaises(v.ValidationError):
                    v.validate_series(candles, **kwargs)

    def test_non_candle_items_raise_validation_error(self):
        with self.assertRaises(v.ValidationError):
            v.validate_series([("not", "a", "candle")], CRYPTO, DAY, T0)

    def test_candles_must_be_a_list_or_tuple(self):
        with self.assertRaises(v.ValidationError):
            v.validate_series(series(3)[0], CRYPTO, DAY, T0)

    def test_tuple_input_is_accepted(self):
        candles = tuple(series(3))
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        self.assertEqual(r.status, v.PASS)


class DeterminismTests(unittest.TestCase):
    def test_same_inputs_give_identical_reports(self):
        candles = series(6, closes=[100, 101, 150, 151, 152, 153])
        now = now_after(candles)
        first = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0)
        second = v.validate_series(candles, CRYPTO, DAY, now, start_s=T0)
        self.assertEqual(first, second)

    def test_bounded_reports_with_truncation_are_identical_on_repeat(self):
        candles = [bar(T0), bar(T0 + 100 * DAY)]
        runs = [v.validate_series(candles, GenericEveryAlignedSlot(), DAY, T0 + 101 * DAY + 3600,
                                  start_s=T0, sample_limit=5) for _ in range(3)]
        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

    def test_report_has_no_decision_field(self):
        candles = series(3)
        r = v.validate_series(candles, CRYPTO, DAY, now_after(candles), start_s=T0)
        for name in ("decision", "action", "signal", "buy", "sell"):
            self.assertFalse(hasattr(r, name), name)

    def test_validation_module_imports_only_pure_modules(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names, {"math", "collections", "dataclasses", "typing", "markets"})
        for banned in ("time", "datetime", "socket", "urllib", "http", "requests", "subprocess"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
