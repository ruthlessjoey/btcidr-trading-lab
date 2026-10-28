"""tools/audit_discrepancy.py - AUDIT ONLY (read-only). Explains Binance BTC/USDT vs Coinbase BTC/USD
and Bitstamp BTC/USD daily differences. It never changes the dataset and never computes any
return for the TEST window (only signal agreement there)."""
import json
import os
import statistics
import sys
import time
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.getcwd())
import fetcher  # noqa: E402
import providers  # noqa: E402
from research import crosscheck, engine, selection, splits as splits_mod, strategy  # noqa: E402
from research.pipeline import load_pinned  # noqa: E402

DAY = 86400


def day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def pct(a, b):
    return (a / b - 1) * 100


def fetch_bitstamp_all(http, first_ts, last_ts):
    out, cur = {}, first_ts
    for _ in range(8):
        q = urllib.parse.urlencode({"step": DAY, "limit": 1000, "start": cur})
        rows = http.get(f"{crosscheck.BITSTAMP}/api/v2/ohlc/btcusd/?{q}")["data"]["ohlc"]
        got = [int(r["timestamp"]) for r in rows]
        for r in rows:
            t = int(r["timestamp"])
            out[t] = fetcher.Candle(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"]))
        if not got or max(got) >= last_ts:
            break
        cur = max(got) + DAY
    return out


def year_stats(a, b, times):
    by = {}
    for t in times:
        by.setdefault(day(t)[:4], []).append(abs(pct(a[t].close, b[t].close)))
    rows = []
    for y, v in sorted(by.items()):
        s = sorted(v)
        rows.append({"year": y, "days": len(v), "median": statistics.median(v), "p95": s[int(.95 * (len(s) - 1))],
                     "max": s[-1], "gt1": sum(x > 1 for x in v), "gt2": sum(x > 2 for x in v), "gt5": sum(x > 5 for x in v)})
    return rows


def hourly(http, d, bn_host):
    t0 = crosscheck.to_ts(d)
    qb = urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "1h", "startTime": t0 * 1000, "endTime": (t0 + DAY - 1) * 1000, "limit": 24})
    b = fetcher.parse_klines(http.get(f"{bn_host}/api/v3/klines?{qb}"))
    f = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    qc = urllib.parse.urlencode({"granularity": 3600, "start": f(t0), "end": f(t0 + DAY - 3600)})
    rows = http.get(f"{crosscheck.COINBASE}/products/BTC-USD/candles?{qc}")
    c = {int(r[0]): float(r[4]) for r in rows}
    return [(day(x.time) + " %02d:00" % ((x.time % DAY) // 3600), x.close, c.get(x.time)) for x in b]


def main():
    cfg = json.load(open("backtest_config.json"))
    manifest, bn_list = load_pinned(cfg, "prev/datasets")
    bn = {c.time: c for c in bn_list}
    http = providers.Http(25, 3, fetcher.default_opener, time.sleep)
    cb = crosscheck.fetch_coinbase_daily(http, bn_list[0].time, bn_list[-1].time)
    bs = fetch_bitstamp_all(http, bn_list[0].time, bn_list[-1].time)
    n = len(bn_list)
    sp = splits_mod.make_splits(n)
    common = sorted(set(bn) & set(cb) & set(bs))
    res = {"dataset": manifest["version_id"], "days_binance": n, "days_coinbase": len(cb), "days_bitstamp": len(bs),
           "common_three": len(common),
           "binance_vs_coinbase": year_stats(bn, cb, common), "coinbase_vs_bitstamp": year_stats(cb, bs, common),
           "binance_vs_bitstamp": year_stats(bn, bs, common)}
    # signed premium: Binance minus Coinbase, by year (median)
    prem = {}
    for t in common:
        prem.setdefault(day(t)[:4], []).append(pct(bn[t].close, cb[t].close))
    res["signed_median_binance_over_coinbase_pct"] = {y: round(statistics.median(v), 3) for y, v in sorted(prem.items())}
    # day-boundary alignment: return correlation at shifts
    def rets(src):
        return {t: src[t].close / src[t - DAY].close - 1 for t in common if t - DAY in src}
    rb, rc = rets(bn), rets(cb)
    def corr(x, y):
        mx, my = statistics.mean(x), statistics.mean(y)
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        den = (sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y)) ** .5
        return num / den
    shifts = {}
    for sh in (-1, 0, 1):
        ts = [t for t in rb if t + sh * DAY in rc]
        shifts[str(sh)] = round(corr([rb[t] for t in ts], [rc[t + sh * DAY] for t in ts]), 4)
    res["return_correlation_by_day_shift"] = shifts
    # candle continuity (open vs previous close) per source
    def cont(src):
        v = [abs(src[t].open / src[t - DAY].close - 1) * 100 for t in common if t - DAY in src]
        return {"median_pct": round(statistics.median(v), 4), "p99_pct": round(sorted(v)[int(.99 * (len(v) - 1))], 3)}
    res["open_vs_prev_close"] = {"binance": cont(bn), "coinbase": cont(cb), "bitstamp": cont(bs)}
    # volume by year (median BTC per day)
    vol = {}
    for t in common:
        vol.setdefault(day(t)[:4], {"binance": [], "coinbase": []})
        vol[day(t)[:4]]["binance"].append(bn[t].volume)
        vol[day(t)[:4]]["coinbase"].append(cb[t].volume)
    res["median_daily_volume_btc"] = {y: {k: round(statistics.median(v), 1) for k, v in d.items()} for y, d in sorted(vol.items())}
    # worst days and hourly look
    worst = sorted(common, key=lambda t: -abs(pct(bn[t].close, cb[t].close)))[:3]
    res["worst3"] = [{"date": day(t), "binance_close": bn[t].close, "coinbase_close": cb[t].close,
                      "bitstamp_close": bs[t].close, "diff_pct": round(pct(bn[t].close, cb[t].close), 2),
                      "coinbase_vs_bitstamp_pct": round(pct(cb[t].close, bs[t].close), 2)} for t in worst]
    res["hourly"] = {}
    for t in worst:
        try:
            res["hourly"][day(t)] = hourly(http, day(t), "https://data-api.binance.vision")
        except Exception as e:  # noqa: BLE001
            res["hourly"][day(t)] = str(e)
    # affected days by segment
    seg = {}
    for k, (a, b) in sp.items():
        ts = [bn_list[i].time for i in range(a, b) if bn_list[i].time in cb]
        d = [abs(pct(bn[t].close, cb[t].close)) for t in ts]
        seg[k] = {"days": len(d), "gt1": sum(x > 1 for x in d), "gt2": sum(x > 2 for x in d), "gt5": sum(x > 5 for x in d),
                  "median": round(statistics.median(d), 3), "max": round(max(d), 2)}
    res["by_segment"] = seg
    # impact on the frozen 150-day rule: signals on Binance vs Coinbase closes (test: signals only)
    cb_series = [cb[c.time] for c in bn_list if c.time in cb]
    if len(cb_series) == n:
        sb, sc = strategy.ma_trend(150)(bn_list), strategy.ma_trend(150)(cb_series)
        res["signal_disagreement_150"] = {k: {"bars": b - a, "differ": sum(sb[i] != sc[i] for i in range(a, b))} for k, (a, b) in sp.items()}
        # returns on Coinbase series: train and validation ONLY (never the test window)
        rr = {}
        for k in ("train", "validation"):
            a, b = sp[k]
            costs = selection.SELECTION_COSTS
            rr[k] = {"binance": engine.metrics(engine.simulate(bn_list, sb, a, b, costs))["total_return"],
                     "coinbase_series_same_rule": engine.metrics(engine.simulate(cb_series, sc, a, b, costs))["total_return"]}
        res["train_validation_return_binance_vs_coinbase_series"] = rr
    res["http_requests"] = http.requests
    os.makedirs("out", exist_ok=True)
    json.dump(res, open("out/audit_discrepancy.json", "w"), indent=2, default=str)
    L = ["# Audit: Binance BTC/USDT vs Coinbase BTC/USD vs Bitstamp BTC/USD (daily)", "",
         f"Dataset `{res['dataset']}`; days Binance {n}, Coinbase {len(cb)}, Bitstamp {len(bs)}, common to all three {len(common)}.", "",
         "Bitstamp API docs were NOT read this session (unverified source).", ""]
    for key, title in (("binance_vs_coinbase", "Binance vs Coinbase"), ("coinbase_vs_bitstamp", "Coinbase vs Bitstamp (both USD)"), ("binance_vs_bitstamp", "Binance vs Bitstamp")):
        L += [f"## |close difference|, {title}", "", "| Year | Days | Median % | P95 % | Max % | >1% | >2% | >5% |", "|---|---|---|---|---|---|---|---|"]
        L += [f"| {r['year']} | {r['days']} | {r['median']:.3f} | {r['p95']:.2f} | {r['max']:.2f} | {r['gt1']} | {r['gt2']} | {r['gt5']} |" for r in res[key]]
        L.append("")
    L += ["## Signed median (Binance minus Coinbase), %", "", json.dumps(res["signed_median_binance_over_coinbase_pct"]), "",
          "## Day boundary alignment (daily return correlation Binance vs Coinbase at day shifts)", "", json.dumps(shifts), "",
          "## Open vs previous close (candle continuity)", "", json.dumps(res["open_vs_prev_close"]), "",
          "## Median daily volume (BTC)", "", "| Year | Binance | Coinbase |", "|---|---|---|"]
    L += [f"| {y} | {v['binance']} | {v['coinbase']} |" for y, v in res["median_daily_volume_btc"].items()]
    L += ["", "## Worst three days", ""] + [f"- {w}" for w in res["worst3"]]
    for d, rows in res["hourly"].items():
        L += ["", f"### Hourly closes on {d} (Binance USDT vs Coinbase USD)", "", "| Hour UTC | Binance | Coinbase | diff % |", "|---|---|---|---|"]
        if isinstance(rows, str):
            L.append(f"| error | {rows} | | |")
        else:
            L += [f"| {h} | {b:,.2f} | {('%.2f' % c) if c else 'n/a'} | {('%+.2f' % pct(b, c)) if c else 'n/a'} |" for h, b, c in rows]
    L += ["", "## Days affected by segment (|Binance-Coinbase close| difference)", "", json.dumps(res["by_segment"], indent=1)]
    if "signal_disagreement_150" in res:
        L += ["", "## 150-day rule: days where the signal differs if Coinbase closes are used", "", json.dumps(res["signal_disagreement_150"]),
              "", "Train/validation return (base costs) on Binance vs Coinbase series (test window deliberately NOT computed):", "",
              json.dumps(res["train_validation_return_binance_vs_coinbase_series"])]
    open("out/audit_discrepancy.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
