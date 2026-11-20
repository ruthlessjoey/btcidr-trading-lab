---
name: architecture-guardrails
description: Use when designing or changing system boundaries, modules, interfaces, milestones, or execution modes in the AI Trading Lab.
---

# Architecture Guardrails

Preserve approved architecture and prevent shortcuts from weakening separation of concerns.

## Required checks
1. Identify the owning layer: market data, strategy, risk, portfolio, persistence, or execution.
2. State allowed inputs and outputs at that boundary.
3. Keep exchange-specific details inside provider adapters. Shared interfaces remain provider-neutral.
4. Keep risk evaluation deterministic and fail-closed. It must not silently fetch data, read the clock, access credentials, or mutate portfolio state.
5. Preserve spot long-only scope: no shorts, leverage, margin, or derivatives.
6. Strategy may propose a stop; risk validates; portfolio owns the accepted stop.
7. Treat PAPER and LIVE as separate authorization states. LIVE remains unavailable; PAPER requires all approved safeguards and separate authorization.
8. Identify affected ADRs, progress records, sequencing gates, and tests before implementation.

## Design review questions
- Does this introduce a dependency in the wrong direction?
- Can malformed, stale, missing, or contradictory inputs reach a state-changing layer?
- Is a trust claim backed by a technical control, or merely a convention?
- Does the design preserve partial closures and cash/cost/P&L conservation?
- Does failure leave state unchanged and produce a stable, auditable refusal?
- Is the change within the current approved milestone?

Stop if a design requires protected paths, private exchange access, credentials, LIVE execution, or an unapproved milestone expansion. Never weaken an invariant to make a test pass.
