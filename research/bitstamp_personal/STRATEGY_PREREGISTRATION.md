# Strategy preregistration — frozen before public data retrieval

Date: 27 November 2026

## Scope
Personal, noncommercial, research-only spot data. No raw data redistribution. No live trading, account access or exchange order endpoints.

## Candidate universe
Candidate Bitstamp SPOT markets: BTC/USD, ETH/USD, XRP/USD, DOGE/USD, SHIB/USD, PEPE/USD, SOL/USD. The public markets endpoint determines actual availability. At least three markets and at least one meme-coin market (DOGE, SHIB, PEPE, BONK or FLOKI) are required for this run. Missing markets are reported; no substitutions are invented.

## Fixed strategy family
1. SMA20/50 long-only trend: at candle close, target 100% long only when SMA20 > SMA50 and close > SMA20; otherwise target flat.
2. RSI14 simple-average mean reversion, long-only: enter when RSI14 < 30; exit when RSI14 > 55; otherwise maintain prior target.
3. Buy-and-hold is a benchmark only, not a candidate strategy.

No parameter optimization or search is permitted in this run.

## Data and timing
- 1-hour closed candles only.
- Requested range 2024-01-01 00:00 UTC through 2026-11-01 00:00 UTC.
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
- Drawdown is reported on both close-to-close and adverse intrabar-low equity marks. The headline maximum drawdown uses the intrabar-low mark after the next-open execution decision; the order of events inside an OHLC candle is unknown, so this does not replace tick/order-book simulation.
- Spread/slippage are assumptions, not historical observations. The actual user fee tier is unknown and no private fee endpoint is accessed.

## Metrics
Net return, maximum drawdown, closed-cycle count, win rate, Wilson 95% interval, profit factor, expectancy, fees, turnover and fill count. Fewer than 30 closed cycles is marked insufficient sample.

## Promotion
This run is exploratory only. No strategy can be promoted from this run. Independent review, multiple-testing adjustment, realistic historical spread/impact, untouched external holdout, provider-rights approval and full release gates remain mandatory.
