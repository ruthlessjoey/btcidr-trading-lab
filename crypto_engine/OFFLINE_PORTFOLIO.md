# Offline synthetic portfolio ledger

`tmm_core.offline_portfolio` adds a deterministic, thread-safe synthetic spot ledger for offline research and test composition.

## Scope and trust boundary

- Synthetic fills only; this module does not simulate or submit exchange orders.
- No network, provider, account, wallet, broker, order router, PAPER or LIVE capability.
- A trusted offline simulator supplies definitive fill records. Strategy agents must never receive direct ledger mutation access.
- Spot-only, long-only: BUY consumes quote cash plus fee; SELL cannot exceed held inventory.
- Decimal accounting; duplicate fill IDs are idempotently ignored.
- Exact market registry; quote currency must equal the account currency. No implicit FX conversion.
- Complete, fresh, non-future marks are mandatory before equity is available.
- Audit events are hash-chained and returned as copies. The local chain is tamper-evident only relative to its retained head; independent external anchoring is still required.

## Interfaces

- `apply_fill(SyntheticFill)`: trusted simulator-only mutation.
- `update_marks(...)`: trusted offline mark ingestion; exact market coverage required.
- `snapshot_holdings(account_id)`, `snapshot_equity(account_id)`: read-only ledger protocol methods.
- `snapshot_cash(account_id)`, `audit_snapshot(account_id)`, `verify_audit_chain(account_id)`: local inspection.

This is an in-memory synthetic implementation, not a production account ledger, durable journal, trusted market-data feed, execution simulator, or permission to activate PAPER.
