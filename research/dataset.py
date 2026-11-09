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
import tempfile
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
    """Atomically publish a new CSV/manifest pair without overwriting existing files.

    The manifest is the discoverability marker and is created only after the CSV
    has been completely written and hashed. Any failed attempt removes only files
    that this invocation successfully created.
    """
    if not isinstance(market, dict):
        raise DatasetError("market must be an object")
    for key in ("provider", "symbol", "timeframe"):
        if not isinstance(market.get(key), str) or not market[key].strip():
            raise DatasetError(f"market {key} must be a non-empty string")
    if market["timeframe"] not in TF_SECONDS:
        raise DatasetError("market timeframe is unsupported")
    if not candles:
        raise DatasetError("refusing to write an empty dataset")
    if type(fetched_utc_ts) is not int or fetched_utc_ts < 0:
        raise DatasetError("fetch timestamp must be a non-negative integer")
    if extra is not None and not isinstance(extra, dict):
        raise DatasetError("extra manifest metadata must be an object")

    reserved = {
        "schema_version", "dataset_name", "version_id", "fetched_utc", "market",
        "price_basis_warning", "candle_convention", "csv_file", "csv_sha256",
        "row_count", "first_open_utc", "last_open_utc", "first_open_unix",
        "last_open_unix", "timeframe_seconds",
    }
    if extra and reserved.intersection(extra):
        raise DatasetError("extra metadata cannot override reserved manifest fields")

    name = dataset_name(market)
    folder = os.path.join(root_dir, name)
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.fromtimestamp(fetched_utc_ts, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fd, tmp = tempfile.mkstemp(prefix=f".tmp_{stamp}_", suffix=".csv", dir=folder)
    csv_path = man_path = None
    csv_created = manifest_created = False
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(CSV_COLUMNS)
            for c in candles:
                w.writerow([market["provider"], market["symbol"], market["timeframe"], c.time,
                            utc_text(c.time), repr(c.open), repr(c.high), repr(c.low),
                            repr(c.close), repr(c.volume)])
            f.flush()
            os.fsync(f.fileno())

        digest = sha256_file(tmp)
        version = f"v{stamp}_{digest[:8]}"
        csv_path = os.path.join(folder, version + ".csv")
        man_path = os.path.join(folder, version + ".manifest.json")

        # A hard link is an atomic create-if-absent operation on this same
        # filesystem. Unlike os.rename(), it cannot silently replace a file
        # created by another process after an existence check.
        try:
            os.link(tmp, csv_path)
        except FileExistsError:
            raise DatasetError(f"version {version} already exists; versions are never overwritten")
        csv_created = True
        os.unlink(tmp)
        tmp = None

        manifest = {
            "schema_version": 1, "dataset_name": name, "version_id": version,
            "fetched_utc": utc_text(fetched_utc_ts) + " UTC", "market": market,
            "price_basis_warning": PRICE_BASIS_WARNING, "candle_convention": CANDLE_CONVENTION,
            "csv_file": os.path.basename(csv_path), "csv_sha256": digest,
            "row_count": len(candles), "first_open_utc": utc_text(candles[0].time) + " UTC",
            "last_open_utc": utc_text(candles[-1].time) + " UTC",
            "first_open_unix": candles[0].time, "last_open_unix": candles[-1].time,
            "timeframe_seconds": TF_SECONDS[market["timeframe"]],
        }
        manifest.update(extra or {})

        # Exclusive creation prevents replacing an existing manifest. Mark
        # ownership immediately after open so even a partial write is cleaned.
        with open(man_path, "x", encoding="utf-8") as f:
            manifest_created = True
            json.dump(manifest, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        return csv_path, man_path
    except BaseException:
        cleanup_errors = []
        for path, owned in ((man_path, manifest_created), (csv_path, csv_created)):
            if owned and path is not None:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                except OSError as cleanup_error:
                    cleanup_errors.append(type(cleanup_error).__name__)
        if cleanup_errors:
            raise DatasetError("publication failed and owned-file cleanup was incomplete: "
                               + ", ".join(cleanup_errors))
        raise
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass




def load_verified(manifest_path, expect=None):
    """Loads a dataset and re-checks everything. `expect` may hold provider, symbol,
    quote_asset, timeframe; any mismatch is an error. Returns (manifest, candles)."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError) as e:
        raise DatasetError(f"cannot read manifest {manifest_path}: {e}")
    if not isinstance(m, dict):
        raise DatasetError("manifest must be a JSON object")
    for key in ("market", "csv_file", "csv_sha256", "row_count", "first_open_unix",
                "last_open_unix", "timeframe_seconds"):
        if key not in m:
            raise DatasetError(f"manifest lacks {key!r}")
    mk = m["market"]
    if not isinstance(mk, dict):
        raise DatasetError("manifest market must be a JSON object")
    for key in ("provider", "symbol", "timeframe"):
        if not isinstance(mk.get(key), str) or not mk[key].strip():
            raise DatasetError(f"manifest market {key} must be a non-empty string")
    if mk["timeframe"] not in TF_SECONDS:
        raise DatasetError("manifest market timeframe is unsupported")
    for key in ("first_open_unix", "last_open_unix"):
        if type(m[key]) is not int or m[key] < 0:
            raise DatasetError(f"manifest {key} must be a non-negative integer")
    if m["last_open_unix"] < m["first_open_unix"]:
        raise DatasetError("manifest last_open_unix precedes first_open_unix")
    csv_file = m["csv_file"]
    if (not isinstance(csv_file, str) or not csv_file or csv_file in (".", "..")
            or "/" in csv_file or "\\" in csv_file or "\x00" in csv_file
            or os.path.basename(csv_file) != csv_file):
        raise DatasetError("manifest CSV filename must be a plain file name inside its dataset folder")
    if (not isinstance(m["csv_sha256"], str) or len(m["csv_sha256"]) != 64
            or any(ch not in "0123456789abcdef" for ch in m["csv_sha256"])):
        raise DatasetError("manifest CSV SHA-256 is malformed")
    if type(m["row_count"]) is not int or m["row_count"] < 1:
        raise DatasetError("manifest row_count must be a positive integer")
    if type(m["timeframe_seconds"]) is not int or m["timeframe_seconds"] <= 0:
        raise DatasetError("manifest timeframe_seconds must be a positive integer")
    if m["timeframe_seconds"] != TF_SECONDS[mk["timeframe"]]:
        raise DatasetError("manifest timeframe does not match its timeframe_seconds")
    expected_rows = ((m["last_open_unix"] - m["first_open_unix"])
                     // m["timeframe_seconds"]) + 1
    if ((m["last_open_unix"] - m["first_open_unix"]) % m["timeframe_seconds"]
            or expected_rows != m["row_count"]):
        raise DatasetError("manifest timestamp range does not match row_count and timeframe")
    for key, want in (expect or {}).items():
        if mk.get(key) != want:
            raise DatasetError(f"market mismatch: dataset has {key}={mk.get(key)!r}, "
                               f"but {want!r} was requested. Markets are never mixed.")
    folder = os.path.realpath(os.path.dirname(manifest_path))
    csv_path = os.path.join(folder, csv_file)
    if os.path.islink(csv_path) or os.path.commonpath((folder, os.path.realpath(csv_path))) != folder:
        raise DatasetError("manifest CSV path must remain inside the dataset folder and must not be a symlink")
    if not os.path.isfile(csv_path):
        raise DatasetError(f"CSV file {csv_file} is missing")
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
            except (TypeError, ValueError, OverflowError):
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
    if not out:
        raise DatasetError("dataset CSV contains no candle rows")
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
