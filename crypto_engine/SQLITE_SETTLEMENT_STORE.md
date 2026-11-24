# SQLite atomic settlement store

`tmm_core.sqlite_settlement_store.SQLiteSettlementStore` is a trusted, offline-only accounting primitive. It has no network, exchange, broker, account, wallet, PAPER or LIVE capability. Never pass the store, its path, or a connection to strategy agents.

## Transaction boundary

`apply_batch` validates the batch and all fill/outbox values before opening its write transaction. Under SQLite `BEGIN IMMEDIATE`, it claims the batch, reads authoritative cash/holdings, verifies market/fill/inventory/cash invariants, writes the resulting balances, fill rows, hash-chained audit events, SELL settlement outbox rows, and the canonical batch result. These changes commit or roll back together.

An identical batch ID and request hash returns the stored result. Reusing an ID with a different request hash is rejected. Fill IDs and outbox idempotency keys are unique database keys.

## Outbox

A batch with SELL settlement messages commits as `COMMITTED_PENDING_OUTBOX`. A trusted worker may read `pending_outbox()`, deliver each message to a receiver that enforces the same idempotency key, then call `acknowledge_outbox` with the receiver's durable receipt. The batch becomes `COMPLETE` after all messages are acknowledged.

The store does not implement a network worker or receiver. Never retry an ambiguous delivery unless the receiver guarantees idempotency. An acknowledgement receipt is evidence supplied by the trusted adapter, not independently verified by this module.

## Storage and limits

- Uses SQLite foreign keys, FULL synchronous mode, DELETE journaling, trusted_schema OFF and bounded busy timeout.
- Requires an absolute path in an existing private directory; rejects symlinked and hard-linked database files and enforces mode 0600.
- Database schema version is explicit; unsupported versions fail closed. No automatic migration, backup/restore or external audit anchoring is implemented.
- Monetary values use canonical Decimal text, not binary floating point.
- Local audit chain detects accidental/tampering changes when verified, but a privileged actor able to rewrite the database can rewrite the chain. External anchoring is still required.
- Filesystem path validation is defense-in-depth; this implementation does not claim race-free protection against a hostile local process replacing path components between validation and SQLite open.
- The current offline settlement controller is not yet integrated with this store. The old journal + in-memory ledger + callback flow remains non-atomic until a separately reviewed integration replaces it.

## Verification boundary

Focused unit tests cover atomic state commit, replay, changed request hash, rollback on invalid SELL, outbox acknowledgement, duplicate fill ID, account identity and audit corruption. Exact-head CI, Python 3.11, cross-process concurrency/crash-injection testing, integration, independent security review and production operations procedures remain required.

This is an implementation milestone, not an install-ready trading system and not evidence of profitability.
