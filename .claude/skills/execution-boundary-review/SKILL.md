---
name: execution-boundary-review
description: Use when reviewing any proposed paper/live execution, order-routing interface, emergency stop, or transition from research to execution.
---

# Execution Boundary Safety Review

## Absolute boundaries
- LIVE trading is unavailable. Never enable, implement, test against, or recommend enabling live order placement under current project policy.
- PAPER execution is separately gated and not automatically authorized by design, test, or documentation approval.
- No exchange credentials, private endpoints, account reads, balance sync, withdrawals, or wallet connection.
- Tokocrypto is the user's custody/funding venue, not a bot account.
- No network calls, workflows, deployments, or scheduled jobs without exact action-specific authorization.

## Review checklist
- Confirm research, strategy, risk, portfolio, and execution are separate components with explicit contracts.
- Strategy may propose; risk validates; portfolio owns accepted stops and position state.
- Fail closed on stale, invalid, incomplete, contradictory, or untrusted inputs.
- Define an emergency stop that blocks new actions and has clear state, precedence, and recovery authorization.
- Check idempotency, duplicate prevention, partial-fill handling, timeout ambiguity, and restart/replay semantics at the design level.
- Ensure execution cannot bypass risk approval or portfolio accounting.
- Ensure paper and live modes cannot be switched by an environment variable, config typo, or fallback.
- Require explicit mode display and an auditable transition record.
- Verify no credentials or account endpoints are reachable from research and market-data components.
- Do not confuse a successful market-data request with an accepted order or completed fill.

## Output
Provide a boundary diagram, fail-closed cases, bypass analysis, required safeguards, and explicit authorization gates. Never change execution mode or trigger an order.
