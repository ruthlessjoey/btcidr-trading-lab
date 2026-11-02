"""markets/validation.py - pure, deterministic validation of one candle series (S2.2, range-semantics correction).

Standard library only. No network, no I/O, no clock reads, no strategy decisions.

validate_series(candles, calendar, timeframe_s, now_s, *, start_s=None, end_s=None, ...) returns a
ValidationReport. Data problems are reported as checks with status PASS, WARN or FAIL. Argument problems raise
ValidationError. A calendar that is not implemented raises CalendarNotImplemented, including for empty input,
and is never converted into a pass.

Status semantics
  FAIL  the series must not be used as a research input without correction.
  WARN  the series may be used, but a person should look at it. Price spikes, partial coverage and a missing
        start_s are WARN.
  PASS  the check found nothing to report.
  ok    True when no check is FAIL. A WARN does not make ok False.

The report contains no strategy decision and no field a strategy could read as one.

REQUESTED VERSUS EFFECTIVE RANGE
  The report keeps two ranges apart:
    requested_start_s, requested_end_s   exactly what the caller asked for (None when omitted)
    range_start_s, range_end_s           the EFFECTIVE range that was actually validated, or None
  The effective range never extends past the last COMPLETED grid slot at now_s, because a slot that has not
  closed cannot be missing. Incomplete future slots are never counted as missing expected candles.

COVERAGE (the explicit statement of what was validated)
  coverage == COVERAGE_COMPLETE   the whole requested range was validated. fully_validated is True.
  coverage == COVERAGE_PARTIAL    only part of the requested range was validated. coverage_reason says why.
                                  This includes an explicit end_s beyond the last completed slot, and an
                                  omitted start_s (leading completeness not established).
  coverage == COVERAGE_NONE       no completed slot in the requested range was validated, because no slot has
                                  completed at now_s, the start is after the last completed slot (future start),
                                  or no range could be established. range_start_s and range_end_s are None.
  The 'range' check is PASS only for COVERAGE_COMPLETE. Otherwise it is WARN. A report is therefore never
  presented as fully validated unless coverage is COVERAGE_COMPLETE.

THE EXPECTED RANGE (completeness boundaries)
  start_s  Expected first grid time. Must be a non-negative integer aligned to timeframe_s. If OMITTED, the first
           OBSERVED candle is used for the grid, and leading completeness is NOT established (coverage PARTIAL).
           The observed first and last candles are never treated as proof of the intended boundaries.
  end_s    Expected final grid time. Must be aligned, and not before start_s. If OMITTED, the effective end is
           derived from now_s: the last completed grid time at now_s. If supplied, it is kept as requested, and
           the effective end is min(end_s, last completed grid time). Where the requested end is beyond the last
           completed slot, coverage is PARTIAL.

EXPECTED MISSING, EXPECTED CLOSURE, UNEXPECTED
  For each grid slot in the effective range:
    expected and absent          -> missing_expected      (FAIL)
    not expected and absent      -> expected_closures     (PASS: the market was closed; not an error)
  For each observed candle at an aligned time in the effective range:
    not expected                 -> unexpected_candles    (FAIL)

MISALIGNED CANDLES
  A misaligned candle lies inside one grid slot. That slot is then occupied, so it is NOT reported as
  missing. Instead the alignment check FAILs once and names the occupied slots. Unrelated missing slots are
  still reported.

BOUNDED REPORTING AND WORK
  Missing and closure counts are exact totals. Only the first sample_limit timestamps of each category are
  kept, and a *_truncated flag says when more exist. Grid work is limited by max_grid_slots, applied to the
  EFFECTIVE range actually evaluated. A requested range whose completed part is too large raises
  ValidationError, so completeness is never silently skipped. For the exact CryptoCalendar24x7 class the
  totals are computed arithmetically, and samples are found by walking the observed times.

Checks, in order: non_empty, range, ordering, duplicates, alignment, ohlc, volume, out_of_range,
expected_missing, unexpected_candles, expected_closures, completed, freshness, price_spikes.

Completed and freshness. now_s is REQUIRED and explicit. A candle is completed when open + timeframe <= now_s.
Freshness compares now_s with the close of the NEWEST OBSERVED candle, against max_age_s (default 48 hours).

Price spikes compare each close with the previous close, only between consecutive grid steps. A spike is a
WARN and never a FAIL.
"""
import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from markets.calendars import Calendar, CryptoCalendar24x7
from markets.candles import Candle

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
_RANK = {PASS: 0, WARN: 1, FAIL: 2}

COVERAGE_COMPLETE = "complete"
COVERAGE_PARTIAL = "partial"
COVERAGE_NONE = "none"

FRESHNESS_LIMIT_S = 172800          # 48 hours, the same research limit as S1. Defined here, not imported from S1.
SPIKE_THRESHOLD = 0.25              # a close-to-close move above 25% is reported as a WARN
DEFAULT_SAMPLE_LIMIT = 20           # timestamps kept per category; totals are always exact
MAX_GRID_SLOTS = 1_000_000          # largest EFFECTIVE expected-slot range a single call will evaluate


class ValidationError(ValueError):
    """An argument to validate_series is invalid or out of bounds. This is a caller error, not a data finding."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class PriceSpike:
    open_time_s: int
    change: float   # fractional close-to-close change from the previous consecutive candle


@dataclass(frozen=True)
class ValidationReport:
    calendar: str
    timeframe_s: int
    now_s: int
    row_count: int
    first_open_s: Optional[int]       # observed
    last_open_s: Optional[int]        # observed
    requested_start_s: Optional[int]  # exactly as the caller supplied it; None when omitted
    requested_end_s: Optional[int]
    range_start_s: Optional[int]      # EFFECTIVE validated range; None when coverage is COVERAGE_NONE
    range_end_s: Optional[int]
    coverage: str                     # COVERAGE_COMPLETE, COVERAGE_PARTIAL or COVERAGE_NONE
    coverage_reason: Optional[str]    # why coverage is not complete; None when complete
    sample_limit: int
    checks: tuple
    missing_expected: tuple           # bounded sample of absent expected slots
    missing_expected_total: int
    missing_expected_truncated: bool
    expected_closures: tuple          # bounded sample of absent slots the calendar marks closed
    expected_closures_total: int
    expected_closures_truncated: bool
    unexpected_candles: tuple         # bounded sample of observed candles at closed times
    unexpected_total: int
    unexpected_truncated: bool
    misaligned_slots: tuple           # bounded sample of slots occupied only by a misaligned candle
    misaligned_slot_total: int
    misaligned_slot_truncated: bool
    duplicate_open_s: tuple           # input-bounded: never sampled
    price_spikes: tuple               # input-bounded: never sampled

    @property
    def status(self):
        """The worst status among the checks. PASS when there are no checks."""
        return max((c.status for c in self.checks), key=_RANK.__getitem__, default=PASS)

    @property
    def ok(self):
        """True when no check is FAIL. Warnings do not make a series not ok."""
        return self.status != FAIL

    @property
    def fully_validated(self):
        """True only when the whole requested range was validated. Never inferred from ok or status."""
        return self.coverage == COVERAGE_COMPLETE


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_args(candles, calendar, timeframe_s, now_s, max_age_s, spike_threshold,
                sample_limit, max_grid_slots):
    if not isinstance(calendar, Calendar):
        raise ValidationError("calendar must be an instance of markets.calendars.Calendar")
    if not _is_int(timeframe_s) or timeframe_s < 1:
        raise ValidationError("timeframe_s must be a positive integer number of seconds")
    if not _is_int(now_s) or now_s < 0:
        raise ValidationError("now_s must be a non-negative integer UTC epoch second")
    if not _is_int(max_age_s) or max_age_s < 0:
        raise ValidationError("max_age_s must be a non-negative integer number of seconds")
    if (isinstance(spike_threshold, bool) or not isinstance(spike_threshold, (int, float))
            or not math.isfinite(spike_threshold) or spike_threshold <= 0):
        raise ValidationError("spike_threshold must be a finite positive number")
    if not _is_int(sample_limit) or sample_limit < 0:
        raise ValidationError("sample_limit must be a non-negative integer")
    if not _is_int(max_grid_slots) or max_grid_slots < 1:
        raise ValidationError("max_grid_slots must be a positive integer")
    if not isinstance(candles, (list, tuple)):
        raise ValidationError("candles must be a list or tuple of Candle objects")
    for item in candles:
        if not isinstance(item, Candle):
            raise ValidationError(f"every item must be a Candle, not {type(item).__name__}")


def _check_bound(name, value, tf):
    if value is None:
        return None
    if not _is_int(value) or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer UTC epoch second")
    if value % tf:
        raise ValidationError(f"{name} {value} is not aligned to the {tf}s timeframe")
    return value


def _fmt(value):
    return "omitted" if value is None else str(value)


def _ohlc_problem(c):
    """Re-checks OHLC even though Candle checks it on construction. Guards against later mutation."""
    for v in (c.open, c.high, c.low, c.close):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            return "non-finite or non-positive price"
    if c.high < c.low:
        return "high is below low"
    if c.high < max(c.open, c.close):
        return "high is below open or close"
    if c.low > min(c.open, c.close):
        return "low is above open or close"
    return None


def _volume_problem(v):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        return "invalid volume"
    return None


_SHORT = 5


def _describe(times, label):
    """Full listing for input-bounded categories (duplicates, OHLC, volume)."""
    head = ", ".join(str(t) for t in times[:_SHORT])
    more = f" (+{len(times) - _SHORT} more)" if len(times) > _SHORT else ""
    return f"{len(times)} {label}: {head}{more}"


def _sample_text(total, sample, label, truncated):
    head = ", ".join(str(t) for t in sample)
    tail = " (sample truncated)" if truncated else ""
    return f"{total} {label}: {head}{tail}"


def _last_completed_slot(now_s, tf):
    """Open time of the last grid slot whose close is <= now_s, or None when no slot has closed yet."""
    if now_s < tf:
        return None
    return ((now_s - tf) // tf) * tf


def _gap_samples(occupied, lo, hi, tf, limit):
    """First `limit` absent aligned slots in [lo, hi], found by walking the sorted occupied slots."""
    out = []
    cursor = lo
    for occ in occupied:
        while cursor < occ and len(out) < limit:
            out.append(cursor)
            cursor += tf
        if len(out) >= limit:
            return tuple(out)
        cursor = occ + tf
    while cursor <= hi and len(out) < limit:
        out.append(cursor)
        cursor += tf
    return tuple(out)


def _scan_generic(calendar, lo, hi, tf, occupied, limit):
    """Slot-by-slot scan for any calendar. Work is bounded by the caller's max_grid_slots check."""
    absent = closures = 0
    missing, closed = [], []
    for t in range(lo, hi + 1, tf):
        if t in occupied:
            continue
        if calendar.is_expected(t, tf):
            absent += 1
            if len(missing) < limit:
                missing.append(t)
        else:
            closures += 1
            if len(closed) < limit:
                closed.append(t)
    return absent, tuple(missing), closures, tuple(closed)


def validate_series(candles, calendar, timeframe_s, now_s, *,
                    start_s=None, end_s=None,
                    max_age_s=FRESHNESS_LIMIT_S, spike_threshold=SPIKE_THRESHOLD,
                    sample_limit=DEFAULT_SAMPLE_LIMIT, max_grid_slots=MAX_GRID_SLOTS):
    """Validates one candle series. Pure: the same inputs always give the same report.

    Raises ValidationError for bad arguments, or when the EFFECTIVE range exceeds max_grid_slots.
    Raises CalendarNotImplemented for a stub calendar, including for empty input.
    Data problems never raise. They are reported as FAIL or WARN checks, and coverage states what was validated.
    """
    _check_args(candles, calendar, timeframe_s, now_s, max_age_s, spike_threshold,
                sample_limit, max_grid_slots)
    tf = timeframe_s
    start = _check_bound("start_s", start_s, tf)
    end = _check_bound("end_s", end_s, tf)
    if start is not None and end is not None and end < start:
        raise ValidationError(f"end_s {end} is before start_s {start}")
    rows = tuple(candles)
    counts = Counter(c.open_time_s for c in rows)
    checks = []

    def add(name, status, detail):
        checks.append(Check(name, status, detail))

    # ---- expected range: requested bounds versus the effective completed range -------------
    last_completed = _last_completed_slot(now_s, tf)
    # Floor division, consistent with misaligned-candle slot occupancy: a timestamp belongs to the slot containing it.
    observed_first_slot = (min(counts) // tf) * tf if counts else None
    lo = start if start is not None else observed_first_slot
    if end is None:
        hi = last_completed                       # derived from now_s; always completed
    else:
        hi = None if last_completed is None else min(end, last_completed)
    has_range = lo is not None and hi is not None and hi >= lo
    slots = (hi - lo) // tf + 1 if has_range else 0

    reasons = []                                  # why coverage is not complete
    if not has_range:
        if last_completed is None:
            reasons.append("no slot has completed at now_s")
        elif start is not None and start > last_completed:
            reasons.append(f"start_s {start} is after the last completed slot {last_completed} at now_s "
                           "(future start); nothing in the requested range is validated")
        elif lo is None:
            reasons.append("no start_s and no observed candles: no range established")
        else:
            reasons.append("no completed slot in the requested range at now_s")
    else:
        if start is None:
            reasons.append("start_s not supplied: leading completeness NOT established; expected candles "
                           "before the first observed candle are not checked")
        if end is not None and end > last_completed:
            reasons.append(f"requested end_s {end} extends beyond the last completed slot {last_completed}; "
                           f"slots after {last_completed} are NOT validated")

    if not has_range:
        coverage = COVERAGE_NONE
    elif reasons:
        coverage = COVERAGE_PARTIAL
    else:
        coverage = COVERAGE_COMPLETE

    notes = [f"requested start_s={_fmt(start)}, requested end_s={_fmt(end)}"]
    notes.append(f"effective validated range={lo}..{hi}" if has_range
                 else "effective validated range=none")
    notes.append(f"coverage={coverage}")
    if has_range and end is None:
        notes.append(f"end_s omitted: derived from now_s as the last completed slot {hi}")
    if slots > max_grid_slots:
        raise ValidationError(f"the effective expected range needs {slots} grid slots, above max_grid_slots "
                              f"{max_grid_slots}; narrow start_s/end_s or pass a larger max_grid_slots")
    range_status = PASS if coverage == COVERAGE_COMPLETE else WARN
    range_detail = "; ".join(notes + reasons)

    def in_range(t):
        return has_range and lo <= t <= hi

    # Ask the calendar at least once, before any early return, so a stub cannot pass silently.
    probe = lo if lo is not None else (last_completed if last_completed is not None else 0)
    calendar.is_expected(probe, tf)

    # ---- input checks ----------------------------------------------------------------------
    if not rows:
        add("non_empty", FAIL, "no candles supplied")
    else:
        add("non_empty", PASS, f"{len(rows)} candles supplied")
    add("range", range_status, range_detail)

    inversions = sum(1 for a, b in zip(rows, rows[1:]) if b.open_time_s < a.open_time_s)
    add("ordering", FAIL if inversions else PASS,
        f"{inversions} out-of-order pair(s)" if inversions else "strictly increasing as supplied")

    dups = tuple(sorted(t for t, k in counts.items() if k > 1))
    add("duplicates", FAIL if dups else PASS,
        _describe(dups, "duplicated open time(s)") if dups else "no duplicate open times")

    misaligned_times = tuple(sorted({c.open_time_s for c in rows if c.open_time_s % tf}))
    # A misaligned candle occupies the grid slot that contains it. Only slots that are expected, in the
    # effective range, and absent of an aligned candle are linked. Those slots are not also reported missing.
    linked = set()
    for m in misaligned_times:
        s = (m // tf) * tf
        if in_range(s) and s not in counts and calendar.is_expected(s, tf):
            linked.add(s)
    linked_sorted = tuple(sorted(linked))
    linked_sample = linked_sorted[:sample_limit]
    if misaligned_times:
        detail = _describe(misaligned_times, "open time(s) not aligned to the timeframe")
        if linked:
            detail += (f"; {len(linked)} expected slot(s) occupied only by misaligned candles, "
                       "reported here and not as missing")
        add("alignment", FAIL, detail)
    else:
        add("alignment", PASS, f"all open times aligned to {tf}s")

    bad_ohlc = tuple(sorted({c.open_time_s for c in rows if _ohlc_problem(c) is not None}))
    add("ohlc", FAIL if bad_ohlc else PASS,
        _describe(bad_ohlc, "candle(s) with inconsistent OHLC or non-positive prices") if bad_ohlc
        else "OHLC consistent and prices positive")

    bad_volume = tuple(sorted({c.open_time_s for c in rows if _volume_problem(c.volume) is not None}))
    supplied = sum(1 for c in rows if c.volume is not None)
    if bad_volume:
        add("volume", FAIL, _describe(bad_volume, "candle(s) with invalid volume"))
    elif supplied == 0:
        add("volume", PASS, "volume not supplied for any candle; not treated as zero")
    elif supplied != len(rows):
        add("volume", WARN,
            f"volume supplied for {supplied} of {len(rows)} candles; missing volume is not treated as zero")
    else:
        add("volume", PASS, "volume supplied and valid for every candle")

    # ---- observed candles relative to the effective range ----------------------------------
    out_of_range = sum(1 for t in counts if t % tf == 0 and t + tf <= now_s and not in_range(t))
    add("out_of_range", WARN if out_of_range else PASS,
        f"{out_of_range} completed aligned candle(s) outside the effective range; not checked for completeness"
        if out_of_range else "no completed aligned candles outside the effective range")

    present_in = sorted(t for t in counts if t % tf == 0 and in_range(t))

    # ---- grid: expected missing, expected closures (effective range only) ------------------
    occupied_set = set(present_in) | linked
    if slots == 0:
        absent, missing_sample, closures_total, closure_sample = 0, (), 0, ()
    elif type(calendar) is CryptoCalendar24x7:      # exact class only: a subclass may change is_expected
        # Every aligned slot is expected, so the counts are arithmetic and samples come from a walk.
        occupied = sorted(occupied_set)
        absent = slots - len(occupied)
        missing_sample = _gap_samples(occupied, lo, hi, tf, sample_limit)
        closures_total, closure_sample = 0, ()
    else:
        absent, missing_sample, closures_total, closure_sample = _scan_generic(
            calendar, lo, hi, tf, occupied_set, sample_limit)

    add("expected_missing", FAIL if absent else PASS,
        _sample_text(absent, missing_sample, "expected candle(s) absent", absent > len(missing_sample))
        if absent else ("no expected candles absent" if slots else "no effective range; nothing checked"))

    # ---- unexpected candles: observed at times the calendar marks closed -------------------
    unexpected = [t for t in present_in if not calendar.is_expected(t, tf)]
    unexpected_sample = tuple(unexpected[:sample_limit])
    add("unexpected_candles", FAIL if unexpected else PASS,
        _sample_text(len(unexpected), unexpected_sample, "candle(s) at times the calendar marks closed",
                     len(unexpected) > len(unexpected_sample))
        if unexpected else "no candles at closed times")

    add("expected_closures", PASS,
        _sample_text(closures_total, closure_sample, "absent at times the calendar marks closed (not an error)",
                     closures_total > len(closure_sample))
        if closures_total else "0 absent at times the calendar marks closed (not an error)")

    # ---- completed and freshness ----------------------------------------------------------
    forming = tuple(sorted(t for t in counts if t + tf > now_s))
    add("completed", FAIL if forming else PASS,
        _describe(forming, "candle(s) not yet complete at now_s") if forming
        else "all candles complete at now_s")

    if not counts:
        add("freshness", FAIL, "no newest candle to measure freshness against")
    else:
        age = now_s - (max(counts) + tf)
        if age < 0:
            add("freshness", FAIL, f"newest candle closes {-age} s after now_s; it is not complete")
        elif age > max_age_s:
            add("freshness", FAIL, f"newest close is {age} s before now_s; limit is {max_age_s} s: STALE")
        else:
            add("freshness", PASS, f"newest close is {age} s before now_s; limit is {max_age_s} s")

    # ---- price spikes: WARN only ----------------------------------------------------------
    by_time = {}
    for c in rows:
        by_time.setdefault(c.open_time_s, c)
    ordered = [by_time[t] for t in sorted(by_time)]
    spikes = []
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.open_time_s - prev.open_time_s != tf:
            continue
        if not (prev.close > 0) or not math.isfinite(prev.close) or not math.isfinite(cur.close):
            continue                     # the OHLC check already reports this
        change = cur.close / prev.close - 1.0
        if abs(change) > spike_threshold:
            spikes.append(PriceSpike(cur.open_time_s, change))
    add("price_spikes", WARN if spikes else PASS,
        f"{len(spikes)} close-to-close move(s) above {spike_threshold:.0%}; WARN only, no decision changed"
        if spikes else f"no close-to-close move above {spike_threshold:.0%}")

    times = [c.open_time_s for c in rows]
    return ValidationReport(
        calendar=calendar.name,
        timeframe_s=tf,
        now_s=now_s,
        row_count=len(rows),
        first_open_s=min(times) if times else None,
        last_open_s=max(times) if times else None,
        requested_start_s=start,
        requested_end_s=end,
        range_start_s=lo if has_range else None,
        range_end_s=hi if has_range else None,
        coverage=coverage,
        coverage_reason="; ".join(reasons) if reasons else None,
        sample_limit=sample_limit,
        checks=tuple(checks),
        missing_expected=missing_sample,
        missing_expected_total=absent,
        missing_expected_truncated=absent > len(missing_sample),
        expected_closures=closure_sample,
        expected_closures_total=closures_total,
        expected_closures_truncated=closures_total > len(closure_sample),
        unexpected_candles=unexpected_sample,
        unexpected_total=len(unexpected),
        unexpected_truncated=len(unexpected) > len(unexpected_sample),
        misaligned_slots=linked_sample,
        misaligned_slot_total=len(linked),
        misaligned_slot_truncated=len(linked) > len(linked_sample),
        duplicate_open_s=dups,
        price_spikes=tuple(spikes),
    )
