# Twin Money Maker — crypto spot core

This is an isolated, offline-only foundation for multi-market crypto spot research. It is additive: it does not replace, import, or modify the existing BTC/IDR application pipeline.

## Safety

- Spot-only and long-only accounting; no shorts, leverage, margin or derivatives.
- Research/synthetic mode only. The package contains no network client or exchange connector.
- No credentials, account access, wallet access, order placement, cancellation, deposits or withdrawals.
- LIVE trading is not implemented and remains disabled.
- MEME_INTEL is not imported or integrated; that project requires independent readiness and separate approval.
- No third-party Python runtime dependencies.
- Venue tick, lot and minimum-notional rules must be supplied explicitly; this package never discovers or guesses them.

## Included

- Deterministic shared-account multi-market allocation across quote currencies.
- Stale/future price and FX rejection, gross exposure, per-market, base-asset and quote-asset caps.
- Synchronized shared-cash backtest with next-bar-open execution, market-specific fees, spread, slippage and prior-bar volume limits.
- Explicit price tick, quantity step, minimum quantity and minimum quote notional.
- Conservative price rounding: BUY up, SELL down; quantity always rounds down.
- Latched portfolio drawdown stop. After the threshold is breached at a completed bar close, later signals are ignored and next opens attempt liquidation. Partial liquidity leaves the halt latched.
- Synthetic tests only. No profitability claim.

## Verify

From this folder:

```sh
sh install.sh
```

This creates a local virtual environment, runs static checks and the isolated synthetic suite, and compiles the package. It makes no network calls and installs no third-party packages.

## Not production-ready

No authentic current multi-market datasets, point-in-time meme-token universe, contract/ownership risk analysis, DEX transaction/reorg/gas model, order-book queue or market-impact model, venue market-halt/delisting lifecycle, covariance-aware de-risking, fee-token accounting, independent external security review, or profitability evidence are included. This core is not approved for paper execution or exchange connection.
