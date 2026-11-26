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

Preregistration ID: `BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2_5FOLD`. The runner rejects date, candidate-universe, minimum-market and meme-market requirement overrides; any design change must be versioned and frozen before a new data request.
- Symbols: BTC/USD, ETH/USD, XRP/USD, DOGE/USD, SHIB/USD, PEPE/USD and SOL/USD where Bitstamp currently exposes a SPOT market.
- Interval: 1 hour; closed candles only.
- Period: first eligible candle opens at 2024-01-01 00:00 UTC; last eligible candle closes no later than 2026-11-01 00:00 UTC.
- Strategies: fixed SMA20/50 long-only trend; fixed RSI14 long-only mean reversion (enter below 30, exit above 55); buy-and-hold is a baseline only.
- Evaluation: 40% initial training history followed by five expanding-training, chronological OOS test folds; 50-bar embargo before each test fold and between test folds. Each fold reserves the immediately following candle for explicit next-open terminal liquidation; that liquidation candle is excluded from OOS test indices. No parameter tuning is performed.
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


## Walk-forward segment state

Train, validation and holdout each begin with a separate flat research account. Rolling indicators can use prior historical candles for warmup, but stateful strategy targets (such as RSI's hold-until-exit rule) reset to flat at each segment boundary. No position target from the prior segment is inherited.


- Every OHLC page's returned pair identity is normalized and compared to the exact requested market symbol before candle rows are accepted; a stable but wrong pair is rejected.


## Fail-closed multi-fold promotion screen

`promotion_gate.py` checks completed fold summaries against frozen defaults: >=5 ordered non-overlapping OOS folds; positive net return in >=60% of folds; beats same-cost buy-and-hold in >=60% with positive mean excess; positive mean net return and positive mean return at 2x costs; >=60% positive folds at 2x costs; max drawdown <=20% per fold; profit factor >=1.20 per fold; DSR >=0.95 per fold; positive paired block-bootstrap excess-return lower bound per fold; >=30 closed trades and >=100 observations aggregate. Every fold must use the same dataset SHA-256 and append-only registered-trial count. A 2x-cost return cannot exceed its same-signal base-cost return.

The gate does not run strategies or calculate DSR/bootstrap statistics. A pass means only `ELIGIBLE_FOR_INDEPENDENT_HUMAN_REVIEW_NOT_PROVEN_PROFITABLE`; it never enables PAPER/LIVE. Dataset/preprocessing hash provenance, untouched status, embargo, statistics and actual costs still require independent verification. Run offline tests with `python -m unittest discover -s research/bitstamp_personal -p 'test_*.py' -v`.


### Additional promotion evidence binding

Every fold must also use identical SHA-256 hashes for the frozen cost model and strategy configuration. Candidate and same-cost benchmark returns must be explicitly tagged `REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT`, and the terminal position must be `FLAT`. This prevents an open-position mark-to-market result from being silently passed off as a realized net return. The gate still relies on independent verification that the hashes bind to the actual source/configuration and that benchmark liquidation uses the same documented execution rules.


## Five-fold walk-forward execution (V2)

The runner now creates five expanding-training OOS folds. Every fold starts with a flat research account, uses causal prior-close indicator warm-up, enters only from next-open signals, and reserves the next candle after the test interval for explicit terminal liquidation at that candle's open with the same modeled fee/spread/slippage. The liquidation candle is not included in the fold's test index range. Fifty additional candles are embargoed before the next fold. The same fold dates are replayed for the candidate and buy-and-hold baseline.

The 2x-cost replay doubles every cost component, including the per-side fee, half-spread and slippage, while preserving the exact same signals and candles. The fold runner reports base and 2x cost results but remains non-promotable until DSR and paired block-bootstrap statistics are computed and independently verified.


The V2 walk-forward schedule and cost stress supersede the earlier 60/20/20 split and prior non-doubled stress assumptions for future research runs. The historical V1 specification is retained for traceability.


## Statistical evidence (offline, deterministic)

`statistical_evidence.py` implements a dependency-free Deflated Sharpe probability and paired circular moving-block bootstrap lower confidence bound from per-period strategy and same-cost benchmark returns. DSR uses sample Sharpe, skewness, non-excess kurtosis, completed-trial Sharpe dispersion and the complete append-only registered-trial count. The bootstrap resamples paired return differences in circular blocks; defaults are 24 hourly observations, 5,000 replicates, 95% confidence and a fixed seed.

These calculations are screening evidence, not independent verification. Trial-registry completeness, candidate inclusion, return-series provenance, dependence assumptions and bootstrap block length still require review. No provider access or strategy execution is performed by this module.
