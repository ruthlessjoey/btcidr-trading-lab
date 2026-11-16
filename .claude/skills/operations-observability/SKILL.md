---
name: operations-observability
description: Use for operational design, health and freshness monitoring, incident response, auditability, and safe runbooks for the AI Trading Lab.
---

# Operations and Observability

## Mission
Make system behavior understandable and recoverable without widening execution authority. Prefer safe detection and clear failure states over automatic retries, hidden recovery, or unattended actions.

## Authorization and boundaries
- Confirm the exact files, environment, and actions authorized before inspection or change.
- Never access protected paths or protected Workstream B implementation/data.
- Never request or use exchange credentials, private endpoints, account data, wallet keys, balance sync, orders, withdrawals, or LIVE trading.
- Tokocrypto public access remains limited to unauthenticated GET on `www.tokocrypto.site` for server time and candles; no `.com`, symbol-info, or `open/v1`.
- Do not run workflows, schedules, scripts, network checks, deployments, or CI without exact explicit authorization.
- A monitoring design does not authorize a live monitor, notification, recurring job, or automated remediation.
- Skills are guidance, not sandboxing or technical permission enforcement.

## Operational design checklist
1. Define service/component ownership, dependencies, expected operating modes, and explicit non-goals.
2. Define health separately from readiness, freshness, correctness, and availability.
3. Make data age measurable using source event time and receive time; define thresholds per timeframe and fail closed when freshness cannot be established.
4. Distinguish missing, stale, malformed, delayed, rejected, and unavailable data; do not silently substitute a last-known value as current.
5. Use structured, bounded, sanitized logs. Exclude secrets, credentials, private account information, raw untrusted payloads, and sensitive URLs.
6. Preserve audit provenance for inputs, decisions, configuration versions, and operator actions without exposing protected data.
7. Design incident severity, stop conditions, escalation owner, recovery prerequisites, and post-incident review.
8. Prefer manual, reversible recovery. Automatic retries or remediation require explicit policy, bounded attempts, idempotency, and authorization.
9. Treat emergency stop as a first-class operational control; test design and implementation separately, with explicit authorization for any execution.
10. Document backup/restore and data-retention expectations before relying on persistent state.

## Trading-specific controls
- A stale, incomplete, contradictory, or untrusted market input must not produce an actionable signal.
- Operational health never overrides risk rejection.
- PAPER remains gated by approved safeguards, emergency stop, and separate authorization; LIVE is unavailable.
- Alerts are evidence of a condition, not permission to trade or change risk settings.

## Output
Provide a component inventory, health/readiness/freshness definitions, alert and incident matrix, safe runbook, audit requirements, failure modes, and unverified assumptions. Clearly label designs that have not been implemented or tested.
