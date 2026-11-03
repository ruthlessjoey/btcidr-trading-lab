"""markets/data_pipeline.py - the shared, provider-neutral market-data pipeline (M4b).

It consumes any markets.providers.MarketDataProvider. It does not know which provider produced the candles, which
venue or symbol is involved, or which asset is traded. Provider selection is the caller's explicit choice (see
markets/providers/registry.py). There is no fallback to another provider.

Flow, one bounded fetch per page, no retries:
    1. provenance     data_source and time_source are explicit (validate_provenance)
    2. request        provider.check_request: unsupported listing or interval is refused BEFORE any transport call
    3. calendar       only 24x7 crypto calendars are implemented; other asset classes are refused
    4. fetch          provider.fetch_candles through a counting transport
    5. validation     S2 validate_series over the explicit window and explicit now_s
    6. freshness      provider freshness from the publication schedule (see freshness_view)
    7. classification (the status contract below)

STATUS CONTRACT
    COMPLETE      every expected completed slot in the window is present and valid, and the provider is current.
    PARTIAL       at least one usable candle is present, and one or more expected slots are missing. Only gaps that the
                  validation layer reports as expected_missing qualify. The observed candles are returned, the gaps
                  are listed, and nothing is filled. A PARTIAL result must never generate a signal.
    UNAVAILABLE   no usable candles exist for the requested completed window. Reachable in exactly two ways:
                  (a) the provider returned an empty response (structured error kind 'empty'), or
                  (b) the response held candles, but none remain inside the window after trimming and removing the
                      candle still forming at now_s.
    REFUSED       unsupported request or calendar, provider error other than 'empty', malformed or conflicting data,
                  any validation FAIL other than missing expected slots, a provider that is overdue, or a validation
                  scope that cannot be fully established. Structured provider error details are kept in 'error'
                  regardless of the top-level status.
    (no status)   PipelineError is raised, before any transport call, for invalid arguments and for a window that
                  cannot be formed: no completed slot by now_s, a window before the epoch, or a lookback above the
                  validation grid limit. A caller error is not a data finding, so it has no status.

FRESHNESS RULE (deterministic; uses only the explicit now_s and the set of observed open times)
    end_s        the expected latest completed slot at now_s (the window end)
    deadline     end_s + timeframe_s + publication_grace_s: when that slot is due to be published
    newest_due   the latest grid slot s with s + timeframe_s + publication_grace_s <= now_s
    latest       the latest observed open time in the window
    state
      overdue               latest < newest_due: the provider has delivered nothing at or after the newest slot it
                            was due to publish. REFUSED.
      awaiting_publication  the expected latest slot is absent, but it is not yet due, and the provider has delivered
                            what it was due to. A gap, reported as PARTIAL. Not a provider outage.
      current               the expected latest slot is present.
    An internal gap, with the expected latest slot present, is a gap and never a freshness failure.
    The default publication_grace_s is an ASSUMPTION about provider publication delay. It is not verified against
    any provider, and it is an explicit argument so callers and tests can set it.

Data provenance is an explicit input, never inferred from the data:
    data_source  live       the real transport, used only when the caller passes no transport
                 replay     caller-supplied recorded bytes, through a caller transport
                 synthetic  caller-supplied offline fixture bytes, through a caller transport
    time_source  explicit-caller  the caller passed now_s
                 runtime-clock    the caller read now_s from the system clock

The result holds canonical candles in memory under 'canonical_candles'. That key holds Python objects, so use
json_safe() before writing any report.

Research only. Standard library plus the S2 markets package. No account, credential, order or trading.
"""
import hashlib
import json
import time

from markets import calendars as cal
from markets import validation as vd  # noqa: F401  (MAX_GRID_SLOTS, validate_series)
from markets.providers import ProviderError
from markets.providers.transport import live_transport

PIPELINE_VERSION = "market-data-m4b-v1"
DATA_SOURCES = ("live", "replay", "synthetic")
TIME_SOURCES = ("explicit-caller", "runtime-clock")
DATA_SOURCE_NOTES = {
    "live": "LIVE: fetched from the public endpoint during this run.",
    "replay": "REPLAY: caller-supplied recorded bytes were replayed. Not a live result.",
    "synthetic": "SYNTHETIC: offline fixture bytes supplied by the caller. Not market data.",
}
DEFAULT_LOOKBACK = 119          # completed candles; S1 needs 50 for its SMA
DEFAULT_PUBLICATION_GRACE_S = 6 * 3600   # ASSUMED provider publication delay after a slot closes. Not verified.
NO_TRADING = "No order, account, credential or exchange trading was used. Public market data only."

COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
UNAVAILABLE = "UNAVAILABLE"
REFUSED = "REFUSED"
STATUSES = (COMPLETE, PARTIAL, UNAVAILABLE, REFUSED)

CURRENT = "current"
AWAITING = "awaiting_publication"
OVERDUE = "overdue"
FRESHNESS_STATES = (CURRENT, AWAITING, OVERDUE)

GAP_CHECK = "expected_missing"


class PipelineError(Exception):
    """An argument is invalid. The run stops without a report."""


class CountingTransport:
    """Counts every transport call, so the report shows requests actually made, not planned ones."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        return self.inner(url)


def utc_text(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def validate_provenance(now_s, data_source, time_source, transport):
    if isinstance(now_s, bool) or not isinstance(now_s, int) or now_s < 0:
        raise PipelineError("now_s must be a non-negative integer UTC epoch second")
    if not isinstance(data_source, str) or data_source not in DATA_SOURCES:
        raise PipelineError(f"data_source must be one of {', '.join(DATA_SOURCES)}; got {data_source!r}")
    if not isinstance(time_source, str) or time_source not in TIME_SOURCES:
        raise PipelineError(f"time_source must be one of {', '.join(TIME_SOURCES)}; got {time_source!r}")
    if data_source == "live":
        if transport is not None:
            raise PipelineError("data_source 'live' is only valid for the real transport; injected transports must "
                                "be labeled 'replay' or 'synthetic'")
    else:
        if transport is None:
            raise PipelineError(f"data_source '{data_source}' needs a caller-supplied transport; it cannot use "
                                "the network")
        if time_source != "explicit-caller":
            raise PipelineError(f"data_source '{data_source}' needs an explicit reference time from the caller")


def window_for(now_s, timeframe_s, lookback):
    """Inclusive window of `lookback` completed slots ending with the last completed slot before now_s.

    Raises PipelineError, before any transport call, when the window cannot be formed:
      - timeframe_s is not a positive integer;
      - lookback is not an integer of at least 2, or exceeds the validation grid limit;
      - no slot has completed by now_s (now_s is earlier than the first slot's close);
      - the window would start before the UTC epoch.
    These are argument errors, not data statuses. Nothing is returned for them."""
    if isinstance(timeframe_s, bool) or not isinstance(timeframe_s, int) or timeframe_s <= 0:
        raise PipelineError("timeframe_s must be a positive integer number of seconds")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 2:
        raise PipelineError("lookback must be an integer of at least 2")
    if lookback > vd.MAX_GRID_SLOTS:
        raise PipelineError(f"lookback {lookback} exceeds the validation grid limit of {vd.MAX_GRID_SLOTS} slots")
    day_start = (now_s // timeframe_s) * timeframe_s
    end_s = day_start - timeframe_s
    if end_s < 0:
        raise PipelineError(f"no slot has completed by now_s {now_s}: the first slot closes at {timeframe_s}")
    start_s = end_s - (lookback - 1) * timeframe_s
    if start_s < 0:
        raise PipelineError(f"a lookback of {lookback} slots ending {utc_text(end_s)} starts before the UTC epoch")
    return start_s, end_s


def freshness_view(observed_open_times, start_s, end_s, timeframe_s, now_s, grace_s):
    """Provider freshness for one window, from the publication schedule. Pure and deterministic.
    Returns a dict with the state and every timestamp the rule used, so the report can show the reasoning."""
    deadline = end_s + timeframe_s + grace_s
    newest_due = ((now_s - timeframe_s - grace_s) // timeframe_s) * timeframe_s
    latest = max(observed_open_times) if observed_open_times else None
    if latest is None or latest < newest_due:
        state = OVERDUE
    elif end_s in observed_open_times:
        state = CURRENT
    else:
        state = AWAITING
    return {
        "state": state,
        "expected_latest_open_utc": utc_text(end_s),
        "expected_latest_close_utc": utc_text(end_s + timeframe_s),
        "publication_deadline_utc": utc_text(deadline),
        "publication_grace_s": grace_s,
        "newest_due_open_utc": utc_text(newest_due) if newest_due >= start_s else None,
        "latest_observed_open_utc": utc_text(latest) if latest is not None else None,
        "expected_latest_present": end_s in observed_open_times,
    }


def dataset_sha256(canon):
    """Deterministic hash of canonical candle content. Same formula as the M3 pipeline, for parity checks.
    A missing volume is hashed as null, never as zero."""
    rows = [[c.open_time_s, c.open, c.high, c.low, c.close, c.volume] for c in canon]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def json_safe(report):
    """The report without in-memory objects, ready for json.dumps."""
    return {k: v for k, v in report.items() if k != "canonical_candles"}


def _base(provider, listing, timeframe_s, now_s, start_s, end_s, data_source, time_source):
    return {
        "pipeline_version": PIPELINE_VERSION,
        "data_source": data_source,
        "data_source_note": DATA_SOURCE_NOTES[data_source],
        "reference_time": {"now_s": now_s, "utc": utc_text(now_s), "source": time_source},
        "provider": provider.info.to_dict(),
        "listing": {"canonical": listing.canonical, "venue": listing.venue, "market_type": listing.market_type},
        "timeframe_s": timeframe_s,
        "window": {"start_utc": utc_text(start_s), "end_utc": utc_text(end_s),
                   "expected_completed_count": (end_s - start_s) // timeframe_s + 1},
        "requests_made": 0,
        "no_trading": NO_TRADING,
    }


def _coverage(expected, returned, status, report=None):
    return {
        "expected_candles": expected,
        "returned_candles": returned,
        "complete": status == COMPLETE,
        "missing_expected_total": report.missing_expected_total if report is not None else None,
        "missing_expected_sample": [utc_text(t) for t in report.missing_expected] if report is not None else [],
    }


def _outcome(base, status, stage, reasons, *, expected, received=None, error=None, report=None, canon=None,
             freshness=None):
    out = dict(base)
    returned = received["completed_count"] if received else 0
    out.update({
        "status": status,
        "stage": stage,
        "reasons": list(reasons),
        "candles": received,
        "error": error,
        "freshness": freshness,
        "coverage": _coverage(expected, returned, status, report),
        "canonical_candles": tuple(canon) if canon is not None and status in (COMPLETE, PARTIAL) else None,
    })
    return out


def fetch_market_data(provider, listing, timeframe_s, now_s, *, data_source, time_source, transport=None,
                      lookback=DEFAULT_LOOKBACK, publication_grace_s=DEFAULT_PUBLICATION_GRACE_S):
    """Runs one bounded market-data pipeline for one listing through one explicitly chosen provider.

    Returns a dict whose 'status' is COMPLETE, PARTIAL, UNAVAILABLE or REFUSED (see the module contract). A
    non-COMPLETE result is a normal outcome, never an exception, except for invalid arguments (PipelineError).
    Never retries. Never falls back.
    """
    validate_provenance(now_s, data_source, time_source, transport)
    if isinstance(publication_grace_s, bool) or not isinstance(publication_grace_s, int) or publication_grace_s < 0:
        raise PipelineError("publication_grace_s must be a non-negative integer number of seconds")
    start_s, end_s = window_for(now_s, timeframe_s, lookback)
    base = _base(provider, listing, timeframe_s, now_s, start_s, end_s, data_source, time_source)

    try:
        provider.check_request(listing, timeframe_s)            # no transport call yet
    except ProviderError as e:
        return _outcome(base, REFUSED, "request", [e.detail], expected=lookback, error=e.to_dict())

    if listing.instrument.asset_class != "crypto":
        reason = (f"no calendar is implemented for asset class {listing.instrument.asset_class!r}; "
                  "equity and FX calendars are deferred")
        return _outcome(base, REFUSED, "calendar", [reason], expected=lookback)
    calendar = cal.CryptoCalendar24x7()

    counting = CountingTransport(transport if transport is not None else live_transport)
    try:
        fetched = provider.fetch_candles(listing, timeframe_s, start_s, end_s, now_s, transport=counting)
    except ProviderError as e:
        base["requests_made"] = counting.calls
        status = UNAVAILABLE if e.kind == "empty" else REFUSED
        return _outcome(base, status, "fetch", [f"{e.kind}: {e.detail}"], expected=lookback, error=e.to_dict())
    base["requests_made"] = counting.calls

    canon = list(fetched.candles)
    if not canon:
        return _outcome(base, UNAVAILABLE, "fetch",
                        ["no usable candles remain inside the completed window after trimming and removing the "
                         "candle still forming at now_s"],
                        expected=lookback, error=None)
    received = {
        "completed_count": len(canon),
        "forming_dropped": fetched.forming_dropped,
        "duplicates_removed": fetched.duplicates_removed,
        "out_of_window_dropped": fetched.out_of_window_dropped,
        "volume_supplied_count": sum(1 for c in canon if c.volume is not None),
        "raw_sha256": fetched.raw_sha256,
        "first_open_utc": utc_text(canon[0].open_time_s),
        "last_open_utc": utc_text(canon[-1].open_time_s),
        "dataset_sha256": dataset_sha256(canon),
    }

    # S2 checks structure, ordering, OHLC, volume and gaps. Its own freshness check looks at the newest candle, so it
    # is given a window-wide limit here. Provider freshness is decided by freshness_view, not by S2.
    # The arguments are built here from validated values, so a ValidationError would be a bug in this module and is
    # deliberately not caught: it must surface, not be reported as a data status.
    report = vd.validate_series(canon, calendar, timeframe_s, now_s, start_s=start_s, end_s=end_s,
                                max_age_s=now_s - start_s + timeframe_s)
    checks =[{"name": c.name, "status": c.status, "detail": c.detail} for c in report.checks]
    failures = [c for c in checks if c["status"] == vd.FAIL]
    received["validation"] = {
        "status": report.status, "ok": report.ok, "coverage": report.coverage,
        "coverage_reason": report.coverage_reason,
        "warnings": [c for c in checks if c["status"] == vd.WARN],
        "failures": failures,
        "checks": checks,
    }

    observed = {c.open_time_s for c in canon}
    fresh = freshness_view(observed, start_s, end_s, timeframe_s, now_s, publication_grace_s)

    if report.coverage != vd.COVERAGE_COMPLETE:
        # Unreachable through this API: the window always ends at the last completed slot. Kept as fail-closed.
        return _outcome(base, REFUSED, "gates",
                        [f"validation could not establish the full window: {report.coverage}: "
                         f"{report.coverage_reason}"],
                        expected=lookback, received=received, report=report, freshness=fresh)

    names = [c["name"] for c in failures]
    other = [n for n in names if n != GAP_CHECK]
    if other:
        return _outcome(base, REFUSED, "gates", ["validation FAIL: " + ", ".join(names)],
                        expected=lookback, received=received, report=report, freshness=fresh)
    if fresh["state"] == OVERDUE:
        return _outcome(base, REFUSED, "gates",
                        [f"provider overdue: it has delivered nothing at or after the newest slot due by its "
                         f"publication schedule ({fresh['newest_due_open_utc']}); latest delivered "
                         f"{fresh['latest_observed_open_utc']}; expected latest slot "
                         f"{fresh['expected_latest_open_utc']} is due by {fresh['publication_deadline_utc']}"],
                        expected=lookback, received=received, report=report, freshness=fresh)

    if GAP_CHECK in names:
        reasons = ["validation FAIL: " + ", ".join(names),
                   f"{report.missing_expected_total} expected candle(s) absent: observed candles returned, "
                   "gaps not filled"]
        if fresh["state"] == AWAITING:
            reasons.append(f"expected latest slot {fresh['expected_latest_open_utc']} is within the publication grace "
                           f"period (deadline {fresh['publication_deadline_utc']}): reported as a gap, not a provider "
                           "outage")
        return _outcome(base, PARTIAL, "gates", reasons, expected=lookback, received=received, report=report,
                        canon=canon, freshness=fresh)
    return _outcome(base, COMPLETE, "all", [], expected=lookback, received=received, report=report, canon=canon,
                    freshness=fresh)
