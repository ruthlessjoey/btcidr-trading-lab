# Multi-market account risk gateway

## Purpose

`tmm_core.risk_gateway.RiskGateway` is the single proposal facade intended for future strategy agents. It is offline-only and does not submit, route, or simulate orders.

## Enforced at the facade

- Strategy callers provide target deltas only; the facade exposes no `holdings` or equity argument.
- Equity and inventory are read from an injected account-owned `InventoryLedger` before proposal authorization. The proposal market IDs must exist in that ledger snapshot.
- The shared `SessionLossGuard` observes ledger equity before authorizing any new exposure.
- Each resulting journal snapshot is saved transactionally through `RiskStateStore`, then its head is published through an independently held `AuditAnchor`. The facade returns no authorization if persistence or anchoring fails, and locks itself after such a failure.
- Startup restore requires both a persisted snapshot and a matching external audit anchor; missing or mismatched state refuses startup.
- Reset requires a positive decision from an injected `ResetAuthorizer`. Non-empty actor/reason/approval strings alone are not sufficient.
- SELL reservations must be settled through the same facade after a definitive fill or rejection.

## Interfaces that deployment must supply

The repository deliberately does not invent or embed trust credentials or a remote control-plane endpoint. A deployment must supply:
1. An account-owned ledger that derives balances and equity from the authoritative paper-account journal, not agent inputs.
2. An owner-controlled reset authorization service that authenticates the owner and verifies approval records.
3. An independently operated audit anchor whose storage and credentials are outside the application host's writable boundary.
4. An owner-controlled session-policy authorizer that approves the opening equity and mandatory non-null session-loss threshold before account initialization.
5. A private durable path for `SQLiteRiskStateStore`; the SQLite snapshot is local transactional persistence, not the external anchor.

Tests use synthetic in-memory implementations of the ledger, authorizer and anchor. These test doubles prove the facade's call contract only; they are not production trust services.

## Non-bypass requirement

Only pass a narrow proposal client to agents. Do not pass the `RiskGateway`'s private dependencies, `SessionLossGuard`, ledger, reset authorizer, state store, broker or order interface to an agent. Python object privacy is not an OS security boundary. The eventual agent runtime must isolate agents in separate processes/containers with no filesystem write access to risk state and no direct broker capability; the trusted orchestrator alone calls the gateway.

The current repository has no such agent runtime or paper broker. Therefore this code does not yet prove end-to-end agent non-bypass.

## Fail-closed deployment gate

Do not initialize or restore a paper account until real implementations of all four trust dependencies are available and independently tested. A failed ledger read, absent snapshot, invalid journal, failed anchor verification, failed anchor publish, or rejected reset must result in no proposal authorization. No network or exchange integration is included here. LIVE remains absent/disabled.
