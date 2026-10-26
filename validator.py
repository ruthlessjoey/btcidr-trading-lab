"""validator.py - checks candle data before anything is allowed to trust it."""
import math
from dataclasses import dataclass, field

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_RANK = {PASS: 0, WARN: 1, FAIL: 2}


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Result:
    checks: list
    clean: list                      # sorted, de-duplicated, fully closed candles
    status: str
    stats: dict = field(default_factory=dict)


def worst(statuses):
    return max(statuses, key=lambda s: _RANK[s], default=PASS)


def clean_candles(candles):
    """Sort by time and drop duplicate timestamps. Keeps the first copy."""
    info = {"was_sorted": True, "exact_duplicates": 0, "conflicting_duplicates": 0}
    times = [c.time for c in candles]
    info["was_sorted"] = all(a <= b for a, b in zip(times, times[1:]))
    seen = {}
    for c in candles:
        if c.time in seen:
            key = "exact_duplicates" if seen[c.time] == c else "conflicting_duplicates"
            info[key] += 1
        else:
            seen[c.time] = c
    return [seen[t] for t in sorted(seen)], info


def split_forming(candles, tf_sec, now_s):
    """A candle whose period has not ended yet is still changing: never use it."""
    closed = [c for c in candles if c.time + tf_sec <= now_s]
    return closed, len(candles) - len(closed)


def find_gaps(candles, tf_sec):
    """Returns [(open_time_of_candle_before_gap, missing_count), ...]."""
    gaps = []
    for a, b in zip(candles, candles[1:]):
        step = b.time - a.time
        if step > tf_sec:
            gaps.append((a.time, max(1, round(step / tf_sec) - 1)))
    return gaps


def bad_ohlc(c):
    vals = (c.open, c.high, c.low, c.close)
    if not all(math.isfinite(v) for v in vals) or min(vals) <= 0:
        return True
    return c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high)


def _t(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def validate(raw, tf_sec, server_now_s, local_now_s, start_s, end_s, cfg):
    checks = []

    def add(name, status, detail):
        checks.append(Check(name, status, detail))

    stats = {"raw_candles": len(raw), "closed_candles": 0, "forming_dropped": 0,
             "missing_candles": 0, "zero_volume_candles": 0}

    if not raw:
        add("has_data", FAIL, "the API returned zero candles")
        return Result(checks, [], FAIL, stats)
    add("has_data", PASS, f"{len(raw)} candles received")

    clean, info = clean_candles(raw)
    order_status = worst([
        FAIL if info["conflicting_duplicates"] else PASS,
        WARN if (info["exact_duplicates"] or not info["was_sorted"]) else PASS])
    add("order_and_duplicates", order_status,
        f"sorted_as_received={info['was_sorted']}, exact_duplicates_removed="
        f"{info['exact_duplicates']}, conflicting_duplicates={info['conflicting_duplicates']}")

    closed, forming = split_forming(clean, tf_sec, server_now_s)
    stats["closed_candles"], stats["forming_dropped"] = len(closed), forming
    if not closed:
        add("closed_candles", FAIL, "no fully closed candles available")
        return Result(checks, [], worst([c.status for c in checks]), stats)
    add("closed_candles", PASS,
        f"{len(closed)} closed candles; {forming} still-forming candle(s) excluded")

    t0 = closed[0].time
    off_grid = sum(1 for c in closed if (c.time - t0) % tf_sec != 0)
    add("timestamp_grid", FAIL if off_grid else PASS,
        f"{off_grid} candle(s) not on the {tf_sec}s grid" if off_grid
        else f"all timestamps are exact multiples of {tf_sec}s")

    gaps = find_gaps(closed, tf_sec)
    missing = sum(m for _, m in gaps)
    stats["missing_candles"] = missing
    ratio = missing / (len(closed) + missing)
    gap_text = "; ".join(f"{m} after {_t(t)} UTC" for t, m in gaps[:5])
    add("missing_candles",
        FAIL if ratio > cfg.get("max_missing_ratio", 0.02) else (WARN if missing else PASS),
        f"{missing} missing ({ratio:.2%})" + (f": {gap_text}" if gaps else ""))

    bad = sum(1 for c in closed if bad_ohlc(c))
    add("ohlc_sanity", FAIL if bad else PASS,
        f"{bad} candle(s) with impossible prices" if bad
        else "high/low/open/close are consistent and positive")

    neg = sum(1 for c in closed if c.volume < 0 or not math.isfinite(c.volume))
    zero = sum(1 for c in closed if c.volume == 0)
    stats["zero_volume_candles"] = zero
    vol_status = FAIL if neg else (WARN if zero / len(closed) > 0.10 else PASS)
    add("volume_sanity", vol_status,
        f"{neg} invalid volume(s); {zero} zero-volume candle(s) of {len(closed)}")

    limit = cfg.get("max_spike_pct", 20)
    spikes = sum(1 for a, b in zip(closed, closed[1:])
                 if b.time - a.time == tf_sec and a.close > 0
                 and abs(b.close / a.close - 1) * 100 > limit)
    add("price_spikes", WARN if spikes else PASS,
        f"{spikes} close-to-close move(s) larger than {limit}%")

    age = server_now_s - (closed[-1].time + tf_sec)
    add("freshness", FAIL if age > 2 * tf_sec else PASS,
        f"newest closed candle ended {age}s before exchange time (limit {2 * tf_sec}s)")

    late = closed[0].time - start_s
    add("history_coverage", WARN if late > 2 * tf_sec else PASS,
        f"first candle {_t(closed[0].time)} UTC vs requested start {_t(start_s)} UTC")

    skew = abs(local_now_s - server_now_s)
    add("clock_skew", WARN if skew > 120 else PASS,
        f"runner clock differs from exchange clock by {skew:.0f}s")

    return Result(checks, closed, worst([c.status for c in checks]), stats)
