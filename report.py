"""report.py - turns results into a Markdown report that reads well on a phone."""
from datetime import datetime, timezone, timedelta

WITA = timezone(timedelta(hours=8))
ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "API ERROR": "❌"}


def fmt_time(ts):
    utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    return f"{utc:%Y-%m-%d %H:%M} UTC ({utc.astimezone(WITA):%m-%d %H:%M} WITA)"


def px(x):
    return f"{x:,.2f}"


def candle_table(candles):
    rows = ["| Open time | Open | High | Low | Close | Volume |", "|---|---|---|---|---|---|"]
    for c in candles:
        rows.append(f"| {fmt_time(c.time)} | {px(c.open)} | {px(c.high)} | "
                    f"{px(c.low)} | {px(c.close)} | {c.volume:,.4f} |")
    return rows


def attempts_lines(r):
    return [f"- {'✅' if a['ok'] else '❌'} **{a['source']}**: {a['detail']}"
            for a in r["attempts"]]


def build_markdown(r, candles):
    L = [f"# {r['pair']} data check ({r['timeframe']} candles)",
         f"Generated {r['generated_utc']} · mode **READ-ONLY** · no orders, no keys", ""]
    L.append(f"## Overall: {ICON[r['status']]} {r['status']}")
    if r["api_error"]:
        L += ["", "No source could be reached or gave usable data:", ""] + attempts_lines(r) + \
             ["", "No data was fetched, so no prices are shown. Nothing is made up."]
        return "\n".join(L) + "\n"

    L += ["", f"Source used: **{r['source']}** (`{r['source_url']}`)",
          f"Requests made: {r['requests_made']} · lookback: {r['lookback_days']} days", ""]
    if len(r["attempts"]) > 1:
        L += ["Sources tried, in order:", ""] + attempts_lines(r) + [""]
    L += ["## Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in r["checks"]:
        L.append(f"| {c['name']} | {ICON[c['status']]} {c['status']} | {c['detail']} |")

    s = r["stats"]
    L += ["", "## Data fetched", "",
          f"- Candles received: {s['raw_candles']}",
          f"- Closed candles kept: {s['closed_candles']} "
          f"(still-forming dropped: {s['forming_dropped']})",
          f"- Missing candles: {s['missing_candles']}",
          f"- Zero-volume candles: {s['zero_volume_candles']}"]
    if candles:
        L += [f"- First candle: {fmt_time(candles[0].time)}",
              f"- Last closed candle: {fmt_time(candles[-1].time)}",
              f"- Lowest low: {px(min(c.low for c in candles))} USDT",
              f"- Highest high: {px(max(c.high for c in candles))} USDT",
              f"- Last close: {px(candles[-1].close)} USDT",
              "", "### First 3 candles (prices in USDT)", ""] + candle_table(candles[:3]) + \
             ["", "### Last 5 closed candles (prices in USDT)", ""] + candle_table(candles[-5:])
    L += ["", "## Limits of this report", "",
          "- Prices are exactly what the endpoint returned; they are not cross-checked "
          "against a second source.",
          "- Candle field order and the volume unit (assumed BTC) follow Binance-style "
          "conventions and are not confirmed by a Tokocrypto page I could read.",
          "- A passing data check says the data looks sane. It says nothing about profit."]
    return "\n".join(L) + "\n"
