# Twin Money Maker — crypto spot core

This is an isolated, offline-only foundation for multi-market crypto spot research. It is additive: it does not replace, import, or modify the existing BTC/IDR application pipeline.

See [DATA_SOURCE_APPROVAL_MATRIX.md](DATA_SOURCE_APPROVAL_MATRIX.md) for the research-only review of CEX, DEX and meme-coin data options, license constraints and provider approval requirements.

## Safety

- Spot-only and long-only accounting; no shorts, leverage, margin or derivatives.
- Research/synthetic mode only. The package contains no network client or exchange connector.
- The only represented source policy is an offline request-shape validator for `https://www.tokocrypto.site/api/v3/klines`. **BTCIDR on this MBX host is UNVERIFIED / BLOCKED**: Tokocrypto documentation places the BTCIDR example on the prohibited NextMe/2meta host. Passing request-shape checks does not prove the market exists on the approved host. No HTTP request is performed.
- The request-shape validator rejects request headers and checks unauthenticated GET syntax, but the provider-compatibility gate blocks BTCIDR ingestion/provenance until the owner-approved host-to-market mapping is independently verified. Do not switch to BTCUSDT or NextMe automatically.
- No credentials, account access, wallet access, order placement, cancellation, deposits or withdrawals.
- LIVE trading is not implemented and remains disabled.
- MEME_INTEL is not imported or integrated; that project requires independent readiness and separate approval.
- No third-party Python runtime dependencies.
- Venue tick, lot and minimum-notional rules must be supplied explicitly; this package never discovers or guesses them.

## Included

- Fail-closed account risk gateway plus owner-authorized exposure-policy wrapper: strategy proposals cannot supply holdings/equity/marks/policy; the strategy-facing wrapper applies fresh-mark, liquidity, gross, per-market and asset-concentration controls before the session-loss gateway. SQLite state storage rejects shared/symlinked paths and enforces private local permissions. See [RISK_GATEWAY.md](RISK_GATEWAY.md) and [POLICY_GATEWAY.md](POLICY_GATEWAY.md). This is still an interface/test implementation only; no trusted production ledger, mark provider, owner authorization service, external anchor, agent sandbox or paper broker is supplied.

- Exact-host/path/method/query validation for unauthenticated GET candles from `https://www.tokocrypto.site/api/v3/klines`, BTCIDR only. The prior `cloudme-toko.2meta.app/api/v1/klines` endpoint is not approved.
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

## Deterministic exposure policy (PR #106)

`tmm_core.exposure_policy` provides an offline, fail-closed pure policy function for long-only spot proposals. It requires trusted equity, holdings, fresh per-market valuation marks, and a precomputed executable buy-liquidity capacity. It caps buys against shared gross exposure, per-market exposure, aggregate base-asset concentration, aggregate quote-asset concentration, and per-market liquidity capacity. Sells are capped to held inventory. Invalid or stale inputs reject the request.

Important: this module is currently a tested policy primitive, not yet wired into `RiskGateway` or a production ledger/agent runtime. Do not treat it as an active account control or advance PAPER. The next integration step must make trusted exposure marks and owner-approved policy mandatory at the gateway boundary, then test restart, concurrency, failure and agent-isolation paths.


## Offline synthetic ledger (PR #108)

`tmm_core.offline_portfolio.SyntheticPortfolioLedger` supplies a trusted-test-side in-memory ledger for registered spot markets quoted in one account currency. It applies Decimal BUY/SELL synthetic fills atomically, rejects insufficient cash/oversells, deduplicates fill IDs, requires complete fresh marks for equity, scopes reads to one account ID and exposes a hash-chained audit snapshot. It is not durable production accounting and must only be mutated by a trusted offline simulator. See [OFFLINE_PORTFOLIO.md](OFFLINE_PORTFOLIO.md). No PAPER advancement or exchange integration is included.


## Offline settlement controller (PR #109)

See [OFFLINE_SETTLEMENT.md](OFFLINE_SETTLEMENT.md). The trusted controller composes a proposal-only risk client, explicit synthetic OHLCV bars, fixed adverse cost assumptions, participation caps, the synthetic ledger and a trusted SELL-settlement callback. It must remain inside the trusted simulator/composition root, never in an agent process. Bar-level execution is an approximation; it does not model order-book queues, intrabar paths or nonlinear market impact. No real provider, exchange, broker, account, wallet, PAPER or LIVE capability exists.
