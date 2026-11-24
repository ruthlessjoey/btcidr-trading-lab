# Atomic offline settlement design

Status: proposed architecture only; implementation and acceptance tests are incomplete. Synthetic spot research only; no PAPER or LIVE authorization.

## Problem

The current controller has three separate state boundaries: the SQLite batch journal, the in-memory portfolio ledger, and an injected SELL-reservation callback. A crash can leave a durable unresolved batch after in-memory balances have changed. Fail-closed replay prevents a second attempt but does not restore or prove portfolio state. This is not atomic settlement or durable accounting.

## Target architecture

Introduce one trusted SQLite accounting store (`SQLiteSettlementStore`) and a transactional outbox. Strategy agents receive only a proposal interface and never receive database handles, fill constructors, settlement methods, reconciliation controls or risk-reset methods.

Trusted components:
- `PolicyEnforcedRiskGateway`: proposal authorization only.
- `SQLiteSettlementStore`: authoritative synthetic cash, holdings, fill idempotency, batch state, audit events and outbox in one database.
- `OfflineSettlementController`: validates synthetic bars/rules and coordinates transactions.
- `SellReservationOutboxWorker`: delivers settlement notifications with stable idempotency keys.
- `ReconciliationService`: read-only discrepancy detection by default; state changes require owner approval and append-only evidence.

## Atomic transaction

After input validation and risk authorization, stage deterministic fills. One `BEGIN IMMEDIATE` transaction must:
1. Verify batch claim and canonical request hash.
2. Recheck account, market registry, cash and inventory inside the transaction.
3. Insert fills under unique deterministic IDs.
4. Apply cash/inventory deltas using canonical Decimal-safe representations.
5. Append hash-chained portfolio audit events.
6. Insert SELL settlement messages into an outbox with stable unique idempotency keys.
7. Store the canonical result and transition batch to `COMMITTED_PENDING_OUTBOX`.
8. Commit all changes together.

A repeated identical batch returns the committed result without applying fills again. A changed payload under the same ID is rejected. Rollback leaves no partial fill, balance, audit, outbox or committed result.

Outbox delivery is asynchronous. Local commit does not prove the reservation service acknowledged settlement. Batch becomes `COMPLETE` only after every outbox item is acknowledged. The receiver must enforce idempotency on the stable key. If it cannot, automatic retry is unsafe and the item remains pending for trusted reconciliation.

## State machine

- `PROCESSING` -> `COMMITTED_PENDING_OUTBOX` after atomic portfolio commit.
- `COMMITTED_PENDING_OUTBOX` -> `COMPLETE` after all acknowledgements.
- Either nonterminal state -> `RECONCILIATION_REQUIRED` only through a trusted evidence-backed recovery procedure.
- No automatic deletion, reset, replay or force-completion.
- Reopen after restart only after checking DB identity, schema, SQLite integrity, audit chain, account identity and unresolved outbox state. Durable account ledger—not process identity—is the continuity anchor.

## Storage requirements

- Private, current-user-owned directory and DB; restrictive permissions; reject symlinks and hard links.
- SQLite foreign keys, FULL synchronous commits, trusted_schema OFF, explicit journal mode and bounded busy timeout.
- Versioned schema and forward-only explicit migrations; no destructive implicit migration.
- Decimal values as canonical text or scaled integers with explicit asset precision; never binary floats.
- Unique constraints for account/market/fill, batch/request, and outbox idempotency keys.
- Verify balance/inventory invariants before commit.
- Audit events bind account, batch, fill, previous hash and event hash. Local hash chains are not tamper-proof against privileged rewrites; external anchoring remains separate.
- Backup/restore must verify SQLite integrity, schema, audit chain, account identity and an independently stored anchor.

## Failure semantics

- Crash before atomic commit: no portfolio mutation; unresolved claim remains; do not automatically rerun risk authorization.
- Crash during SQL transaction: SQLite yields full commit or no commit.
- Crash after commit before delivery: durable outbox remains pending; retry only with receiver-side idempotency.
- Crash after receiver effect before local acknowledgement: resend same key; receiver must return prior outcome without repeating effect.
- Unknown outcome or non-idempotent receiver: stop and reconcile; never guess.
- Corrupt DB, audit mismatch, missing anchor, unsupported schema or inconsistent balances: fail closed.

## Required acceptance tests

1. Crash injection before transaction, after each SQL mutation, before commit and after commit.
2. Rollback leaves no fill, balance delta, audit event, outbox item or committed batch.
3. Successful commit contains all expected ledger, batch, audit and outbox rows.
4. Concurrent duplicate claims across processes produce one commit; identical replay returns stored result.
5. Changed payload under same batch ID is rejected.
6. Duplicate outbox delivery causes one receiver-side effect.
7. Crash after receiver effect/before local acknowledgement retries without duplicate effect.
8. Partial/zero SELL fills and multi-market exits preserve exact reservations.
9. Cash, inventory, fee, precision, overflow, negative quantity and account isolation tests.
10. Symlink/hardlink/permissions/path-race/contention tests.
11. Backup/restore, migrations, audit corruption and missing external anchor tests.
12. Python 3.11/runtime matrix, exact-head CI and independent security review.

## Rollout

1. Implement store/schema in a new module; retain current fail-closed path.
2. Add property, crash, concurrency, migration and outbox tests.
3. Build an offline adapter for existing ledger reads.
4. Integrate behind a new controller; keep storage outside agent capabilities.
5. Compare both implementations on deterministic fixtures.
6. Independent review attacks replay, crash, race, path, precision and authorization.
7. Only after evidence passes, propose retiring split journal/in-memory ledger. No automatic merge or PAPER transition.

## Non-goals

No exchange, broker, account, wallet, private API, orders, funding, withdrawals, PAPER activation, LIVE, leverage, shorts, derivatives or MEME_INTEL integration. This design does not establish profitability or win rate. Strategy evaluation remains separate, preregistered and independently reproducible with realistic costs, point-in-time data, untouched holdouts and multiple-testing controls.
