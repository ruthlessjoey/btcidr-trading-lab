"""research/history.py - Step 1 hard gate: fetch the full candle history, then check it.

READ-ONLY. Public market-data endpoints only. If any gate check FAILS, no dataset
file is written and nothing downstream may run; the report shows the actual coverage.
"""
import json
import os
import time
import urllib.parse
from datetime import datetime, timezone

import fetcher
import providers
import validator
from fetcher import ApiError, TF_SECONDS
from research import dataset
from research.data_report import build_markdown

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _date_to_ts(text):
    return int(datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def fetch_exchange_info(http, cfg):
    """Asks the exchange what this symbol is. Returns the symbol entry."""
    q = urllib.parse.urlencode({"symbol": cfg["symbol"]})
    obj = http.get(f"{cfg['host']}/api/v3/exchangeInfo?{q}")
    entries = obj.get("symbols") if isinstance(obj, dict) else None
    if not isinstance(entries, list) or len(entries) != 1:
        raise ApiError(f"exchangeInfo did not return exactly one symbol: {str(obj)[:200]}")
    return entries[0]


def fetch_pages(http, cfg, from_s, now_s):
    """Pages forward through history. Returns (all rows as received, per-page evidence)."""
    tf_sec, limit = TF_SECONDS[cfg["timeframe"]], cfg["page_limit"]
    rows, pages, cursor = [], [], from_s
    for _ in range(cfg["max_pages"]):
        q = urllib.parse.urlencode({"symbol": cfg["symbol"], "interval": cfg["timeframe"],
                                    "startTime": cursor * 1000, "endTime": now_s * 1000,
                                    "limit": limit})
        page = fetcher.parse_klines(http.get(f"{cfg['host']}/api/v3/klines?{q}"))
        ev = {"requested_from": _day(cursor), "rows": len(page),
              "first": _day(page[0].time) if page else None,
              "last": _day(page[-1].time) if page else None,
              "first_ts": page[0].time if page else None, "last_ts": page[-1].time if page else None,
              "starts_before_request": bool(page) and page[0].time < cursor,
              "ascending": all(a.time < b.time for a, b in zip(page, page[1:]))}
        pages.append(ev)
        rows.extend(page)
        if len(page) < limit:
            return rows, pages
        cursor = page[-1].time + tf_sec
    raise ApiError(f"stopped after {cfg['max_pages']} pages without reaching the end")


def merge(rows):
    """One candle per open time. Returns (sorted candles, exact duplicates, conflicting duplicates)."""
    seen, exact, conflict = {}, 0, 0
    for c in rows:
        if c.time in seen:
            if seen[c.time] == c:
                exact += 1
            else:
                conflict += 1
        else:
            seen[c.time] = c
    return [seen[t] for t in sorted(seen)], exact, conflict


def gaps(candles, tf_sec):
    out = []
    for a, b in zip(candles, candles[1:]):
        if b.time - a.time > tf_sec:
            out.append((a.time + tf_sec, (b.time - a.time) // tf_sec - 1))
    return out


def run_step1(cfg, out_dir="out", opener=fetcher.default_opener, sleep=time.sleep,
              local_now=None, previous_root=None):
    if cfg.get("mode") != "read_only":
        raise SystemExit("Refusing to run: only mode 'read_only' is supported.")
    if cfg["timeframe"] not in TF_SECONDS:
        raise SystemExit(f"Unknown timeframe {cfg['timeframe']!r}")
    os.makedirs(out_dir, exist_ok=True)
    tf_sec = TF_SECONDS[cfg["timeframe"]]
    local_now = int(time.time() if local_now is None else local_now)
    http = providers.Http(cfg["http_timeout_seconds"], cfg["http_retries"], opener, sleep)
    checks, info = [], {}

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": detail})

    market = {"provider": cfg["provider"], "host": cfg["host"], "symbol": cfg["symbol"],
              "base_asset": cfg["base_asset"], "quote_asset": cfg["quote_asset"],
              "pair_label": f"{cfg['base_asset']}/{cfg['quote_asset']}",
              "timeframe": cfg["timeframe"], "market_type": "spot"}
    result = {"generated_utc": dataset.utc_text(local_now) + " UTC", "market": market,
              "config": {k: cfg[k] for k in ("fetch_from_utc_date", "require_first_candle_on_or_before",
                                             "min_rows", "page_limit")},
              "checks": checks, "pages": [], "gate": FAIL, "dataset": None, "previous": None,
              "coverage": None, "exchange_info": None, "stop_reason": None, "top_moves": []}
    candles = []

    try:
        # 1. market identity, from the exchange itself
        entry = fetch_exchange_info(http, cfg)
        result["exchange_info"] = {k: entry.get(k) for k in
                                   ("symbol", "status", "baseAsset", "quoteAsset", "isSpotTradingAllowed")}
        ok = (entry.get("symbol") == cfg["symbol"] and entry.get("baseAsset") == cfg["base_asset"]
              and entry.get("quoteAsset") == cfg["quote_asset"] and entry.get("status") == "TRADING"
              and entry.get("isSpotTradingAllowed") is True)
        add("market_identity", PASS if ok else FAIL,
            f"exchange says symbol={entry.get('symbol')} base={entry.get('baseAsset')} "
            f"quote={entry.get('quoteAsset')} status={entry.get('status')} "
            f"spot={entry.get('isSpotTradingAllowed')}; expected {cfg['symbol']} "
            f"{cfg['base_asset']}/{cfg['quote_asset']} TRADING spot")
        if not ok:
            raise ApiError("market identity does not match the configuration")

        # 2. exchange clock and paged history
        server_now = fetcher.extract_server_time(http.get(cfg["host"] + "/api/v3/time"))
        add("clock", PASS if abs(server_now - local_now) <= 120 else WARN,
            f"exchange time {dataset.utc_text(server_now)} UTC; runner differs by "
            f"{abs(server_now - local_now)}s")
        from_s = _date_to_ts(cfg["fetch_from_utc_date"])
        rows, pages = fetch_pages(http, cfg, from_s, server_now)
        result["pages"] = [{k: v for k, v in p.items() if k not in ("first_ts", "last_ts")}
                           for p in pages]
        boundary = [(a["last_ts"], b["first_ts"]) for a, b in zip(pages, pages[1:])
                    if a["last_ts"] is not None and b["first_ts"] is not None]
        bad_bounds = sum(1 for last, first in boundary if first != last + tf_sec)
        empty_mid = sum(1 for p in pages[:-1] if p["rows"] == 0)
        add("pagination", FAIL if (bad_bounds or empty_mid or any(
            p["starts_before_request"] or not p["ascending"] for p in pages)) else PASS,
            f"{len(pages)} request(s); {sum(p['rows'] for p in pages)} rows received; "
            f"{bad_bounds} page boundary problem(s); every page ascending and not earlier "
            f"than its requested start")

        # 3. duplicates, closed candles
        unique, exact, conflict = merge(rows)
        add("duplicates", FAIL if (exact or conflict) else PASS,
            f"{exact} exact duplicate(s), {conflict} conflicting duplicate(s) among {len(rows)} "
            f"received rows (the pager asks for non-overlapping ranges, so none are expected)")
        closed = [c for c in unique if c.time + tf_sec <= server_now]
        forming = len(unique) - len(closed)
        add("closed_candles_only", PASS if closed else FAIL,
            f"{forming} still-forming candle(s) excluded; {len(closed)} completed candles kept")
        if not closed:
            raise ApiError("no completed candles")
        candles = closed

        # 4. history depth, from what the exchange really returned
        first, last = candles[0], candles[-1]
        need_by = _date_to_ts(cfg["require_first_candle_on_or_before"])
        depth_ok = first.time <= need_by and len(candles) >= cfg["min_rows"]
        add("history_depth", PASS if depth_ok else FAIL,
            f"actual first candle {_day(first.time)}, last {_day(last.time)}, {len(candles)} rows; "
            f"required: first on or before {cfg['require_first_candle_on_or_before']} and at least "
            f"{cfg['min_rows']} rows")

        # 5. missing days, grid
        g = gaps(candles, tf_sec)
        missing = sum(n for _, n in g)
        expected_rows = (last.time - first.time) // tf_sec + 1
        add("missing_days", FAIL if missing else PASS,
            f"{missing} missing of {expected_rows} expected" +
            ("; first gaps: " + ", ".join(f"{_day(t)} (+{n})" for t, n in g[:8]) if g else ""))
        off = sum(1 for c in candles if c.time % tf_sec)
        add("timestamp_grid", FAIL if off else PASS,
            f"{off} candle(s) not on a UTC {cfg['timeframe']} boundary")

        # 6. the generic validator (price sanity, volume, spikes, freshness)
        vcfg = {"max_missing_ratio": 0.0, "max_spike_pct": cfg["max_spike_pct"]}
        v = validator.validate(candles, tf_sec, server_now, local_now, first.time, server_now, vcfg)
        for c in v.checks:
            if c.name in ("ohlc_sanity", "volume_sanity", "price_spikes", "freshness"):
                add("validator_" + c.name, c.status, c.detail)
        moves = sorted(((abs(b.close / a.close - 1) * 100, b.time, b.close / a.close - 1)
                        for a, b in zip(candles, candles[1:])
                        if b.time - a.time == tf_sec and a.close > 0), reverse=True)[:5]
        result["top_moves"] = [{"date": _day(t), "close_to_close_pct": round(m * 100, 2)}
                               for _, t, m in moves]
        result["coverage"] = {"first_open_utc": _day(first.time), "last_open_utc": _day(last.time),
                              "rows": len(candles), "expected_rows": expected_rows,
                              "missing": missing, "exact_duplicates": exact,
                              "conflicting_duplicates": conflict, "forming_excluded": forming,
                              "requests": http.requests}
        info["server_now"] = server_now
    except ApiError as e:
        add("fetch", FAIL, str(e))
        result["stop_reason"] = str(e)
    result["http_log"] = http.log[:12]

    # 7. previous version must still verify, and is compared with this fetch
    if previous_root:
        prev = dataset.latest_manifest(previous_root, dataset.dataset_name(market))
        if prev is None:
            result["previous"] = {"found": False}
            add("previous_version", PASS, "no earlier version exists yet; this is the first")
        else:
            try:
                pm, pc = dataset.load_verified(prev, expect={"provider": market["provider"],
                                                             "symbol": market["symbol"],
                                                             "quote_asset": market["quote_asset"],
                                                             "timeframe": market["timeframe"]})
                cmp_ = dataset.compare_versions(pc, candles) if candles else None
                result["previous"] = {"found": True, "version": pm["version_id"], "compare": cmp_}
                bad = cmp_ and (cmp_["changed"] or cmp_["only_in_old"])
                add("previous_version", FAIL if bad else PASS,
                    f"{pm['version_id']} re-verified (hash ok). " + (
                        f"vs this fetch: {cmp_['common']} common candles, {cmp_['changed']} changed, "
                        f"{cmp_['only_in_old']} only in old, {cmp_['added_in_new']} new" if cmp_
                        else "no new data to compare"))
            except dataset.DatasetError as e:
                result["previous"] = {"found": True, "error": str(e)}
                add("previous_version", FAIL, f"earlier version FAILED re-verification: {e}")

    gate = FAIL if any(c["status"] == FAIL for c in checks) else PASS
    result["gate"] = gate
    if gate == PASS:
        csv_path, man_path = dataset.write_version(
            os.path.join(out_dir, "datasets"), market, candles, local_now,
            extra={"exchange_info": result["exchange_info"], "coverage": result["coverage"],
                   "gate_checks": checks})
        # round trip: reload from disk exactly as later code will
        m, again = dataset.load_verified(man_path, expect={
            "provider": market["provider"], "symbol": market["symbol"],
            "quote_asset": market["quote_asset"], "timeframe": market["timeframe"]})
        same = again == candles
        add("csv_hash_roundtrip", PASS if same else FAIL,
            f"re-read from disk: {len(again)} rows, sha256 {m['csv_sha256']}, identical to fetched: {same}")
        result["dataset"] = {"version_id": m["version_id"], "csv": os.path.basename(csv_path),
                             "manifest": os.path.basename(man_path), "sha256": m["csv_sha256"],
                             "rows": m["row_count"]}
        if not same:
            result["gate"] = FAIL
    result["backtest_allowed"] = result["gate"] == PASS
    text = build_markdown(result)
    with open(os.path.join(out_dir, "dataset_report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "dataset_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0 if result["gate"] == PASS else 1
