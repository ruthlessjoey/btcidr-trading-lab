# Bitstamp personal spot research — preregistration V2

Date: 27 November 2026
Status: FROZEN DESIGN; no provider run authorized by this file alone.

Preregistration ID: `BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2`

## Scope
Personal, noncommercial SPOT research only. No raw data redistribution, account access, credentials, order endpoints or live trading. Candidate strategies are fixed SMA20/50 long-only trend and RSI14 long-only mean reversion (enter below 30, exit above 55; flat 14-change window is neutral RSI 50). Buy-and-hold is a same-cost baseline only. No parameter tuning or search. Any additional candidate/parameter variant must be appended to the hash-chained registry before evaluation.

## Data and timing
- 1-hour closed candles; 2024-01-01 00:00 UTC candle open through 2026-11-01 00:00 UTC inclusive candle-close boundary.
- Exact market identity required on every page; gaps/incomplete coverage block the market.
- First 50% of contiguous candles is historical indicator warm-up/development history; no model fitting.
- Five sequential, non-overlapping test windows on the remaining bars; 50-bar embargo between folds; >=750 bars per fold; minimum dataset 7,900 candles. This provides at least 30 complete non-overlapping 24-bar return observations per fold for the DSR/bootstrap evidence.
- Each fold starts flat; indicators use only prior closes available at the signal time.
- Signal at close, execute at next open; max participation 5% of prior-hour base volume.

## Costs
- Fee 16 bps per side (public example only).
- Large-market base: 5 bps half-spread + 10 bps slippage per side.
- Meme-market base: 15 bps half-spread + 20 bps slippage per side.
- 2x replay doubles fee, half-spread and slippage; same signals/data, costs only changed.
- Candidate and buy-hold use identical dates and same costs.
- Returns are mark-to-market after executed costs; no hypothetical terminal liquidation fill.
- Drawdown uses conservative high-first-then-low OHLC path, not observed intrabar sequencing.

## Statistics and promotion
- Non-overlapping 24-bar returns for DSR and paired comparison.
- DSR uses the complete registered-trial count.
- Paired circular block bootstrap: 10,000 resamples; block length ceil(n^(1/3)); deterministic seed bound to dataset hash and fold ID; lower 2.5th percentile.
- Promotion: >=5 OOS folds; >=60% positive net-return folds and >=60% beating same-cost buy-hold; positive mean net and excess; >=60% positive at 2x costs and positive mean 2x return; every fold drawdown <=20%, PF >=1.20, DSR >=0.95, bootstrap lower bound >0; >=30 closed trades and >=100 observations aggregate.
- All folds share dataset hash, registry hash and registered-trial count. Passing qualifies for independent human review only; it does not prove future profitability or authorize PAPER/LIVE.
- DSR independence assumptions, bootstrap assumptions, data rights and untouched holdout status require independent review.

## Trial registry
- Family: `BITSTAMP_PERSONAL_SPOT_V2`
- Current candidate trials: 2
- File: `trial_registry.jsonl`
- SHA-256: `7fa30c75dfc71d1db2b939586b3bf3d3006607a4479f5187dabf1b479e530778`
- Append every new/failed/abandoned candidate trial; do not delete or rewrite previous events. Preserve Git history. The hash chain is tamper-evident, not WORM or an external trust anchor.

No public-data request is made by this preregistration.
