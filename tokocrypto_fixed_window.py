"""Fixed-UTC-boundary Tokocrypto candle retrieval for preregistered research.

No system clock or provider server-time endpoint is read. The caller supplies
frozen boundaries. This module does not verify that those boundaries are in the
past, authenticate them, or certify provider clock synchronization.
"""
from __future__ import annotations

import re
from typing import Callable

import fetcher
from tokocrypto_public_window import (
    ALLOWED_TOKOCRYPTO_PAIRS,
    validate_complete_candle_grid,
)

MAX_FIXED_WINDOW_DAYS = 14
PAIR_RE = re.compile(r"^[A-Z0-9]{2,10}_[A-Z0-9]{2,10}$")


def validate_fixed_window(*, pair: str, timeframe: str,
                          start_epoch_utc: int,
                          end_epoch_utc_exclusive: int) -> dict[str, object]:
    """Validate a finite, aligned UTC interval without consulting current time."""
    if not isinstance(pair, str) or not PAIR_RE.fullmatch(pair):
        raise ValueError("pair must use BASE_QUOTE uppercase symbol form")
    if pair not in ALLOWED_TOKOCRYPTO_PAIRS:
        raise ValueError("pair is not in the reviewed Tokocrypto adapter allowlist")
    if timeframe not in fetcher.TF_SECONDS:
        raise ValueError("timeframe is not supported by the approved candle adapter")
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
        raise ValueError("fixed UTC boundaries must be increasing and timeframe-aligned")
    duration = end_epoch_utc_exclusive - start_epoch_utc
    if duration > MAX_FIXED_WINDOW_DAYS * 86400:
        raise ValueError("fixed UTC window exceeds the 14-day request bound")

    return {
        "pair": pair,
        "timeframe": timeframe,
        "interval_seconds": interval,
        "start_timestamp": start_epoch_utc,
        "end_timestamp_inclusive": end_epoch_utc_exclusive - 1,
        "end_exclusive_timestamp": end_epoch_utc_exclusive,
        "window_mode": "fixed_utc_preregistered",
        "clock_source": "fixed_utc_boundaries",
        "provider_clock_skew": "NOT_VERIFIED",
        "temporal_past_assertion": "NOT_PERFORMED",
    }


def fetch_tokocrypto_fixed_window(
    *,
    pair: str,
    timeframe: str,
    start_epoch_utc: int,
    end_epoch_utc_exclusive: int,
    timeout: int = 15,
    retries: int = 3,
    opener: Callable | None = None,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, object]:
    """Fetch an explicitly frozen UTC interval via the sole approved klines URL.

    No current wall-clock value, provider time, symbol-discovery or other
    Tokocrypto endpoint is used. All network behavior is delegated to the
    existing bounded fetcher and injectable synthetic opener.
    """
    if (isinstance(timeout, bool) or not isinstance(timeout, int)
            or not 1 <= timeout <= 60):
        raise ValueError("timeout must be an integer from 1 to 60 seconds")
    if (isinstance(retries, bool) or not isinstance(retries, int)
            or not 1 <= retries <= 5):
        raise ValueError("retries must be an integer from 1 to 5")

    window = validate_fixed_window(
        pair=pair,
        timeframe=timeframe,
        start_epoch_utc=start_epoch_utc,
        end_epoch_utc_exclusive=end_epoch_utc_exclusive,
    )
    source = fetcher.Source(
        name="tokocrypto", style="binance_style",
        base_url=fetcher.TOKOCRYPTO_BASE_URL,
    )
    candles, requests_made = fetcher.fetch_candles(
        source, pair, timeframe,
        start_epoch_utc, end_epoch_utc_exclusive - 1,
        timeout, retries,
        opener if opener is not None else fetcher.default_opener,
        sleep if sleep is not None else __import__("time").sleep,
        _allow_tokocrypto_fixed_window=True,
    )
    expected_candles = validate_complete_candle_grid(
        candles,
        start_epoch_utc=start_epoch_utc,
        end_epoch_utc_exclusive=end_epoch_utc_exclusive,
        timeframe=timeframe,
    )
    return {
        **window,
        "candles": candles,
        "requests_made": requests_made,
        "expected_candles": expected_candles,
        "received_candles": len(candles),
        "data_quality_status": "COMPLETE_CONTIGUOUS_CLOSED_GRID",
        "provider": "tokocrypto",
        "endpoint": fetcher.TOKOCRYPTO_KLINES_PATH,
    }
