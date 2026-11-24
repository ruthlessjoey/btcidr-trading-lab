# SQLite reservation schema v2 primitives

Status: isolated schema component; not integrated into SQLiteSettlementStore.

## Added objects

The v2 helper defines three normalized tables:

- `reservations`: immutable reservation identity, account/market ownership, authorized and consumed base quantity, creation time, version, and explicit lifecycle state.
- `reservation_allocations`: exact allocation rows linking a batch, SELL fill, reservation, account, market, quantity and observed reservation version.
- `reservation_outbox`: one durable delivery row per allocation, binding idempotency key, allocation, reservation, fill, owner, market, version, quantity, payload digest and receiver receipt state.

Primary keys, foreign keys, uniqueness and lifecycle CHECK constraints are part of the expected schema definition. The helper verifies stored DDL while normalizing formatting whitespace only outside quoted SQL literals and identifiers; quoted contents are preserved exactly. This prevents whitespace changes inside CHECK values from being normalized away. It rejects partial schema creation or unapproved indexes/triggers on these tables.

## Transaction contract

`ensure_reservation_schema_v2(db)` requires:
- A real SQLite connection.
- A caller-owned open transaction.
- Existing parent tables `markets`, `batches`, and `fills`.

It creates all three objects inside the caller's transaction and does not commit. The caller must commit or roll back. Repeated calls on the exact schema are idempotent.

## Migration boundary

This helper deliberately does not migrate schema v1 and does not change the current `SQLiteSettlementStore.SCHEMA_VERSION`. Do not call it as a startup auto-migration.

A future explicit migration must:
1. Back up and verify the v1 database using a separately reviewed procedure.
2. Inspect every historical outbox row.
3. Refuse automatic migration when pending or historical reservation identity cannot be proven.
4. Never synthesize reservation IDs or allocation rows.
5. Preserve the original audit chain and add an independently reviewable migration event/manifest.
6. Validate exact v2 DDL, foreign keys, integrity and audit continuity before enabling the upgraded store.
7. Keep unresolved legacy outbox records out of the COMPLETE state until evidence-backed reconciliation.

## Critical integration still required

The helper only creates and verifies schema objects. It does not:
- create or authorize reservations;
- validate Decimal quantities or reservation state transitions;
- bind allocations to fills inside `apply_batch`;
- atomically consume reservation quantities or compare-and-set versions;
- create per-allocation outbox rows;
- deliver outbox messages or verify receiver receipts;
- integrate with the trusted offline settlement controller.

The future integration must load reservation rows under `BEGIN IMMEDIATE`, validate ownership/version/remaining quantity, write allocations and update consumed quantity/version in the same transaction as fills, balances, audit, batch and outbox. Any failure must roll back the entire transaction.

## Verification

Nine focused test methods are committed for transaction ownership, parent-table requirements, creation, idempotent revalidation, partial schema rejection, altered constraint detection, trigger rejection, foreign-key enforcement and rollback. They have not yet been executed against the exact PR head.

Exact-head CI, Python 3.11, crash injection, multi-process concurrency, v1 migration, controller integration and independent adversarial review remain required.

## Safety

Offline synthetic spot only. Spot-only and long-only. PAPER remains on hold; LIVE disabled. No network, exchange, account, wallet, credentials or real-money capability. Strategy agents remain proposal-only and must never receive the database connection.
