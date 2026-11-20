---
name: security-review
description: Use when reviewing trust boundaries, untrusted inputs, credentials, persistence, approvals, workflows, or security-sensitive code.
---

# Security Review

## Threat model first
Identify assets, actors, trust boundaries, attacker capabilities, and consequences. Distinguish accidental corruption, malicious remote input, and arbitrary hostile code already executing in-process; do not claim one defense covers all three.

## Mandatory rules
- Never access protected paths: `P1/`, `signal/data/`, or any copy of `signal/`.
- Never handle exchange credentials, private account endpoints, wallet secrets, orders, or withdrawals.
- Only approved unauthenticated Tokocrypto public GET endpoints may be considered: `www.tokocrypto.site` server time and candles. Reject `www.tokocrypto.com` unless separately approved.
- Treat provider responses, timestamps, numeric fields, identifiers, error strings, and serialized payloads as untrusted.
- Validate type, schema, range, finiteness, precision, timestamp units, and cross-field consistency at each trust boundary.
- Use allowlisted hosts and fixed endpoint paths. Do not construct arbitrary request destinations from untrusted data.
- Do not log secrets, sensitive payloads, or untrusted strings without safe normalization.
- Fail closed: invalid, ambiguous, stale, missing, or contradictory evidence must not produce eligibility or state mutation.
- Keep refusal paths state-preserving and test with before/after state comparisons.
- A hash chain detects some edits only when its trusted root is protected. It does not authenticate authorship if an attacker can rewrite and recompute the journal.
- An object type check, public hash, caller-supplied flag, or deterministic identifier is not proof of trusted origin.
- Process-local object identity or in-memory registries do not protect against arbitrary code in the same interpreter.

## Review output
For each finding record severity, affected boundary, preconditions, reproducible path, expected versus actual behavior, state impact, smallest safe remediation, and tests needed. Separate confirmed findings from hypotheses and author-side reports.

If the only proposed fix is an unverified trust convention, label the limitation and keep the dependent gate blocked. Never recommend enabling PAPER or LIVE as a workaround.
