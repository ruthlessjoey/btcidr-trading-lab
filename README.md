# BTC/IDR Trading Lab

The historical Milestone 1 runner is **disabled** pending a safe, unprotected validation/reporting boundary and an independently accepted market-identity method.

## Current public-data boundary

- Only unauthenticated HTTPS GET candles from `https://www.tokocrypto.site/api/v3/klines` are authorized.
- Only the fixed BTCUSDT symbol and bounded candle query fields are accepted by the transport allowlist.
- Tokocrypto `.com`, Tokocrypto `/open/v1`, server-time, symbol-metadata, and all other unapproved provider hosts/routes are rejected before network access.
- No API keys, login, private account data, balances, orders, withdrawals, or transfers exist in the approved workflow.
- `run.py`, `live_check.py`, `probe.py`, and `tools/net_lab.py` are inert legacy entrypoints. They must not be used to bypass the transport boundary or protected validator/report paths.

## Research and profitability

Candle retrieval alone does not independently prove market identity. Dataset publication and backtesting remain blocked until the market-identity gate is accepted through a separately approved method. A passing synthetic/offline test says nothing about live reachability or profitability. Never describe the historical strategy as profitable without reproducible, chronological out-of-sample evidence net of fees and realistic slippage.

## Trading safety

Spot-only, long-only, PAPER-only. LIVE trading is disabled and unavailable. No leverage, margin, shorts, derivatives, real-money orders, funding, or withdrawals.
