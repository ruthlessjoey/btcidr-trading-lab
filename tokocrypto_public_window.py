"""Bounded Tokocrypto candle retrieval using a caller-supplied UTC clock.

This module deliberately does not call Tokocrypto server-time, symbol-discovery,
account, order, or any other endpoint. The supplied clock is an explicit input;
its synchronization accuracy is not independently verified here.
"""
from __future__ import annotations

import re
from typing import Callable

import fetcher

MAX_LOOKBACK_DAYS = 14
PAIR_RE = re.compile(r"^[A-Z0-9]{2,10}_[A-Z0-9]{2,10}$")


def build_window(*, pair: str, timeframe: str, lookback_days: int,
                 now_epoch_utc: int) -> dict[str, object]:
    """Build a closed-candle UTC window without querying provider time."""
    if not isinstance(pair, str) or not PAIR_RE.fullmatch(pair):
        raise ValueError("pair must use BASE_QUOTE uppercase symbol form")
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
    """Fetch only the approved public klines endpoint for the bounded window.

    The caller must supply a trusted UTC epoch. This function never requests
    provider server time and does not claim that the caller's clock is synced.
    """
    if (isinstance(timeout, bool) or not isinstance(timeout, int)
            or not 1 <= timeout <= 60):
        raise ValueError("timeout must be an integer from 1 to 60 seconds")
    if (isinstance(retries, bool) or not isinstance(retries, int)
            or not 1 <= retries <= 5):
        raise ValueError("retries must be an integer from 1 to 5")

    window = build_window(
        pair=pair, timeframe=timeframe, lookback_days=lookback_days,
        now_epoch_utc=now_epoch_utc,
    )
    source = fetcher.Source(
        name="tokocrypto", style="binance_style",
        base_url=fetcher.TOKOCRYPTO_BASE_URL,
    )
    kwargs = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    candles, requests_made = fetcher.fetch_candles(
        source, pair, timeframe,
        int(window["start_timestamp"]),
        int(window["end_timestamp_inclusive"]),
        timeout, retries,
        opener if opener is not None else fetcher.default_opener,
        kwargs.get("sleep", __import__("time").sleep),
    )
    if not candles:
        raise fetcher.ApiError("approved Tokocrypto klines endpoint returned zero candles")
    previous_open = None
    for candle in candles:
        if (isinstance(candle.time, bool) or not isinstance(candle.time, int)
                or candle.time % int(window["interval_seconds"]) != 0
                or candle.time < int(window["start_timestamp"])
                or candle.time + int(window["interval_seconds"]) >
                   int(window["end_exclusive_timestamp"])):
            raise fetcher.ApiError("Tokocrypto returned a candle outside the requested closed UTC window")
        if previous_open is not None and candle.time <= previous_open:
            raise fetcher.ApiError("Tokocrypto returned duplicate or out-of-order candle timestamps")
        previous_open = candle.time
    return {
        **window,
        "candles": candles,
        "requests_made": requests_made,
        "provider": "tokocrypto",
        "endpoint": fetcher.TOKOCRYPTO_KLINES_PATH,
    }
