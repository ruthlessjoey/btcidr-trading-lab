"""research/dataset.py - versioned, hash-checked candle datasets for research.

A dataset version is two files that are never overwritten:
  <name>/v<fetch time>_<hash8>.csv            the candles
  <name>/v<fetch time>_<hash8>.manifest.json  who/what/when, plus the CSV's sha256
The loader refuses a dataset whose hash, market identity, ordering or spacing
does not check out, so later code can never silently use the wrong market.
"""
import csv
import hashlib
import json
import math
import os
from datetime import datetime, timezone

import validator
from fetcher import Candle, TF_SECONDS

CSV_COLUMNS = ["provider", "symbol", "timeframe", "open_time_unix", "open_time_utc",
               "open", "high", "low", "close", "volume"]
PRICE_BASIS_WARNING = ("Prices come from the exchange named in 'market'. They are a PROXY for "
                       "research and are NOT Tokocrypto execution prices.")
CANDLE_CONVENTION = ("open_time_unix is the candle OPEN time in UTC seconds. A candle is complete "
                     "only at open_time + timeframe; only completed candles are stored.")


class DatasetError(Exception):
    """The dataset is missing, altered, or is not the market that was asked for."""


def utc_text(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def dataset_name(market):
    return f"{market['provider']}_{market['symbol']}_{market['timeframe']}"


def write_version(root_dir, market, candles, fetched_utc_ts, extra=None):
    """Writes a NEW version. Raises if that version already exists. Returns (csv, manifest) paths."""
    if not candles:
        raise DatasetError("refusing to write an empty dataset")
    folder = os.path.join(root_dir, dataset_name(market))
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.fromtimestamp(fetched_utc_ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp = os.path.join(folder, f".tmp_{stamp}.csv")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_COLUMNS)
        for c in candles:
            w.writerow([market["provider"], market["symbol"], market["timeframe"], c.time,
                        utc_text(c.time), repr(c.open), repr(c.high), repr(c.low),
                        repr(c.close), repr(c.volume)])
    digest = sha256_file(tmp)
    version = f"v{stamp}_{digest[:8]}"
    csv_path = os.path.join(folder, version + ".csv")
    man_path = os.path.join(folder, version + ".manifest.json")
    if os.path.exists(csv_path) or os.path.exists(man_path):
        os.remove(tmp)
        raise DatasetError(f"version {version} already exists; versions are never overwritten")
    os.rename(tmp, csv_path)
    manifest = {"schema_version": 1, "dataset_name": dataset_name(market), "version_id": version,
                "fetched_utc": utc_text(fetched_utc_ts) + " UTC", "market": market,
                "price_basis_warning": PRICE_BASIS_WARNING, "candle_convention": CANDLE_CONVENTION,
                "csv_file": os.path.basename(csv_path), "csv_sha256": digest,
                "row_count": len(candles), "first_open_utc": utc_text(candles[0].time) + " UTC",
                "last_open_utc": utc_text(candles[-1].time) + " UTC",
                "first_open_unix": candles[0].time, "last_open_unix": candles[-1].time,
                "timeframe_seconds": TF_SECONDS[market["timeframe"]]}
    manifest.update(extra or {})
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return csv_path, man_path


def load_verified(manifest_path, expect=None):
    """Loads a dataset and re-checks everything. `expect` may hold provider, symbol,
    quote_asset, timeframe; any mismatch is an error. Returns (manifest, candles)."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError) as e:
        raise DatasetError(f"cannot read manifest {manifest_path}: {e}")
    for key in ("market", "csv_file", "csv_sha256", "row_count", "first_open_unix",
                "last_open_unix", "timeframe_seconds"):
        if key not in m:
            raise DatasetError(f"manifest lacks {key!r}")
    mk = m["market"]
    for key, want in (expect or {}).items():
        if mk.get(key) != want:
            raise DatasetError(f"market mismatch: dataset has {key}={mk.get(key)!r}, "
                               f"but {want!r} was requested. Markets are never mixed.")
    csv_path = os.path.join(os.path.dirname(manifest_path), m["csv_file"])
    if not os.path.exists(csv_path):
        raise DatasetError(f"CSV file {m['csv_file']} is missing")
    if sha256_file(csv_path) != m["csv_sha256"]:
        raise DatasetError("CSV hash does not match the manifest: the file was changed")
    step = m["timeframe_seconds"]
    out = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        if next(reader, None) != CSV_COLUMNS:
            raise DatasetError("CSV header is not the expected schema")
        for n, row in enumerate(reader, start=2):
            if len(row) != len(CSV_COLUMNS):
                raise DatasetError(f"line {n}: wrong number of columns")
            if (row[0], row[1], row[2]) != (mk["provider"], mk["symbol"], mk["timeframe"]):
                raise DatasetError(f"line {n}: row belongs to {row[:3]}, not to the manifest market")
            try:
                t = int(row[3])
                c = Candle(t, *[float(x) for x in row[5:10]])
            except ValueError:
                raise DatasetError(f"line {n}: non-numeric value")
            if row[4] != utc_text(t):
                raise DatasetError(f"line {n}: open_time_utc does not match open_time_unix")
            if not all(math.isfinite(x) for x in (c.open, c.high, c.low, c.close, c.volume)) \
                    or validator.bad_ohlc(c) or c.volume < 0:
                raise DatasetError(f"line {n}: impossible price or volume")
            if out and t - out[-1].time != step:
                raise DatasetError(f"line {n}: candles are not strictly consecutive "
                                   f"(step {t - out[-1].time}s, expected {step}s): "
                                   "unsorted, duplicated or missing data")
            out.append(c)
    if len(out) != m["row_count"]:
        raise DatasetError(f"row count {len(out)} differs from manifest {m['row_count']}")
    if out[0].time != m["first_open_unix"] or out[-1].time != m["last_open_unix"]:
        raise DatasetError("first/last candle differ from the manifest")
    return m, out


def latest_manifest(root_dir, name):
    folder = os.path.join(root_dir, name)
    if not os.path.isdir(folder):
        return None
    found = sorted(f for f in os.listdir(folder) if f.endswith(".manifest.json"))
    return os.path.join(folder, found[-1]) if found else None


def compare_versions(old, new):
    """How a new fetch differs from an older version, over the candles they share."""
    o, n = {c.time: c for c in old}, {c.time: c for c in new}
    common = sorted(set(o) & set(n))
    changed = [t for t in common if o[t] != n[t]]
    return {"old_rows": len(old), "new_rows": len(new), "common": len(common),
            "changed": len(changed), "changed_first": [utc_text(t) for t in changed[:5]],
            "only_in_old": len(set(o) - set(n)), "added_in_new": len(set(n) - set(o))}
