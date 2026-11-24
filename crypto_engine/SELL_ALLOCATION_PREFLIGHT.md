# SELL allocation preflight validator

`tmm_core.reservation_allocations.validate_sell_allocations` is a pure validation helper for the proposed reservation identity contract.

## Validated invariants

- Every SELL fill is allocated exactly, including partial fills.
- BUY fills cannot consume SELL reservations.
- Every allocation references a known fill and reservation.
- Reservation account and market must match the settlement account and fill.
- Reservation version must match the supplied trusted snapshot.
- Aggregate allocations cannot exceed the reservation's remaining authorized quantity.
- Allocation IDs and fill IDs are unique within the supplied batch.
- Decimal inputs are finite, positive where required, and bounded to 38 significant digits with at most 18 fractional places.
- Output is normalized and sorted by allocation ID.

## Critical trust boundary

This helper is not a durable reservation ledger, does not lock inventory, does not authorize a SELL, and does not prevent concurrent over-consumption by itself. Its input reservation snapshot must come from trusted settlement code, not a strategy agent or user-supplied payload.

The future settlement integration must, inside one authoritative SQLite write transaction:

1. Load reservation rows from the database.
2. Validate current ownership, market, version and remaining quantity.
3. Call this helper using those rows and the staged fills/allocations.
4. Persist per-fill allocation rows and increment consumed reservation quantities with compare-and-set version checks.
5. Persist fill, cash, holdings, audit, outbox and batch state atomically.
6. Roll back every write on any mismatch or stale version.

Until that transactional integration and its crash/multi-process tests exist, this helper is only an offline preflight primitive. It must not be used as the sole enforcement point for settlement.

## Safety

Synthetic spot research only. No network, exchange, account, wallet, PAPER activation or LIVE capability. Strategy agents remain proposal-only.
