"""Bounded Tokocrypto candle retrieval using a caller-supplied UTC clock.

This module deliberately does not call Tokocrypto server-time, symbol-discovery,
account, order, or any other endpoint. The supplied clock is an explicit input;
its synchronization accuracy is not independently verified here.
"""
from __future__ import annotations

import math
import re
from typing import Callable

import fetcher

MAX_LOOKBACK_DAYS = 14
PAIR_RE = re.compile(r"^[A-Z0-9]{2,10}_[A-Z0-9]{2,10}$")
# Only the single Tokocrypto market configured in the reviewed repository
# snapshot is eligible for this adapter. This does not prove the listing is live.
ALLOWED_TOKOCRYPTO_PAIRS = frozenset({"BTC_USDT"})


def build_window(*, pair: str, timeframe: str, lookback_days: int,
                 now_epoch_utc: int) -> dict[str, object]:
    """Build a closed-candle UTC window without querying provider time."""
    if not isinstance(pair, str) or not PAIR_RE.fullmatch(pair):
        raise ValueError("pair must use BASE_QUOTE uppercase symbol form")
    if pair not in ALLOWED_TOKOCRYPTO_PAIRS:
        raise ValueError("pair is not in the reviewed Tokocrypto adapter allowlist")
    if timeframe not in fetcher.TF_SECONDS:
        raise ValueError("timeframe is not supported by the approved candle adapter")
    if (isinstance(lookback_days, bool) or not isinstance(lookback_days, int)
            or not 1 <= lookback_days <= MAX_LOOKBACK_DAYS):
        raise ValueError("lookback_days must be an integer from 1 to 14")
    if (isinstance(now_epoch_utc, bool) or not isinstance(now_epoch_utc, int)
            or now_epoch_utc <= 0):
        raise ValueError("now_epoch_utc must be a positive integer UTC epoch")

    interval_seconds = fetcher.TF_SECONDS[timeframe]
    end_exclusive = (now_epoch_utc // interval_seconds) * interval_seconds
    start_inclusive = end_exclusive - lookback_days * 86400
    if start_inclusive <= 0:
        raise ValueError("requested UTC window is outside the supported epoch range")

    return {
        "pair": pair,
        "timeframe": timeframe,
        "interval_seconds": interval_seconds,
        "start_timestamp": start_inclusive,
        "end_timestamp_inclusive": end_exclusive - 1,
        "end_exclusive_timestamp": end_exclusive,
        "clock_source": "caller_supplied_utc_epoch",
        "provider_clock_skew": "NOT_VERIFIED",
    }


def validate_complete_candle_grid(
    candles,
    *,
    start_epoch_utc: int,
    end_epoch_utc_exclusive: int,
    timeframe: str,
) -> int:
    """Validate exact boundary coverage, contiguity and OHLCV integrity.

    Returns the expected candle count. Missing bars are never interpolated.
    This pure validator is shared by current-window and fixed-window fetchers.
    """
    if timeframe not in fetcher.TF_SECONDS:
        raise ValueError("timeframe is not supported")
    for name, value in (
        ("start_epoch_utc", start_epoch_utc),
        ("end_epoch_utc_exclusive", end_epoch_utc_exclusive),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer UTC epoch")
    interval = fetcher.TF_SECONDS[timeframe]
    if (start_epoch_utc % interval != 0
            or end_epoch_utc_exclusive % interval != 0
            or end_epoch_utc_exclusive <= start_epoch_utc):
        raise ValueError("UTC window boundaries must be increasing and timeframe-aligned")
    if not candles:
        raise fetcher.ApiError("approved Tokocrypto klines endpoint returned zero candles")

    previous_open = None
    expected_open = start_epoch_utc
    for candle in candles:
        if (isinstance(candle.time, bool) or not isinstance(candle.time, int)
                or candle.time % interval != 0
                or candle.time < start_epoch_utc
                or candle.time + interval > end_epoch_utc_exclusive):
            raise fetcher.ApiError("Tokocrypto returned a candle outside the requested closed UTC window")
        if candle.time < expected_open:
            raise fetcher.ApiError("Tokocrypto returned duplicate or out-of-order candle timestamps")
        if candle.time > expected_open:
            missing = (candle.time - expected_open) // interval
            raise fetcher.ApiError(
                f"Tokocrypto candle grid is incomplete: {missing} missing interval(s) "
                f"before candle {candle.time}"
            )
        if previous_open is not None and candle.time <= previous_open:
            raise fetcher.ApiError("Tokocrypto returned duplicate or out-of-order candle timestamps")
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if any(not math.isfinite(value) for value in values):
            raise fetcher.ApiError("Tokocrypto returned non-finite OHLCV values")
        if min(candle.open, candle.high, candle.low, candle.close) <= 0 or candle.volume < 0:
            raise fetcher.ApiError("Tokocrypto returned nonpositive prices or negative volume")
        if (candle.high < max(candle.open, candle.close, candle.low)
                or candle.low > min(candle.open, candle.close, candle.high)):
            raise fetcher.ApiError("Tokocrypto returned inconsistent OHLC bounds")
        previous_open = candle.time
        expected_open += interval

    if expected_open != end_epoch_utc_exclusive:
        missing = (end_epoch_utc_exclusive - expected_open) // interval
        raise fetcher.ApiError(
            f"Tokocrypto candle grid is incomplete: {missing} trailing interval(s) are missing"
        )

    expected_candles = (end_epoch_utc_exclusive - start_epoch_utc) // interval
    if len(candles) != expected_candles:
        raise fetcher.ApiError("Tokocrypto candle count does not match the complete requested interval grid")
    return expected_candles


def fetch_tokocrypto_candles(
    *,
    pair: str,
    timeframe: str,
    lookback_days: int,
    now_epoch_utc: int,
    timeout: int = 15,
    retries: int = 3,
    opener: Callable | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, object]:
    """Fail closed: current-window retrieval requires a reviewed UTC attestor.

    The prior version accepted any caller-supplied positive integer epoch and
    proceeded to the network despite documenting that its synchronization was
    unverified. This compatibility entry point is intentionally disabled.
    Historical fixed-boundary retrieval remains available through
    `tokocrypto_fixed_window.fetch_tokocrypto_fixed_window`, subject to its
    separately documented preregistration and market-identity gates.
    """
    raise fetcher.ApiError(
        "Tokocrypto current-window collection is blocked: caller-supplied UTC "
        "time is unauthenticated; a platform host-clock attestor must be "
        "implemented and independently reviewed before current-window retrieval"
    )
