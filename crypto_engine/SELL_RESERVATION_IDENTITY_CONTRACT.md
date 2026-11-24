# SELL reservation identity and fill-allocation contract

Status: proposed interface contract; no runtime implementation or acceptance claim.

## Purpose

The SQLite settlement store currently checks that aggregate SELL outbox filled quantities equal aggregate SELL fills per market. That aggregate invariant does not prove which reservation authorized each fill, which account owns that reservation, or whether a partial fill consumes the correct reservation balance.

This contract defines the identity and allocation evidence required before adding durable reservation binding to the settlement schema.

## Required identities

Every reservation must have immutable, nonempty identifiers:

- `reservation_id`: globally unique, opaque identifier created by the trusted reservation authority.
- `account_id`: exact synthetic account owner.
- `market_id`: exact registered spot market.
- `base_asset` and `quote_asset`: immutable market identity.
- `authorized_quantity`: positive canonical Decimal quantity in the market base asset.
- `created_at`: trusted integer timestamp.
- `version`: monotonic reservation version for compare-and-set updates.

The reservation authority must be explicit in the integration design. A strategy agent may request a reservation through a proposal API but must never create, enlarge, release, or settle one directly.

## Fill allocation model

A SELL fill must be allocated to one or more existing reservations using explicit allocation records. Each record contains:

- `reservation_id`
- `fill_id`
- `account_id`
- `market_id`
- `allocated_quantity`
- `reservation_version` observed during authorization

Multiple fills may consume one reservation, and one fill may be split across multiple reservations only when the trusted allocator explicitly records each allocation. No inference from market-level totals is allowed.

## Invariants checked in one trusted transaction

For each committed batch:

1. Every SELL fill has allocation records; BUY fills have none.
2. Sum of allocations for each `fill_id` equals that fill's exact quantity.
3. Every allocation references an existing reservation and a SELL fill in the same batch.
4. Reservation `account_id` and `market_id` match the settlement account and fill.
5. Sum of allocations in the batch for a reservation does not exceed its unconsumed authorized quantity.
6. The reservation version is current at commit; stale versions fail closed and require a fresh authorization decision.
7. The same allocation identity cannot be committed twice.
8. Aggregate SELL fill totals and aggregate allocation totals reconcile exactly per account and market.
9. All quantity arithmetic uses canonical Decimal values; no binary float conversions.
10. Any mismatch rolls back the entire batch: fills, balances, audit, allocation records, outbox, and batch result.

A zero-fill attempt creates no fill allocation. Releasing unused reservation quantity is a distinct, explicitly authorized state transition with its own idempotency key and audit event; it must not be inferred from a zero-fill result.

## Partial fills and multiple reservations

- Partial fill: allocate only the executed quantity; leave the unused reservation amount reserved until a separate trusted release/expiry transition.
- Multiple fills against one reservation: each fill has a distinct allocation row; cumulative allocations cannot exceed remaining authorized quantity.
- One fill across multiple reservations: permitted only with explicit rows per reservation, all checked in the same transaction.
- Multiple reservations in one market: each fill must identify the exact reservation(s); aggregate market equality is insufficient.
- Cross-account or cross-market allocation: always rejected.
- Reservation expiry, cancellation, amendment, and release: explicit versioned transitions; no silent mutation or automatic release during replay.

## Outbox contract

Each allocation produces a durable outbox instruction with:

- stable idempotency key derived from the canonical tuple (account, reservation, batch, fill, allocation sequence/version);
- reservation ID and version;
- batch ID and fill ID;
- market ID and exact allocated quantity;
- canonical payload digest.

The receiver must persist idempotency keys and return the original durable receipt for repeats without applying the effect twice. A timeout or ambiguous response is not proof of failure. Retry is permitted only when the receiver contract guarantees idempotency. If receiver idempotency cannot be demonstrated, the outbox item remains unresolved and the batch cannot become COMPLETE automatically.

Acknowledgement must bind the receipt digest to the exact idempotency key, reservation, batch, fill and quantity. The acknowledgement event and batch-state transition must be committed atomically and appended to the local audit chain. Receipt authenticity and independent audit anchoring remain separate trust requirements.

## Schema and migration implications

The existing schema-v1 outbox fields (`idempotency_key`, `batch_id`, `market_id`, `authorized_quantity`, `filled_quantity`) do not encode reservation identity or per-fill allocation.

A future schema version should add, at minimum:

- reservation records or an explicitly specified durable external reservation authority;
- reservation version and ownership fields;
- per-fill allocation records with uniqueness and foreign-key constraints;
- outbox reservation/fill identity and canonical payload digest;
- explicit migration from v1 with fail-closed behavior when historical reservation identity cannot be reconstructed.

Do not infer reservation IDs for historical rows. Existing pending outbox rows without identity must remain unresolved for evidence-backed reconciliation; never auto-complete, delete, or synthesize ownership.

## Acceptance tests required before integration

1. Missing reservation identity is rejected.
2. Cross-account and cross-market reservation references are rejected.
3. SELL fill without allocations is rejected.
4. Allocation totals below or above fill quantity are rejected.
5. Reservation over-consumption across multiple fills is rejected.
6. Stale reservation version is rejected.
7. Duplicate allocation and duplicate outbox key are rejected.
8. Partial fill preserves unused reservation quantity.
9. One fill split across multiple reservations reconciles exactly.
10. Zero-fill does not silently release a reservation.
11. Crash injection at every transaction boundary leaves all-or-nothing state.
12. Multi-process concurrent consumption cannot over-allocate a reservation.
13. Receiver duplicate delivery produces one effect and the same receipt.
14. Ambiguous delivery remains unresolved without proven receiver idempotency.
15. Migration fixtures with pending v1 outbox rows fail closed without fabricated identity.
16. Python 3.11 exact-head CI and independent adversarial review pass.

## Security and rollout boundary

- Synthetic offline spot accounting only.
- Long-only; no shorts, leverage, margin, derivatives or live execution.
- PAPER activation remains on hold; LIVE disabled.
- No network, exchange, account, wallet, credential, or real-money capability.
- Strategy agents remain proposal-only and receive no database handles or settlement authority.
- Do not merge or enable this design until implementation, exact-head tests, concurrency/crash evidence, and independent review are complete.
