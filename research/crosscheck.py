"""research/crosscheck.py - compare preserved Binance daily candles with Coinbase.

READ-ONLY. Coinbase BTC/USD is used as the independent comparison source.
USD is not USDT, so small differences are normal. This checks whether a
flagged day is broadly supported by the comparison source.
The Binance candles are never changed.
"""
import json
import math
import os
import statistics
import time
import urllib.parse
from datetime import datetime, timezone

import fetcher
import providers
from fetcher import ApiError, Candle
from validator import bad_ohlc

DAY = 86400
COINBASE = "https://api.exchange.coinbase.com"

# Pre-stated rule for a flagged day.
TOLERANCE_PCT = 3.0


def _validated_research_candle(ts, open_, high, low, close, volume):
    """Build a finite, positive-price research candle with non-negative volume."""
    candle = Candle(
        ts, float(open_), float(high), float(low), float(close), float(volume)
    )
    if bad_ohlc(candle) or not math.isfinite(candle.volume) or candle.volume < 0:
        raise ValueError("invalid research candle values")
    return candle


def day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def to_ts(text):
    return int(
        datetime.strptime(text, "%Y-%m-%d")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def fetch_coinbase_daily(http, first_ts, last_ts):
    out, cur = {}, first_ts

    while cur <= last_ts:
        end = min(cur + 299 * DAY, last_ts + DAY)
        q = urllib.parse.urlencode({
            "granularity": DAY,
            "start": datetime.fromtimestamp(
                cur, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": datetime.fromtimestamp(
                end, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

        rows = http.get(
            f"{COINBASE}/products/BTC-USD/candles?{q}"
        )

        if not isinstance(rows, list):
            raise ApiError(
                "Coinbase response has an invalid candle structure"
            )

        for row in rows:
            try:
                # Coinbase format: [time, low, high, open, close, volume]
                ts = fetcher.to_seconds(row[0])
                out[ts] = _validated_research_candle(
                    ts, row[3], row[2], row[1], row[4], row[5]
                )
            except (
                KeyError, TypeError, ValueError, IndexError, OverflowError
            ):
                raise ApiError(
                    "Coinbase response contains an invalid candle row"
                )

        cur = end

    return out


def pct(a, b):
    return (a / b - 1) * 100


def judge(binance, other, timestamp):
    """Compare one flagged day against Coinbase."""
    if (
        timestamp not in other
        or timestamp - DAY not in other
        or timestamp - DAY not in binance
    ):
        return None

    b = binance[timestamp]
    o = other[timestamp]

    ret_b = pct(b.close, binance[timestamp - DAY].close)
    ret_o = pct(o.close, other[timestamp - DAY].close)

    result = {
        "open_diff_pct": pct(b.open, o.open),
        "close_diff_pct": pct(b.close, o.close),
        "high_diff_pct": pct(b.high, o.high),
        "low_diff_pct": pct(b.low, o.low),
        "binance_return_pct": ret_b,
        "other_return_pct": ret_o,
        "return_gap_pp": ret_b - ret_o,
    }

    result["agrees"] = (
        abs(result["open_diff_pct"]) <= TOLERANCE_PCT
        and abs(result["close_diff_pct"]) <= TOLERANCE_PCT
        and abs(result["return_gap_pp"]) <= TOLERANCE_PCT
    )

    return result


def compare(candles, coinbase, flagged_dates, window_days=2):
    """Pure comparison. `candles` is the preserved Binance list."""
    bn = {c.time: c for c in candles}
    common = sorted(set(bn) & set(coinbase))

    diffs = [
        (abs(pct(bn[t].close, coinbase[t].close)), t)
        for t in common
    ]
    abs_d = [d for d, _ in diffs]

    result = {
        "common_days": len(common),
        "binance_days": len(bn),
        "coinbase_days": len(coinbase),
        "summary": None,
        "worst_days": [],
        "flagged": [],
    }

    if abs_d:
        sorted_diffs = sorted(abs_d)
        result["summary"] = {
            "median_abs_close_diff_pct": statistics.median(abs_d),
            "p95_abs_close_diff_pct": sorted_diffs[
                int(0.95 * (len(sorted_diffs) - 1))
            ],
            "p99_abs_close_diff_pct": sorted_diffs[
                int(0.99 * (len(sorted_diffs) - 1))
            ],
            "max_abs_close_diff_pct": sorted_diffs[-1],
            "days_over_1pct": sum(1 for d in abs_d if d > 1),
            "days_over_2pct": sum(1 for d in abs_d if d > 2),
            "days_over_5pct": sum(1 for d in abs_d if d > 5),
        }

        result["worst_days"] = [
            {
                "date": day(timestamp),
                "abs_close_diff_pct": round(diff, 3),
            }
            for diff, timestamp in sorted(diffs, reverse=True)[:8]
        ]

    for flagged_date in flagged_dates:
        timestamp = to_ts(flagged_date)
        coinbase_judgement = judge(bn, coinbase, timestamp)

        entry = {
            "date": flagged_date,
            "table": [],
            "coinbase": coinbase_judgement,
        }

        for offset in range(-2, 3):
            current_ts = timestamp + offset * DAY

            for source_name, source in (
                ("binance", bn),
                ("coinbase", coinbase),
            ):
                if current_ts in source:
                    candle = source[current_ts]
                    entry["table"].append({
                        "date": day(current_ts),
                        "source": source_name,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                    })

        if coinbase_judgement is None:
            entry["verdict"] = "UNAVAILABLE"
        elif coinbase_judgement["agrees"]:
            entry["verdict"] = (
                "CONFIRMED (approximate: USD is not USDT)"
            )
        else:
            entry["verdict"] = "NOT CONFIRMED"

        result["flagged"].append(entry)

    return result


def run_crosscheck(
    manifest,
    candles,
    flagged_dates,
    out_dir,
    opener=fetcher.default_opener,
    sleep=time.sleep,
    timeout=20,
    retries=3,
):
    os.makedirs(out_dir, exist_ok=True)

    http = providers.Http(timeout, retries, opener, sleep)

    result = {
        "dataset_version": manifest["version_id"],
        "dataset_sha256": manifest["csv_sha256"],
        "rule": (
            f"open and close within {TOLERANCE_PCT}%, "
            f"and the day's return within {TOLERANCE_PCT} "
            "percentage points, on Coinbase BTC/USD"
        ),
        "coinbase_error": None,
        "http_log": [],
    }

    coinbase = {}

    try:
        coinbase = fetch_coinbase_daily(
            http, candles[0].time, candles[-1].time
        )
    except ApiError as error:
        result["coinbase_error"] = str(error)

    result.update(compare(candles, coinbase, flagged_dates))

    result["http_log"] = (
        http.log[:6]
        + (
            [("...", f"{len(http.log)} requests in total")]
            if len(http.log) > 6 else []
        )
    )

    with open(
        os.path.join(out_dir, "crosscheck.json"),
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(result, file, indent=2)

    markdown = build_markdown(result)

    with open(
        os.path.join(out_dir, "crosscheck.md"),
        "w",
        encoding="utf-8",
    ) as file:
        file.write(markdown)

    print(markdown)
    return result


def build_markdown(result):
    lines = [
        "# Cross-check of flagged candles",
        "",
        (
            f"Dataset `{result['dataset_version']}` "
            f"(sha256 `{result['dataset_sha256'][:16]}...`). "
            "The Binance candles were **not changed**."
        ),
        "",
        (
            "Source: **Coinbase BTC/USD** daily candles. "
            "USD is not USDT, so price differences are possible."
        ),
        f"Pre-stated rule: {result['rule']}.",
        "",
    ]

    if result["coinbase_error"]:
        lines.append(
            f"- Coinbase could not be fetched: "
            f"{result['coinbase_error']}"
        )

    summary = result["summary"]

    if summary:
        lines += [
            "",
            (
                "## Whole-history comparison with Coinbase "
                f"({result['common_days']} common days)"
            ),
            "",
            "| Close difference |  |",
            "|---|---|",
            (
                f"| Median | "
                f"{summary['median_abs_close_diff_pct']:.3f}% |"
            ),
            (
                f"| 95th percentile | "
                f"{summary['p95_abs_close_diff_pct']:.3f}% |"
            ),
            (
                f"| 99th percentile | "
                f"{summary['p99_abs_close_diff_pct']:.3f}% |"
            ),
            (
                f"| Maximum | "
                f"{summary['max_abs_close_diff_pct']:.3f}% |"
            ),
            (
                f"| Days over 1% / 2% / 5% | "
                f"{summary['days_over_1pct']} / "
                f"{summary['days_over_2pct']} / "
                f"{summary['days_over_5pct']} |"
            ),
            "",
            "Largest disagreements: "
            + ", ".join(
                f"{item['date']} ({item['abs_close_diff_pct']}%)"
                for item in result["worst_days"]
            ),
        ]

    for entry in result["flagged"]:
        lines += [
            "",
            (
                f"## Flagged day {entry['date']}: "
                f"**{entry['verdict']}**"
            ),
            "",
            "| Date | Source | Open | High | Low | Close |",
            "|---|---|---|---|---|---|",
        ]

        lines += [
            (
                f"| {item['date']} | {item['source']} | "
                f"{item['open']:,.2f} | {item['high']:,.2f} | "
                f"{item['low']:,.2f} | {item['close']:,.2f} |"
            )
            for item in entry["table"]
        ]

        judgement = entry["coinbase"]

        if judgement:
            lines.append(
                f"- vs Coinbase: "
                f"open {judgement['open_diff_pct']:+.2f}%, "
                f"close {judgement['close_diff_pct']:+.2f}%, "
                f"high {judgement['high_diff_pct']:+.2f}%, "
                f"low {judgement['low_diff_pct']:+.2f}%; "
                f"day return "
                f"{judgement['binance_return_pct']:+.2f}% "
                f"(Binance) vs "
                f"{judgement['other_return_pct']:+.2f}% "
                f"(Coinbase); "
                f"gap {judgement['return_gap_pp']:+.2f} pp; "
                f"rule met: {judgement['agrees']}"
            )
        else:
            lines.append("- vs Coinbase: not available")

        lines.append(
            "- High and low are shown but not used by the rule: "
            "they depend on when each venue traded the extreme, "
            "and this strategy uses only closes and next-day opens."
        )

    lines += [
        "",
        "## Limits",
        "",
        (
            "- One independent comparison source supports the check, "
            "but does not prove every price is exact."
        ),
        "- USD and USDT prices can differ, especially in a crash.",
    ]

    return "\n".join(lines) + "\n"
