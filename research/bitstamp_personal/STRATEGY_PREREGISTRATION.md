# Strategy preregistration — frozen before public data retrieval

Date: 27 November 2026

Preregistration ID: `BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V1`

The executable runner rejects overrides to the date range, candidate universe, minimum market count or meme-market requirement. Any change to this design requires a new versioned preregistration before any provider data is requested.

## Scope
Personal, noncommercial, research-only spot data. No raw data redistribution. No live trading, account access or exchange order endpoints.

## Candidate universe
Candidate Bitstamp SPOT markets: BTC/USD, ETH/USD, XRP/USD, DOGE/USD, SHIB/USD, PEPE/USD, SOL/USD. The public markets endpoint determines actual availability. At least three markets and at least one meme-coin market (DOGE, SHIB, PEPE, BONK or FLOKI) are required for this run. Missing markets are reported; no substitutions are invented.

## Fixed strategy family
1. SMA20/50 long-only trend: at candle close, target 100% long only when SMA20 > SMA50 and close > SMA20; otherwise target flat.
2. RSI14 simple-average mean reversion, long-only: enter when RSI14 < 30; exit when RSI14 > 55; otherwise maintain prior target. A 14-change window with zero gains and zero losses is neutral (RSI 50), not overbought.
3. Buy-and-hold is a benchmark only, not a candidate strategy.

No parameter optimization or search is permitted in this run.

## Data and timing
- 1-hour closed candles only.
- Requested range: start at the 2024-01-01 00:00 UTC candle open; include candles only while their close timestamp is at or before 2026-11-01 00:00 UTC. The end is an inclusive candle-close boundary, not an inclusive calendar day.
- Signal is calculated at candle close; fill is at the next candle open.
- A 50-bar embargo separates train, validation and holdout segments.
- Each segment starts with a separate USD 10,000 research account; positions are not carried across split boundaries.
- Data gaps block backtesting for that market.

## Execution and costs
- Long-only, spot-only, no leverage, no margin, no derivatives, no shorts.
- Maximum participation: 5% of prior-hour base volume.
- Taker fee: 16 bps per side as a public API example only, not the user's account tier.
- Large-market base assumptions: 5 bps half-spread + 10 bps slippage per side.
- Meme-market base assumptions: 15 bps half-spread + 20 bps slippage per side.
- Stress costs are separately reported (10/25 bps for large markets; 30/50 bps for meme markets).
- Drawdown is reported on both close-to-close and adverse OHLC equity marks. For the headline risk measure, each post-execution candle is evaluated using a worst-case high-first-then-low sequence, so the candle high can raise the running peak before the low is marked. This is a conservative upper-bound assumption for a long-only position, not a claim about the actual intrabar event order; OHLC does not reveal sequencing, liquidity or actual stop/market execution and does not replace tick/order-book simulation.
- Spread/slippage are assumptions, not historical observations. The actual user fee tier is unknown and no private fee endpoint is accessed.

## Metrics
Realized net return (reported only when the segment ends flat), mark-to-market return, terminal position status/value, maximum drawdown, closed-cycle count, win rate, Wilson 95% interval, profit factor, expectancy, fees, turnover and fill count. If a segment ends with an open position, `net_return_pct` is null and the mark-to-market return is shown separately; no exit fill or liquidation cost is assumed. Fewer than 30 closed cycles is marked insufficient sample.

## Promotion
This run is exploratory only. No strategy can be promoted from this run. Independent review, multiple-testing adjustment, realistic historical spread/impact, untouched external holdout, provider-rights approval and full release gates remain mandatory.


## Segment state reset

Each train, validation and holdout segment uses a separate account that starts flat. Indicator calculations may use only historical closes available up to each signal candle, including pre-segment history for rolling-window warmup. Stateful strategy position targets are reset to flat at the first candle of every segment; a prior segment's open/held target is not carried into the next segment. The first new position can only be entered by a signal generated within the new segment and filled at the following candle open.


## Frozen statistical promotion policy

At least five chronological, non-overlapping OOS folds are required. At least 60% must have positive net return and beat same-cost buy-and-hold; mean net return and mean excess must be positive. At least 60% must remain positive at 2x costs and mean 2x-cost return must be positive. Every fold must have maximum drawdown <=20%, profit factor >=1.20, Deflated Sharpe probability >=0.95 and positive paired block-bootstrap lower bound. Aggregate closed trades >=30 and observations >=100. Every fold must use the same dataset hash and complete registered-trial count.

These frozen defaults are conservative screening rules, not universal financial laws. The current single train/validation/holdout split is insufficient. Passing permits independent human review only; source rights, holdout integrity, DSR/bootstrap calculation validity and production review remain separate gates.
