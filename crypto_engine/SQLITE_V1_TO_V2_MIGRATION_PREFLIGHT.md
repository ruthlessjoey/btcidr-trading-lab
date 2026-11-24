# SQLite v1 to reservation schema v2 migration preflight

This component is a read-only eligibility gate, not a migration. It requires a caller-owned consistent read transaction and `PRAGMA query_only=ON`. It never creates tables, updates metadata, changes outbox rows, or invents reservation identities.

## Fail-closed rules

The preflight rejects:
- Any schema other than the expected v1 table, column and exact normalized DDL definitions (including CHECK, primary-key and foreign-key constraints).
- Any schema version other than exactly `1`.
- Unexpected non-auto indexes or triggers.
- Any historical SELL fill, because v1 does not prove which durable reservation authorized each fill.
- Any historical outbox row, including acknowledged rows, because v1 outbox records are not bound to v2 allocation identity.
- Any `PROCESSING` or `RECONCILIATION_REQUIRED` batch.
- Broken audit hash chain, failed SQLite integrity check, or failed foreign-key check.
- A caller connection that is not in a transaction or is not query-only.

A clean result means only that the snapshot passed these preflight checks. It does not authorize migration, prove a backup, guarantee restore, or make a v2 store operational.

## Why historical SELL and outbox records are blocked

Do not synthesize reservation IDs, allocation IDs, versions, or ownership from old aggregate quantities. Historical SELLs and outbox rows require evidence-backed reconciliation by a trusted operator and independent review. Even acknowledged legacy outbox rows are blocked because the v1 schema has no per-allocation identity digest.

## Required future migration protocol

1. Stop all writers and obtain an independently verified backup.
2. Open the source DB read-only; set `PRAGMA query_only=ON`; begin a consistent transaction.
3. Run this preflight and retain the complete result and database identity in the migration evidence manifest.
4. If any blocker exists, abort. Preserve the original database and reconcile out-of-band with evidence; never auto-repair.
5. If eligible, run a separately reviewed migration against a verified copy, not the source.
6. Create v2 schema objects and update the schema version only inside one migration transaction.
7. Preserve all existing account, market, holdings, BUY fills, batches, audit and other permitted records exactly; no generated SELL reservation evidence.
8. Verify table definitions, row counts, foreign keys, SQLite integrity, audit chain and deterministic before/after manifests.
9. Restore-test the backup and migrated copy in isolation.
10. Obtain independent review before enabling the upgraded store.

The actual migration implementation is intentionally not part of this PR.

## Verification status

Thirteen focused tests are committed. They have not been executed against the exact PR head. Exact-head CI, Python 3.11, migration-copy/restore tests, crash injection and independent review remain pending.
