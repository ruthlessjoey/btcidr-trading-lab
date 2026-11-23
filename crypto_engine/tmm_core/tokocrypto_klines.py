"""Offline parser for Tokocrypto NextMe's 12-field kline response.

This module only parses payloads supplied by the caller. It performs no HTTP,
DNS, authentication, credential, exchange-account or order operations. The
caller remains responsible for ensuring that data came from the approved
unauthenticated GET endpoint and that the requested market is approved.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


class KlinePayloadError(ValueError):
    """Raised when an exchange kline payload is malformed or not as-of safe."""


def _epoch_ms(value: Any, field: str, index: int) -> int:
    if isinstance(value, bool):
        raise KlinePayloadError(f"candle {index} {field} must be integer milliseconds")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdecimal():
        result = int(value)
    else:
        raise KlinePayloadError(f"candle {index} {field} must be integer milliseconds")
    if result < 0:
        raise KlinePayloadError(f"candle {index} {field} cannot be negative")
    return result


def _decimal(value: Any, field: str, index: int) -> Decimal:
    if isinstance(value, bool):
        raise KlinePayloadError(f"candle {index} {field} cannot be boolean")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise KlinePayloadError(f"candle {index} {field} is invalid") from exc
    if not result.is_finite():
        raise KlinePayloadError(f"candle {index} {field} must be finite")
    return result


def normalize_tokocrypto_klines(response: Mapping[str, Any], *, decision_time_ms: int) -> list[dict[str, Any]]:
    """Convert wrapped 12-field public klines to close-time epoch-second bars.

    The source API identifies bars by open time. This parser uses field 6
    (close time) for internal availability while preserving field 0 as the
    separate open timestamp used for next-bar execution event labels. Any
    candle whose close time is at/after decision time is rejected.
    """
    if isinstance(decision_time_ms, bool) or not isinstance(decision_time_ms, int) or decision_time_ms <= 0:
        raise KlinePayloadError("decision_time_ms must be a positive integer")
    if not isinstance(response, Mapping):
        raise KlinePayloadError("response must be an object")
    code = response.get("code")
    if isinstance(code, bool) or not isinstance(code, int) or code != 0:
        raise KlinePayloadError("Tokocrypto response code is not successful")
    rows = response.get("data")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise KlinePayloadError("response data must be a non-empty ordered candle list")

    candles: list[dict[str, Any]] = []
    previous_open: int | None = None
    previous_close: int | None = None
    for index, raw in enumerate(rows):
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 12:
            raise KlinePayloadError(f"candle {index} must contain exactly twelve documented fields")
        open_ms = _epoch_ms(raw[0], "open_time", index)
        close_ms = _epoch_ms(raw[6], "close_time", index)
        if close_ms <= open_ms:
            raise KlinePayloadError(f"candle {index} close time must be after open time")
        if close_ms >= decision_time_ms:
            raise KlinePayloadError(f"candle {index} is not closed as of decision time")
        if previous_open is not None and open_ms <= previous_open:
            raise KlinePayloadError(f"candle {index} open time is duplicated or out of order")
        if previous_close is not None and open_ms <= previous_close:
            raise KlinePayloadError(f"candle {index} overlaps the previous candle")

        values = {
            "open": _decimal(raw[1], "open", index),
            "high": _decimal(raw[2], "high", index),
            "low": _decimal(raw[3], "low", index),
            "close": _decimal(raw[4], "close", index),
            "volume": _decimal(raw[5], "volume", index),
        }
        if min(values[name] for name in ("open", "high", "low", "close")) <= 0:
            raise KlinePayloadError(f"candle {index} prices must be positive")
        if values["volume"] < 0:
            raise KlinePayloadError(f"candle {index} volume cannot be negative")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise KlinePayloadError(f"candle {index} high violates OHLC bounds")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise KlinePayloadError(f"candle {index} low violates OHLC bounds")

        gap_before_ms = (0 if previous_close is None
                         else max(0, open_ms - previous_close - 1))
        candles.append({
            "timestamp": close_ms // 1000,
            "open_timestamp": open_ms // 1000,
            "gap_before_ms": gap_before_ms,
            "open": str(values["open"]),
            "high": str(values["high"]),
            "low": str(values["low"]),
            "close": str(values["close"]),
            "volume": str(values["volume"]),
            "source_open_time_ms": open_ms,
            "source_close_time_ms": close_ms,
        })
        previous_open, previous_close = open_ms, close_ms

    for index in range(1, len(candles)):
        if candles[index]["timestamp"] <= candles[index - 1]["timestamp"]:
            raise KlinePayloadError("close-time seconds are not strictly increasing")
    return candles
