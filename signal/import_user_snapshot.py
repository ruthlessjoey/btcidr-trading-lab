"""signal/import_user_snapshot.py - build ONE provisional, USER-SUPPLIED snapshot offline.

Combines:
  * the committed historical BTCUSDT daily rows (provenance: committed research-data object), and
  * the completed candles from a user-supplied Binance kline JSON response (provenance: user-stated).

Labelled USER-SUPPLIED / PROVISIONAL. Nothing here authenticates the source: the script makes no
network request, and the download time is supplied by the user. The independent pin added later
establishes SNAPSHOT INTEGRITY only, not source authenticity.

The user file is validated by the same functions as fetch_latest.py (structure, completed-only,
ordering, OHLC, overlap). Any failed check stops the run and writes nothing. Stdlib only.

Run manually:
    python3 signal/import_user_snapshot.py --user-json <file> --history-csv <csv> \
        --history-manifest <manifest> --download-utc "2026-11-01 08:45:00"
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import btc_signal as bs
import fetch_latest as fl

PROVENANCE_LABEL = "USER-SUPPLIED / PROVISIONAL"
AUTHENTICITY = ("NOT AUTHENTICATED. No request was made by this script. The download time and "
                "the origin of the user file are user-stated only.")
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


class ImportError_(Exception):
    """The import failed a check. Nothing is written."""


def parse_download_utc(text):
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ImportError_("download time must look like 'YYYY-MM-DD HH:MM:SS' in UTC")
    return int(dt.timestamp())


def _row(c):
    return ",".join(["binance-vision", fl.SYMBOL, fl.INTERVAL, str(c.time), bs.utc_text(c.time),
                     repr(c.open), repr(c.high), repr(c.low), repr(c.close), repr(c.volume)])


def build_combined(user_body, history_csv_bytes, history_manifest_path, fetch_s):
    """Pure function. Returns (csv_bytes, manifest, raw_sha256)."""
    hist_m, hist = bs.load_verified(history_manifest_path)
    try:
        completed, forming = fl.parse_klines(user_body, fetch_s)
    except fl.FetchError as e:
        raise ImportError_(str(e))
    age = fetch_s - (completed[-1].time + bs.STEP)
    if age > bs.MAX_AGE_SECONDS:
        raise ImportError_("newest completed candle is older than 48 hours at download time: refusing")
    try:
        compared = fl.check_history_overlap(completed, hist)
    except fl.FetchError as e:
        raise ImportError_(str(e))
    tail = [c for c in completed if c.time > hist[-1].time]
    if not tail:
        raise ImportError_("the user file adds no completed candle after committed history")

    # The historical rows keep their committed bytes exactly; new rows are appended.
    hist_lines = history_csv_bytes.decode("utf-8").rstrip("\n").split("\n")
    combined = ("\n".join(hist_lines) + "\n" + "".join(_row(c) + "\n" for c in tail)).encode("utf-8")

    all_candles = hist + tail
    parsed = bs.parse_csv_bytes(combined, bs.EXPECTED_MARKET)
    if parsed != all_candles:
        raise ImportError_("combined CSV does not reproduce the verified candles exactly")
    digest = hashlib.sha256(combined).hexdigest()
    stamp = datetime.fromtimestamp(fetch_s, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    version = f"v{stamp}_{digest[:8]}"
    raw_sha = hashlib.sha256(user_body).hexdigest()
    checks = [
        {"name": "user_file_scope", "status": "PASS",
         "detail": f"{len(completed) + forming} candles in user file; {forming} forming excluded; "
                   f"{len(tail)} completed candles added after committed history"},
        {"name": "completed_only", "status": "PASS",
         "detail": f"{forming} forming candle(s) excluded"},
        {"name": "utc_daily_grid", "status": "PASS", "detail": "all candles on UTC day boundaries"},
        {"name": "ordering_gaps_duplicates", "status": "PASS",
         "detail": "combined series strictly consecutive daily, no gaps or duplicates"},
        {"name": "ohlc_sanity", "status": "PASS", "detail": "high/low/open/close consistent, positive"},
        {"name": "history_overlap", "status": "PASS",
         "detail": f"{compared} overlapping committed candles match the user file exactly"},
        {"name": "freshness", "status": "PASS",
         "detail": f"newest completed candle closed {age / 3600:.2f} h before the stated download time"},
        fl.price_spike_entries(all_candles),
    ]
    manifest = {
        "schema_version": 1,
        "dataset_name": fl.DATASET_NAME,
        "version_id": version,
        "fetched_utc": bs.utc_text(fetch_s) + " UTC",
        "market": dict(bs.EXPECTED_MARKET),
        "price_basis_warning": fl.PROXY_WARNING,
        "candle_convention": "open_time_unix is the candle OPEN time in UTC seconds; only "
                             "completed candles are stored.",
        "csv_file": version + ".csv",
        "csv_sha256": digest,
        "row_count": len(all_candles),
        "first_open_unix": all_candles[0].time,
        "last_open_unix": all_candles[-1].time,
        "first_open_utc": bs.utc_text(all_candles[0].time) + " UTC",
        "last_open_utc": bs.utc_text(all_candles[-1].time) + " UTC",
        "timeframe_seconds": bs.STEP,
        "provenance": {
            "label": PROVENANCE_LABEL,
            "authenticity": AUTHENTICITY,
            "download_utc_user_stated": bs.utc_text(fetch_s) + " UTC",
            "historical_rows": {
                "rows": len(hist),
                "first_open_utc": bs.utc_text(hist[0].time) + " UTC",
                "last_open_utc": bs.utc_text(hist[-1].time) + " UTC",
                "source": f"committed research-data object {hist_m['version_id']} "
                          "(repository pipeline output; no independent pin)",
                "source_manifest_sha256": hashlib.sha256(
                    open(history_manifest_path, "rb").read()).hexdigest(),
                "source_csv_sha256": hist_m["csv_sha256"],
            },
            "user_supplied_rows": {
                "rows": len(tail),
                "first_open_utc": bs.utc_text(tail[0].time) + " UTC",
                "last_open_utc": bs.utc_text(tail[-1].time) + " UTC",
                "source": "user-supplied Binance kline JSON (40 candles, public spot endpoint "
                          "as stated by the user)",
                "raw_sha256": raw_sha,
                "raw_file": version + ".raw-user-supplied.json",
            },
            "overlap_checked_against_user_file": compared,
        },
        "gate_checks": checks,
    }
    return combined, manifest, raw_sha


def main(argv=None, out_dir=DEFAULT_OUT_DIR):
    p = argparse.ArgumentParser(description="Build ONE provisional USER-SUPPLIED snapshot (offline).")
    p.add_argument("--user-json", required=True)
    p.add_argument("--history-csv", required=True)
    p.add_argument("--history-manifest", required=True)
    p.add_argument("--download-utc", required=True, help="'YYYY-MM-DD HH:MM:SS' in UTC, user-stated")
    args = p.parse_args(argv)
    try:
        fetch_s = parse_download_utc(args.download_utc)
        with open(args.user_json, "rb") as f:
            user_body = f.read()
        with open(args.history_csv, "rb") as f:
            history_csv = f.read()
        combined, manifest, raw_sha = build_combined(user_body, history_csv,
                                                     args.history_manifest, fetch_s)
        folder = os.path.join(out_dir, fl.DATASET_NAME)
        os.makedirs(folder, exist_ok=True)
        base = manifest["version_id"]
        paths = {"csv": os.path.join(folder, base + ".csv"),
                 "manifest": os.path.join(folder, base + ".manifest.json"),
                 "raw": os.path.join(folder, base + ".raw-user-supplied.json")}
        for pth in paths.values():
            if os.path.exists(pth):
                raise ImportError_(f"{os.path.basename(pth)} already exists; never overwritten")
        with open(paths["csv"], "xb") as f:
            f.write(combined)
        with open(paths["raw"], "xb") as f:
            f.write(user_body)
        with open(paths["manifest"], "x", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        bs.load_verified(paths["manifest"])                # the loader must accept what was written
    except (ImportError_, fl.FetchError, bs.SignalError, OSError) as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"manifest": paths["manifest"], "version_id": base,
                      "csv_sha256": manifest["csv_sha256"], "row_count": manifest["row_count"],
                      "raw_sha256": raw_sha, "label": PROVENANCE_LABEL}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
