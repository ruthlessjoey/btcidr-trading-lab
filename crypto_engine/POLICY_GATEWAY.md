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
6. Send only the policy-permitted proposal deltas to the existing session-loss gateway.
7. The existing gateway independently re-reads equity/holdings, applies the session-loss latch and sell reservations, persists the risk journal and publishes the external audit anchor before returning authorization.

## Strategy-agent API

The public facade exposes only:
- `propose(proposals, timestamp)`
- `is_halted`

It deliberately does **not** expose sell-settlement or risk-reset controls. Sell settlement belongs to a future trusted execution/settlement service after a definitive fill or rejection is independently verified. Risk reset belongs to a separate owner-only control plane. Do not pass the raw inner gateway or any trusted dependency to agents.

## Security boundary and limitations

This is an in-process interface, not an OS/process security boundary. Python object introspection and same-process code execution can bypass private attributes; production strategy agents require separate process/container isolation and capability-limited IPC. Production ledger, mark/liquidity provider, owner policy/reset services and independent external audit-anchor adapter remain unimplemented. The wrapper does not create a broker, order router, paper account or exchange connection. No PAPER advancement or LIVE activity is authorized.

## Verification state

The focused implementation and adversarial tests are committed on the enforcement branch. The exact current branch head must pass the complete offline suite, static boundary check and compile check; CI and independent review are separate gates. This is not production-ready until all required gates and production services are complete.
