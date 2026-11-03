"""research/crosscheck.py - compare the preserved Binance daily candles with independent sources.

READ-ONLY. Coinbase BTC/USD (docs read) is compared over the whole history. Bitstamp BTC/USD
(docs NOT read this session, so treated as unverified) is compared only around flagged days.
USD is not USDT, so small differences are normal; this checks that a flagged day really happened.
The Binance candles are never changed.
"""
import json
import os
import statistics
import time
import urllib.parse
from datetime import datetime, timezone

import fetcher
import providers
from fetcher import ApiError, Candle

DAY = 86400
COINBASE = "https://api.exchange.coinbase.com"
BITSTAMP = "https://www.bitstamp.net"
# Pre-stated rule for a flagged day (written before looking at the answer):
TOLERANCE_PCT = 3.0       # open and close within 3%, and the day's return within 3 percentage points


def day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def to_ts(text):
    return int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_coinbase_daily(http, first_ts, last_ts):
    out, cur = {}, first_ts
    while cur <= last_ts:
        end = min(cur + 299 * DAY, last_ts + DAY)
        q = urllib.parse.urlencode({"granularity": DAY,
                                    "start": datetime.fromtimestamp(cur, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "end": datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        rows = http.get(f"{COINBASE}/products/BTC-USD/candles?{q}")
        if not isinstance(rows, list):
            raise ApiError(f"Coinbase did not return a list: {str(rows)[:200]}")
        for r in rows:
            try:      # [time, low, high, open, close, volume]
                out[int(r[0])] = Candle(int(r[0]), float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]))
            except (TypeError, ValueError, IndexError):
                raise ApiError(f"unexpected Coinbase candle: {str(r)[:200]}")
        cur = end
    return out


def fetch_bitstamp_window(http, first_ts, days):
    q = urllib.parse.urlencode({"step": DAY, "limit": days, "start": first_ts})
    obj = http.get(f"{BITSTAMP}/api/v2/ohlc/btcusd/?{q}")
    try:
        rows = obj["data"]["ohlc"]
        return {int(r["timestamp"]): Candle(int(r["timestamp"]), float(r["open"]), float(r["high"]),
                                            float(r["low"]), float(r["close"]), float(r["volume"]))
                for r in rows}
    except (KeyError, TypeError, ValueError):
        raise ApiError(f"unexpected Bitstamp answer: {str(obj)[:200]}")


def pct(a, b):
    return (a / b - 1) * 100


def judge(binance, other, t):
    """Verdict inputs for one flagged day against one other source."""
    if t not in other or t - DAY not in other or t - DAY not in binance:
        return None
    b, o = binance[t], other[t]
    ret_b = pct(b.close, binance[t - DAY].close)
    ret_o = pct(o.close, other[t - DAY].close)
    d = {"open_diff_pct": pct(b.open, o.open), "close_diff_pct": pct(b.close, o.close),
         "high_diff_pct": pct(b.high, o.high), "low_diff_pct": pct(b.low, o.low),
         "binance_return_pct": ret_b, "other_return_pct": ret_o,
         "return_gap_pp": ret_b - ret_o}
    d["agrees"] = (abs(d["open_diff_pct"]) <= TOLERANCE_PCT and abs(d["close_diff_pct"]) <= TOLERANCE_PCT
                   and abs(d["return_gap_pp"]) <= TOLERANCE_PCT)
    return d


def compare(candles, coinbase, bitstamp, flagged_dates, window_days=2):
    """Pure comparison. `candles` is the preserved Binance list."""
    bn = {c.time: c for c in candles}
    common = sorted(set(bn) & set(coinbase))
    diffs = [(abs(pct(bn[t].close, coinbase[t].close)), t) for t in common]
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
        if cb is None:
            entry["verdict"] = "UNAVAILABLE"
        elif cb["agrees"] and (bs is None or bs["agrees"]):
            entry["verdict"] = "CONFIRMED (approximate: USD is not USDT)"
        else:
            entry["verdict"] = "NOT CONFIRMED"
        res["flagged"].append(entry)
    return res


def run_crosscheck(manifest, candles, flagged_dates, out_dir, opener=fetcher.default_opener,
                   sleep=time.sleep, timeout=20, retries=3):
    os.makedirs(out_dir, exist_ok=True)
    http = providers.Http(timeout, retries, opener, sleep)
    result = {"dataset_version": manifest["version_id"], "dataset_sha256": manifest["csv_sha256"],
              "rule": f"open and close within {TOLERANCE_PCT}%, and the day's return within "
                      f"{TOLERANCE_PCT} percentage points, on Coinbase BTC/USD (and Bitstamp if available)",
              "coinbase_error": None, "bitstamp_error": None, "http_log": []}
    coinbase, bitstamp = {}, {}
    try:
        coinbase = fetch_coinbase_daily(http, candles[0].time, candles[-1].time)
    except ApiError as e:
        result["coinbase_error"] = str(e)
    if flagged_dates:
        try:
            first = to_ts(min(flagged_dates)) - 3 * DAY
            bitstamp = fetch_bitstamp_window(http, first, 8 + (to_ts(max(flagged_dates)) - to_ts(min(flagged_dates))) // DAY)
        except ApiError as e:
            result["bitstamp_error"] = str(e)
    result.update(compare(candles, coinbase, bitstamp, flagged_dates))
    result["http_log"] = http.log[:6] + ([("...", f"{len(http.log)} requests in total")] if len(http.log) > 6 else [])
    with open(os.path.join(out_dir, "crosscheck.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    text = build_markdown(result)
    with open(os.path.join(out_dir, "crosscheck.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return result


def build_markdown(r):
    L = ["# Cross-check of flagged candles", "",
         f"Dataset `{r['dataset_version']}` (sha256 `{r['dataset_sha256'][:16]}...`). The Binance candles "
         "were **not changed**.", "",
         "Sources: **Coinbase BTC/USD** daily candles (official docs read; USD is not USDT) and "
         "**Bitstamp BTC/USD** around flagged days (official docs NOT read this session, so unverified).",
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
                         f"{j['binance_return_pct']:+.2f}% (Binance) vs {j['other_return_pct']:+.2f}% ({name}); "
                         f"gap {j['return_gap_pp']:+.2f} pp; rule met: {j['agrees']}")
            else:
                L.append(f"- vs {name}: not available")
        L.append("- High and low are shown but not used by the rule: they depend on when each venue "
                 "traded the extreme, and this strategy uses only closes and next-day opens.")
    L += ["", "## Limits", "",
          "- Two other venues agreeing supports that the move happened; it does not prove every price is exact.",
          "- USD and USDT prices can differ, especially in a crash."]
    return "\n".join(L) + "\n"
