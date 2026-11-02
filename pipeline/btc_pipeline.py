"""pipeline/btc_pipeline.py - first end-to-end BTC/USDT daily research pipeline.

Flow, one bounded public request per live run, no retries, no fallback data:

    Binance public klines (committed S1 fetcher, signal/fetch_latest.py)
      -> canonical markets.candles.Candle (S2.1 schema)
      -> validate_series (S2.2, CryptoCalendar24x7, explicit window, explicit now_s)
      -> freshness gate (48 hours, same limit as S1)
      -> S1 signal_at (committed S1 rules, signal/btc_signal.py)
      -> JSON + Markdown report

Data provenance is an explicit caller input, never inferred from the data:
    data_source  live       the real public endpoint, fetched during this run
                 replay     caller-supplied recorded bytes (a historical snapshot); never labeled live
                 synthetic  caller-supplied offline fixture bytes; never labeled live
    time_source  explicit-caller  the caller passed the reference time
                 runtime-clock    the reference time was read from the system clock at entry

The S1 engine is evaluated ONLY when the validation gate and the freshness gate both pass. Otherwise the
report records gate REFUSED with reasons and no signal. A WARN from validation (for example a large price move)
does not refuse the run; it is listed in the report, as S1 itself does for WARN entries.

Research only. Standard library only. No account, credential, order or trading. The output is a research
snapshot, not a trading instruction.
"""
import argparse
import errno
import hashlib
import json
import os
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SIGNAL = os.path.join(_ROOT, "signal")
for _p in (_ROOT, _SIGNAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import btc_signal as bs                       # noqa: E402  committed S1 engine (pure signal_at)
import fetch_latest as fl                     # noqa: E402  committed S1 fetcher (one request, completed only)
from markets import calendars as cal          # noqa: E402  committed S2.2
from markets import candles as mc             # noqa: E402  committed S2.1
from markets import identity as mi            # noqa: E402  committed S2.1
from markets import validation as vd          # noqa: E402  committed S2.2

PIPELINE_VERSION = "btc-pipeline-v2"
STEP = bs.STEP                                 # 86400 seconds, daily candles
REQUEST_LIMIT = 120                            # 1 forming + 119 completed. S1 needs 50 completed for SMA50.
MAX_AGE_SECONDS = bs.MAX_AGE_SECONDS           # 172800 (48 h)
MARKET_CANONICAL = "crypto:binance-spot:BTC-USDT"
PROVIDER_NAME = "binance-vision"
DISCLAIMER = bs.DISCLAIMER
NO_TRADING = "No order, account, credential or exchange trading was used. Public market data only."

DATA_SOURCES = ("live", "replay", "synthetic")
TIME_SOURCES = ("explicit-caller", "runtime-clock")
DATA_SOURCE_NOTES = {
    "live": "LIVE: fetched from the public endpoint during this run.",
    "replay": "REPLAY: caller-supplied recorded bytes were replayed. The live fetch path was not used. "
              "Not a live result.",
    "synthetic": "SYNTHETIC: offline fixture bytes supplied by the caller. Not market data.",
}
DECISION_MEANING = {
    "BUY": "BUY = bullish/entry candidate in spot research, not an order instruction.",
    "SELL": "SELL = bearish/exit candidate in spot research, not a short instruction.",
    "WAIT": "WAIT = no research candidate on this basis candle; no order is implied.",
}

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_INVALID = 1
EXIT_OUTPUT_ERROR = 3


class PipelineError(Exception):
    """An argument or internal input is invalid. The run stops without a report."""


class OutputError(Exception):
    """Report files could not be written safely. Nothing pre-existing was modified."""


def utc_text(ts):
    return bs.utc_text(ts) + " UTC"


def window_for(now_s, limit):
    """Expected window from the explicit now_s.

    The request returns `limit` daily slots ending with the forming slot. The expected COMPLETED window is
    [start, end]: `limit - 1` slots, with the forming slot excluded. It is derived from now_s, never from the
    response, so a stale or gapped response cannot define its own expectation.
    """
    if not isinstance(now_s, int) or isinstance(now_s, bool) or now_s < 0:
        raise PipelineError("now_s must be a non-negative integer UTC epoch second")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 2:
        raise PipelineError("limit must be an integer of at least 2")
    day_start = (now_s // STEP) * STEP
    return day_start - (limit - 1) * STEP, day_start - STEP


def validate_provenance(now_s, data_source, time_source, opener):
    """Checks the caller's provenance declarations. Raises PipelineError on any inconsistency.

    Rules (the source is never inferred from the data):
      - live means the real endpoint: it requires opener is None (no injected bytes).
      - replay and synthetic mean caller-supplied bytes: they require an injected opener.
      - replay and synthetic require an explicit reference time from the caller.
    """
    if not isinstance(now_s, int) or isinstance(now_s, bool) or now_s < 0:
        raise PipelineError("now_s must be a non-negative integer UTC epoch second")
    if not isinstance(data_source, str) or data_source not in DATA_SOURCES:
        raise PipelineError(f"data_source must be one of {', '.join(DATA_SOURCES)}; got {data_source!r}")
    if not isinstance(time_source, str) or time_source not in TIME_SOURCES:
        raise PipelineError(f"time_source must be one of {', '.join(TIME_SOURCES)}; got {time_source!r}")
    if data_source == "live":
        if opener is not None:
            raise PipelineError("data_source 'live' is only valid for the real public endpoint; injected bytes "
                                "must be labeled 'replay' or 'synthetic'")
    else:
        if opener is None:
            raise PipelineError(f"data_source '{data_source}' needs caller-supplied bytes; it cannot use the "
                                "network fetch path")
        if time_source != "explicit-caller":
            raise PipelineError(f"data_source '{data_source}' needs an explicit reference time from the caller")


def freshness_gate(last_close_s, now_s, limit_s=MAX_AGE_SECONDS):
    """Returns (ok, age_seconds, reason). Refuses a basis older than the limit, and a basis that closes after now_s."""
    age = now_s - last_close_s
    if age < 0:
        return False, age, "newest completed candle closes after the fetch time"
    if age > limit_s:
        return False, age, (f"stale: newest completed candle closed {age / 3600:.2f} h before the fetch time; "
                            f"limit is {limit_s / 3600:.0f} h")
    return True, age, "current: newest completed candle is within the freshness limit"


def to_canonical(s1_candles):
    """Converts committed S1 candles to canonical markets.candles.Candle objects. Refuses rows without volume."""
    out = []
    for c in s1_candles:
        if c.volume is None:
            raise PipelineError(f"candle at {c.time} has no volume")
        try:
            out.append(mc.Candle(c.time, c.open, c.high, c.low, c.close, c.volume))
        except mc.CandleError as e:
            raise PipelineError(f"candle at {c.time} is not canonical: {e}")
    return out


def dataset_sha256(canon):
    """Deterministic hash of the normalized candle content (open time, OHLCV), canonical JSON."""
    rows = [[c.open_time_s, c.open, c.high, c.low, c.close, c.volume] for c in canon]
    text = json.dumps(rows, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _refused(base, stage, reasons, received=None):
    out = dict(base)
    out.update({"candles": received,
                "gate": {"status": "REFUSED", "stage": stage, "reasons": list(reasons)},
                "signal": None, "explanation": [
                    "Signal NOT produced. The data did not pass the gate:"] + [f"- {r}" for r in reasons]})
    return out


def _base(now_s, limit, start_s, end_s, data_source, time_source):
    listing = mi.parse_listing(MARKET_CANONICAL)
    if start_s is None:
        window = {"expected_completed_start_utc": None, "expected_completed_end_utc": None,
                  "expected_completed_count": None, "note": "window not defined: invalid request limit"}
    else:
        window = {
            "expected_completed_start_utc": utc_text(start_s),
            "expected_completed_end_utc": utc_text(end_s),
            "expected_completed_count": (end_s - start_s) // STEP + 1,
        }
    return {
        "report_type": "BTC/USDT daily research candidate (pipeline, rule-based)",
        "pipeline_version": PIPELINE_VERSION,
        "disclaimer": DISCLAIMER,
        "no_trading": NO_TRADING,
        "data_source": data_source,
        "data_source_note": DATA_SOURCE_NOTES[data_source],
        "reference_time": {"now_s": now_s, "utc": utc_text(now_s), "source": time_source},
        "now_s": now_s,
        "generated_utc": utc_text(now_s),
        "provider": {
            "name": PROVIDER_NAME,
            "host": fl.HOST,
            "path": fl.PATH,
            "symbol": fl.SYMBOL,
            "interval": fl.INTERVAL,
            "request_limit": limit,
            "auth": "none (public market data)",
            "network_requests_attempted": 0,      # set to 1 only after a live request is actually issued
            "proxy_warning": fl.PROXY_WARNING,
        },
        "market": {"canonical": listing.canonical, "listing": listing.to_dict()},
        "window": window,
        "pipeline_code": {"file": "pipeline/btc_pipeline.py", "pipeline_version": PIPELINE_VERSION,
                          "s1_rule_version": bs.RULE_VERSION},
    }


def run(now_s, *, data_source, time_source, opener=None, limit=REQUEST_LIMIT):
    """One bounded fetch, validation, freshness gate, then S1 if and only if both gates pass.

    data_source and time_source are required keyword arguments with no defaults.
    A refusal is a normal result (gate REFUSED, signal None), not an exception.
    Never retries. Never falls back to other data.
    """
    validate_provenance(now_s, data_source, time_source, opener)
    try:
        start_s, end_s = window_for(now_s, limit)
    except PipelineError as e:
        return _refused(_base(now_s, limit, None, None, data_source, time_source), "request", [str(e)])
    base = _base(now_s, limit, start_s, end_s, data_source, time_source)

    # ---- 1. one bounded fetch, normalization to completed candles ----------------------
    try:
        url = fl.build_url(limit)
    except fl.FetchError as e:
        return _refused(base, "request", [str(e)])
    live = opener is None
    if live:
        base["provider"]["network_requests_attempted"] = 1
    try:
        body = fl.fetch_body(url) if live else fl.fetch_body(url, opener)
        completed, forming_dropped = fl.parse_klines(body, now_s)
        canon = to_canonical(completed)
    except (fl.FetchError, PipelineError) as e:
        return _refused(base, "fetch_or_parse", [str(e)])

    received = {
        "completed_count": len(canon),
        "forming_rows_dropped": forming_dropped,
        "first_open_utc": utc_text(canon[0].open_time_s),
        "last_open_utc": utc_text(canon[-1].open_time_s),
        "dataset_sha256": dataset_sha256(canon),
    }

    # ---- 2. S2.2 validation against the explicit window ---------------------------------
    try:
        report = vd.validate_series(canon, cal.CryptoCalendar24x7(), STEP, now_s,
                                    start_s=start_s, end_s=end_s)
    except vd.ValidationError as e:
        return _refused(base, "validation", [f"validation rejected its arguments: {e}"], received)

    val_checks = [{"name": c.name, "status": c.status, "detail": c.detail} for c in report.checks]
    val_summary = {
        "status": report.status,
        "ok": report.ok,
        "coverage": report.coverage,
        "coverage_reason": report.coverage_reason,
        "range_start_utc": utc_text(report.range_start_s) if report.range_start_s is not None else None,
        "range_end_utc": utc_text(report.range_end_s) if report.range_end_s is not None else None,
        "missing_expected_total": report.missing_expected_total,
        "warnings": [c for c in val_checks if c["status"] == vd.WARN],
        "failures": [c for c in val_checks if c["status"] == vd.FAIL],
        "checks": val_checks,
    }
    received["validation"] = val_summary

    # ---- 3. gates ----------------------------------------------------------------------------
    refusals = []
    if not report.ok:
        refusals.append("validation FAIL: " + ", ".join(c["name"] for c in val_summary["failures"]))
    if not report.fully_validated:
        refusals.append(f"validation coverage is {report.coverage}: {report.coverage_reason}")
    fresh_ok, age_s, fresh_reason = freshness_gate(canon[-1].open_time_s + STEP, now_s)
    received["freshness"] = {"ok": fresh_ok, "age_hours": round(age_s / 3600.0, 2),
                             "limit_hours": MAX_AGE_SECONDS / 3600.0, "reason": fresh_reason}
    if not fresh_ok:
        refusals.append(fresh_reason)
    if refusals:
        return _refused(base, "gates", refusals, received)

    # ---- 4. S1 evaluates the validated data only -----------------------------------------
    s1 = [bs.Candle(c.open_time_s, c.open, c.high, c.low, c.close, c.volume) for c in canon]
    result = bs.signal_at(s1, len(s1) - 1)
    meaning = DECISION_MEANING[result["decision"]]
    out = dict(base)
    out.update({
        "candles": received,
        "gate": {"status": "PASSED", "stage": "all", "reasons": []},
        "signal": {
            "decision": result["decision"],
            "decision_meaning": meaning,
            "rule_version": result["rule_version"],
            "basis_candle_open_utc": result["basis_candle_open_utc"],
            "basis_candle_close_utc": result["basis_candle_close_utc"],
            "values": result["values"],
            "reasons": result["reasons"],
        },
        "explanation": [meaning] + result["reasons"] + (
            ["Validation WARN: " + w["name"] + " - " + w["detail"] for w in val_summary["warnings"]]),
    })
    return out


def render_markdown(r):
    lines = [f"# {r['report_type']}", "", f"> {r['disclaimer']}", "",
             f"**Gate: {r['gate']['status']}**  (generated {r['generated_utc']}, pipeline {r['pipeline_version']})",
             "", f"**Data source: {r['data_source']}** - {r['data_source_note']}",
             f"- Reference time: {r['reference_time']['utc']} (source: {r['reference_time']['source']})",
             "", "## Market and provider",
             f"- Market: `{r['market']['canonical']}`",
             f"- Provider: {r['provider']['name']} via {r['provider']['host']}{r['provider']['path']} "
             f"(symbol {r['provider']['symbol']}, interval {r['provider']['interval']}, "
             f"limit {r['provider']['request_limit']}, network requests attempted "
             f"{r['provider']['network_requests_attempted']})",
             f"- Proxy notice: {r['provider']['proxy_warning']}",
             "", "## Window",
             f"- Expected completed candles: {r['window']['expected_completed_count']} "
             f"({r['window']['expected_completed_start_utc']} to {r['window']['expected_completed_end_utc']})"]
    if r.get("candles") and "completed_count" in r["candles"]:
        c = r["candles"]
        lines += ["", "## Data",
                  f"- Completed candles: {c['completed_count']} (forming rows dropped: {c['forming_rows_dropped']})",
                  f"- First open: {c['first_open_utc']}; last open: {c['last_open_utc']}",
                  f"- Dataset SHA-256: `{c['dataset_sha256']}`"]
        if "validation" in c:
            v = c["validation"]
            lines += [f"- Validation: {v['status']} (ok={v['ok']}, coverage={v['coverage']})"]
            if v["coverage_reason"]:
                lines += [f"  - Coverage reason: {v['coverage_reason']}"]
            for w in v["warnings"]:
                lines += [f"  - WARN {w['name']}: {w['detail']}"]
            for f_ in v["failures"]:
                lines += [f"  - FAIL {f_['name']}: {f_['detail']}"]
        if "freshness" in c:
            lines += [f"- Freshness: {c['freshness']['reason']} (age {c['freshness']['age_hours']} h)"]
    lines += ["", "## Gate reasons"]
    lines += [f"- {x}" for x in r["gate"]["reasons"]] or ["- none"]
    lines += ["", "## Signal"]
    if r["signal"] is None:
        lines += ["- NOT PRODUCED (gate refused)."]
    else:
        s = r["signal"]
        lines += [f"- Decision: **{s['decision']}** (rule {s['rule_version']})",
                  f"- Meaning: {s['decision_meaning']}",
                  f"- Basis candle: {s['basis_candle_open_utc']} to {s['basis_candle_close_utc']}",
                  f"- Values: {json.dumps(s['values'], sort_keys=True)}"]
        lines += [f"  - {x}" for x in s["reasons"]]
    lines += ["", "## Explanation"] + [f"- {x}" for x in r["explanation"]]
    lines += ["", f"_{r['no_trading']}_", ""]
    return "\n".join(lines)


def _targets(result, out_dir):
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(result["now_s"]))
    base = os.path.join(out_dir, f"btc_pipeline_{stamp}")
    return {"json": f"{base}.json", "md": f"{base}.md"}


def _write_temp(out_dir, text):
    """Writes text to a new hidden temp file in out_dir, flushed and fsynced. Returns its path."""
    fd, path = tempfile.mkstemp(dir=out_dir, prefix=".btc_pipeline_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(path, 0o644)
    except BaseException:
        _unlink_quiet(path)
        raise
    return path


def _unlink_quiet(path):
    """Removes a file this module created. Returns an error description, or None."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        return None
    except OSError as e:
        return f"{path} ({e})"
    return None


def _identity(path):
    st = os.stat(path, follow_symlinks=False)
    return (st.st_dev, st.st_ino)


def _rollback(created):
    """Removes final files this run created, newest first. Returns problems that need manual attention.

    Each entry is (path, identity) recorded when this run linked the file. A path is unlinked only while it still
    has that identity. If something else now sits at the path (for example a user file put there during the run),
    it is left in place and reported, never deleted.
    """
    problems = []
    for path, ident in reversed(created):
        try:
            current = _identity(path)
        except FileNotFoundError:
            continue                                   # already gone: nothing of ours remains
        except OSError as e:
            problems.append(f"{path} ({e})")
            continue
        if current != ident:
            problems.append(f"{path} (replaced after this run wrote it; left in place, not deleted)")
            continue
        err = _unlink_quiet(path)
        if err:
            problems.append(err)
    return problems


# errno values that mean "this filesystem cannot make the hard link the safe finalization needs"
_NO_HARDLINK_ERRNOS = {errno.EPERM, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}


def write_outputs(result, out_dir):
    """Writes the JSON and Markdown pair safely. Returns (paths, warnings).

    Safety steps:
      1. Create the directory, then check BOTH target names before writing anything. Any existing file refuses
         the whole run, so a collision never leaves a half pair.
      2. Write each output to a new temp file in the destination directory, flush and fsync it.
      3. Finalize with os.link(temp, final). Unlike os.rename, link fails if the final name already exists, so
         a file that appears during the run is never overwritten. The temp name is then removed.
      4. If finalization fails, remove the finals this run created, so no half pair is left behind. A final is
         removed only while it still has the device and inode this run wrote. A file that was replaced during the
         run is left in place and reported.

    Limitations (not atomic, stated plainly):
      - Two independent link operations are NOT one atomic transaction. A crash or power loss between them can
        leave one file. The rollback is best effort and runs only while the process is alive.
      - If rollback itself fails, the returned error names each leftover file for manual cleanup. It never
        reports success in that case.
      - Filesystems without hard links fail with an OutputError that says so. Nothing is written.
      - The directory is not fsynced after linking, so a power loss may lose the new directory entries.
      - Temp-file cleanup failure after a successful write is returned as a warning, not an error. The report
        pair is complete.
    """
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        raise OutputError(f"cannot create output directory {out_dir}: {e}. Nothing was written.")
    targets = _targets(result, out_dir)
    present = [p for p in targets.values() if os.path.lexists(p)]
    if present:
        raise OutputError("report file(s) already exist; nothing was written or changed: " + ", ".join(present))

    texts = {"json": json.dumps(result, indent=2, sort_keys=True) + "\n", "md": render_markdown(result)}
    temps = {}
    created = []
    try:
        for ext in ("json", "md"):
            temps[ext] = _write_temp(out_dir, texts[ext])
        for ext in ("json", "md"):
            ident = _identity(temps[ext])              # the final name will share this inode after the link
            try:
                os.link(temps[ext], targets[ext])
            except FileExistsError:
                raise OutputError(f"{targets[ext]} appeared during the run; nothing was overwritten")
            created.append((targets[ext], ident))
    except (OSError, OutputError) as e:
        problems = _rollback(created)
        for t in temps.values():
            err = _unlink_quiet(t)
            if err:
                problems.append(err)
        if isinstance(e, OSError) and e.errno in _NO_HARDLINK_ERRNOS:
            reason = (f"this filesystem may not support hard links, which the safe finalization requires "
                      f"(errno {e.errno}); no report was written")
        else:
            reason = str(e)
        msg = f"report not written: {reason}"
        if problems:
            msg += "; these files could not be removed and need manual cleanup: " + "; ".join(problems)
        else:
            msg += "; any partial files from this run were removed"
        raise OutputError(msg) from e

    warnings = []
    for t in temps.values():
        err = _unlink_quiet(t)
        if err:
            warnings.append(f"temporary file could not be removed: {err}")
    return targets, warnings


def main(argv=None, opener=None, now_s=None):
    parser = argparse.ArgumentParser(description="One bounded BTC/USDT daily research pipeline run.")
    parser.add_argument("--out-dir", required=True, help="directory for the JSON and Markdown report")
    parser.add_argument("--data-source", required=True, choices=DATA_SOURCES,
                        help="provenance of the data: live (real endpoint), replay or synthetic")
    parser.add_argument("--now", type=int, default=None,
                        help="explicit reference time, UTC epoch seconds (otherwise the system clock is read)")
    parser.add_argument("--limit", type=int, default=REQUEST_LIMIT, help="daily klines to request")
    args = parser.parse_args(argv)
    if args.now is not None:
        ref, time_source = args.now, "explicit-caller"
    elif now_s is not None:
        ref, time_source = now_s, "explicit-caller"
    else:
        ref, time_source = int(time.time()), "runtime-clock"
    try:
        result = run(ref, data_source=args.data_source, time_source=time_source, opener=opener, limit=args.limit)
    except PipelineError as e:
        print(f"invalid run, no report written: {e}")
        return EXIT_INVALID
    try:
        paths, warnings = write_outputs(result, args.out_dir)
    except OutputError as e:
        print(f"output error: {e}")
        return EXIT_OUTPUT_ERROR
    print(f"data source: {result['data_source']} (reference time from {result['reference_time']['source']})")
    print(f"gate: {result['gate']['status']}")
    if result["signal"] is not None:
        print(f"decision: {result['signal']['decision']} (basis {result['signal']['basis_candle_open_utc']})")
        print(result["signal"]["decision_meaning"])
    else:
        for reason in result["gate"]["reasons"]:
            print(f"refused: {reason}")
    for w in warnings:
        print(f"warning: {w}")
    print(f"json: {paths['json']}")
    print(f"md:   {paths['md']}")
    return EXIT_OK if result["gate"]["status"] == "PASSED" else EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
