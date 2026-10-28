"""research/backtest_report.py - Markdown for the Step 2 backtest, readable on a phone."""

METRIC_LIMITS = [
    "**Total return** - one number for one start and end date; moving either by a few weeks can change "
    "it a lot. Open positions are valued at the last close without exit costs, for the strategy and "
    "buy-and-hold alike.",
    "**Maximum drawdown** - measured on daily closing equity, so it hides intraday drops; real drawdowns "
    "are at least this large. It describes the past worst case, not a limit.",
    "**Trade count** - closed round trips. A trend filter makes few trades, so every other statistic "
    "rests on a small sample. Under 30 closed trades is flagged as too few to conclude anything.",
    "**Win rate** - share of closed trades with a profit after costs. It ignores size: a strategy can win "
    "often and still lose money, or win rarely and make money.",
    "**Profit factor** - gross profit divided by gross loss. Shown as n/a with no losing trade; it swings "
    "wildly with a handful of trades.",
    "**Exposure** - share of days a position was held. Lower exposure explains lower risk and lower "
    "return; compare return per unit of exposure, not return alone.",
    "**Benchmarks** - buy-and-hold pays the same entry costs once. Cash returns exactly 0%: no interest "
    "is modelled.",
]


def pct(x):
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def plain(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def short(name):
    return name.split(":")[0]


def metric_row(label, scenario, m):
    pf = "n/a" if m["profit_factor"] is None else f"{m['profit_factor']:.2f}"
    trades = f"{m['closed_trades']}" + (" (+1 open)" if m["open_position"] else "")
    return (f"| {scenario} | {label} | {pct(m['total_return'])} | {plain(m['max_drawdown'])} | {trades} | "
            f"{plain(m['win_rate'])} | {pf} | {plain(m['exposure'])} |")


def seg_table(block):
    L = ["| Costs | Row | Return | Max drawdown | Closed trades | Win rate | Profit factor | Exposure |",
         "|---|---|---|---|---|---|---|---|"]
    for scen, parts in block.items():
        L.append(metric_row("Strategy", short(scen), parts["strategy"]))
        L.append(metric_row("Buy and hold", short(scen), parts["buy_and_hold"]))
        L.append(metric_row("Cash", short(scen), parts["cash"]))
    return L


def build_markdown(r):
    L = ["# BTC/USDT trend-filter backtest (research only)",
         f"Run `{r.get('run_id')}` · **READ-ONLY** · no keys, no orders, no live trading", "",
         "> **This is a historical simulation on a proxy market. It does not show that the strategy is "
         "profitable and it is not a signal.** Costs are unverified assumptions, past data is one sample, "
         "and the market is Binance BTC/USDT, **not** Tokocrypto execution prices.", ""]
    if r["status"] != "OK":
        L += ["## STOPPED", "", f"The backtest did not run: **{r['error']}**", "",
              "Nothing was simulated and no results are shown."]
        return "\n".join(L) + "\n"
    d = r["dataset"]
    L += ["## Data (preserved version, pinned)", "",
          f"- `{d['version_id']}` · sha256 `{d['sha256']}`",
          f"- {d['market']['provider']} {d['market']['pair_label']} {d['market']['timeframe']} spot · "
          f"{d['rows']} candles · {d['first_open_utc'][:10]} to {d['last_open_utc'][:10]} (UTC open times)",
          "- Re-verified at load: hash, market identity, order, no duplicates, no gaps, only completed candles."]
    # flagged candle
    L += ["", "## Flagged candle (2020-03-12, -39.5% in one day)", ""]
    c = r.get("crosscheck")
    if c:
        for e in c["flagged"]:
            L.append(f"- **{e['date']}: {e['verdict']}** (rule: {c['rule']}).")
            for name in ("coinbase", "bitstamp"):
                j = e[name]
                if j:
                    L.append(f"  - {name}: day return {j['other_return_pct']:+.2f}% vs Binance "
                             f"{j['binance_return_pct']:+.2f}%, close diff {j['close_diff_pct']:+.2f}%, "
                             f"low diff {j['low_diff_pct']:+.2f}%")
        if c.get("summary"):
            s = c["summary"]
            L.append(f"- Whole history vs Coinbase: median close difference {s['median_abs_close_diff_pct']:.2f}%, "
                     f"99th percentile {s['p99_abs_close_diff_pct']:.2f}%, max {s['max_abs_close_diff_pct']:.2f}%.")
        for k in ("coinbase_error", "bitstamp_error"):
            if c.get(k):
                L.append(f"- {k.split('_')[0]} could not be fetched: {c[k]}")
    else:
        L.append("- **No cross-check evidence was available in this run: the candle is NOT verified.**")
    sv = r.get("sensitivity")
    if sv:
        sel2 = sv["selection"]
        L += ["", f"Sensitivity: the same selection with the candle **removed** ({', '.join(sv['removed'])}); "
              "the original candle is kept in the data.",
              f"- Selected period with the candle: **{r['selection']['selected_n']}**; without it: "
              f"**{sel2['selected_n']}** ({'CHANGED' if sv['selected_n_changed'] else 'unchanged'}).",
              f"- Test-window signals for the chosen period identical with and without the candle: "
              f"**{sv['test_signals_identical_for_original_choice']}**."]
        L += ["", "| MA | Train return (with / without) | Validation return (with / without) |", "|---|---|---|"]
        for a, b in zip(r["selection"]["rows"], sel2["rows"]):
            L.append(f"| {a['n']} | {pct(a['train']['total_return'])} / {pct(b['train']['total_return'])} | "
                     f"{pct(a['validation']['total_return'])} / {pct(b['validation']['total_return'])} |")
    # assumptions
    ru = r["rules"]
    L += ["", "## Assumptions (ALL UNVERIFIED for Tokocrypto)", "",
          "| Item | Value | Status |", "|---|---|---|"]
    L += [f"| {g['name'].split(':')[0]} | fee {g['fee'] * 100:.2f}% per side, slippage {g['slip'] * 100:.2f}% per fill | "
          "assumption; the 0.40% estimate came from a Tokocrypto support page read through a summarizer, not confirmed for any account |"
          for g in r["cost_grid"]]
    L += [f"| Starting capital | {ru['capital']:.0f} USDT per segment (hypothetical) | assumption |",
          f"| Position size | {ru['fraction'] * 100:.0f}% of cash, long only, no leverage | design choice |",
          f"| Minimum order | {ru['min_notional']:.0f} USDT | assumption, unverified |",
          f"| Quantity step | {ru['qty_step']} BTC (rounded down) | assumption, unverified |",
          "| Fills | next candle's open, worsened by slippage | design rule against look-ahead |",
          "| Not modelled | interest on cash, taxes beyond the fee estimate, partial fills, order-book depth, downtime | - |"]
    # splits
    L += ["", "## Chronological split (60% / 20% / 20% by row count)", "",
          "| Segment | From | To | Bars |", "|---|---|---|---|"]
    for k, label in (("train", "Train"), ("validation", "Validation"), ("test", "Test")):
        s = r["splits"][k]
        L.append(f"| {label} | {s['start']} | {s['end']} | {s['bars']} |")
    L.append("Train scoring starts after a 200-bar warm-up so every candidate is scored on the same bars. "
             "Each segment starts flat with fresh capital; earlier candles only warm up the averages.")
    # selection
    sel, fz = r["selection"], r["frozen"]
    L += ["", "## Selection (train + validation only)", "", f"_{fz['rule_text']}_", "",
          "| MA days | Train return | Train max DD | Eligible | Validation return | Validation max DD | Val. trades | Score | Chosen |",
          "|---|---|---|---|---|---|---|---|---|"]
    for row in sel["rows"]:
        L.append(f"| {row['n']} | {pct(row['train']['total_return'])} | {plain(row['train']['max_drawdown'])} | "
                 f"{'yes' if row['eligible'] else 'no'} | {pct(row['validation']['total_return'])} | "
                 f"{plain(row['validation']['max_drawdown'])} | {row['validation']['closed_trades']} | "
                 f"{row['score']:.2f} | {'**yes**' if row['n'] == sel['selected_n'] else ''} |")
    if sel["selected_n"] is None:
        L += ["", "**No candidate passed the training screen. Nothing was selected and the test window was not evaluated.**"]
    else:
        L += ["", f"**Frozen choice: {sel['selected_n']}-day moving average.** Frozen record hash "
              f"`{fz['frozen_hash'][:16]}...` was written before the test window was evaluated."]
        if r.get("expected_selected_n") is not None:
            L.append(f"It matches the choice recorded in the config before the final run "
                     f"(expected_selected_n = {r['expected_selected_n']}, set after the dry run).")
    # results
    shown = r.get("shown")
    if shown:
        L += ["", "## Results for the frozen choice", "",
              "Train and validation were used to choose, so they are NOT independent evidence. "
              "Only the test block is out-of-sample, and it is a single period."]
        for k, label in (("train", "TRAIN (in-sample)"), ("validation", "VALIDATION (used for selection)")):
            L += ["", f"### {label}: {r['splits'][k]['start']} to {r['splits'][k]['end']}", ""] + seg_table(shown[k])
        t = r["test"]
        s = r["splits"]["test"]
        L += ["", f"### TEST (final, evaluated once): {s['start']} to {s['end']}", ""]
        if t["status"] == "evaluated":
            L.append(f"Evaluation number {t['evaluation_number']}" + (" (**re-evaluation: this is a repeated look at the test window**)" if t["re_evaluation"] else " (first and only)") + ".")
            L += [""] + seg_table(t["results"])
            base = next(iter(t["results"].values()))
            n_tr = base["strategy"]["closed_trades"]
            L += ["", f"Base costs: strategy {pct(base['strategy']['total_return'])} vs buy-and-hold "
                  f"{pct(base['buy_and_hold']['total_return'])} vs cash +0.0%; strategy max drawdown "
                  f"{plain(base['strategy']['max_drawdown'])} vs buy-and-hold {plain(base['buy_and_hold']['max_drawdown'])}; "
                  f"{n_tr} closed trade(s)." + (" **Too few trades to conclude anything.**" if n_tr < 30 else "")]
        elif t["status"] == "already_evaluated":
            p = t["prior"]
            L += [f"**Refused: the test window was already evaluated (run {p.get('run_id')}) for this frozen choice. "
                  "A second look would turn the test into another training set.** The earlier recorded result is shown.", ""]
            L += seg_table(p["results"])
        else:
            L.append(f"Not evaluated: {t['reason']}.")
            if t["status"] == "skipped":
                L.append("**DRY RUN: no test-window result exists yet.** The choice above is frozen; "
                         "the final run will evaluate the test window once.")
    L += ["", "## How to read this", "",
          "- A positive number here is not evidence of profit; a negative one is not proof of failure.",
          "- Only one asset, one rule and one test period were examined; the four candidates were compared on the same history.",
          "- Compare every strategy row with buy-and-hold in the same block and with the drawdown it took.",
          "- Before trusting anything: more trades, other periods or assets, real fees, and paper trading with live prices.",
          "", "## Metric limitations", ""] + [f"- {m}" for m in METRIC_LIMITS]
    L += ["", "## Unresolved concerns", "",
          "- The market is Binance BTC/USDT; Tokocrypto prices, spreads, fees and order rules are unverified.",
          "- Cost and trading-rule numbers above are assumptions.",
          "- Only closes and opens are used; intraday stops and intraday drawdowns are not simulated.",
          "- One cross-check of the flagged day uses USD venues, not USDT."]
    L += ["", "Logs for the frozen choice under base costs: `trades.csv`, `orders.csv`, `equity.csv`; "
          "the frozen record is `frozen_choice.json`."]
    return "\n".join(L) + "\n"
