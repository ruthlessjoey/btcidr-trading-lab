# Bitstamp personal spot-data research

This is an isolated, noncommercial research-only workstream. It uses unauthenticated public Bitstamp SPOT market metadata and 1-hour OHLC candles. It does not access an account, credentials, wallet, order endpoint, private API or live trading.

## Data rights and storage
Bitstamp's API documentation identifies the public markets and OHLC endpoints and states that companies using Bitstamp exchange data for their own commercial purposes must obtain a commercial Data License Agreement. This branch is limited to personal, noncommercial research, with no raw-data redistribution. Any commercial product, signal distribution or resale requires a separate written license assessment and approval.

Sources:
- https://www.bitstamp.net/api/
- https://www.bitstamp.net/fee-schedule/

The GitHub Actions workflow keeps candles in runner memory, emits only summary metrics and hashes, and uploads no dataset artifact. It does not retain raw provider data.

The public API documentation states that companies using Bitstamp exchange data for their own commercial purposes must contact Bitstamp and sign a commercial-use Data License Agreement. That statement is not treated here as a blanket grant of personal-use rights or permission for a future commercial product. Any commercial use, redistributed dataset, paid signal or production integration remains blocked pending a separate written rights assessment and approval.

## Preregistered research

Preregistration ID: `BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V1`. The runner rejects date, candidate-universe, minimum-market and meme-market requirement overrides; any design change must be versioned and frozen before a new data request.
- Symbols: BTC/USD, ETH/USD, XRP/USD, DOGE/USD, SHIB/USD, PEPE/USD and SOL/USD where Bitstamp currently exposes a SPOT market.
- Interval: 1 hour; closed candles only.
- Period: first eligible candle opens at 2024-01-01 00:00 UTC; last eligible candle closes no later than 2026-11-01 00:00 UTC.
- Strategies: fixed SMA20/50 long-only trend; fixed RSI14 long-only mean reversion (enter below 30, exit above 55); buy-and-hold is a baseline only.
- Chronological split: 60% train / 20% validation / 20% holdout with 50-bar embargo between segments.
- No parameter search, no tuning on validation or holdout, all preregistered strategies reported.
- Execution: signal at candle close, execute at next candle open; maximum participation 5% of prior-hour base volume.
- Costs: 16 bps taker fee per side as a documented public API example (not the user's actual fee tier); assumed spread/slippage scenarios are reported separately. These are assumptions, not historical order-book observations.
- Drawdown reporting includes close-to-close marks and a worst-case high-first-then-low OHLC path after the next-open execution decision. The top-level maximum drawdown uses that conservative peak-to-trough mark; actual intrabar sequencing, liquidity and stop/market execution are not known from OHLC data, so this is an upper-bound assumption rather than tick-level execution simulation.
- Long-only spot, no shorts, leverage, margin or derivatives.

## Fail-closed conditions
- Only exact HTTPS host www.bitstamp.net and documented public markets/OHLC paths.
- No redirects, no credentials, no cookies, strict TLS, 4 MiB response cap, duplicate-key JSON rejection, 1000-row page cap and bounded pagination.
- Only SPOT markets; exact market identity must match.
- Duplicate candles, invalid OHLC, gaps, insufficient history or market identity mismatch block the affected backtest.
- No raw data artifacts or dataset publication.

## Important limits
This is exploratory research, not an installable trading system. The workflow does not place orders. Results do not establish profitability, high win rate, independent validation or production readiness. A missing/unsupported meme-coin market is reported; the script does not substitute another asset silently.


## Terminal return valuation

A segment that ends with an open long position reports mark-to-market return and the marked value of the remaining inventory separately. The `net_return_pct` field is null unless the segment ends flat, because the simulator does not invent a terminal exit fill or liquidation cost. The mark-to-market return is after costs on the fills that were actually simulated, not a realized liquidation return.
