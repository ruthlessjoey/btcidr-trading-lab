"""probe.py - bounded, policy-enforced public time/candle diagnostic.

Manual-only. It requests only the exact approved Tokocrypto public GET routes.
No symbol metadata, response snippets, credentials, account endpoints, or orders.
"""
import json
import os
import sys
import time
import urllib.error
from datetime import datetime, timezone

import fetcher
import transport_policy
from run import assert_read_only, load_config


def probe_get(url, timeout, opener):
    """One GET. Preflight validation also applies to injected test openers."""
    try:
        limit = transport_policy.validate_request(url, "GET")
        status, body = opener(url, timeout)
        if not isinstance(body, (bytes, bytearray)) or len(body) > limit:
            raise transport_policy.PolicyError("response exceeds policy")
        return {"status": status, "bytes": len(body), "body": bytes(body), "error": None}
    except urllib.error.HTTPError as exc:
        try:
            exc.close()
        except Exception:
            pass
        return {"status": None, "bytes": 0, "body": b"", "error": "request rejected or unavailable"}
    except Exception:
        return {"status": None, "bytes": 0, "body": b"", "error": "request rejected or unavailable"}


def describe(result):
    if result["error"]:
        return "request rejected or unavailable"
    return f"HTTP {result['status']} · {result['bytes']} bytes"


def probe_source(src, cfg, opener):
    timeout = cfg.get("http_timeout_seconds", 15)
    pair, tf = cfg["pair"], cfg["timeframe"]
    lines = [f"## {src.name}", f"Provider ID: {src.provider_id}", ""]

    time_result = probe_get(src.time_url(), timeout, opener)
    lines += [f"**Server time** — {describe(time_result)}"]
    if time_result["status"] == 200:
        try:
            ts = fetcher.extract_server_time(json.loads(time_result["body"].decode("utf-8")))
            lines.append(f"Parsed server time: {datetime.fromtimestamp(ts, tz=timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
        except (ValueError, fetcher.ApiError, UnicodeDecodeError):
            lines.append("Server-time payload did not pass the parser.")
    lines.append("")

    import urllib.parse
    query = urllib.parse.urlencode({"symbol": src.symbol(pair), "interval": tf, "limit": 3})
    url = f"{src.klines_url()}?{query}"
    candle_result = probe_get(url, timeout, opener)
    lines += [f"**Latest candles** — {describe(candle_result)}"]
    if candle_result["status"] == 200:
        try:
            rows = fetcher.parse_klines(json.loads(candle_result["body"].decode("utf-8")))
            lines.append(f"Parsed {len(rows)} candle(s); payload values are not printed.")
        except (ValueError, fetcher.ApiError, UnicodeDecodeError):
            lines.append("Candle payload did not pass the parser.")
    lines.append("")
    return lines


def run_probe(cfg, out_dir="out", opener=fetcher.default_opener):
    assert_read_only(cfg)
    os.makedirs(out_dir, exist_ok=True)
    lines = [f"# Endpoint probe: {cfg['pair']} on {cfg['exchange']}",
             f"Run at {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S UTC} · READ-ONLY", ""]
    for source_cfg in cfg["sources"]:
        lines += probe_source(fetcher.Source(**source_cfg), cfg, opener)
    text = "\n".join(lines) + "\n"
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
