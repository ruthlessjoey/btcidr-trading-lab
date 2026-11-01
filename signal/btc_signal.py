"""signal/btc_signal.py - local, read-only, standard-library-only BTC daily research candidate.

Produces ONE research candidate (BUY / SELL / WAIT) for the latest completed daily BTC/USDT
candle in a pinned, hash-verified dataset, with the indicator values that produced it.

Research only. This module places no orders, reads no accounts or credentials, makes no network
calls, and writes nothing. A candidate is not a trading instruction, and no model score or
probability of profit is produced.

Rules are fixed in advance and are NOT tuned on any data. They are version-labelled
(RULE_VERSION). Changing a rule means a new version, not an edit in place.

Integrity layers:
  1. The manifest's csv_sha256 must match the CSV bytes.
  2. An independent expected pin (signal/expected_pins.json) must also match the same bytes.
     That pin is a durable trust anchor only after its values are reviewed and committed.
  3. The CSV bytes are read once, hashed, and parsed from the same bytes in memory.
  4. The last candle must be complete at the dataset fetch time (a forming candle is refused).
  5. Dataset validation WARN entries are kept in the output; FAIL entries stop the run.
  6. A report older than MAX_AGE_SECONDS is marked NOT CURRENT and is not a live signal.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone

RULE_VERSION = "btc-rules-v1"
STEP = 86400                       # daily candles, seconds
SMA_FAST = 20
SMA_SLOW = 50
RSI_N = 14
RSI_OVERBOUGHT = 70.0
MAX_AGE_SECONDS = 172800           # 48 h, same limit as the dataset validator's freshness gate
COLUMNS = ["provider", "symbol", "timeframe", "open_time_unix", "open_time_utc",
           "open", "high", "low", "close", "volume"]
EXPECTED_MARKET = {"provider": "binance-vision", "symbol": "BTCUSDT", "base_asset": "BTC",
                   "quote_asset": "USDT", "timeframe": "1d", "market_type": "spot"}
REQUIRED_MANIFEST_KEYS = ("version_id", "market", "dataset_name", "csv_file", "csv_sha256",
                          "row_count", "first_open_unix", "last_open_unix", "timeframe_seconds",
                          "fetched_utc", "gate_checks")
GATE_STATUSES = ("PASS", "WARN", "FAIL")
DEFAULT_PINS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expected_pins.json")
DISCLAIMER = ("RESEARCH ONLY. Not a trading instruction, not financial advice, and not a claim of "
              "profit. No order, account or exchange was used. Every trading decision remains "
              "with a human. SELL means a bearish or exit candidate in BTC spot research, "
              "not a short position.")

Candle = namedtuple("Candle", "time open high low close volume")


class SignalError(Exception):
    """The dataset is missing, altered, incomplete or not the expected market. The run stops."""


def utc_text(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _read_once(path):
    """Reads the file exactly once. Hashing and parsing both use these same bytes (F5)."""
    with open(path, "rb") as f:
        return f.read()


def _parse_fetched(text):
    if not isinstance(text, str):
        raise SignalError("manifest fetched_utc is missing or not text")
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except ValueError:
        raise SignalError(f"manifest fetched_utc is malformed: {text!r}")
    return int(dt.timestamp())


def load_pins(path=DEFAULT_PINS_PATH):
    """Loads the independent expected-hash pins. Refuses a malformed pin file."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise SignalError(f"cannot read independent pin file: {e}")
    pins = doc.get("pins") if isinstance(doc, dict) else None
    if not isinstance(pins, dict):
        raise SignalError("independent pin file has no 'pins' object")
    for name, entries in pins.items():
        if not isinstance(entries, list) or not entries:
            raise SignalError(f"pins for {name!r} must be a non-empty list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise SignalError(f"a pin for {name!r} is malformed")
            digest = entry.get("csv_sha256")
            if not isinstance(digest, str) or len(digest) != 64 or \
                    any(ch not in "0123456789abcdef" for ch in digest):
                raise SignalError(f"a pin for {name!r} has a malformed csv_sha256")
            if not isinstance(entry.get("version_id"), str):
                raise SignalError(f"a pin for {name!r} has no version_id")
    return {"status": doc.get("status", ""), "pins": pins}


def check_independent_pin(digest, manifest, pins):
    name = manifest["dataset_name"]
    entries = pins["pins"].get(name)
    if not entries:
        raise SignalError(f"no independent pin exists for dataset {name!r}")
    matches = [e for e in entries if e["version_id"] == manifest["version_id"]]
    if not matches:
        raise SignalError(f"no independent pin exists for version {manifest['version_id']}")
    if len(matches) > 1:
        raise SignalError(f"duplicate independent pins exist for version {manifest['version_id']}")
    if digest != matches[0]["csv_sha256"]:
        raise SignalError("CSV bytes do not match the INDEPENDENT pin, even if the manifest "
                          "agrees with them")


def dataset_checks(manifest):
    """WARN and FAIL gate entries from the manifest, kept verbatim for the report (F3)."""
    out = []
    for g in manifest["gate_checks"]:
        status = g.get("status")
        if status in ("WARN", "FAIL"):
            out.append({"name": g.get("name"), "status": status, "detail": g.get("detail")})
    return out


def parse_csv_bytes(raw, mk):
    """Parses the given bytes. Returns the candles. Raises SignalError on any defect."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise SignalError("CSV is not valid UTF-8")
    candles = []
    reader = csv.reader(io.StringIO(text, newline=""))
    if next(reader, None) != COLUMNS:
        raise SignalError("CSV header is not the expected schema")
    prev = None
    for n, row in enumerate(reader, start=2):
        if len(row) != len(COLUMNS):
            raise SignalError(f"line {n}: wrong number of columns")
        if row[0:3] != [mk["provider"], mk["symbol"], mk["timeframe"]]:
            raise SignalError(f"line {n}: row is not the manifest market")
        try:
            t = int(row[3])
            o, h, lo, c, v = (float(x) for x in row[5:10])
        except ValueError:
            raise SignalError(f"line {n}: non-numeric value")
        try:
            expected_text = utc_text(t)
        except (OverflowError, OSError, ValueError):
            raise SignalError(f"line {n}: timestamp out of range")
        if row[4] != expected_text:
            raise SignalError(f"line {n}: open_time_utc does not match open_time_unix")
        if t % STEP != 0:
            raise SignalError(f"line {n}: candle is not on a UTC daily boundary")
        if not all(math.isfinite(x) for x in (o, h, lo, c, v)):
            raise SignalError(f"line {n}: non-finite value")
        if min(o, h, lo, c) <= 0 or v < 0 or h < lo or h < max(o, c) or lo > min(o, c):
            raise SignalError(f"line {n}: impossible OHLC or volume")
        if prev is not None and t - prev != STEP:
            raise SignalError(f"line {n}: not consecutive (step {t - prev}s): "
                              "gap, duplicate or unsorted data")
        candles.append(Candle(t, o, h, lo, c, v))
        prev = t
    if not candles:
        raise SignalError("dataset is empty")
    return candles


def load_verified(manifest_path, expect_version=None, pins=None):
    """Loads and fully re-checks one dataset version. Returns (manifest, candles).

    If `pins` (from load_pins) is given, the CSV bytes must also match the independent pin.
    Refuses on any mismatch, gap, duplicate, unsorted row, impossible price, FAIL gate, or a
    last candle that was still forming at the fetch time."""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError) as e:
        raise SignalError(f"cannot read manifest: {e}")
    if not isinstance(m, dict):
        raise SignalError("manifest is not a JSON object")
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in m:
            raise SignalError(f"manifest lacks {key!r}")
    mk = m["market"]
    if not isinstance(mk, dict):
        raise SignalError("manifest market is not an object")
    for key, want in EXPECTED_MARKET.items():
        if mk.get(key) != want:
            raise SignalError(f"not the BTC/USDT daily spot market: market.{key} is "
                              f"{mk.get(key)!r}, expected {want!r}")
    if m["timeframe_seconds"] != STEP:
        raise SignalError("manifest timeframe is not daily")
    if expect_version is not None and m["version_id"] != expect_version:
        raise SignalError(f"dataset version {m['version_id']} is not the pinned "
                          f"version {expect_version}")
    if not isinstance(m["csv_file"], str) or os.path.basename(m["csv_file"]) != m["csv_file"]:
        raise SignalError("manifest csv_file must be a bare file name")
    if not isinstance(m["gate_checks"], list):
        raise SignalError("manifest gate_checks is not a list")
    for g in m["gate_checks"]:
        if not isinstance(g, dict) or g.get("status") not in GATE_STATUSES:
            raise SignalError("manifest contains a gate check with an unknown status")
        if g["status"] == "FAIL":
            raise SignalError(f"dataset validation FAILED: {g.get('name')}: {g.get('detail')}")

    fetched_ts = _parse_fetched(m["fetched_utc"])
    csv_path = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), m["csv_file"])
    if not os.path.isfile(csv_path):
        raise SignalError(f"CSV file {m['csv_file']} is missing")

    raw = _read_once(csv_path)                       # F5: one read
    digest = hashlib.sha256(raw).hexdigest()         # F5: hash those exact bytes
    if digest != m["csv_sha256"]:
        raise SignalError("CSV hash does not match the manifest: the file was changed")
    if pins is not None:
        check_independent_pin(digest, m, pins)       # F2

    candles = parse_csv_bytes(raw, mk)               # F5: parse the same bytes
    if len(candles) != m["row_count"]:
        raise SignalError(f"row count {len(candles)} differs from manifest {m['row_count']}")
    if candles[0].time != m["first_open_unix"] or candles[-1].time != m["last_open_unix"]:
        raise SignalError("first or last candle differs from the manifest")
    last_close = candles[-1].time + STEP
    if last_close > fetched_ts:                      # F4
        raise SignalError(f"forming candle refused: the last candle closes "
                          f"{utc_text(last_close)} UTC, after the dataset fetch time "
                          f"{utc_text(fetched_ts)} UTC")
    return m, candles


def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def rsi(closes, n=RSI_N):
    """Wilder RSI on the closes given. Uses only the values passed in."""
    if len(closes) < n + 1:
        return None
    diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in diffs]
    losses = [max(-d, 0.0) for d in diffs]
    avg_gain = sum(gains[:n]) / n
    avg_loss = sum(losses[:n]) / n
    for g, lo in zip(gains[n:], losses[n:]):
        avg_gain = (avg_gain * (n - 1) + g) / n
        avg_loss = (avg_loss * (n - 1) + lo) / n
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def signal_at(candles, k):
    """Research candidate for the completed candle at index k. Reads candles[:k+1] only."""
    if not 0 <= k < len(candles):
        raise SignalError("index outside the dataset")
    window = candles[:k + 1]
    closes = [c.close for c in window]
    last = window[-1]
    s_fast = sma(closes, SMA_FAST)
    s_slow = sma(closes, SMA_SLOW)
    r = rsi(closes, RSI_N)
    values = {
        "close": round(last.close, 2),
        "sma20": None if s_fast is None else round(s_fast, 2),
        "sma50": None if s_slow is None else round(s_slow, 2),
        "rsi14": None if r is None else round(r, 2),
    }
    base = {
        "rule_version": RULE_VERSION,
        "basis_candle_open_utc": utc_text(last.time),
        "basis_candle_close_utc": utc_text(last.time + STEP),
        "values": values,
    }
    if s_slow is None:
        return dict(base, decision="WAIT", reasons=[
            f"insufficient history: need {SMA_SLOW} completed daily candles, have {len(window)}"])

    up = s_fast > s_slow
    down = s_fast < s_slow
    if up and last.close > s_slow and r < RSI_OVERBOUGHT:
        return dict(base, decision="BUY", reasons=[
            f"SMA20 {s_fast:.2f} is above SMA50 {s_slow:.2f} (uptrend)",
            f"close {last.close:.2f} is above SMA50 {s_slow:.2f}",
            f"RSI14 {r:.2f} is below {RSI_OVERBOUGHT:.0f} (not overbought)"])
    if down and last.close < s_slow:
        return dict(base, decision="SELL", reasons=[
            f"SMA20 {s_fast:.2f} is below SMA50 {s_slow:.2f} (downtrend; bearish or exit candidate)",
            f"close {last.close:.2f} is below SMA50 {s_slow:.2f}",
            f"RSI14 {r:.2f} (context only)"])

    reasons = []
    if s_fast == s_slow:
        reasons.append(f"SMA20 equals SMA50 at {s_fast:.2f} (no trend)")
    if up and last.close <= s_slow:
        reasons.append(f"close {last.close:.2f} is not above SMA50 {s_slow:.2f}")
    if up and r >= RSI_OVERBOUGHT:
        reasons.append(f"RSI14 {r:.2f} is at or above {RSI_OVERBOUGHT:.0f} (overbought, no BUY)")
    if down and last.close >= s_slow:
        reasons.append(f"close {last.close:.2f} is not below SMA50 {s_slow:.2f}")
    return dict(base, decision="WAIT", reasons=reasons or ["no rule condition met"])


def check_config(config_path, manifest, market):
    """Confirms the dataset is the version pinned in backtest_config.json."""
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as e:
        raise SignalError(f"cannot read config: {e}")
    if cfg.get("dataset_version") != manifest["version_id"]:
        raise SignalError(f"dataset {manifest['version_id']} is not the version pinned in "
                          f"config ({cfg.get('dataset_version')!r})")
    if cfg.get("provider") != market["provider"] or cfg.get("symbol") != market["symbol"] \
            or cfg.get("timeframe") != market["timeframe"]:
        raise SignalError("config provider, symbol or timeframe does not match the dataset")
    return cfg.get("dataset_version")


def build_report(manifest_path, config_path=None, now_ts=None, pins=None):
    m, candles = load_verified(manifest_path, pins=pins)
    if config_path:
        pinned = check_config(config_path, m, m["market"])
    else:
        pinned = "NOT CHECKED (no config supplied)"
    now = time.time() if now_ts is None else now_ts
    result = signal_at(candles, len(candles) - 1)
    close_ts = candles[-1].time + STEP
    age_seconds = now - close_ts
    stale = age_seconds > MAX_AGE_SECONDS
    waits = result["reasons"] if result["decision"] == "WAIT" else []
    if pins is None:
        pin_status = "NOT CHECKED (no independent pin supplied to this run)"
    else:
        pin_status = ("VERIFIED against signal/expected_pins.json. The pin establishes snapshot "
                      "integrity only, not source authenticity. Provisional until committed.")
    return {
        "report_type": "BTC/USDT daily research candidate (rule-based)",
        "disclaimer": DISCLAIMER,
        "generated_utc": utc_text(now) + " UTC",
        "status": "NOT CURRENT" if stale else "CURRENT",
        "stale": stale,
        "stale_limit_hours": MAX_AGE_SECONDS / 3600.0,
        "stale_notice": ("NOT CURRENT: the data basis is older than the 48-hour limit at "
                         "generation time. This is a historical snapshot, NOT a live signal, "
                         "and must not be acted on as one.") if stale else "",
        "dataset": {
            "name": m["dataset_name"],
            "version_id": m["version_id"],
            "pinned_in_config": pinned,
            "independent_pin": pin_status,
            "csv_sha256_verified": m["csv_sha256"],
            "fetched_utc": m["fetched_utc"],
            "row_count": m["row_count"],
            "first_open_utc": utc_text(candles[0].time) + " UTC",
            "last_open_utc": utc_text(candles[-1].time) + " UTC",
            "price_basis_warning": m.get("price_basis_warning"),
        },
        "dataset_checks": dataset_checks(m),
        "provenance": m.get("provenance"),
        "code": {
            "file": "signal/btc_signal.py",
            "sha256": sha256_file(os.path.abspath(__file__)),
            "rule_version": RULE_VERSION,
            "git_commit": "not recorded by this tool: the working tree is uncommitted",
        },
        "model": "none: fixed, untuned rules; no fitted parameters and no model score",
        "decision": result["decision"],
        "decision_basis": {
            "candle_open_utc": result["basis_candle_open_utc"],
            "candle_close_utc": result["basis_candle_close_utc"],
            "values": result["values"],
            "reasons": result["reasons"],
        },
        "reasons_for_wait": waits,
        "data_freshness_hours_since_basis_close": round(age_seconds / 3600.0, 2),
        "no_trading": "No order, account, credential or exchange access was used.",
    }


def render_markdown(r):
    d = r["decision_basis"]
    lines = [f"# {r['report_type']}", ""]
    if r["stale"]:
        lines += [f"> **{r['stale_notice']}**", ""]
    lines += [f"> {r['disclaimer']}", "",
              f"**Status: {r['status']}**  (generated {r['generated_utc']})", "",
              f"**Decision: {r['decision']}**  (basis candle opened {d['candle_open_utc']}, "
              f"closed {d['candle_close_utc']})", "",
              "## Reasons"]
    lines += [f"- {x}" for x in d["reasons"]]
    v = d["values"]
    lines += ["", "## Values",
              f"- close: {v['close']}", f"- SMA20: {v['sma20']}", f"- SMA50: {v['sma50']}",
              f"- RSI14: {v['rsi14']}", "",
              "## Dataset",
              f"- version: {r['dataset']['version_id']} (pinned in config: "
              f"{r['dataset']['pinned_in_config']})",
              f"- independent pin: {r['dataset']['independent_pin']}",
              f"- CSV SHA-256: {r['dataset']['csv_sha256_verified']}",
              f"- fetched: {r['dataset']['fetched_utc']}",
              f"- rows: {r['dataset']['row_count']}, {r['dataset']['first_open_utc']} to "
              f"{r['dataset']['last_open_utc']}",
              f"- price basis: {r['dataset']['price_basis_warning']}",
              "", "## Provenance"]
    prov = r.get("provenance")
    if prov:
        lines += [f"- label: {prov['label']}",
                  f"- authenticity: {prov['authenticity']}",
                  f"- historical rows: {prov['historical_rows']['rows']} from "
                  f"{prov['historical_rows']['source']}",
                  f"- user-supplied rows: {prov['user_supplied_rows']['rows']} from "
                  f"{prov['user_supplied_rows']['source']}"]
    else:
        lines.append("- none recorded")
    lines += ["", "## Dataset checks (WARN and FAIL)"]
    if r["dataset_checks"]:
        lines += [f"- {c['name']}: {c['status']} - {c['detail']}" for c in r["dataset_checks"]]
    else:
        lines.append("- none")
    lines += ["", "## Code and model",
              f"- file: {r['code']['file']}, SHA-256 {r['code']['sha256']}",
              f"- rule version: {r['code']['rule_version']}; git commit: {r['code']['git_commit']}",
              f"- model: {r['model']}",
              "", f"Data freshness: {r['data_freshness_hours_since_basis_close']} hours since the "
              "basis candle closed.",
              "", r["no_trading"], ""]
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="BTC/USDT daily research candidate (read-only).")
    p.add_argument("--manifest", required=True, help="path to the dataset manifest JSON")
    p.add_argument("--config", help="path to backtest_config.json, to check the pinned version")
    p.add_argument("--pins", default=DEFAULT_PINS_PATH,
                   help="independent expected-hash pin file (default: signal/expected_pins.json)")
    p.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    args = p.parse_args(argv)
    try:
        pins = load_pins(args.pins)
        report = build_report(args.manifest, args.config, pins=pins)
    except SignalError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
