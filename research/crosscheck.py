"""research/crosscheck.py - compare preserved daily candles with independent sources.

READ-ONLY. External cross-check acquisition is disabled pending separate owner approval.
Only pure comparison/report helpers remain available; this module cannot fetch Coinbase
or Bitstamp data or be enabled through mutable module state.
"""
import json
import math
import os
import statistics
from datetime import datetime, timezone

from fetcher import ApiError

DAY = 86400
TOLERANCE_PCT = 3.0
REQUIRED_CROSSCHECK_PROVIDERS = frozenset({"coinbase", "bitstamp"})
CONFIRMED_VERDICT = "CONFIRMED (approximate: USD is not USDT)"


def _valid_confirmed_comparison(value):
    """Require a complete, finite, agreeing result from one independent venue."""
    if type(value) is not dict or value.get("agrees") is not True:
        return False
    numeric_fields = (
        "open_diff_pct", "close_diff_pct", "high_diff_pct", "low_diff_pct",
        "binance_return_pct", "other_return_pct", "return_gap_pp",
    )
    numbers = {}
    for field in numeric_fields:
        number = value.get(field)
        if type(number) not in (int, float):
            return False
        try:
            if not math.isfinite(number):
                return False
        except (OverflowError, TypeError, ValueError):
            return False
        numbers[field] = number
    return (
        abs(numbers["open_diff_pct"]) <= TOLERANCE_PCT
        and abs(numbers["close_diff_pct"]) <= TOLERANCE_PCT
        and abs(numbers["return_gap_pp"]) <= TOLERANCE_PCT
    )

# No independent cross-check provider is authorized under the current policy.
# Keep the gate explicit and immutable; approval requires a reviewed source change.
AUTHORIZED_CROSSCHECK_PROVIDERS = frozenset()


class CrosscheckError(RuntimeError):
    """Safe, unprotected error type for dataset-bound cross-check validation."""


def validate_crosscheck_artifact(cfg, manifest, crosscheck_path, authorized_providers):
    """Validate dataset-bound evidence without importing the protected backtest engine."""
    flagged = cfg.get("flagged_dates", [])
    if not flagged:
        return None
    try:
        allowed = frozenset(authorized_providers)
    except (TypeError, ValueError):
        allowed = frozenset()
    if not REQUIRED_CROSSCHECK_PROVIDERS.issubset(allowed):
        raise CrosscheckError(
            "no independent cross-check provider set contains both required venues; two independent providers are required; flagged-date backtests are blocked"
        )
    if not crosscheck_path or not os.path.isfile(crosscheck_path):
        raise CrosscheckError(
            "independent cross-check evidence is required for flagged dates; no artifact was supplied"
        )
    try:
        with open(crosscheck_path, encoding="utf-8") as f:
            evidence = json.load(f)
    except (OSError, ValueError) as e:
        raise CrosscheckError(
            f"independent cross-check artifact is unreadable: {type(e).__name__}"
        ) from None
    if not isinstance(evidence, dict):
        raise CrosscheckError("independent cross-check artifact must be a JSON object")
    if (evidence.get("dataset_version") != manifest.get("version_id") or
            evidence.get("dataset_sha256") != manifest.get("csv_sha256")):
        raise CrosscheckError(
            "cross-check evidence does not match the pinned dataset version and hash"
        )
    used = evidence.get("providers")
    if (type(used) is not list or len(used) < 2 or
            any(type(p) is not str for p in used) or
            len(used) != len(set(used)) or
            not REQUIRED_CROSSCHECK_PROVIDERS.issubset(used) or
            any(p not in allowed for p in used)):
        raise CrosscheckError(
            "cross-check artifact must identify both distinct authorized independent providers"
        )
    flagged_entries = evidence.get("flagged")
    if not isinstance(flagged_entries, list):
        raise CrosscheckError("cross-check artifact flagged entries must be a list")
    entries = {}
    for item in flagged_entries:
        if not isinstance(item, dict) or not isinstance(item.get("date"), str):
            raise CrosscheckError("cross-check artifact contains a malformed flagged entry")
        if item["date"] in entries:
            raise CrosscheckError("cross-check artifact contains duplicate flagged dates")
        entries[item["date"]] = item
    for date in flagged:
        item = entries.get(date)
        if (not item or type(item.get("verdict")) is not str or
                item["verdict"] != CONFIRMED_VERDICT or
                not _valid_confirmed_comparison(item.get("coinbase")) or
                not _valid_confirmed_comparison(item.get("bitstamp"))):
            raise CrosscheckError(
                f"flagged date {date} lacks confirmed, complete agreeing evidence from both independent providers"
            )
    return evidence


def load_required_crosscheck(cfg, manifest, crosscheck_path):
    """Apply the current immutable provider policy to cross-check evidence."""
    return validate_crosscheck_artifact(
        cfg, manifest, crosscheck_path, AUTHORIZED_CROSSCHECK_PROVIDERS
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
        elif cb["agrees"] is True and bs["agrees"] is True:
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


def build_markdown(r):
    L = ["# Cross-check of flagged candles", "",
         f"Dataset `{r['dataset_version']}` (sha256 `{r['dataset_sha256'][:16]}...`). The source candles "
         "were **not changed**.", "",
         "Sources: **Coinbase BTC/USD** daily candles (USD is not USDT) and "
         "**Bitstamp BTC/USD** around flagged days. Cross-check providers remain disabled pending authorization.",
         f"Pre-stated rule: {r['rule']}.", ""]
    if r["coinbase_error"]:
        L.append(f"- Coinbase could not be fetched: {r['coinbase_error']}")
    if r["bitstamp_error"]:
        L.append(f"- Bitstamp could not be fetched: {r['bitstamp_error']}")
    s = r["summary"]
    if s:
        L += ["", f"## Whole-history comparison with Coinbase ({r['common_days']} common days)", "",
              "| Close difference |  |", "|---|---|",
              f"| Median | {s['median_abs_close_diff_pct']:.3f}% |", f"| 95th percentile | {s['p95_abs_close_diff_pct']:.3f}% |",
              f"| 99th percentile | {s['p99_abs_close_diff_pct']:.3f}% |", f"| Maximum | {s['max_abs_close_diff_pct']:.3f}% |",
              f"| Days over 1% / 2% / 5% | {s['days_over_1pct']} / {s['days_over_2pct']} / {s['days_over_5pct']} |", "",
              "Largest disagreements: " + ", ".join(f"{w['date']} ({w['abs_close_diff_pct']}%)" for w in r["worst_days"])]
    for e in r["flagged"]:
        L += ["", f"## Flagged day {e['date']}: **{e['verdict']}**", "",
              "| Date | Source | Open | High | Low | Close |", "|---|---|---|---|---|---|"]
        L += [f"| {t['date']} | {t['source']} | {t['open']:,.2f} | {t['high']:,.2f} | {t['low']:,.2f} | {t['close']:,.2f} |"
              for t in e["table"]]
        for name in ("coinbase", "bitstamp"):
            j = e[name]
            if j:
                L.append(f"- vs {name}: open {j['open_diff_pct']:+.2f}%, close {j['close_diff_pct']:+.2f}%, "
                         f"high {j['high_diff_pct']:+.2f}%, low {j['low_diff_pct']:+.2f}%; day return "
                         f"{j['binance_return_pct']:+.2f}% (source) vs {j['other_return_pct']:+.2f}% ({name}); "
                         f"gap {j['return_gap_pp']:+.2f} pp; rule met: {j['agrees']}")
            else:
                L.append(f"- vs {name}: not available")
        L.append("- High and low are shown but not used by the rule: they depend on when each venue "
                 "traded the extreme, and this strategy uses only closes and next-day opens.")
    L += ["", "## Limits", "",
          "- Two other venues agreeing supports that the move happened; it does not prove every price is exact.",
          "- USD and USDT prices can differ, especially in a crash."]
    return "\n".join(L) + "\n"
