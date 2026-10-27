"""live_check.py - READ-ONLY live smoke test of public BTC candle providers.

For each provider (isolated: one failing never stops the others) it records
  1. reachability  - did the exchange clock endpoint answer, and with what HTTP status
  2. parsing       - did candles come back and parse
  3. validation    - closed candles, gaps, OHLC sanity, freshness, coverage, clock skew
A provider is VERIFIED only if its real candles pass every validation check.
The overall result is PASS only if at least `min_verified` providers are VERIFIED.

Usage: python3 live_check.py
Writes: out/providers.md, out/providers.json, out/candles_<provider>.csv
Exit 0 = PASS or WARN, 1 = FAIL.
"""
import csv
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

import fetcher
import providers
import report
import validator
from fetcher import ApiError

BLOCK_MARKERS = ("HTTP 403", "HTTP 451")


def utc(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def check_provider(name, cfg, opener, sleep, local_now):
    """Runs one provider end to end. Never raises for provider problems."""
    tf = cfg["timeframe"]
    tf_sec = fetcher.TF_SECONDS[tf]
    t0 = time.time()
    p = providers.build(name)
    http = providers.Http(cfg.get("http_timeout_seconds", 15), cfg.get("http_retries", 3),
                          opener, sleep)
    r = {"provider": name, "pair": p.label, "quote": p.quote, "docs": p.docs,
         "timeframe": tf, "reachability": "not run", "parsing": "not run",
         "validation": "not run", "verdict": "FAILED", "detail": "", "stats": {}, "checks": [],
         "first_candle": None, "last_candle": None, "last_close": None,
         "requests": 0, "http_log": [], "seconds": 0.0}
    clean = []
    try:
        try:
            server_now = p.server_time(http)
        except ApiError as e:
            r.update(reachability="FAIL", detail=str(e))
            r["verdict"] = "BLOCKED FROM RUNNER" if any(m in str(e) for m in BLOCK_MARKERS) else "FAILED"
            raise
        r["reachability"] = f"OK (exchange time {utc(server_now)} UTC)"
        start_s = server_now - cfg["lookback_days"] * 86400
        try:
            raw = p.candles(tf, start_s, server_now, http)
        except ApiError as e:
            r.update(parsing="FAIL", detail=str(e))
            r["verdict"] = "BLOCKED FROM RUNNER" if any(m in str(e) for m in BLOCK_MARKERS) else "FAILED"
            raise
        if not raw:
            r.update(parsing="FAIL", detail="answered, but returned zero candles", verdict="FAILED")
            raise ApiError("zero candles")
        r["parsing"] = f"OK ({len(raw)} candles parsed)"
        v = validator.validate(raw, tf_sec, server_now, local_now, start_s, server_now, cfg)
        clean = v.clean
        r.update(validation=v.status, stats=v.stats, checks=[asdict(c) for c in v.checks])
        r["verdict"] = {"PASS": "VERIFIED", "WARN": "USABLE WITH WARNINGS"}.get(v.status, "FAILED")
        if clean:
            r.update(first_candle=utc(clean[0].time), last_candle=utc(clean[-1].time),
                     last_close=clean[-1].close)
    except ApiError:
        pass
    r["requests"], r["http_log"] = http.requests, http.log
    r["seconds"] = round(time.time() - t0, 2)
    return r, clean


def cross_check(results, candles_by):
    """Informational only: compares the latest candle time every verified provider shares."""
    ok = [r["provider"] for r in results if r["verdict"] in ("VERIFIED", "USABLE WITH WARNINGS")]
    if len(ok) < 2:
        return None
    maps = {n: {c.time: c for c in candles_by[n]} for n in ok}
    common = set.intersection(*(set(m) for m in maps.values()))
    if not common:
        return {"note": "no common candle time", "rows": []}
    t = max(common)
    rows = [(n, next(r["quote"] for r in results if r["provider"] == n), maps[n][t].close) for n in ok]
    lo, hi = min(c for _, _, c in rows), max(c for _, _, c in rows)
    return {"time": utc(t), "rows": rows, "spread_pct": (hi / lo - 1) * 100}


def build_markdown(out):
    ICON = {"VERIFIED": "✅", "USABLE WITH WARNINGS": "⚠️", "BLOCKED FROM RUNNER": "🚫", "FAILED": "❌"}
    L = [f"# Live market-data check ({out['timeframe']} candles, last {out['lookback_days']} days)",
         f"Generated {out['generated_utc']} · **READ-ONLY** · no keys, no orders", "",
         f"## Overall: {report.ICON.get(out['status'], '')} {out['status']}",
         f"{out['verified']} of {len(out['providers'])} providers VERIFIED "
         f"(need {out['min_verified']}). {out['status_reason']}", "",
         "| Provider | Pair | Verdict | Last close | Last closed candle | Candles | Requests |",
         "|---|---|---|---|---|---|---|"]
    for r in out["providers"]:
        s = r["stats"]
        close = "{:,.2f} {}".format(r["last_close"], r["quote"]) if r["last_close"] else "-"
        when = r["last_candle"] + " UTC" if r["last_candle"] else "-"
        L.append("| {} | {} | {} {} | {} | {} | {} | {} |".format(
            r["provider"], r["pair"], ICON[r["verdict"]], r["verdict"], close, when,
            s.get("closed_candles", "-"), r["requests"]))
    for r in out["providers"]:
        L += ["", f"## {r['provider']} - {ICON[r['verdict']]} {r['verdict']}",
              f"- Pair: **{r['pair']}** (quote asset {r['quote']}; USD and USDT are different assets)",
              f"- Docs: {r['docs']}",
              f"- 1 Reachability: {r['reachability']}",
              f"- 2 Parsing: {r['parsing']}",
              f"- 3 Validation: {r['validation']}"]
        if r["detail"]:
            L.append(f"- Failure detail: {r['detail'][:400]}")
        if r["http_log"]:
            L.append("- HTTP evidence: " + "; ".join(f"`{p}` {w}" for p, w in r["http_log"][:8]))
        if r["checks"]:
            L += ["", "| Check | Result | Detail |", "|---|---|---|"]
            L += [f"| {c['name']} | {report.ICON[c['status']]} {c['status']} | {c['detail']} |"
                  for c in r["checks"]]
    cc = out.get("cross_check")
    if cc and cc.get("rows"):
        L += ["", f"## Cross-check (information only) at candle {cc['time']} UTC", "",
              "| Provider | Quote | Close |", "|---|---|---|"]
        L += [f"| {n} | {q} | {c:,.2f} |" for n, q, c in cc["rows"]]
        L += ["", f"Spread between highest and lowest close: {cc['spread_pct']:.3f}%. "
              "Different venues and quote assets (USD vs USDT) are expected to differ a little."]
    L += ["", "## Limits of this report", "",
          "- A VERIFIED provider means: the endpoint answered from this runner, the candles parsed, "
          "and they passed every check above at this moment. It says nothing about profit.",
          "- Only one run is shown; availability from GitHub can change. Re-run to re-verify.",
          "- BLOCKED FROM RUNNER means the exchange refused this runner (HTTP 403/451). "
          "No attempt is made to bypass it."]
    return "\n".join(L) + "\n"


def run_live_check(cfg, out_dir="out", opener=fetcher.default_opener, sleep=time.sleep,
                   local_now=None):
    if cfg.get("mode") != "read_only":
        raise SystemExit("Refusing to run: only mode 'read_only' is supported.")
    if cfg["timeframe"] not in fetcher.TF_SECONDS:
        raise SystemExit(f"Unknown timeframe {cfg['timeframe']!r}")
    os.makedirs(out_dir, exist_ok=True)
    local_now = time.time() if local_now is None else local_now
    results, candles_by = [], {}
    for name in cfg["live_providers"]:
        r, clean = check_provider(name, cfg, opener, sleep, local_now)
        results.append(r)
        candles_by[name] = clean
        if clean:
            with open(os.path.join(out_dir, f"candles_{name}.csv"), "w", newline="",
                      encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["time_unix", "time_utc", "open", "high", "low", "close", "volume"])
                for c in clean:
                    w.writerow([c.time, utc(c.time), c.open, c.high, c.low, c.close, c.volume])
    verified = sum(1 for r in results if r["verdict"] == "VERIFIED")
    warned = sum(1 for r in results if r["verdict"] == "USABLE WITH WARNINGS")
    need = cfg.get("min_verified", 1)
    if verified >= need:
        status, why = "PASS", "Enough providers passed every validation check."
    elif verified + warned >= need:
        status, why = "WARN", "No provider passed cleanly; data is usable only with the warnings shown."
    else:
        status, why = "FAIL", "No provider delivered validated live data. Nothing is made up."
    out = {"generated_utc": datetime.fromtimestamp(local_now, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
           "timeframe": cfg["timeframe"], "lookback_days": cfg["lookback_days"], "mode": cfg["mode"],
           "min_verified": need, "verified": verified, "status": status, "status_reason": why,
           "providers": results, "cross_check": cross_check(results, candles_by)}
    text = build_markdown(out)
    with open(os.path.join(out_dir, "providers.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "providers.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0 if status in ("PASS", "WARN") else 1


if __name__ == "__main__":
    with open("config.json", encoding="utf-8") as f:
        sys.exit(run_live_check(json.load(f)))
