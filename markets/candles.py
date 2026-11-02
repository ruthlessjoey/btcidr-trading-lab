"""markets/candles.py - market-neutral OHLCV candle schema (S2.1).

Standard library only. Deterministic. No network, no orders, no credentials.

Conventions:
  * open_time_s is the candle OPEN time, an integer count of UTC epoch seconds.
  * Timestamp policy: open_time_s must be a NON-NEGATIVE integer, from 0 (1970-01-01T00:00:00Z) through
    9999-12-31T23:59:59Z. Pre-1970 data is UNSUPPORTED for now and is refused, not clamped or shifted.
    Adding pre-epoch support later would be an explicit schema change, not an edit to this check.
  * Timezone-aware UTC datetimes are used only at I/O boundaries (utc_datetime, epoch_seconds).
    Naive datetimes are refused.
  * volume is optional. None means "not supplied" and is never converted to 0.
    0.0 means a reported volume of zero. The two are never equal.
  * Prices must be finite and positive. high >= max(open, close), low <= min(open, close), high >= low.
  * Serialization is canonical: sorted keys, no whitespace, finite numbers only.
"""
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

MIN_OPEN_TIME_S = 0
MAX_OPEN_TIME_S = 253402300799          # 9999-12-31T23:59:59Z
FIELDS = ("open_time_s", "open", "high", "low", "close", "volume")


class CandleError(ValueError):
    """A candle or timestamp is invalid. Nothing is coerced or repaired."""


def _check_time(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CandleError(f"open_time_s must be an integer UTC epoch second, not {type(value).__name__}")
    if value < MIN_OPEN_TIME_S:
        raise CandleError(f"open_time_s {value} is before 1970-01-01T00:00:00Z; pre-1970 timestamps "
                          "are unsupported for now")
    if value > MAX_OPEN_TIME_S:
        raise CandleError(f"open_time_s {value} is after 9999-12-31T23:59:59Z, the supported UTC range")
    return value


def _number(name, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandleError(f"{name} must be a number, not {type(value).__name__}")
    number = float(value)
    if not math.isfinite(number):
        raise CandleError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class Candle:
    open_time_s: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def __post_init__(self):
        _check_time(self.open_time_s)
        o = _number("open", self.open)
        h = _number("high", self.high)
        lo = _number("low", self.low)
        c = _number("close", self.close)
        for name, value in (("open", o), ("high", h), ("low", lo), ("close", c)):
            if value <= 0:
                raise CandleError(f"{name} must be positive")
        if h < lo:
            raise CandleError("high is below low")
        if h < max(o, c):
            raise CandleError("high is below open or close")
        if lo > min(o, c):
            raise CandleError("low is above open or close")
        vol = None if self.volume is None else _number("volume", self.volume)
        if vol is not None and vol < 0:
            raise CandleError("volume must not be negative")
        object.__setattr__(self, "open", o)
        object.__setattr__(self, "high", h)
        object.__setattr__(self, "low", lo)
        object.__setattr__(self, "close", c)
        object.__setattr__(self, "volume", vol)

    def to_dict(self):
        return {"open_time_s": self.open_time_s, "open": self.open, "high": self.high,
                "low": self.low, "close": self.close, "volume": self.volume}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise CandleError("candle must be a JSON object")
        if set(data) != set(FIELDS):
            raise CandleError(f"candle must have exactly the keys {sorted(FIELDS)}; "
                              "volume must be present, as null if not supplied")
        return cls(**data)

    @classmethod
    def from_json(cls, text):
        try:
            data = json.loads(text)
        except (TypeError, ValueError) as e:
            raise CandleError(f"candle is not valid JSON: {e}")
        return cls.from_dict(data)


def check_alignment(candle, timeframe_s):
    """Confirms the candle opens on a boundary of the given timeframe. Returns the candle."""
    if isinstance(timeframe_s, bool) or not isinstance(timeframe_s, int) or timeframe_s <= 0:
        raise CandleError("timeframe_s must be a positive integer number of seconds")
    if candle.open_time_s % timeframe_s:
        raise CandleError(f"open_time_s {candle.open_time_s} is not aligned to a {timeframe_s}s timeframe")
    return candle


def utc_datetime(open_time_s):
    """Timezone-aware UTC datetime for an I/O boundary."""
    _check_time(open_time_s)
    return datetime.fromtimestamp(open_time_s, tz=timezone.utc)


def epoch_seconds(dt):
    """Integer UTC epoch seconds from a timezone-aware datetime. Naive or sub-second values are refused."""
    if not isinstance(dt, datetime):
        raise CandleError("expected a datetime")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise CandleError("naive datetimes are refused; use a timezone-aware datetime")
    if dt.microsecond:
        raise CandleError("sub-second timestamps are refused")
    try:
        seconds = dt.astimezone(timezone.utc).timestamp()
    except (OverflowError, OSError, ValueError) as e:
        # Near the datetime limits, a negative UTC offset can push the UTC value out of range.
        raise CandleError(f"datetime {dt.isoformat()} cannot be converted to UTC epoch seconds "
                          f"within the supported range: {e}")
    return _check_time(int(seconds))
