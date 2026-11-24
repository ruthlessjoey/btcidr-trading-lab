# Policy-enforced risk gateway

`tmm_core.policy_gateway.PolicyEnforcedRiskGateway` composes the existing account risk gateway with the deterministic exposure policy.

## Required trusted dependencies

- `InventoryLedger`: authoritative account equity and complete market holdings.
- `ExposureMarkProvider`: fresh per-market unit valuation and executable BUY-liquidity capacity for every held market.
- `ExposurePolicyAuthorizer`: owner approval of the complete exposure policy record. A production implementation must enforce policy versioning and prohibit unapproved limit increases.
- Existing session-policy, reset, state-store and external-audit-anchor services.

The factory refuses startup unless the exposure-policy authorizer returns exactly `True`. Restore repeats this authorization; a policy supplied by an agent is never accepted.

## Proposal flow

1. Read complete equity and holdings from the trusted ledger.
2. Reject empty inventory or any proposed market absent from the ledger.
3. Obtain marks for the exact complete holdings market set.
4. Reject missing, stale, future, malformed or incomplete mark evidence.
5. Apply shared gross, per-market, base-asset, quote-asset and executable-liquidity limits.
6. Send only the policy-permitted proposal deltas to the underlying risk gateway.
7. The underlying gateway independently re-reads equity/holdings, applies the session-loss latch and sell reservations, persists the risk journal and publishes the external audit anchor before returning authorization.

## Agent API

Agents should receive only the facade methods:
- `propose(proposals, timestamp)`
- `settle_sell(...)` for the trusted fill/rejection settlement service, not general strategy agents
- `is_halted`

Reset should be held by a separate owner-only control plane; the current wrapper exposes it only for trusted orchestration and must not pass it to strategy agents.

## Limitations

This is an integration facade, not a complete production trust boundary. Python object introspection and same-process code execution can bypass private attributes; production strategy agents require separate process/container isolation and capability-limited IPC. Production ledger, mark/liquidity provider, owner policy/reset services and independent external audit-anchor adapter remain unimplemented. The wrapper does not create a broker, order router, paper account or exchange connection. No PAPER advancement or LIVE activity is authorized.

## Verification state

The implementation and focused tests are committed on the enforcement branch. Exact-head test execution, CI and independent review remain pending; do not treat this change as passed or production-ready until those checks are recorded.
