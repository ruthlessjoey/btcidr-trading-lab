"""Versioned common-UTC OOS calendar for per-market inception datasets.

Each market retains its own verified inception history for training and indicator
warmup. All markets share the same UTC OOS windows, embargoes, liquidation bars,
and untouched final holdout. This module is offline and performs no I/O.
"""
from __future__ import annotations

from typing import Any

FOLD_COUNT = 5
EMBARGO_BARS = 50
MINIMUM_TRAIN_BARS = 1500
MINIMUM_TEST_BARS = 500
INITIAL_TRAIN_NUMERATOR = 2
INITIAL_TRAIN_DENOMINATOR = 5
HOLDOUT_START_NUMERATOR = 9
HOLDOUT_START_DENOMINATOR = 10


class GlobalOOSCalendarError(ValueError):
    """Datasets cannot support one identical, contiguous UTC OOS calendar."""


def _timestamp(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GlobalOOSCalendarError(f"{field} must be a nonnegative integer timestamp")
    return value


def _plan_folds(count: int) -> list[dict[str, int | str]]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 6000:
        raise GlobalOOSCalendarError("common UTC window requires at least 6000 hourly candles")
    initial_train_end = count * INITIAL_TRAIN_NUMERATOR // INITIAL_TRAIN_DENOMINATOR
    final_holdout_start = count * HOLDOUT_START_NUMERATOR // HOLDOUT_START_DENOMINATOR
    if initial_train_end - EMBARGO_BARS < MINIMUM_TRAIN_BARS:
        raise GlobalOOSCalendarError("initial common-calendar training window is too small")
    cursor = initial_train_end + EMBARGO_BARS
    folds = []
    for index in range(FOLD_COUNT):
        remaining = FOLD_COUNT - index
        reserved = remaining * (1 + EMBARGO_BARS)
        test_length = (final_holdout_start - cursor - reserved) // remaining
        if test_length < MINIMUM_TEST_BARS:
            raise GlobalOOSCalendarError("common-calendar OOS fold is too small")
        test_start = cursor
        test_end = test_start + test_length
        if test_end >= final_holdout_start:
            raise GlobalOOSCalendarError("common-calendar fold overlaps untouched holdout")
        folds.append({
            "fold_id": f"wf-{index + 1:02d}",
            "train_start": 0,
            "train_end": test_start - EMBARGO_BARS,
            "test_start": test_start,
            "test_end": test_end,
            "liquidation_index": test_end,
        })
        cursor = test_end + 1 + EMBARGO_BARS
    return folds


def build_global_oos_calendar(
    market_datasets: list[tuple[dict, dict]],
    *,
    end_timestamp: int,
    interval_seconds: int = 3600,
) -> dict[str, Any]:
    """Build per-market index plans over identical UTC OOS/holdout timestamps.

    The common evaluation start is the latest verified market inception. Earlier
    markets retain all earlier candles as expanding training history. No rows are
    synthesized, backfilled, or forward-filled.
    """
    end_timestamp = _timestamp(end_timestamp, "end_timestamp")
    interval_seconds = _timestamp(interval_seconds, "interval_seconds")
    if interval_seconds <= 0:
        raise GlobalOOSCalendarError("interval_seconds must be positive")
    if not isinstance(market_datasets, list) or len(market_datasets) < 2:
        raise GlobalOOSCalendarError("at least two market datasets are required")

    indexed: dict[str, dict[str, Any]] = {}
    common_start = None
    for market, dataset in market_datasets:
        symbol = market.get("market_symbol") if isinstance(market, dict) else None
        candles = dataset.get("candles") if isinstance(dataset, dict) else None
        if not isinstance(symbol, str) or not symbol or symbol in indexed:
            raise GlobalOOSCalendarError("market symbols must be unique non-empty strings")
        if not isinstance(candles, list) or len(candles) < 2:
            raise GlobalOOSCalendarError(f"{symbol} has insufficient candle rows")
        opens = []
        previous_close = None
        for index, candle in enumerate(candles):
            if not isinstance(candle, dict):
                raise GlobalOOSCalendarError(f"{symbol} candle {index} is not an object")
            opened = _timestamp(candle.get("open_timestamp"), f"{symbol}[{index}].open_timestamp")
            closed = _timestamp(candle.get("timestamp"), f"{symbol}[{index}].timestamp")
            if closed != opened + interval_seconds:
                raise GlobalOOSCalendarError(f"{symbol} candle {index} has an invalid close boundary")
            if previous_close is not None and opened != previous_close:
                raise GlobalOOSCalendarError(f"{symbol} candle history has a gap or overlap")
            opens.append(opened)
            previous_close = closed
        if previous_close != end_timestamp:
            raise GlobalOOSCalendarError(f"{symbol} does not reach the common end boundary")
        start = opens[0]
        common_start = start if common_start is None else max(common_start, start)
        indexed[symbol] = {
            "opens": opens,
            "open_to_index": {timestamp: index for index, timestamp in enumerate(opens)},
            "first_open_timestamp": start,
            "last_close_timestamp": previous_close,
        }

    if common_start is None or common_start >= end_timestamp:
        raise GlobalOOSCalendarError("no common UTC evaluation interval exists")
    common_opens = [
        timestamp for timestamp in indexed[next(iter(indexed))]["opens"]
        if common_start <= timestamp < end_timestamp
    ]
    if not common_opens or common_opens[0] != common_start:
        raise GlobalOOSCalendarError("common UTC start is not an exact candle boundary")
    expected = list(range(common_start, end_timestamp, interval_seconds))
    if common_opens != expected:
        raise GlobalOOSCalendarError("reference market common UTC calendar is not contiguous")

    for symbol, item in indexed.items():
        observed = [t for t in item["opens"] if common_start <= t < end_timestamp]
        if observed != expected:
            raise GlobalOOSCalendarError(
                f"{symbol} does not contain the exact shared UTC evaluation calendar"
            )
        item["common_start_index"] = item["open_to_index"][common_start]

    common_count = len(expected)
    relative_folds = _plan_folds(common_count)
    plans = {}
    calendars = {}
    for symbol, item in indexed.items():
        offset = item["common_start_index"]
        folds = []
        intervals = []
        for fold in relative_folds:
            mapped = {
                "fold_id": fold["fold_id"],
                "train_start": 0,
                "train_end": offset + int(fold["train_end"]),
                "test_start": offset + int(fold["test_start"]),
                "test_end": offset + int(fold["test_end"]),
                "liquidation_index": offset + int(fold["liquidation_index"]),
            }
            folds.append(mapped)
            start_ts = item["opens"][mapped["test_start"]]
            end_ts = item["opens"][mapped["test_end"]]
            liquidation_ts = item["opens"][mapped["liquidation_index"]]
            intervals.append({
                "fold_id": mapped["fold_id"],
                "oos_start_timestamp": start_ts,
                "oos_end_timestamp_exclusive": end_ts,
                "liquidation_open_timestamp": liquidation_ts,
            })
        plans[symbol] = folds
        calendars[symbol] = intervals

    reference = calendars[next(iter(calendars))]
    if any(calendar != reference for calendar in calendars.values()):
        raise GlobalOOSCalendarError("mapped market folds do not share identical UTC boundaries")

    holdout_relative = common_count * HOLDOUT_START_NUMERATOR // HOLDOUT_START_DENOMINATOR
    holdouts = {
        symbol: {
            "start_index": item["common_start_index"] + holdout_relative,
            "end_index": len(item["opens"]),
            "start_timestamp": item["opens"][item["common_start_index"] + holdout_relative],
            "end_timestamp_exclusive": end_timestamp,
            "status": "RESERVED_UNTOUCHED_NOT_EVALUATED",
        }
        for symbol, item in indexed.items()
    }
    return {
        "aligned": True,
        "status": "ALIGNED_PER_MARKET_INCEPTION_COMMON_UTC_OOS_V1",
        "calendar_version": "PER_MARKET_INCEPTION_COMMON_UTC_OOS_V1",
        "common_start_timestamp": common_start,
        "common_end_timestamp_exclusive": end_timestamp,
        "common_interval_seconds": interval_seconds,
        "common_bar_count": common_count,
        "reference_market": next(iter(calendars)),
        "market_calendars": calendars,
        "fold_plans_by_market": plans,
        "holdouts_by_market": holdouts,
        "training_policy": "each market retains its own verified inception through each common UTC fold training cutoff",
        "oos_policy": "identical UTC OOS start, end-exclusive and next-open liquidation timestamps across all markets",
    }
