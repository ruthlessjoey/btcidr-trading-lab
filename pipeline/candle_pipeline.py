"""pipeline/candle_pipeline.py - provider-neutral daily candle pipeline (M4a).

Flow, one bounded fetch per chunk, no retries, no fallback data:

    provider.check_request      unsupported listing or interval: refused before any transport call
    calendar check              only 24x7 crypto calendars are implemented; others are refused
    provider.fetch_candles      canonical S2 Candle objects; structured ProviderError on failure
    S2 validate_series          explicit window and explicit now_s
    freshness gate             newest completed candle within 2 intervals of now_s
    signal_fn (optional)        a caller-supplied function; the caller decides which listings it applies to

Data provenance is an explicit input, never inferred from the data:
    data_source  live       the real transport, fetched during this run
                 replay     caller-supplied recorded bytes (through a caller transport)
                 synthetic  caller-supplied offline fixture bytes (through a caller transport)
    time_source  explicit-caller  the caller passed now_s
                 runtime-clock    now_s was read from the system clock by the caller

Research only. Standard library, plus the S2 markets package. No account, credential, order or trading.
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markets import calendars as cal  # noqa: E402  committed S2.2
from markets import validation as vd  # noqa: E402  committed S2.2
from markets.providers import ProviderError  # noqa: E402
from markets.providers.transport import live_transport  # noqa: E402

PIPELINE_VERSION = "candle-pipeline-m4a-v1"
DATA_SOURCES = ("live", "replay", "synthetic")
TIME_SOURCES = ("explicit-caller", "runtime-clock")
DATA_SOURCE_NOTES = {
    "live": "LIVE: fetched from the public endpoint during this run.",
    "replay": "REPLAY: caller-supplied recorded bytes were replayed. Not a live result.",
    "synthetic": "SYNTHETIC: offline fixture bytes supplied by the caller. Not market data.",
}
DEFAULT_LOOKBACK = 119          # completed candles; S1 needs 50 for its SMA
FRESHNESS_INTERVALS = 2         # newest completed candle may be at most 2 intervals old (daily: 48 h, as in S1)
NO_TRADING = "No order, account, credential or exchange trading was used. Public market data only."


class PipelineError(Exception):
    """An argument is invalid. The run stops without a report."""


class _CountingTransport:
    """Counts every transport call, so the report shows real requests made, not planned ones."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        return self.inner(url)


def utc_text(ts):
    import time
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
    """Inclusive window of `lookback` completed slots ending with the last completed slot before now_s."""
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 2:
        raise PipelineError("lookback must be an integer of at least 2")
    day_start = (now_s // timeframe_s) * timeframe_s
    end_s = day_start - timeframe_s
    return end_s - (lookback - 1) * timeframe_s, end_s


def freshness_gate(last_close_s, now_s, max_age_s):
    age = now_s - last_close_s
    if age < 0:
        return False, age, "newest completed candle closes after the reference time"
    if age > max_age_s:
        return False, age, (f"stale: newest completed candle closed {age / 3600:.2f} h before the reference time; "
                            f"limit is {max_age_s / 3600:.0f} h")
    return True, age, "current: newest completed candle is within the freshness limit"


def dataset_sha256(canon):
    """Deterministic hash of canonical candle content. Same formula as the M3 pipeline, for parity checks."""
    import json
    rows = [[c.open_time_s, c.open, c.high, c.low, c.close, c.volume] for c in canon]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


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


def _refused(base, stage, reasons, received=None, error=None):
    out = dict(base)
    out.update({
        "candles": received,
        "error": error,
        "gate": {"status": "REFUSED", "stage": stage, "reasons": list(reasons)},
        "signal": None,
        "explanation": ["Signal NOT produced. The data did not pass the gate:"] + [f"- {r}" for r in reasons],
    })
    return out


def run_candle_pipeline(provider, listing, timeframe_s, now_s, *, data_source, time_source, transport=None,
                        lookback=DEFAULT_LOOKBACK, signal_fn=None):
    """Runs one candle pipeline. Returns a report dict. A refusal is a normal result with gate REFUSED."""
    validate_provenance(now_s, data_source, time_source, transport)
    start_s, end_s = window_for(now_s, timeframe_s, lookback)
    base = _base(provider, listing, timeframe_s, now_s, start_s, end_s, data_source, time_source)

    try:
        provider.check_request(listing, timeframe_s)           # no transport call yet
    except ProviderError as e:
        return _refused(base, "request", [e.detail], error=e.to_dict())

    if listing.instrument.asset_class != "crypto":
        reason = (f"no calendar is implemented for asset class {listing.instrument.asset_class!r}; "
                  "equity and FX calendars are deferred")
        return _refused(base, "calendar", [reason])
    calendar = cal.CryptoCalendar24x7()

    inner = transport if transport is not None else live_transport
    counting = _CountingTransport(inner)
    try:
        fetched = provider.fetch_candles(listing, timeframe_s, start_s, end_s, now_s, transport=counting)
    except ProviderError as e:
        base["requests_made"] = counting.calls
        return _refused(base, "fetch", [f"{e.kind}: {e.detail}"], error=e.to_dict())
    base["requests_made"] = counting.calls

    canon = list(fetched.candles)
    if not canon:
        return _refused(base, "fetch", ["no candles remain inside the window after trimming"],
                        error=None)
    received = {
        "completed_count": len(canon),
        "forming_dropped": fetched.forming_dropped,
        "duplicates_removed": fetched.duplicates_removed,
        "out_of_window_dropped": fetched.out_of_window_dropped,
        "raw_sha256": fetched.raw_sha256,
        "first_open_utc": utc_text(canon[0].open_time_s),
        "last_open_utc": utc_text(canon[-1].open_time_s),
        "dataset_sha256": dataset_sha256(canon),
    }

    try:
        report = vd.validate_series(canon, calendar, timeframe_s, now_s, start_s=start_s, end_s=end_s)
    except vd.ValidationError as e:
        return _refused(base, "validation", [f"validation rejected its arguments: {e}"], received)
    checks = [{"name": c.name, "status": c.status, "detail": c.detail} for c in report.checks]
    received["validation"] = {
        "status": report.status, "ok": report.ok, "coverage": report.coverage,
        "coverage_reason": report.coverage_reason,
        "warnings": [c for c in checks if c["status"] == vd.WARN],
        "failures": [c for c in checks if c["status"] == vd.FAIL],
        "checks": checks,
    }

    refusals = []
    if not report.ok:
        refusals.append("validation FAIL: " + ", ".join(c["name"] for c in received["validation"]["failures"]))
    if not report.fully_validated:
        refusals.append(f"validation coverage is {report.coverage}: {report.coverage_reason}")
    fresh_ok, age_s, fresh_reason = freshness_gate(canon[-1].open_time_s + timeframe_s, now_s,
                                                   FRESHNESS_INTERVALS * timeframe_s)
    received["freshness"] = {"ok": fresh_ok, "age_hours": round(age_s / 3600.0, 2), "reason": fresh_reason}
    if not fresh_ok:
        refusals.append(fresh_reason)
    if refusals:
        return _refused(base, "gates", refusals, received)

    out = dict(base)
    signal = signal_fn(canon) if signal_fn is not None else None
    explanation = []
    if signal is not None:
        explanation.append(signal["decision_meaning"])
        explanation += signal["reasons"]
    else:
        explanation.append("No signal function was configured for this listing; candles passed validation only.")
    explanation += [f"Validation WARN: {w['name']} - {w['detail']}" for w in received["validation"]["warnings"]]
    out.update({
        "candles": received,
        "error": None,
        "gate": {"status": "PASSED", "stage": "all", "reasons": []},
        "signal": signal,
        "explanation": explanation,
    })
    return out


def render_markdown(r):
    lines = [f"# Candle pipeline report ({r['listing']['canonical']})", "",
             f"**Gate: {r['gate']['status']}**  (pipeline {r['pipeline_version']})", "",
             f"**Data source: {r['data_source']}** - {r['data_source_note']}",
             f"- Reference time: {r['reference_time']['utc']} (source: {r['reference_time']['source']})",
             f"- Provider: {r['provider']['name']} (venue {r['provider']['venue']}); requests made: {r['requests_made']}",
             f"- Window: {r['window']['start_utc']} to {r['window']['end_utc']} "
             f"({r['window']['expected_completed_count']} slots)"]
    if r.get("error"):
        lines += [f"- Provider error: {r['error']['kind']} - {r['error']['detail']} "
                  f"(retriable: {r['error']['retriable']})"]
    if r.get("candles"):
        c = r["candles"]
        lines += [f"- Candles: {c['completed_count']} (forming dropped {c['forming_dropped']}, "
                  f"duplicates removed {c['duplicates_removed']}, out of window {c['out_of_window_dropped']})",
                  f"- Dataset SHA-256: `{c['dataset_sha256']}`"]
        if "validation" in c:
            lines += [f"- Validation: {c['validation']['status']} (coverage {c['validation']['coverage']})"]
    lines += ["", "## Gate reasons"] + ([f"- {x}" for x in r["gate"]["reasons"]] or ["- none"])
    lines += ["", "## Signal"]
    if r["signal"] is None:
        lines += ["- NOT PRODUCED."]
    else:
        lines += [f"- Decision: **{r['signal']['decision']}**", f"- Meaning: {r['signal']['decision_meaning']}"]
    lines += ["", "## Explanation"] + [f"- {x}" for x in r["explanation"]] + ["", f"_{r['no_trading']}_", ""]
    return "\n".join(lines)
