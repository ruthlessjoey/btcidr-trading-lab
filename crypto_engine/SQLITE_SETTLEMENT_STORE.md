# SQLite atomic settlement store

`tmm_core.sqlite_settlement_store.SQLiteSettlementStore` is a trusted, offline-only accounting primitive. It has no network, exchange, broker, account, wallet, PAPER or LIVE capability. Never pass the store, its path, or a connection to strategy agents.

## Transaction boundary

`apply_batch` validates the batch and all fill/outbox values before opening its write transaction. Under SQLite `BEGIN IMMEDIATE`, it claims the batch, reads authoritative cash/holdings, verifies market/fill/inventory/cash invariants, writes the resulting balances, fill rows, hash-chained audit events, SELL settlement outbox rows, and the canonical batch result. These changes commit or roll back together.

The store normalizes fills and SELL reservation messages, builds a versioned canonical request envelope (account, currency, batch ID, timestamp, fills and outbox), and computes SHA-256 internally. An identical batch ID and canonical payload returns the stored result. Reusing an ID with any changed payload field is rejected; callers cannot choose the authoritative replay digest. Fill IDs and outbox idempotency keys are unique database keys.

## Outbox

A batch with SELL settlement messages commits as `COMMITTED_PENDING_OUTBOX`. A trusted worker may read `pending_outbox()`, deliver each message to a receiver that enforces the same idempotency key, then call `acknowledge_outbox` with the receiver's durable receipt. The batch becomes `COMPLETE` after all messages are acknowledged.

For every market, the sum of SELL fill quantities must equal the sum of nonzero outbox filled quantities. Zero-fill reservation notifications are allowed. This is an aggregate invariant; reservation identity/ownership still requires integration-level proof. The store does not implement a network worker or receiver. Never retry an ambiguous delivery unless the receiver guarantees idempotency. An acknowledgement receipt is evidence supplied by the trusted adapter, not independently verified by this module. A receipt digest and outbox acknowledgement audit event are committed atomically with the acknowledgement; the batch result is updated to COMPLETE in the same transaction after the final acknowledgement.

## Audit resource envelope

New audit events are limited to 64 KiB of canonical UTF-8 JSON each. The retained audit chain is limited to 1,000,000 events and 256 MiB of aggregate canonical event bytes. The writer checks these limits inside the same SQLite transaction as the accounting mutation; an oversized event or exhausted history budget aborts and rolls back the entire batch/acknowledgement.

The read-only v1 migration preflight applies the same limits before parsing or hashing audit payloads. Both the preflight and store verifier also treat SQLite text-decoding errors, including invalid UTF-8 stored in an audit event, as a failed audit chain rather than propagating an exception. Historical audit data above any limit is a migration blocker. It is never truncated, skipped, rewritten, or partially accepted. These limits are a deliberate operational envelope for this store; any future increase requires a reviewed change to both writer and preflight, plus resource and compatibility tests.

## Storage and limits

- Uses SQLite foreign keys, FULL synchronous mode, DELETE journaling, trusted_schema OFF and bounded busy timeout. Startup runs PRAGMA integrity_check and verifies the local audit chain before accepting the store. Existing databases must contain the complete expected table and column layout and a recognized schema-version row; incomplete or altered schemas are rejected rather than silently recreated. Only a genuinely empty database is initialized automatically.
- Requires an absolute path in an existing private directory; rejects symlinked and hard-linked database files and enforces mode 0600.
- Database schema version is explicit; unsupported versions fail closed. No automatic migration, backup/restore or external audit anchoring is implemented.
- Monetary values use canonical Decimal text, not binary floating point.
- Local audit chain detects accidental/tampering changes when verified, but a privileged actor able to rewrite the database can rewrite the chain. External anchoring is still required.
- Filesystem path validation is defense-in-depth; this implementation does not claim race-free protection against a hostile local process replacing path components between validation and SQLite open.
- The current offline settlement controller is not yet integrated with this store. The old journal + in-memory ledger + callback flow remains non-atomic until a separately reviewed integration replaces it.

## Verification boundary

Focused unit tests cover atomic state commit, replay, changed request hash, rollback on invalid SELL, outbox acknowledgement, duplicate fill ID, account identity and audit corruption. Exact-head CI, Python 3.11, cross-process concurrency/crash-injection testing, integration, independent security review and production operations procedures remain required.

This is an implementation milestone, not an install-ready trading system and not evidence of profitability.
