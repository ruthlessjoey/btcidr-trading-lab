# Offline settlement controller

`tmm_core.offline_settlement.OfflineSettlementController` is trusted offline composition-root code. It must not be passed to strategy agents.

## Flow

1. Accept target-delta proposals and a timestamp-matched synthetic OHLCV bar per proposed market.
2. Ask the injected proposal-only risk client for authorization.
3. Require exact authorization coverage; no agent-supplied permitted quantity is accepted.
4. Apply venue-like quantity steps, price ticks, fee bps, half-spread, slippage and maximum bar-volume participation.
5. Apply resulting synthetic fills to the in-memory portfolio ledger.
6. Settle each SELL reservation with authorized and actually filled quantities, including partial or zero fills.

## Model limits

- This is a deterministic bar-level approximation, not an order-book queue or market-impact model.
- The bar open is the execution reference; spread and slippage are adverse fixed bps, with conservative price-tick rounding.
- Participation caps are based on the supplied bar volume. No intrabar path is inferred.
- Fee, spread, slippage and participation rules must be preregistered per market. They are not fetched or guessed.
- No FX conversion, derivatives, leverage, shorting, broker, exchange, network, wallet, PAPER or LIVE capability.
- Synthetic fills use timestamp/market/side IDs; callers must process each market/time batch only once. Persistent replay-safe simulation IDs and durable transaction orchestration remain future work.

This module is not production execution infrastructure and does not establish strategy profitability. It is an offline test foundation for realistic-cost experiments.
