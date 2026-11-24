# Twin Money Maker — crypto spot core

This is an isolated, offline-only foundation for multi-market crypto spot research. It is additive: it does not replace, import, or modify the existing BTC/IDR application pipeline.

See [DATA_SOURCE_APPROVAL_MATRIX.md](DATA_SOURCE_APPROVAL_MATRIX.md) for the research-only review of CEX, DEX and meme-coin data options, license constraints and provider approval requirements.

## Safety

- Spot-only and long-only accounting; no shorts, leverage, margin or derivatives.
- Research/synthetic mode only. The package contains no network client or exchange connector.
- The only represented data source is an offline policy validator for the specifically approved Tokocrypto NextMe BTCIDR kline URL. It does not perform HTTP requests.
- The validator rejects all request headers and permits only unauthenticated GET to the exact approved host/path with BTCIDR candles.
- No credentials, account access, wallet access, order placement, cancellation, deposits or withdrawals.
- LIVE trading is not implemented and remains disabled.
- MEME_INTEL is not imported or integrated; that project requires independent readiness and separate approval.
- No third-party Python runtime dependencies.
- Venue tick, lot and minimum-notional rules must be supplied explicitly; this package never discovers or guesses them.

## Included

- Fail-closed account risk gateway: strategy proposals cannot supply holdings/equity; those are read from an injected authoritative ledger, state snapshots are transactionally stored, an external audit anchor is mandatory, account startup requires owner approval of a non-null session-loss threshold, and resets require an injected owner authorization verifier. See [RISK_GATEWAY.md](RISK_GATEWAY.md). This is an interface/test implementation only; no trusted production ledger, reset service, external anchor, agent sandbox or paper broker is supplied.

- Exact-host/path/method/query validation for unauthenticated GET candles from `https://cloudme-toko.2meta.app/api/v1/klines`, BTCIDR only.
- Raw payload size, UTF-8, duplicate-key, schema, closed-candle and SHA-256 provenance validation. Provenance does not independently authenticate the network peer.
- Versioned point-in-time CEX spot / DEX pool instrument registry keyed by stable market and asset identifiers, not ticker symbols alone.
- Market lifecycle gate for ACTIVE, HALTED, DELISTING_ANNOUNCED, DELISTED, MIGRATION_PENDING and UNKNOWN states. Stale metadata blocks both new entries and assumed exit availability; reactivation requires explicit confirmation.
- Deterministic shared-account multi-market allocation across quote currencies.
- Stale/future price and FX rejection, gross exposure, per-market, base-asset and quote-asset caps.
- Synchronized shared-cash backtest with next-bar-open execution, market-specific fees, spread, slippage and prior-bar volume limits.
- Explicit price tick, quantity step, minimum quantity and minimum quote notional.
- Conservative price rounding: BUY up, SELL down; quantity always rounds down.
- Latched portfolio drawdown stop. After the threshold is breached, later signals are ignored and next opens attempt liquidation. Partial liquidity leaves the halt latched.
- Thread-safe shared session-loss guard: re-marks equity at executable opens before new exposure, blocks all BUY proposals after the configured session-loss threshold, caps SELL proposals to unreserved held inventory, and reserves concurrent exits to prevent duplicate sells.
- Hash-chained session risk audit journal, JSON snapshot/restore, and explicit reset requiring actor, reason and approval reference. Snapshot integrity checks detect event changes; durable trusted storage and external hash anchoring remain deployment responsibilities.
- Point-in-time sample-covariance volatility overlay. It requires aligned, equally spaced timestamped returns, rejects stale/future/misaligned data, and only scales long-only weights down to an explicit per-observation volatility cap. It does not annualize or impute missing data.
- Evidence-driven token eligibility gate for crypto/meme research. Missing or failed required controls, stale evidence, insufficient liquidity/LP lock/holders, concentrated top holders or excessive taxes block eligibility. A pass means only `ELIGIBLE_FOR_HUMAN_REVIEW`; it never authorizes an order and does not verify the truth of supplied evidence.
- Synthetic tests only. No profitability claim.

## Verify

From this folder:

```sh
sh install.sh
```

This creates a local virtual environment, runs static checks and the isolated synthetic suite, and compiles the package. It makes no network calls and installs no third-party packages.

## Not production-ready

No authentic current multi-market datasets, independently verified contract/ownership/LP evidence, DEX transaction/reorg/gas model, order-book queue or market-impact model, robust covariance shrinkage or regime-aware stress analysis, fee-token accounting, independent external security review, or profitability evidence are included. The token gate only evaluates supplied evidence and cannot authenticate its source. The approved BTCIDR feed was previously observed to be stale; no new request was made in this package. This core is not approved for paper execution or exchange connection.
