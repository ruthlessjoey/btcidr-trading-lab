"""research/data_report.py - Markdown for the Step 1 gate, readable on a phone."""

ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}


def build_markdown(r):
    m, cov = r["market"], r["coverage"]
    L = [f"# Dataset gate: {m['pair_label']} {m['timeframe']} ({m['provider']})",
         f"Generated {r['generated_utc']} · **READ-ONLY** · no keys, no orders", "",
         f"## GATE: {ICON[r['gate']]} {r['gate']}",
         ("The dataset passed every check. The backtest may use it." if r["gate"] == "PASS" else
          "**The dataset FAILED. No dataset file was written and the backtest must not run.** "
          "The actual coverage is shown below; nothing is padded or assumed."), ""]
    if r.get("stop_reason"):
        L += [f"Stopped because: {r['stop_reason']}", ""]
    L += ["## Market identity", "",
          f"- Provider: **{m['provider']}** (`{m['host']}`), spot market",
          f"- Symbol **{m['symbol']}** = base {m['base_asset']} / quote **{m['quote_asset']}**",
          "- This is **not** Tokocrypto and not USD. It is a PROXY for Tokocrypto BTC/USDT; "
          "Tokocrypto prices, spreads and fills are unverified."]
    ei = r.get("exchange_info")
    if ei:
        L.append(f"- Exchange's own description: `{ei}`")
    if cov:
        L += ["", "## Coverage (actual, from the exchange)", "",
              "| Item | Value |", "|---|---|",
              f"| First candle (open, UTC) | {cov['first_open_utc']} |",
              f"| Last completed candle (open, UTC) | {cov['last_open_utc']} |",
              f"| Rows | {cov['rows']} |",
              f"| Rows expected for a gap-free range | {cov['expected_rows']} |",
              f"| Missing days | {cov['missing']} |",
              f"| Exact / conflicting duplicates | {cov['exact_duplicates']} / {cov['conflicting_duplicates']} |",
              f"| Still-forming candle excluded | {cov['forming_excluded']} |",
              f"| HTTP requests | {cov['requests']} |"]
    if r["pages"]:
        L += ["", "## Pagination evidence", "", "| Request | Asked from | Rows | First | Last |",
              "|---|---|---|---|---|"]
        L += [f"| {i} | {p['requested_from']} | {p['rows']} | {p['first']} | {p['last']} |"
              for i, p in enumerate(r["pages"], 1)]
    L += ["", "## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    L += [f"| {c['name']} | {ICON[c['status']]} {c['status']} | {c['detail']} |" for c in r["checks"]]
    if r.get("http_log"):
        L += ["", "HTTP evidence (first requests): " +
              "; ".join(f"`{p}` {w}" for p, w in r["http_log"])]
    if r["top_moves"]:
        L += ["", "## Largest daily moves (shown so outliers are visible, not hidden)", ""]
        L += [f"- {t['date']}: {t['close_to_close_pct']:+.2f}%" for t in r["top_moves"]]
    d = r.get("dataset")
    if d:
        L += ["", "## Dataset version (preserved, never overwritten)", "",
              f"- Version: `{d['version_id']}`", f"- CSV: `{d['csv']}`", f"- Manifest: `{d['manifest']}`",
              f"- SHA-256: `{d['sha256']}`", f"- Rows: {d['rows']}"]
    p = r.get("previous")
    if p:
        L += ["", "## Earlier version", "",
              "- None yet; this is the first version." if not p.get("found") else
              f"- {p.get('version') or p.get('error')}"]
    L += ["", "## Limits", "",
          "- Passing this gate means the data is complete, ordered, de-duplicated and correctly "
          "labelled. It says nothing about whether any strategy makes money.",
          "- Candle time = open time in UTC; a daily candle is known only after 00:00 UTC the next day.",
          "- Binance can revise or delist data in future; each fetch is stored as a new version so "
          "changes can be detected."]
    return "\n".join(L) + "\n"
