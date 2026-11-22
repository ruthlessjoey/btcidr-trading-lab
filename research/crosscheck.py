"""research/crosscheck.py - compare preserved daily candles with independent sources.

READ-ONLY. External cross-check acquisition is disabled pending separate owner approval.
Only pure comparison/report helpers remain available; this module cannot fetch Coinbase
or Bitstamp data or be enabled through mutable module state.
"""
import json
import math
import os
import re
import statistics
import stat
from datetime import datetime, timezone

from fetcher import ApiError

DAY = 86400
TOLERANCE_PCT = 3.0

# No independent cross-check provider is authorized under the current policy.
# Production entrypoints pass a fresh empty frozenset; this named constant is
# informational and is not consulted to authorize production backtests.
AUTHORIZED_CROSSCHECK_PROVIDERS = frozenset()
MAX_CROSSCHECK_ARTIFACT_BYTES = 1_048_576
CROSSCHECK_ARTIFACT_SCHEMA = "twin-money-maker.crosscheck/v1"
CROSSCHECK_ARTIFACT_PRODUCER = "research.crosscheck"
CONFIRMED_VERDICT = "CONFIRMED (approximate: USD is not USDT)"


class CrosscheckError(RuntimeError):
    """Safe, unprotected error type for dataset-bound cross-check validation."""


def _unique_json_object(pairs):
    """Reject duplicate keys so evidence has one unambiguous interpretation."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value):
    """Reject non-standard NaN/Infinity tokens in evidence JSON."""
    raise ValueError("non-standard JSON numeric constant")


def is_confirmed_verdict(value):
    """Accept only the exact verdict emitted by the two-source comparison rule."""
    return type(value) is str and value == CONFIRMED_VERDICT


def _valid_comparison_evidence(source):
    """Require the exact finite metrics emitted by judge() and recompute its rule."""
    required = {
        "open_diff_pct", "close_diff_pct", "high_diff_pct", "low_diff_pct",
        "binance_return_pct", "other_return_pct", "return_gap_pp", "agrees",
    }
    if type(source) is not dict or set(source) != required:
        return False
    numeric_fields = required - {"agrees"}
    for field in numeric_fields:
        value = source[field]
        if type(value) not in (int, float):
            return False
        try:
            if not math.isfinite(float(value)):
                return False
        except (OverflowError, ValueError):
            return False
    try:
        calculated_gap = (
            float(source["binance_return_pct"])
            - float(source["other_return_pct"])
        )
        if not math.isclose(
            float(source["return_gap_pp"]),
            calculated_gap,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            return False
    except (OverflowError, ValueError):
        return False
    expected = (
        abs(source["open_diff_pct"]) <= TOLERANCE_PCT
        and abs(source["close_diff_pct"]) <= TOLERANCE_PCT
        and abs(source["return_gap_pp"]) <= TOLERANCE_PCT
    )
    return type(source["agrees"]) is bool and source["agrees"] is expected


def validate_crosscheck_artifact(cfg, manifest, crosscheck_path, authorized_providers):
    """Validate versioned, dataset-bound evidence from at least two approved sources.

    This pure helper accepts an explicit immutable provider set for isolated
    fixtures. Production entrypoints below always pass a fresh empty frozenset.
    """
    if type(cfg) is not dict or type(manifest) is not dict:
        raise CrosscheckError("cross-check configuration and dataset manifest must be objects")
    flagged = cfg.get("flagged_dates", [])
    if type(flagged) is not list:
        raise CrosscheckError("cross-check flagged_dates must be a list")
    if not flagged:
        return None
    if (any(type(date) is not str or not date for date in flagged)
            or len(flagged) != len(set(flagged))):
        raise CrosscheckError("cross-check flagged_dates must contain unique non-empty strings")
    for date in flagged:
        try:
            if datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d") != date:
                raise ValueError("date is not canonical")
        except ValueError:
            raise CrosscheckError("cross-check flagged_dates must use YYYY-MM-DD dates") from None
    if (type(authorized_providers) is not frozenset
            or len(authorized_providers) < 2
            or any(type(provider) is not str or not provider
                   for provider in authorized_providers)):
        raise CrosscheckError(
            "no independent cross-check provider set is accepted; "
            "at least two distinct authorized providers are required"
        )
    if type(crosscheck_path) is not str or not crosscheck_path:
        raise CrosscheckError("independent cross-check artifact path must be a non-empty string")
    try:
        if not os.path.lexists(crosscheck_path):
            raise CrosscheckError(
                "independent cross-check evidence is required for flagged dates; no artifact was supplied"
            )
        # lstat rejects symlinks even on platforms without O_NOFOLLOW. The
        # path/descriptor comparisons catch replacement during the open.
        path_metadata = os.lstat(crosscheck_path)
        if not stat.S_ISREG(path_metadata.st_mode):
            raise ValueError("cross-check artifact is not a regular file")
        flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0))
        descriptor = os.open(crosscheck_path, flags)
        with os.fdopen(descriptor, "rb") as f:
            metadata = os.fstat(f.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("cross-check artifact is not a regular file")
            if not os.path.samestat(path_metadata, metadata):
                raise ValueError("cross-check artifact changed during open")
            current_path_metadata = os.lstat(crosscheck_path)
            if (not stat.S_ISREG(current_path_metadata.st_mode)
                    or not os.path.samestat(current_path_metadata, metadata)):
                raise ValueError("cross-check artifact path changed during open")
            if metadata.st_size > MAX_CROSSCHECK_ARTIFACT_BYTES:
                raise ValueError("cross-check artifact exceeds the size limit")
            raw = f.read(MAX_CROSSCHECK_ARTIFACT_BYTES + 1)
        if len(raw) > MAX_CROSSCHECK_ARTIFACT_BYTES:
            raise ValueError("cross-check artifact exceeds the size limit")
        evidence = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (OSError, ValueError, RecursionError) as e:
        raise CrosscheckError(
            f"independent cross-check artifact is unreadable: {type(e).__name__}"
        ) from None
    if type(evidence) is not dict:
        raise CrosscheckError("independent cross-check artifact must be a JSON object")
    expected_evidence_keys = {
        "schema", "producer", "dataset_version", "dataset_sha256", "providers", "flagged",
    }
    if set(evidence) != expected_evidence_keys:
        raise CrosscheckError("cross-check artifact contains unsupported fields")
    if (evidence.get("schema") != CROSSCHECK_ARTIFACT_SCHEMA
            or evidence.get("producer") != CROSSCHECK_ARTIFACT_PRODUCER):
        raise CrosscheckError(
            "cross-check artifact schema or producer identity is unsupported"
        )
    manifest_version = manifest.get("version_id")
    manifest_sha256 = manifest.get("csv_sha256")
    if (type(manifest_version) is not str or not manifest_version
            or type(manifest_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256)):
        raise CrosscheckError("pinned dataset manifest identity is invalid")
    if (evidence.get("dataset_version") != manifest_version
            or evidence.get("dataset_sha256") != manifest_sha256):
        raise CrosscheckError(
            "cross-check evidence does not match the pinned dataset version and hash"
        )
    used = evidence.get("providers")
    if (type(used) is not list or len(used) < 2
            or any(type(provider) is not str or not provider for provider in used)
            or len(used) != len(set(used))
            or any(provider not in authorized_providers for provider in used)):
        raise CrosscheckError(
            "cross-check artifact must identify at least two distinct authorized independent providers"
        )
    flagged_entries = evidence.get("flagged")
    if type(flagged_entries) is not list:
        raise CrosscheckError("cross-check artifact flagged entries must be a list")
    entries = {}
    expected_entry_keys = {"date", "verdict", *used}
    for item in flagged_entries:
        if (type(item) is not dict
                or set(item) != expected_entry_keys
                or type(item.get("date")) is not str
                or not item["date"]):
            raise CrosscheckError("cross-check artifact contains a malformed flagged entry")
        if item["date"] in entries:
            raise CrosscheckError("cross-check artifact contains duplicate flagged dates")
        entries[item["date"]] = item
    if set(entries) != set(flagged):
        raise CrosscheckError(
            "cross-check artifact flagged dates do not exactly match the requested dates"
        )
    for date in flagged:
        item = entries[date]
        for provider in used:
            source = item.get(provider)
            if not _valid_comparison_evidence(source):
                raise CrosscheckError(
                    f"flagged date {date} has invalid comparison evidence from provider {provider}"
                )
            if source["agrees"] is not True:
                raise CrosscheckError(
                    f"flagged date {date} lacks affirmative agreement from provider {provider}"
                )
        if not is_confirmed_verdict(item.get("verdict")):
            verdict = item.get("verdict", "MISSING")
            raise CrosscheckError(
                f"flagged date {date} lacks the exact confirmed verdict ({verdict})"
            )
    return evidence

def load_required_crosscheck(cfg, manifest, crosscheck_path):
    """Keep production flagged-date backtests fail-closed pending separate approval."""
    return validate_crosscheck_artifact(
        cfg, manifest, crosscheck_path, frozenset()
    )



def day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def to_ts(text):
    return int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def pct(a, b):
    if b == 0:
        raise ValueError("comparison reference price must be non-zero")
    return (a / b - 1) * 100


def judge(binance, other, t):
    """Verdict inputs for one flagged day against one other source."""
    if t not in other or t - DAY not in other or t - DAY not in binance:
        return None
    b, o = binance[t], other[t]
    try:
        ret_b = pct(b.close, binance[t - DAY].close)
        ret_o = pct(o.close, other[t - DAY].close)
        d = {"open_diff_pct": pct(b.open, o.open), "close_diff_pct": pct(b.close, o.close),
             "high_diff_pct": pct(b.high, o.high), "low_diff_pct": pct(b.low, o.low),
             "binance_return_pct": ret_b, "other_return_pct": ret_o,
             "return_gap_pp": ret_b - ret_o}
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    d["agrees"] = (abs(d["open_diff_pct"]) <= TOLERANCE_PCT and abs(d["close_diff_pct"]) <= TOLERANCE_PCT
                   and abs(d["return_gap_pp"]) <= TOLERANCE_PCT)
    return d


def compare(candles, coinbase, bitstamp, flagged_dates, window_days=2):
    """Pure comparison. `candles` is the preserved source list."""
    bn = {c.time: c for c in candles}
    common = sorted(set(bn) & set(coinbase))
    diffs = []
    for t in common:
        try:
            diffs.append((abs(pct(bn[t].close, coinbase[t].close)), t))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    abs_d = [d for d, _ in diffs]
    res = {"common_days": len(common), "binance_days": len(bn),
           "coinbase_days": len(coinbase), "summary": None, "worst_days": [], "flagged": []}
    if abs_d:
        srt = sorted(abs_d)
        res["summary"] = {"median_abs_close_diff_pct": statistics.median(abs_d),
                          "p95_abs_close_diff_pct": srt[int(0.95 * (len(srt) - 1))],
                          "p99_abs_close_diff_pct": srt[int(0.99 * (len(srt) - 1))],
                          "max_abs_close_diff_pct": srt[-1],
                          "days_over_1pct": sum(1 for d in abs_d if d > 1),
                          "days_over_2pct": sum(1 for d in abs_d if d > 2),
                          "days_over_5pct": sum(1 for d in abs_d if d > 5)}
        res["worst_days"] = [{"date": day(t), "abs_close_diff_pct": round(d, 3)}
                             for d, t in sorted(diffs, reverse=True)[:8]]
    for fd in flagged_dates:
        t = to_ts(fd)
        entry = {"date": fd, "table": [], "coinbase": judge(bn, coinbase, t),
                 "bitstamp": judge(bn, bitstamp, t) if bitstamp else None}
        for k in range(-2, 3):
            tt = t + k * DAY
            for name, src in (("binance", bn), ("coinbase", coinbase), ("bitstamp", bitstamp or {})):
                if tt in src:
                    c = src[tt]
                    entry["table"].append({"date": day(tt), "source": name, "open": c.open, "high": c.high,
                                           "low": c.low, "close": c.close})
        cb, bs = entry["coinbase"], entry["bitstamp"]
        if cb is None or bs is None:
            entry["verdict"] = "UNAVAILABLE"
        elif cb.get("agrees") is True and bs.get("agrees") is True:
            entry["verdict"] = CONFIRMED_VERDICT
        else:
            entry["verdict"] = "NOT CONFIRMED"
        res["flagged"].append(entry)
    return res


def run_crosscheck(manifest, candles, flagged_dates, out_dir, opener=None,
                   sleep=None, timeout=20, retries=3):
    """Fail closed until independent cross-check sources receive separate approval.

    No provider authorization can be enabled by mutating a module global or by
    injecting a transport. Re-enabling this feature requires a reviewed source change.
    """
    raise ApiError("independent cross-check providers are not authorized")


def _safe_report_text(value, limit=160):
    """Render only ordinary strings; remove line breaks and control characters."""
    if type(value) is not str:
        return "unavailable"
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else "unavailable"


def _safe_report_number(value, spec=".2f"):
    """Format only finite built-in numeric primitives, never caller-defined objects."""
    if type(value) not in (int, float):
        return "unavailable"
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return "unavailable"
    if not math.isfinite(number):
        return "unavailable"
    return format(number, spec)


def _safe_report_count(value):
    """Render non-negative built-in integer counts only."""
    return str(value) if type(value) is int and value >= 0 else "unavailable"


def _safe_report_bool(value):
    return "true" if value is True else "false" if value is False else "unavailable"


def build_markdown(r):
    """Render offline comparison summaries without formatting caller-defined values."""
    version = _safe_report_text(r.get("dataset_version"))
    digest = r.get("dataset_sha256")
    digest_prefix = digest[:16] if type(digest) is str and re.fullmatch(
        r"[0-9a-f]{64}", digest
    ) else "unavailable"
    lines = [
        "# Cross-check of flagged candles",
        "",
        f"Dataset `{version}` (sha256 `{digest_prefix}...`). The source candles were **not changed**.",
        "",
        "External acquisition status: **DISABLED**. No external source was contacted; "
        "Coinbase and Bitstamp data were not acquired. Comparison helpers are retained for offline fixtures only. "
        "Any provider acquisition requires separate owner authorization.",
        f"Pre-stated rule: {_safe_report_text(r.get('rule'))}.",
        "",
    ]
    for name in ("coinbase", "bitstamp"):
        error = r.get(name + "_error")
        if error is not None:
            lines.append(
                f"- {name.title()} could not be fetched: {_safe_report_text(error)}"
            )

    summary = r.get("summary")
    if summary:
        lines.extend([
            "",
            f"## Whole-history comparison with Coinbase ({_safe_report_count(r.get('common_days'))} common days)",
            "",
            "| Close difference |  |",
            "|---|---|",
            f"| Median | {_safe_report_number(summary.get('median_abs_close_diff_pct'), '.3f')}% |",
            f"| 95th percentile | {_safe_report_number(summary.get('p95_abs_close_diff_pct'), '.3f')}% |",
            f"| 99th percentile | {_safe_report_number(summary.get('p99_abs_close_diff_pct'), '.3f')}% |",
            f"| Maximum | {_safe_report_number(summary.get('max_abs_close_diff_pct'), '.3f')}% |",
            "| Days over 1% / 2% / 5% | "
            + " / ".join(_safe_report_count(summary.get(key)) for key in (
                "days_over_1pct", "days_over_2pct", "days_over_5pct"
            ))
            + " |",
            "",
            "Largest disagreements: " + ", ".join(
                f"{_safe_report_text(item.get('date'))} "
                f"({_safe_report_number(item.get('abs_close_diff_pct'), '.3f')}%)"
                for item in r.get("worst_days", [])
            ),
        ])

    for entry in r.get("flagged", []):
        lines.extend([
            "",
            f"## Flagged day {_safe_report_text(entry.get('date'))}: "
            f"**{_safe_report_text(entry.get('verdict'))}**",
            "",
            "| Date | Source | Open | High | Low | Close |",
            "|---|---|---|---|---|---|",
        ])
        for candle in entry.get("table", []):
            lines.append(
                f"| {_safe_report_text(candle.get('date'))} "
                f"| {_safe_report_text(candle.get('source'))} "
                f"| {_safe_report_number(candle.get('open'), ',.2f')} "
                f"| {_safe_report_number(candle.get('high'), ',.2f')} "
                f"| {_safe_report_number(candle.get('low'), ',.2f')} "
                f"| {_safe_report_number(candle.get('close'), ',.2f')} |"
            )
        for name in ("coinbase", "bitstamp"):
            comparison = entry.get(name)
            if comparison:
                lines.append(
                    f"- vs {name}: open {_safe_report_number(comparison.get('open_diff_pct'), '+.2f')}%, "
                    f"close {_safe_report_number(comparison.get('close_diff_pct'), '+.2f')}%, "
                    f"high {_safe_report_number(comparison.get('high_diff_pct'), '+.2f')}%, "
                    f"low {_safe_report_number(comparison.get('low_diff_pct'), '+.2f')}%; "
                    f"day return {_safe_report_number(comparison.get('binance_return_pct'), '+.2f')}% "
                    f"(source) vs {_safe_report_number(comparison.get('other_return_pct'), '+.2f')}% ({name}); "
                    f"gap {_safe_report_number(comparison.get('return_gap_pp'), '+.2f')} pp; "
                    f"rule met: {_safe_report_bool(comparison.get('agrees'))}"
                )
            else:
                lines.append(f"- vs {name}: not available")
        lines.append(
            "- High and low are shown but not used by the rule: they depend on when each venue "
            "traded the extreme, and this strategy uses only closes and next-day opens."
        )

    lines.extend([
        "",
        "## Limits",
        "",
        "- Two other venues agreeing supports that the move happened; it does not prove every price is exact.",
        "- USD and USDT prices can differ, especially in a crash.",
    ])
    return "\n".join(lines) + "\n"
