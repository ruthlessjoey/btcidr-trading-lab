---
name: risk-invariants
description: Use when changing or reviewing risk configuration, eligibility decisions, sizing, stops, or portfolio risk integration.
---

# Risk Invariants

- Risk evaluation is deterministic and fail-closed over explicitly supplied inputs.
- It does not fetch data, read a clock, access credentials, or own mutable portfolio state.
- Validate price/data freshness, symbol listing, account snapshot consistency, strategy decision shape, notional, cash, exposure, risk limits, and stop geometry.
- Use exact Decimal arithmetic and explicit rounding policy for financial values.
- Reject non-finite, negative, malformed, out-of-range, stale, or inconsistent inputs.
- Keep strategy proposals, risk validation, and portfolio ownership separate.
- Preserve long-only spot behavior; prohibit leverage, shorts, margin, and derivatives.
- A `RiskDecision` object is not authenticated merely because its type or status says ELIGIBLE.
- A `RiskConfig` instance is not necessarily validated merely because it has the expected dataclass type. Enforce validation at every public consumption boundary, not only in an optional builder.
- Public hashes and caller-supplied approval references do not prove that a trusted risk engine issued an approval.
- Direct construction, deserialization, mutation, replay, or alternate API paths must not bypass eligibility and provenance checks.

## Required tests
Cover builder and direct construction, every public evaluation entry point, forged/modified decisions, missing/deleted attributes, serialization round-trips, timestamp boundaries, Decimal edge cases, rounding ties, stale data, stop behavior, and state-preserving refusal paths.

## Claims discipline
State exactly what is checked and what is trusted. If decision provenance cannot be technically enforced at the ledger boundary, do not call the fill risk-authorized; document the remaining trust assumption and keep PAPER authorization gated.
