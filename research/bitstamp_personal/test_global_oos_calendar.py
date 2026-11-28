import unittest

from global_oos_calendar import GlobalOOSCalendarError, build_global_oos_calendar

START = 1_700_000_000
STEP = 3600
COUNT = 7000
END = START + COUNT * STEP


def dataset(symbol, offset, *, gap_at=None, end_shift=0):
    candles = []
    for index in range(offset, COUNT):
        if gap_at is not None and index == gap_at:
            continue
        opened = START + index * STEP
        candles.append({
            "open_timestamp": opened,
            "timestamp": opened + STEP,
            "open": "100", "high": "101", "low": "99",
            "close": "100", "volume": "1000",
        })
    if end_shift:
        candles[-1]["timestamp"] += end_shift
    return ({"market_symbol": symbol}, {"candles": candles})


class GlobalOOSCalendarTests(unittest.TestCase):
    def test_per_market_inception_maps_to_identical_utc_oos_and_holdout(self):
        btc = dataset("btcusd", 0)
        pepe = dataset("pepeusd", 120)
        result = build_global_oos_calendar([btc, pepe], end_timestamp=END)
        self.assertTrue(result["aligned"])
        self.assertEqual(result["calendar_version"], "PER_MARKET_INCEPTION_COMMON_UTC_OOS_V1")
        self.assertEqual(result["common_start_timestamp"], START + 120 * STEP)
        self.assertEqual(result["fold_plans_by_market"]["btcusd"][0]["train_start"], 0)
        self.assertEqual(result["fold_plans_by_market"]["pepeusd"][0]["train_start"], 0)
        self.assertGreater(
            result["fold_plans_by_market"]["btcusd"][0]["test_start"],
            result["fold_plans_by_market"]["pepeusd"][0]["test_start"],
        )
        self.assertEqual(
            result["market_calendars"]["btcusd"],
            result["market_calendars"]["pepeusd"],
        )
        self.assertEqual(
            result["holdouts_by_market"]["btcusd"]["start_timestamp"],
            result["holdouts_by_market"]["pepeusd"]["start_timestamp"],
        )
        self.assertEqual(
            result["holdouts_by_market"]["btcusd"]["end_timestamp_exclusive"],
            result["holdouts_by_market"]["pepeusd"]["end_timestamp_exclusive"],
        )

    def test_common_oos_window_must_have_sufficient_history(self):
        with self.assertRaisesRegex(GlobalOOSCalendarError, "at least 6000"):
            build_global_oos_calendar(
                [dataset("btcusd", 0), dataset("pepeusd", 1500)],
                end_timestamp=END,
            )

    def test_gap_in_any_market_blocks_global_calendar(self):
        with self.assertRaisesRegex(GlobalOOSCalendarError, "gap or overlap"):
            build_global_oos_calendar(
                [dataset("btcusd", 0), dataset("pepeusd", 120, gap_at=5000)],
                end_timestamp=END,
            )

    def test_different_end_boundary_blocks(self):
        with self.assertRaisesRegex(GlobalOOSCalendarError, "common end boundary"):
            build_global_oos_calendar(
                [dataset("btcusd", 0), dataset("pepeusd", 120, end_shift=STEP)],
                end_timestamp=END,
            )

    def test_non_hourly_boundary_and_duplicate_market_are_rejected(self):
        btc = dataset("btcusd", 0)
        btc[1]["candles"][100]["open_timestamp"] += 1
        with self.assertRaises(GlobalOOSCalendarError):
            build_global_oos_calendar([btc, dataset("pepeusd", 120)], end_timestamp=END)
        with self.assertRaisesRegex(GlobalOOSCalendarError, "unique"):
            build_global_oos_calendar(
                [dataset("btcusd", 0), dataset("btcusd", 120)], end_timestamp=END
            )


if __name__ == "__main__":
    unittest.main()
