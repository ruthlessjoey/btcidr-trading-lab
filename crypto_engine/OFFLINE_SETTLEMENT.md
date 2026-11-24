# Offline settlement controller

`tmm_core.offline_settlement.OfflineSettlementController` is trusted offline composition-root code. It must not be passed to strategy agents.

## Durable batch journal

The controller requires a trusted `SQLiteBatchJournal` on an absolute path inside an existing private directory. The journal uses SQLite immediate transactions, FULL synchronous commits, restrictive file permissions, and a unique batch key bound to a canonical request hash. A repeated completed batch with identical content returns its stored result without a second gateway call. Reusing an ID with different content is rejected.

The journal binds itself to a runtime identity. A new process/runtime cannot reuse the journal automatically: it fails closed and requires operator reconciliation. An interrupted `PROCESSING` batch remains unresolved and cannot be replayed automatically. This is intentional because the portfolio ledger is still in-memory; replaying a stored result into a fresh ledger would produce inconsistent accounting.

## Flow

The trusted simulator must supply a unique, stable batch ID. Never accept it from an untrusted strategy agent.

1. Accept a trusted, stable `batch_id`, target-delta proposals and a timestamp-matched synthetic OHLCV bar per proposed market.
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
- Every call requires a trusted `batch_id`; duplicate or previously attempted IDs are rejected before a second risk-gateway call. Fill IDs derive from the batch ID.
- Batch claims and completed results are durably recorded. An interrupted attempt remains `PROCESSING`; a new runtime is rejected until trusted reconciliation. Do not delete or reset the journal to bypass this lock.
- All bars/rules are validated before the stateful risk proposal call. Aggregate BUY cash and SELL inventory are preflighted before ledger mutation.
- The SQLite journal is not a transaction spanning the in-memory portfolio ledger and SELL settlement callback. A callback/process failure after a fill can leave partial in-memory state; the durable journal then remains unresolved and the runtime fails closed. Durable portfolio persistence and atomic ledger/settlement orchestration remain future work.

This module is not production execution infrastructure and does not establish strategy profitability. It is an offline test foundation for realistic-cost experiments.
