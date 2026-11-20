---
name: risk-engine-invariants
description: Use when reviewing or designing risk calculations, position sizing, exposure limits, stop handling, or paper-accounting invariants in authorized source files.
---
# Risk Engine Invariants

## Scope
Only review explicitly authorized, unprotected files. Never inspect `P1/`, `signal/data/`, any `signal/`, or protected Workstream B content.

## Non-negotiable rules
- Crypto spot only; long-only. No leverage, margin, shorts, or derivatives.
- Strategy may propose a stop; risk validates it; portfolio owns the accepted stop.
- Partial closures must be supported in paper accounting.
- Emergency stop is required before paper execution.
- PAPER safeguards require separate approval; LIVE remains unavailable.
- Tokocrypto is the user's funding/custody venue, not a bot account.

## Invariants
- Reject non-finite, negative, invalid-zero, overflowed, or dimensionally inconsistent values.
- Position sizing respects paper capital, configured risk budget, exposure caps, precision constraints, and fee assumptions.
- Stops must be valid relative to entry/reference and must not be silently widened downstream.
- Partial closes conserve quantity and cost basis within defined rounding tolerances.
- Repeated events must not double-count fills, fees, realized PnL, or exposure.
- Missing/stale inputs fail closed; no default-to-unlimited behavior.
- Accounting is deterministic with explicit rounding policy.

## Output
List each invariant, owning layer, negative/boundary test, and remaining ambiguity. Passing invariant tests is not evidence of profitability.
