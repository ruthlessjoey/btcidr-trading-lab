---
name: portfolio-accounting-review
description: Use when reviewing portfolio state, positions, fills, fees, partial closures, realized and unrealized PnL, or accounting persistence.
---

# Portfolio Accounting Review

## Scope and safety
This skill is a design/source-review mandate only. Respect all protected-path restrictions. Do not inspect protected Workstream B implementation or data. Do not access accounts, wallets, exchange credentials, or private endpoints. Do not execute trades or mutate ledgers.

## Invariants to review
- Use exact decimal arithmetic for monetary values and quantities; avoid binary floating point for ledger state.
- Every position and fill must have stable identity, source provenance, and deterministic ordering.
- Partial closures must preserve remaining quantity and allocate entry cost, fees, and realized PnL consistently.
- Enforce quantity conservation: opening quantity equals remaining quantity plus all closed quantities, subject only to explicitly modeled adjustments.
- Reject negative quantities, impossible fee values, over-closes, duplicate fill application, and inconsistent asset/quote units.
- Make fill ingestion idempotent; replaying the same event must not double-count.
- Separate order intent, exchange acknowledgement, fill, and portfolio position. Public candles never prove a fill.
- Keep realized PnL, unrealized PnL, cash, reserved funds, and fees distinct.
- Define treatment for missing, late, corrected, duplicated, and out-of-order events.
- Preserve audit history; do not silently rewrite prior ledger events.
- Make reconciliation an explicit, authorized capability; do not infer exchange balances from market data.

## Review output
Provide an invariant table with definition, failure mode, evidence location, deterministic test case, and unresolved policy. Clearly distinguish design review from implementation verification.
