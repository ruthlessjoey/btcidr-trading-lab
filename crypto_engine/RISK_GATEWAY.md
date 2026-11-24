# Multi-market account risk gateway

## Purpose

`tmm_core.risk_gateway.RiskGateway` is a lower-level trusted proposal/reset service. It is offline-only and does not submit, route, or simulate orders. Strategy agents must not receive this raw object. The strategy-facing wrapper is `tmm_core.policy_gateway.PolicyEnforcedRiskGateway`, which adds owner-approved exposure/liquidity policy and exposes only proposal and halt-status methods.

## Enforced at the lower-level gateway

- Strategy callers provide target deltas only; the facade exposes no holdings or equity argument.
- Equity and inventory are read from an injected account-owned `InventoryLedger` before proposal authorization. Proposal market IDs must exist in that ledger snapshot.
- The shared `SessionLossGuard` observes ledger equity before authorizing any new exposure.
- Each resulting journal snapshot is saved transactionally through `RiskStateStore`, then its head is published through an independently held `AuditAnchor`. No authorization is returned if persistence or anchoring fails; the gateway locks after such a failure.
- Startup restore requires both a persisted snapshot and a matching external audit anchor; missing or mismatched state refuses startup.
- Reset requires a positive decision from an injected `ResetAuthorizer`. Non-empty actor/reason/approval strings alone are not sufficient.
- SELL reservations remain outstanding until the trusted execution/settlement service reports a definitive fill or rejection. Strategy agents must not receive the lower-level settlement or reset controls.

## SQLite local storage hardening

`SQLiteRiskStateStore` now:
- Requires the immediate parent directory to be owned by the current user and private from group/other users on POSIX.
- Rejects symlinked parent components, symlinked database files, non-regular files and hard-linked database files.
- Creates a new database with restrictive permissions and enforces mode `0600`.
- Uses SQLite full synchronous commits, foreign keys, trusted-schema disablement and DELETE journaling.
- Revalidates storage path integrity around database use.

This is defense-in-depth for a local offline deployment, not a substitute for host security, encrypted storage, backup controls or an independently operated audit anchor. POSIX permission checks are platform-specific; deployment must verify equivalent controls on other operating systems.

## Interfaces that deployment must supply

The repository deliberately does not invent or embed trust credentials or a remote control-plane endpoint. A deployment must supply:
1. An account-owned ledger deriving balances/equity from an authoritative paper-account journal, not agent inputs.
2. A trusted execution/settlement service that verifies definitive fills/rejections and settles reserved SELL quantities.
3. An owner-controlled reset authorization service authenticating the owner and verifying approval records.
4. An independently operated audit anchor whose storage and credentials are outside the application host's writable boundary.
5. An owner-controlled session-policy authorizer approving opening equity and a mandatory non-null session-loss threshold.
6. An owner-controlled exposure-policy authorizer that enforces policy versioning and prevents unapproved limit increases.
7. A trusted mark/liquidity provider supplying fresh per-market account-currency valuations and executable BUY capacity.

Tests use synthetic in-memory implementations of these services. Test doubles prove call contracts only; they are not production trust services.

## Non-bypass requirement

Only pass the narrow `PolicyEnforcedRiskGateway` proposal facade to agents. Do not pass the raw `RiskGateway`, its private dependencies, `SessionLossGuard`, ledger, mark provider, reset authorizer, state store, broker or order interface to an agent. Python object privacy is not an OS security boundary. The eventual agent runtime must isolate agents in separate processes/containers with no filesystem write access to risk state and no direct broker capability; the trusted orchestrator alone calls the gateway.

The current repository has no such agent runtime or paper broker. Therefore this code does not yet prove end-to-end agent non-bypass.

## Fail-closed deployment gate

Do not initialize or restore a paper account until real implementations of all trust dependencies are available and independently tested. A failed ledger read, absent snapshot, invalid journal, failed anchor verification, failed anchor publish, missing/stale marks, rejected exposure policy or rejected reset must result in no proposal authorization. No network or exchange integration is included here. PAPER advancement remains separately withheld. LIVE remains absent/disabled.
