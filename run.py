"""run.py - fetch BTC/USDT candles from Tokocrypto, validate them, write a report.

READ-ONLY.  Usage:  python3 run.py
Writes: out/candles.csv, out/report.md, out/report.json
Exit code 0 = data passed (or has warnings). Exit code 1 = failed.
"""
import csv
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

import fetcher
import report
import validator


def load_config(path="config.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assert_read_only(cfg):
    """Safety guard: this milestone refuses to run in any other mode."""
    if cfg.get("mode") != "read_only":
        raise SystemExit("Refusing to run: Milestone 1 only supports mode 'read_only'.")


def run_pipeline(cfg, out_dir="out", opener=fetcher.default_opener,
                 sleep=time.sleep, local_now=None):
    assert_read_only(cfg)
    tf = cfg["timeframe"]
    if tf not in fetcher.TF_SECONDS:
        raise SystemExit(f"Unknown timeframe {tf!r}. Allowed: {', '.join(fetcher.TF_SECONDS)}")
    os.makedirs(out_dir, exist_ok=True)
    tf_sec = fetcher.TF_SECONDS[tf]
    local_now = time.time() if local_now is None else local_now
    timeout = cfg.get("http_timeout_seconds", 15)
    retries = cfg.get("http_retries", 3)

    result = {"generated_utc": datetime.fromtimestamp(local_now, tz=timezone.utc)
              .strftime("%Y-%m-%d %H:%M:%S UTC"),
              "pair": cfg["pair"], "timeframe": tf, "mode": cfg["mode"],
              "lookback_days": cfg["lookback_days"], "api_error": None,
              "requests_made": 0, "checks": [], "stats": {}, "attempts": [],
              "source": None, "source_url": None}

    chosen = None
    for source_cfg in cfg["sources"]:
        src = fetcher.Source(**source_cfg)
        try:
            server_now = fetcher.fetch_server_time(src, timeout, retries, opener, sleep)
            start_s = server_now - cfg["lookback_days"] * 86400
            raw, n_req = fetcher.fetch_candles(src, cfg["pair"], tf, start_s, server_now,
                                               timeout, retries, opener, sleep)
            if not raw:
                raise fetcher.ApiError("answered, but returned zero candles")
        except fetcher.ApiError as e:
            result["attempts"].append({"source": src.name, "ok": False, "detail": str(e)})
            continue
        result["attempts"].append({"source": src.name, "ok": True,
                                   "detail": f"{len(raw)} candles in {n_req} request(s)"})
        chosen = (src, server_now, start_s, raw, n_req)
        break

    candles = []
    if chosen is None:
        result["status"] = "API ERROR"
        result["api_error"] = "all sources failed"
    else:
        src, server_now, start_s, raw, n_req = chosen
        v = validator.validate(raw, tf_sec, server_now, local_now, start_s, server_now, cfg)
        candles = v.clean
        result.update(status=v.status, stats=v.stats, requests_made=n_req,
                      source=src.name, source_url=src.base_url,
                      checks=[asdict(c) for c in v.checks])
        with open(os.path.join(out_dir, "candles.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["time_unix", "time_utc", "open", "high", "low", "close", "volume"])
            for c in candles:
                w.writerow([c.time, datetime.fromtimestamp(c.time, tz=timezone.utc)
                            .strftime("%Y-%m-%d %H:%M"), c.open, c.high, c.low, c.close, c.volume])

    text = report.build_markdown(result, candles)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0 if result["status"] in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(run_pipeline(load_config()))
