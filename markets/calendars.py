"""markets/calendars.py - which candle open times are EXPECTED for a market (S2.2).

Standard library only. Deterministic. No network access, no holiday, weekend or session data.

A calendar answers one question for an open time and a timeframe: is a candle expected here?
  True   the market should trade in this interval. If the candle is absent, it is a GENUINE MISSING candle.
  False  the market is closed in this interval. If the candle is absent, it is an EXPECTED CLOSURE, not an error.

Implemented:
  CryptoCalendar24x7   every timeframe-aligned open time is expected (crypto trades continuously).

Interface-only stubs. They raise CalendarNotImplemented until an approved session schedule exists, and they
never pass silently as 24/7:
  EquityCalendarStub, FxCalendarStub.
  No weekend, holiday or session schedule is invented in this module.

Timestamps are integer UTC epoch seconds, as in markets.candles. Negative values are refused, matching the
S2.1 timestamp policy.
"""
import abc


class CalendarError(ValueError):
    """A calendar input is invalid."""


class CalendarNotImplemented(CalendarError):
    """This calendar has no approved schedule yet. It must not be treated as open or 24/7."""


def _check_int(name, value, minimum):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CalendarError(f"{name} must be an integer, not {type(value).__name__}")
    if value < minimum:
        raise CalendarError(f"{name} must be at least {minimum}, got {value}")
    return value


class Calendar(abc.ABC):
    """Interface. Subclasses decide whether a candle opening at a given time is expected."""

    name = "abstract"

    @abc.abstractmethod
    def is_expected(self, open_time_s, timeframe_s):
        """True if a candle opening at open_time_s (UTC epoch seconds) is expected for timeframe_s."""

    def _inputs(self, open_time_s, timeframe_s):
        _check_int("open_time_s", open_time_s, 0)
        _check_int("timeframe_s", timeframe_s, 1)
        return open_time_s, timeframe_s


class CryptoCalendar24x7(Calendar):
    """Crypto trades continuously. Every timeframe-aligned open time is expected."""

    name = "crypto-24x7"

    def is_expected(self, open_time_s, timeframe_s):
        open_time_s, timeframe_s = self._inputs(open_time_s, timeframe_s)
        return open_time_s % timeframe_s == 0


class _StubCalendar(Calendar):
    """Interface only. Input checks run first; the answer is never guessed."""

    def is_expected(self, open_time_s, timeframe_s):
        self._inputs(open_time_s, timeframe_s)
        raise CalendarNotImplemented(
            f"{self.name}: no approved session schedule is available; refusing to guess one")


class EquityCalendarStub(_StubCalendar):
    name = "equity-stub"


class FxCalendarStub(_StubCalendar):
    name = "fx-stub"
