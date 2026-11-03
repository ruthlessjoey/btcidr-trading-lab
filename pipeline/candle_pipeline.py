"""pipeline/candle_pipeline.py - the M4a signal layer on top of the shared M4b market-data pipeline.

The data path lives in markets/data_pipeline.py and is provider-neutral. This module adds one rule: a signal is
produced if and only if the shared pipeline reports COMPLETE data and every gate passes. PARTIAL, UNAVAILABLE and
REFUSED data never reach the signal function, and the gate reports them as REFUSED, as M4a did.

Research only. No account, credential, order or trading.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markets import data_pipeline as dp  # noqa: E402
from markets.data_pipeline import (  # noqa: E402  (re-exported for callers of this module)
    DATA_SOURCE_NOTES, DATA_SOURCES, DEFAULT_LOOKBACK, NO_TRADING, TIME_SOURCES, PipelineError, dataset_sha256,
    utc_text, validate_provenance, window_for,
)

PIPELINE_VERSION = "candle-pipeline-m4b-v1"


def run_candle_pipeline(provider, listing, timeframe_s, now_s, *, data_source, time_source, transport=None,
                        lookback=DEFAULT_LOOKBACK, signal_fn=None):
    """Runs the shared pipeline, then the signal gate. Returns a report dict. A refusal is a normal result."""
    report = dp.fetch_market_data(provider, listing, timeframe_s, now_s, data_source=data_source,
                                  time_source=time_source, transport=transport, lookback=lookback)
    canon = report.pop("canonical_candles")
    report["pipeline_version"] = PIPELINE_VERSION

    if report["status"] != dp.COMPLETE:
        report["gate"] = {"status": "REFUSED", "stage": report["stage"], "reasons": list(report["reasons"])}
        report["signal"] = None
        report["explanation"] = ["Signal NOT produced. The data did not pass the gate:"] + [
            f"- {r}" for r in report["reasons"]]
        return report

    report["gate"] = {"status": "PASSED", "stage": "all", "reasons": []}
    signal = signal_fn(list(canon)) if signal_fn is not None else None
    explanation = []
    if signal is not None:
        explanation.append(signal["decision_meaning"])
        explanation += signal["reasons"]
    else:
        explanation.append("No signal function was configured for this listing; candles passed validation only.")
    explanation += [f"Validation WARN: {w['name']} - {w['detail']}"
                    for w in report["candles"]["validation"]["warnings"]]
    report.update({"error": None, "signal": signal, "explanation": explanation})
    return report


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
    if r.get("status"):
        lines += [f"- Data status: {r['status']} (stage {r['stage']})"]
    if r.get("freshness"):
        f = r["freshness"]
        lines += [f"- Provider freshness: {f['state']} (expected latest slot {f['expected_latest_open_utc']}, "
                  f"publication deadline {f['publication_deadline_utc']}, grace {f['publication_grace_s']} s)"]
    lines += ["", "## Gate reasons"] + ([f"- {x}" for x in r["gate"]["reasons"]] or ["- none"])
    lines += ["", "## Signal"]
    if r["signal"] is None:
        lines += ["- NOT PRODUCED."]
    else:
        lines += [f"- Decision: **{r['signal']['decision']}**", f"- Meaning: {r['signal']['decision_meaning']}"]
    lines += ["", "## Explanation"] + [f"- {x}" for x in r["explanation"]] + ["", f"_{r['no_trading']}_", ""]
    return "\n".join(lines)
