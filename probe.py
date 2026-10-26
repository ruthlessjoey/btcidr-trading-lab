"""probe.py - shows exactly what Tokocrypto's public endpoints answer from THIS machine.

READ-ONLY diagnostic. It never fails the build; it just records the evidence:
HTTP status, a short piece of the raw answer, and what we could make of it.
Usage:  python3 probe.py        Writes: out/probe.md
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
from datetime import datetime, timezone

import fetcher
from run import assert_read_only, load_config

WANTED = {"BTC_USDT", "BTCUSDT"}


def probe_get(url, timeout, opener):
    """One GET that never raises. Returns what happened."""
    t0 = time.time()
    status, body, error = None, b"", None
    try:
        status, body = opener(url, timeout)
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body = e.read()
        except Exception:
            body = b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        error = f"network error: {e}"
    return {"url": url, "status": status, "error": error, "bytes": len(body),
            "seconds": round(time.time() - t0, 2), "body": body}


def find_symbol_entry(obj, wanted=WANTED):
    """Walk any JSON and return the first dict that mentions BTC_USDT / BTCUSDT."""
    if isinstance(obj, dict):
        if any(isinstance(v, str) and v.upper() in wanted for v in obj.values()):
            return obj
        for v in obj.values():
            hit = find_symbol_entry(v, wanted)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find_symbol_entry(v, wanted)
            if hit is not None:
                return hit
    return None


def describe(p):
    if p["error"]:
        return f"❌ {p['error']}"
    mark = "✅" if p["status"] == 200 else "❌"
    return f"{mark} HTTP {p['status']} · {p['bytes']} bytes · {p['seconds']}s"


def raw_block(p, size=300):
    text = fetcher.snippet(p["body"], size).replace("`", "'")
    return f"```\n{text or '(empty)'}\n```"


def probe_source(src, cfg, opener):
    timeout = cfg.get("http_timeout_seconds", 15)
    pair, tf = cfg["pair"], cfg["timeframe"]
    L = [f"## {src.name}", f"Base: `{src.base_url}` · style: `{src.style}`", ""]

    p = probe_get(src.time_url(), timeout, opener)
    L += [f"**Server time** `{src.time_url()}`", describe(p), raw_block(p)]
    if p["status"] == 200:
        try:
            ts = fetcher.extract_server_time(json.loads(p["body"].decode("utf-8")))
            L.append(f"Parsed: {datetime.fromtimestamp(ts, tz=timezone.utc):%Y-%m-%d %H:%M:%S} UTC "
                     f"(this machine's clock differs by {abs(time.time() - ts):.0f}s)")
        except (ValueError, fetcher.ApiError) as e:
            L.append(f"Could not parse: {e}")
    L.append("")

    query = urllib.parse.urlencode({"symbol": src.symbol(pair), "interval": tf, "limit": 3})
    url = f"{src.klines_url()}?{query}"
    p = probe_get(url, timeout, opener)
    L += [f"**Latest 3 candles** `{url}`", describe(p), raw_block(p)]
    if p["status"] == 200:
        try:
            rows = fetcher.parse_klines(json.loads(p["body"].decode("utf-8")))
            L.append(f"Parsed {len(rows)} candle(s); newest open time "
                     f"{datetime.fromtimestamp(rows[-1].time, tz=timezone.utc):%Y-%m-%d %H:%M} UTC"
                     if rows else "Parsed 0 candles")
        except (ValueError, fetcher.ApiError) as e:
            L.append(f"Could not parse: {e}")
    L.append("")

    url = src.symbols_url(pair)
    p = probe_get(url, timeout, opener)
    L += [f"**Symbol info for {pair}** `{url}`", describe(p)]
    if p["status"] == 200:
        try:
            entry = find_symbol_entry(json.loads(p["body"].decode("utf-8")))
        except ValueError:
            entry = None
        if entry is None:
            L += [f"No entry mentioning {pair} was found in the answer.", raw_block(p)]
        else:
            L += [f"Entry found for {pair} (raw, includes any size/notional rules):",
                  "```", json.dumps(entry, indent=1)[:1500], "```"]
    else:
        L.append(raw_block(p))
    L.append("")
    return L


def run_probe(cfg, out_dir="out", opener=fetcher.default_opener):
    assert_read_only(cfg)
    os.makedirs(out_dir, exist_ok=True)
    L = [f"# Endpoint probe: {cfg['pair']} on {cfg['exchange']}",
         f"Run at {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC · READ-ONLY · "
         "this shows what the exchange really answered from this machine.", ""]
    for source_cfg in cfg["sources"]:
        L += probe_source(fetcher.Source(**source_cfg), cfg, opener)
    text = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "probe.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(run_probe(load_config()))
