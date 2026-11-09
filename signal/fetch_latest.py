"""signal/fetch_latest.py - ONE manual, read-only fetch of recent BTC/USDT daily candles.

Source (the only network call in this module):
    GET https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=40
Binance public spot market data. No API key, no account, no order. A PROXY for research:
these are NOT Tokocrypto execution prices.

Rules:
  * Exactly one request per run. No retries, no pagination, no fallback to older data.
  * Only completed candles are kept. A candle is complete when open + 1 day <= fetch time.
  * The new snapshot is cross-checked against committed history (overlap must match exactly).
  * Any failed check stops the run and writes NOTHING.
  * Snapshots are written with exclusive creation and are never overwritten.

Stdlib only. Not for workflows. Run manually:
    python3 signal/fetch_latest.py --history-manifest <path to committed manifest>
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetcher
import transport_policy
import btc_signal as bs

HOST = transport_policy.provider_base_url("binance-vision")
PATH = "/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1d"
STEP = bs.STEP
DEFAULT_LIMIT = 40
MAX_LIMIT = 1000
TIMEOUT_SECONDS = 20
MIN_OVERLAP = 20
MAX_DAILY_MOVE = 0.25
USER_AGENT = "btcidr-signal-fetch/1 (manual, read-only)"
DATASET_NAME = "binance-vision_BTCUSDT_1d"
PROXY_WARNING = ("Prices come from Binance-Vision public spot market data (BTCUSDT). They are a "
                 "PROXY for research and are NOT Tokocrypto execution prices.")
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class FetchError(Exception):
    """The fetch or a check failed. Nothing is written."""


def build_url(limit=DEFAULT_LIMIT):
    if not 1 <= limit <= MAX_LIMIT:
        raise FetchError(f"limit must be between 1 and {MAX_LIMIT}")
    query = urllib.parse.urlencode({"symbol": SYMBOL, "interval": INTERVAL, "limit": limit})
    return f"{HOST}{PATH}?{query}"


def fetch_body(url, opener=None):
    """One approved public GET. Uses shared proxy-free, no-redirect bounded transport."""
    try:
        limit = transport_policy.validate_request(url, "GET")
        if opener is None:
            status, body = fetcher.default_opener(url, TIMEOUT_SECONDS)
        else:
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": USER_AGENT,
                                                  "Accept": "application/json"})
            with opener(req, timeout=TIMEOUT_SECONDS) as resp:
                status = getattr(resp, "status", 200)
                body = transport_policy.read_bounded(resp, limit, TIMEOUT_SECONDS)
        if status != 200 or not isinstance(body, (bytes, bytearray)) or len(body) > limit:
            raise FetchError("request rejected or unavailable; nothing written")
        return bytes(body)
    except (fetcher.ApiError, transport_policy.PolicyError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise FetchError("request rejected or unavailable; nothing written")


def parse_klines(body, fetch_s):
    """Validates the raw kline rows and returns only the COMPLETED candles, oldest first."""
    try:
        rows = json.loads(body)
    except (ValueError, TypeError):
        raise FetchError("response is not valid JSON")
    if not isinstance(rows, list) or not rows:
        raise FetchError("response is not a non-empty list of candles")
    parsed = []
    for n, r in enumerate(rows):
        if not isinstance(r, list) or len(r) < 12:
            raise FetchError(f"row {n} is malformed")
        try:
            open_ms = int(r[0])
            close_ms = int(r[6])
            o, h, lo, c, v = (float(x) for x in r[1:6])
        except (TypeError, ValueError):
            raise FetchError(f"row {n} has a non-numeric field")
        if open_ms % (STEP * 1000) != 0:
            raise FetchError(f"row {n} is not on a UTC daily boundary")
        if close_ms != open_ms + STEP * 1000 - 1:
            raise FetchError(f"row {n} has an unexpected close time")
        if not all(math.isfinite(x) for x in (o, h, lo, c, v)):
            raise FetchError(f"row {n} has a non-finite value")
        if min(o, h, lo, c) <= 0 or v < 0 or h < lo or h < max(o, c) or lo > min(o, c):
            raise FetchError(f"row {n} has impossible OHLC or volume")
        parsed.append(bs.Candle(open_ms // 1000, o, h, lo, c, v))
    for a, b in zip(parsed, parsed[1:]):
        if b.time - a.time != STEP:
            raise FetchError("candles are not strictly consecutive daily (gap, duplicate or "
                             "unsorted)")
    forming = [c for c in parsed if c.time + STEP > fetch_s]
    if len(forming) > 1 or (forming and forming[0] is not parsed[-1]):
        raise FetchError("more than the last candle is still forming: refusing")
    completed = [c for c in parsed if c.time + STEP <= fetch_s]
    if not completed:
        raise FetchError("no completed candle in the response")
    return completed, len(parsed) - len(completed)


def check_history_overlap(new, history):
    """Every committed candle that the new fetch covers must match it exactly."""
    if not history:
        raise FetchError("history is empty")
    hist_last = history[-1].time
    if new[-1].time < hist_last:
        raise FetchError("new fetch does not reach the end of committed history: refusing")
    by_time = {c.time: c for c in new}
    compared = 0
    for h in history:
        if h.time < new[0].time:
            continue
        n = by_time.get(h.time)
        if n is None:
            raise FetchError(f"committed candle {bs.utc_text(h.time)} is missing from the fetch")
        if (n.open, n.high, n.low, n.close, n.volume) != (h.open, h.high, h.low, h.close, h.volume):
            raise FetchError(f"candle {bs.utc_text(h.time)} differs from committed history")
        compared += 1
    if compared < MIN_OVERLAP:
        raise FetchError(f"only {compared} overlapping candles; at least {MIN_OVERLAP} required")
    return compared


def price_spike_entries(candles):
    worst = 0.0
    count = 0
    for a, b in zip(candles, candles[1:]):
        move = abs(b.close / a.close - 1.0)
        worst = max(worst, move)
        if move > MAX_DAILY_MOVE:
            count += 1
    if count:
        return {"name": "validator_price_spikes", "status": "WARN",
                "detail": f"{count} close-to-close move(s) larger than 25%"}
    return {"name": "validator_price_spikes", "status": "PASS",
            "detail": f"largest close-to-close move {worst * 100:.2f}%"}


def csv_bytes(candles):
    lines = [",".join(bs.COLUMNS)]
    for c in candles:
        lines.append(",".join(["binance-vision", SYMBOL, INTERVAL, str(c.time),
                               bs.utc_text(c.time), repr(c.open), repr(c.high), repr(c.low),
                               repr(c.close), repr(c.volume)]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_snapshot(body, fetch_s, history_manifest_path, opener_url):
    """Pure function: validates everything and returns (csv_bytes, manifest_dict)."""
    completed, forming_excluded = parse_klines(body, fetch_s)
    now_age = fetch_s - (completed[-1].time + STEP)
    if now_age > bs.MAX_AGE_SECONDS:
        raise FetchError("newest completed candle is already older than 48 hours: refusing")
    hist_m, hist = bs.load_verified(history_manifest_path)
    compared = check_history_overlap(completed, hist)
    spike = price_spike_entries(completed)
    data = csv_bytes(completed)
    digest = hashlib.sha256(data).hexdigest()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(fetch_s))
    version = f"v{stamp}_{digest[:8]}"
    checks = [
        {"name": "request_scope", "status": "PASS",
         "detail": f"one GET to {HOST}{PATH} for {SYMBOL} {INTERVAL}"},
        {"name": "completed_only", "status": "PASS",
         "detail": f"{forming_excluded} forming candle(s) excluded; {len(completed)} completed kept"},
        {"name": "utc_daily_grid", "status": "PASS", "detail": "all candles on UTC day boundaries"},
        {"name": "ordering_gaps_duplicates", "status": "PASS",
         "detail": "strictly consecutive, no gaps or duplicates"},
        {"name": "ohlc_sanity", "status": "PASS", "detail": "high/low/open/close consistent, positive"},
        {"name": "history_overlap", "status": "PASS",
         "detail": f"{compared} overlapping committed candles match exactly "
                   f"(history {hist_m['version_id']})"},
        {"name": "freshness", "status": "PASS",
         "detail": f"newest completed candle closed {now_age / 3600:.2f} h before fetch"},
        spike,
    ]
    manifest = {
        "schema_version": 1,
        "dataset_name": DATASET_NAME,
        "version_id": version,
        "fetched_utc": bs.utc_text(fetch_s) + " UTC",
        "market": dict(bs.EXPECTED_MARKET),
        "price_basis_warning": PROXY_WARNING,
        "candle_convention": "open_time_unix is the candle OPEN time in UTC seconds; only "
                             "completed candles are stored.",
        "source": {"host": HOST, "path": PATH, "request_url": opener_url,
                   "note": "public market data; no key; proxy prices"},
        "csv_file": version + ".csv",
        "csv_sha256": digest,
        "row_count": len(completed),
        "first_open_unix": completed[0].time,
        "last_open_unix": completed[-1].time,
        "first_open_utc": bs.utc_text(completed[0].time) + " UTC",
        "last_open_utc": bs.utc_text(completed[-1].time) + " UTC",
        "timeframe_seconds": STEP,
        "forming_excluded": forming_excluded,
        "history_check": {"history_version": hist_m["version_id"], "compared": compared},
        "gate_checks": checks,
    }
    return data, manifest


def write_snapshot(out_dir, data, manifest):
    """Exclusive creation only. Refuses to overwrite. Returns the manifest path."""
    folder = os.path.join(out_dir, DATASET_NAME)
    os.makedirs(folder, exist_ok=True)
    csv_path = os.path.join(folder, manifest["csv_file"])
    man_path = os.path.join(folder, manifest["version_id"] + ".manifest.json")
    for p in (csv_path, man_path):
        if os.path.exists(p):
            raise FetchError(f"{os.path.basename(p)} already exists; snapshots are never overwritten")
    with open(csv_path, "xb") as f:
        f.write(data)
    with open(man_path, "x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return man_path


def main(argv=None, opener=None, now=None):
    p = argparse.ArgumentParser(description="ONE manual, read-only BTCUSDT daily fetch.")
    p.add_argument("--history-manifest", required=True,
                   help="committed history manifest to cross-check against")
    p.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = p.parse_args(argv)
    try:
        url = build_url(args.limit)
        fetch_s = int(time.time() if now is None else now)
        body = fetch_body(url, opener=opener)
        data, manifest = build_snapshot(body, fetch_s, args.history_manifest, url)
        man_path = write_snapshot(args.out_dir, data, manifest)
        bs.load_verified(man_path)                     # the loader must accept what was written
    except (FetchError, bs.SignalError) as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": man_path, "version_id": manifest["version_id"],
                      "csv_sha256": manifest["csv_sha256"], "row_count": manifest["row_count"],
                      "first_open_utc": manifest["first_open_utc"],
                      "last_open_utc": manifest["last_open_utc"],
                      "fetched_utc": manifest["fetched_utc"],
                      "forming_excluded": manifest["forming_excluded"],
                      "history_check": manifest["history_check"],
                      "gate_checks": manifest["gate_checks"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
