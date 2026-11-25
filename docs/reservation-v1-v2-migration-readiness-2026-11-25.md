# Reservation Database Migration — Readiness and Acceptance Plan

**Date:** 25 November 2026 (Asia/Makassar)  
**Repository:** `ruthlessjoey/btcidr-trading-lab`  
**Documentation base:** `main` at `0426e1ecd5bd01913a568272792c355c4b7059c7`  
**Status:** Design / preflight requirements only. No migration implementation or execution is authorized by this document.

## 1. Decision summary

Candidate PR #150 now requires the complete, exact reservation schema v2 and exact per-fill allocations before any SELL. This closes the legacy v1 SELL bypass. It intentionally leaves older databases unable to SELL until a separately reviewed v2 rollout.

- BUY-only operation may continue on an exact legacy v1 settlement schema.
- SELL is blocked on v1 databases and on the earlier reservation-v2 schema.
- Schema upgrade, inventory bootstrap, historical reconciliation and remote receiver are separate deliverables.
- No existing user or production database is to be modified by this plan.

**No automatic backfill is permitted.** Existing holdings are not proof of user-approved sell reservations. An earlier reservation without persisted expiry cannot be given an invented expiry timestamp. Unknown or unreconciled rows remain blocked.

## 2. Relevant schema versions

### 2.1 Settlement v1 without reservation tables

The offline settlement store's base schema includes `markets`, `batches`, `fills`, `account`, `holdings`, `audit` and the legacy `outbox`. A v1 database has no `reservations`, `reservation_allocations` or `reservation_outbox` tables.

Candidate PR #150 rejects SELLs against this v1 state with a reservation-v2-required error. BUY-only batches remain available. PR #150 does not migrate v1 databases.

### 2.2 Earlier reservation v2 (before lifecycle/expiry)

The earlier reservation-v2 `reservations` table contained:

- `reservation_id`, `account_id`, `market_id`
- `base_asset`, `quote_asset`
- `authorized_quantity`, `consumed_quantity`
- `created_at`, `version`, `status`

Its status CHECK allowed `ACTIVE`, `RELEASED`, `CANCELLED` and `EXPIRED`. It did not persist `expires_at`, did not include `PENDING`, and had the earlier version constraint. It also included dependent `reservation_allocations` and `reservation_outbox` tables. Their rows and foreign-key relationships are historical accounting evidence and must not be discarded or regenerated.

The exact earlier DDL was read from the candidate baseline at PR #143 head `4589a2f6548085ffbb8d88e814a7df2983c4b1f7`.

### 2.3 Current lifecycle reservation v2

The current schema adds:

- `expires_at INTEGER NOT NULL CHECK(expires_at > created_at)`
- `PENDING` as a reservation state
- a positive, bounded SQLite integer version constraint
- explicit PENDING→ACTIVE, release, cancel and expire transitions
- version-checked compare-and-set updates and settlement audit events

The current DDL is defined in `crypto_engine/tmm_core/reservation_schema_v2.py` on the PR #148–#150 candidate chain. Exact DDL verification, parent-table DDL checks, foreign-key enforcement, CHECK enforcement, foreign-key integrity checks and unexpected schema-object rejection are required before operations.

The earlier and current v2 definitions are intentionally not treated as compatible. The verifier fails closed on a mismatch. This plan does not relax that check.

## 3. Source database classification

| Source database state | Required disposition | SELL allowed? |
|---|---|---|
| Exact v1, no reservation tables | Read-only preflight, then separately approved bootstrap / migration | No |
| Exact earlier v2 without `expires_at` | Read-only preflight plus historical reconciliation and explicit expiry mapping | No |
| Current exact v2 | Verify schema, foreign keys, audit, account/market identity and outboxes | Only through exact per-fill allocation |
| Partial reservation tables | Reject; preserve source bytes and investigate | No |
| Unexpected DDL, trigger, index, TEMP shadow or FK violation | Reject; security review required | No |
| Corrupt audit chain, unresolved batch or outbox ambiguity | Hold for reconciliation | No |

No source database should be upgraded in place during initial acceptance. Any future migration must operate on a verified disposable copy and produce a new candidate database file.

## 4. Required read-only preflight

A future preflight must not create, update, delete, rename or vacuum any database object. It must report a fixed, bounded result with source file identity, schema classification, pass/fail reasons and evidence hashes. It must fail closed on malformed types, unknown objects, schema drift, exceptions or resource-limit breaches.

### 4.1 File and environment identity

- Verify the input is an explicitly selected regular file, not a directory, symlink or device.
- Reject unexpected file size, path, permissions or unsupported filesystem conditions.
- Work only on a separately created disposable copy; never select an implicit default database path.
- Record SHA-256 of the source and copied file; verify the copy hash before opening it.
- Open read-only using SQLite URI read-only mode and refuse to create a missing database.
- Do not expose database paths or contents to strategy agents.

### 4.2 Schema and pragma checks

- Classify only exact known v1, earlier-v2 and current-v2 schema definitions.
- Verify exact parent table DDL, column order, primary keys, CHECKs, foreign keys and collations.
- Verify foreign-key and CHECK enforcement on any isolated connection used in a later migration test.
- Run `PRAGMA integrity_check` and `PRAGMA foreign_key_check`; bound result rows and runtime.
- Inspect `main.sqlite_master` and `temp.sqlite_master` for unexpected triggers, indexes, views, shadow objects and case-variant targets.
- Reject partial reservation schemas and unexpected persistent or TEMP triggers.
- Matching column names alone do not establish schema compatibility.

### 4.3 Settlement, audit and outbox checks

- Verify the complete expected settlement schema, not merely reservation tables.
- Verify the full settlement audit hash chain.
- Require no `PROCESSING` or `RECONCILIATION_REQUIRED` batches.
- Require every legacy outbox record to be accounted for; unresolved deliveries block migration acceptance.
- For earlier-v2 databases, verify each allocation's batch, fill, reservation, account, market, side, quantity and version against persisted source rows.
- Recompute canonical reservation-outbox payload hashes and reject mismatches.
- Do not change legacy request hashes, batch results, fills, outbox identifiers, receipts or historical audit events.

### 4.4 Holdings and inventory reconciliation

- Reconcile each registered market's current holding to persisted BUY/SELL fill history and settlement ledger.
- Require long-only, nonnegative holdings and valid account/quote-currency identity.
- V1 databases have no historical reservation ledger. Existing holdings must not automatically become sell-authorized reservations.
- Any bootstrap quantity, account/market identity, created-at time and expiry must have an explicit operator-approved source. Missing evidence is a hard blocker.
- Across active reservations for a market, total unconsumed authorized quantity must not exceed reconciled available base inventory. Any mismatch requires manual reconciliation, not automatic trimming.

## 5. Required design for earlier-v2 migration

A migration from the earlier reservation-v2 DDL is a preservation task, not a table reset.

Before implementation, the design must specify and test:

1. A complete, immutable source backup and verified disposable working copy.
2. Exact source schema fingerprint and source row counts.
3. An explicit, evidence-backed `expires_at` mapping for every legacy reservation row. There is no default expiry and no fabricated timestamp.
4. Preservation of reservation IDs, account/market/base/quote identities, authorized and consumed quantities, version, status and every allocation/outbox row.
5. A one-to-one mapping from each legacy row to its current-schema representation.
6. Referential integrity across `reservations`, `reservation_allocations`, `reservation_outbox`, `fills` and `batches`.
7. Receipt, idempotency-key and canonical-payload integrity for any pending delivery.
8. An audit migration event appended only after preconditions pass and committed atomically with schema conversion.
9. Post-migration exact-schema verification, integrity check, foreign-key check, full audit verification, row-count equality and content reconciliation.
10. A rollback plan that leaves the source file untouched and exposes no partial state if any postcondition fails.

A failed migration must leave the original database byte-for-byte unchanged. No partial state may be exposed to settlement code.

## 6. Required v1 bootstrap design

A v1 database has no reservation rows to migrate. A separate bootstrap design must identify which current holdings are explicitly approved to become sellable reservations.

Minimum requirements:

- Require user/operator-supplied authorization for each account/market quantity and expiry.
- Do not infer reservation quantity from strategy signals, stale positions, historical highs or an unverified holdings snapshot.
- Reject quantities above reconciled long inventory.
- Use unique reservation IDs and an auditable, idempotent bootstrap manifest.
- Create reservations in `PENDING`; activate only through the explicit lifecycle transition.
- Keep SELL disabled until active reservation state is verified and the new database passes migration acceptance tests.
- Preserve the original v1 source and link its hash to the bootstrap manifest hash and migrated database hash.

A market without an approved bootstrap row remains unsellable.

## 7. Required test and reliability matrix

| Test group | Required evidence |
|---|---|
| Source classification | Exact v1, old-v2, current-v2, partial, unknown and corrupted schema fixtures |
| Read-only proof | Source database hash unchanged after preflight; read-only open rejects writes |
| DDL | Exact schema and parent contracts, quoted literals, CHECKs, FK targets and shadow-object rejection |
| Inventory | Under/over allocation, negative holdings, mismatch, multiple reservations, mixed markets |
| Historical data | Row counts, field equality, foreign-key references, hashes and audit chain preserved |
| Outbox | Pending, acknowledged, duplicate receipt, changed payload, missing sender/receiver state |
| Transactions | Injected exception at every migration step; original file unchanged |
| Concurrency | Competing writers/readers, lock timeout and repeated bootstrap idempotency |
| Crash and restore | Termination before, during and after commit; restore from backup; repeat preflight |
| Resources | Bounded file size, row count, JSON size, decimal precision, SQL result size and runtime |
| Version matrix | Python 3.11 and 3.13 with supported SQLite runtime |
| Independent review | Separate reviewer validates code, tests, hashes, migration manifest and rollback evidence |

The six isolated suites on the PR #150 candidate validate reservation schema/lifecycle/allocation/settlement/receiver behavior. They do not validate an implemented migrator, backup/restore, process crash, production receiver or the full repository test suite.

## 8. Operational rollout gate

Migration implementation and execution require a separate approval naming:

- the specific source database class and source file hash,
- whether the task is v1 bootstrap or earlier-v2 upgrade,
- the disposable test-copy location and backup/restore method,
- the exact market/account reservation bootstrap manifest,
- the expiry evidence source,
- the operator who authorizes each active reservation,
- the exact code commit, schema fingerprint and rollback conditions.

Approval to continue general engineering is not blanket authorization to mutate an existing database. No production database, user account, live wallet, exchange connection or real-money execution may be used.

## 9. Role assignments

- **Commander / coordinator:** freeze scope, sequence work, maintain decision/evidence register and prevent hidden rollout assumptions.
- **SQLite migration architect:** specify read-only preflight, source classifications, transactional conversion and rollback.
- **Ledger/accounting specialist:** reconcile balances, fills, reservation allocations, batches, audit events and outboxes.
- **Security specialist:** inspect schema spoofing, TEMP/main shadowing, malformed data, unexpected objects and trust-boundary bypasses.
- **Reliability specialist:** run concurrency, crash, restore, file-copy and resource-exhaustion drills on disposable copies.
- **Test engineer:** pin exact SHAs, Python/SQLite versions, commands, test output and fixture provenance.
- **Independent acceptance reviewer:** assess source and target evidence without authoring the migration implementation.
- **Project owner:** explicitly approve source class, migration manifest, market quantities, expiry mapping and any later deployment or trading activation.

Strategy agents remain proposal-only and must never receive SQLite handles, reservation mutation functions or migration authority.

## 10. Readiness decision as of 25 November 2026

- Reservation lifecycle and per-fill SELL allocation candidate code: implemented in stacked draft PRs.
- PR #149 receiver hardening: 13/13 isolated tests passed on Python 3.11 and 3.13.
- PR #150 reservation/settlement chain: 110/110 isolated tests passed on Python 3.11 and 3.13 on the tested tree.
- Legacy SELL bypass: blocked in candidate PR #150; v1 remains BUY-only.
- Earlier-v2 → current-v2 migration: not implemented.
- V1 bootstrap and existing inventory authorization: not implemented.
- Remote authenticated receiver and real external business effect: not implemented.
- Full multi-process crash/restore and independent adversarial acceptance: pending.
- Profitability / high-win-rate evidence: not established.
- Install readiness: NOT READY.
- Trading readiness: NOT READY.
- PAPER activation: ON HOLD.
- LIVE trading: DISABLED / ABSENT.
- Overall whole-project completion: UNRATED.

This document is a migration acceptance design, not a migration script, release authorization, production runbook or trading permission.
