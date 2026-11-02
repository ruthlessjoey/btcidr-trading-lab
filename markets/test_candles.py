"""Offline tests for markets/candles.py. No network, no repository data. Run from the repository root:
    python3 -B -m unittest discover -s markets -p "test_*.py"
"""
import json
import unittest
from datetime import datetime, timedelta, timezone

from markets import candles as mc

DAY = 86400
T0 = 1609459200                      # 2021-01-01T00:00:00Z, on a daily boundary


def make(**overrides):
    fields = dict(open_time_s=T0, open=100.0, high=110.0, low=90.0, close=105.0, volume=1000.0)
    fields.update(overrides)
    return mc.Candle(**fields)


class CandleTimestampTests(unittest.TestCase):
    def test_integer_utc_epoch_seconds_accepted(self):
        self.assertEqual(make().open_time_s, T0)
        self.assertEqual(make(open_time_s=0).open_time_s, 0)
        self.assertEqual(make(open_time_s=mc.MAX_OPEN_TIME_S).open_time_s, mc.MAX_OPEN_TIME_S)

    def test_invalid_timestamps_refused(self):
        for value in (1.0, T0 + 0.5, True, False, None, "1609459200", -1,
                      mc.MAX_OPEN_TIME_S + 1):
            with self.subTest(value=value):
                with self.assertRaises(mc.CandleError):
                    make(open_time_s=value)

    def test_alignment_to_timeframe(self):
        candle = make()
        self.assertIs(mc.check_alignment(candle, DAY), candle)
        with self.assertRaises(mc.CandleError):
            mc.check_alignment(make(open_time_s=T0 + 3600), DAY)
        for bad in (0, -DAY, True, 1.5, None):
            with self.subTest(timeframe=bad):
                with self.assertRaises(mc.CandleError):
                    mc.check_alignment(candle, bad)

    def test_utc_datetime_round_trip(self):
        dt = mc.utc_datetime(T0)
        self.assertEqual(dt, datetime(2021, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(dt.utcoffset(), timedelta(0))
        self.assertEqual(mc.epoch_seconds(dt), T0)

    def test_non_utc_aware_datetime_converted(self):
        plus_eight = timezone(timedelta(hours=8))
        local = datetime(2021, 1, 1, 8, 0, 0, tzinfo=plus_eight)
        self.assertEqual(mc.epoch_seconds(local), T0)

    def test_utc_datetime_refuses_bool(self):
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(mc.CandleError):
                    mc.utc_datetime(value)

    def test_pre_1970_datetime_is_rejected(self):
        # Timestamp policy: non-negative epoch seconds only. Pre-1970 data is unsupported for now.
        with self.assertRaises(mc.CandleError) as ctx:
            mc.epoch_seconds(datetime(1960, 1, 1, tzinfo=timezone.utc))
        self.assertIn("pre-1970", str(ctx.exception))
        with self.assertRaises(mc.CandleError):
            mc.epoch_seconds(datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        self.assertEqual(mc.epoch_seconds(datetime(1970, 1, 1, tzinfo=timezone.utc)), 0)

    def test_far_future_datetime_with_negative_offset_raises_candle_error(self):
        # Regression: converting this to UTC overflows datetime. It must surface as CandleError,
        # never as a bare OverflowError.
        far_future = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=-8)))
        with self.assertRaises(mc.CandleError) as ctx:
            mc.epoch_seconds(far_future)
        self.assertIn("cannot be converted", str(ctx.exception))

    def test_far_future_datetime_with_positive_offset_still_converts(self):
        # 23:59:59 at +08:00 is 15:59:59 UTC, eight hours before the UTC maximum.
        east = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(mc.epoch_seconds(east), mc.MAX_OPEN_TIME_S - 8 * 3600)

    def test_naive_and_sub_second_datetimes_refused(self):
        with self.assertRaises(mc.CandleError):
            mc.epoch_seconds(datetime(2021, 1, 1))
        with self.assertRaises(mc.CandleError):
            mc.epoch_seconds(datetime(2021, 1, 1, tzinfo=timezone.utc).replace(microsecond=1))
        with self.assertRaises(mc.CandleError):
            mc.epoch_seconds("2021-01-01")
        with self.assertRaises(mc.CandleError):
            mc.utc_datetime(1.0)


class OhlcTests(unittest.TestCase):
    def test_valid_ohlc_accepted_and_normalized_to_float(self):
        c = mc.Candle(T0, 100, 110, 90, 105, 5)
        self.assertEqual((c.open, c.high, c.low, c.close, c.volume), (100.0, 110.0, 90.0, 105.0, 5.0))
        self.assertIsInstance(c.open, float)

    def test_high_below_low_refused(self):
        with self.assertRaises(mc.CandleError):
            make(high=89.0, low=90.0)

    def test_high_below_open_or_close_refused(self):
        with self.assertRaises(mc.CandleError):
            make(high=104.0)                       # below close 105
        with self.assertRaises(mc.CandleError):
            make(open=111.0, high=110.0)           # open above high

    def test_low_above_open_or_close_refused(self):
        with self.assertRaises(mc.CandleError):
            make(low=101.0)                        # above open 100
        with self.assertRaises(mc.CandleError):
            make(open=100.0, close=95.0, low=96.0)

    def test_flat_candle_is_consistent(self):
        flat = make(open=100.0, high=100.0, low=100.0, close=100.0)
        self.assertEqual(flat.high, flat.low)

    def test_non_positive_prices_refused(self):
        for field in ("open", "high", "low", "close"):
            for value in (0, 0.0, -1.0):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(mc.CandleError):
                        make(**{field: value})

    def test_non_finite_and_non_numeric_prices_refused(self):
        for field in ("open", "high", "low", "close"):
            for value in (float("nan"), float("inf"), float("-inf"), "100", None, True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(mc.CandleError):
                        make(**{field: value})


class VolumeTests(unittest.TestCase):
    def test_missing_volume_stays_none_and_is_never_zero(self):
        c = make(volume=None)
        self.assertIsNone(c.volume)
        self.assertNotEqual(c, make(volume=0.0))
        self.assertIsNone(c.to_dict()["volume"])

    def test_zero_volume_is_a_real_value(self):
        self.assertEqual(make(volume=0.0).volume, 0.0)
        self.assertEqual(make(volume=0).volume, 0.0)

    def test_negative_or_invalid_volume_refused(self):
        for value in (-1.0, float("nan"), float("inf"), "1000", True):
            with self.subTest(value=value):
                with self.assertRaises(mc.CandleError):
                    make(volume=value)

    def test_from_dict_requires_explicit_volume_key(self):
        data = make().to_dict()
        del data["volume"]
        with self.assertRaises(mc.CandleError):
            mc.Candle.from_dict(data)
        data["volume"] = None
        self.assertIsNone(mc.Candle.from_dict(data).volume)


class SerializationTests(unittest.TestCase):
    def test_exact_canonical_json(self):
        c = mc.Candle(T0, 100, 110, 90, 105, None)
        self.assertEqual(c.to_json(),
                         '{"close":105.0,"high":110.0,"low":90.0,"open":100.0,'
                         '"open_time_s":1609459200,"volume":null}')

    def test_repeated_serialization_is_identical(self):
        c = make()
        self.assertEqual({c.to_json() for _ in range(5)}, {c.to_json()})

    def test_json_round_trip(self):
        for c in (make(), make(volume=None), make(volume=0.0)):
            with self.subTest(c=c):
                self.assertEqual(mc.Candle.from_json(c.to_json()), c)
                self.assertEqual(mc.Candle.from_dict(c.to_dict()), c)

    def test_from_dict_refuses_unknown_or_missing_keys(self):
        data = make().to_dict()
        with self.assertRaises(mc.CandleError):
            mc.Candle.from_dict(dict(data, extra=1))
        data2 = make().to_dict()
        del data2["close"]
        with self.assertRaises(mc.CandleError):
            mc.Candle.from_dict(data2)
        with self.assertRaises(mc.CandleError):
            mc.Candle.from_dict([T0, 1, 2, 3, 4, 5])

    def test_from_json_refuses_malformed_text(self):
        for text in ("not json", "", "[1,2]", "null"):
            with self.subTest(text=text):
                with self.assertRaises(mc.CandleError):
                    mc.Candle.from_json(text)

    def test_json_contains_no_nan_or_infinity(self):
        def reject(token):
            raise ValueError(f"non-finite token in JSON: {token}")
        json.loads(make().to_json(), parse_constant=reject)   # would raise if NaN or Infinity appeared


if __name__ == "__main__":
    unittest.main()
