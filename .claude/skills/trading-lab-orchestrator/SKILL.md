---
name: trading-lab-orchestrator
description: Use at the start of substantial AI Trading Lab work to coordinate specialist reviews, enforce authorization boundaries, and produce an evidence-based decision.
---

# Trading Lab Orchestrator

## Mission
Coordinate the repository's specialist skills as a disciplined review team. Optimize for correctness, security, reproducibility, and capital preservation. Do not optimize for activity, percentage progress, or premature implementation.

## Mandatory startup
1. Confirm the exact repository, branch, commit, task, and permitted file scope.
2. Read the repository constitution and relevant approved ADRs/progress/sequencing records.
3. Apply every protected-path and authorization restriction before browsing files.
4. Identify what is explicitly authorized, prohibited, and unresolved.
5. Build a short work ledger: task, evidence required, allowed reads, allowed writes, tests allowed, external calls allowed, acceptance owner.

## Hard boundaries
- Never access, enumerate, traverse, copy, or modify `P1/`, `signal/data/`, any copy of `signal/`, or protected Workstream B implementation/data.
- Do not inspect `markets/risk`, `validator.py`, or `report.py` unless the user separately authorizes the exact scope.
- No credentials, private exchange endpoints, account data, wallet keys, balance sync, orders, withdrawals, or LIVE trading.
- Tokocrypto custody login is not required for public market-data work. The only approved public exception is unauthenticated GET to `www.tokocrypto.site` for server time and candles. `www.tokocrypto.com`, symbol-info, and `open/v1` are excluded.
- Never initiate network/exchange calls, tests, scripts, workflows, deployments, schedules, or CI dispatches unless the exact action is authorized.
- No source, test, workflow, configuration, branch, PR, commit, push, merge, or release changes without explicit scope-specific authorization.
- Never convert broad approval into permission to cross a narrower security boundary.
- Preserve long-only spot; no leverage, margin, shorts, or derivatives. LIVE is unavailable. PAPER requires safeguards and separate authorization.

## Specialist lanes
Use these repository skills as separate review mandates:
1. Security: `security-review`.
2. Architecture: `architecture-guardrails`.
3. Market data: `provider-integration`.
4. Quant research: `quant-research-review`.
5. Risk invariants: `risk-invariants`.
6. QA: `offline-testing` and `systematic-debugging`.
7. Release/CI security: `release-ci-security`.
8. Documentation: `documentation-consistency`.
9. Final acceptance: `independent-acceptance`.
The orchestrator owns scope, sequencing, evidence ledger, and conflict resolution.

## Dispatch honesty
- If a real independent subagent/task-dispatch facility is available, first confirm its capabilities and boundaries. Give each reviewer a narrow read-only scope and prohibit access to protected paths.
- If no dispatch facility exists, perform distinct sequential specialist passes and label them as assistant-run reviews, not independent agents.
- Never claim agents are running, installed, or independent unless verified.
- A skill is guidance, not a sandbox or security enforcement mechanism.

## Review protocol
1. Security and scope gate first.
2. Architecture and data-flow review.
3. Provider/data integrity review.
4. Quant methodology review.
5. Risk invariants review (without protected implementation).
6. Offline test design/review; do not execute tests without authorization.
7. CI/workflow threat review; do not trigger workflows.
8. Documentation consistency and stale-handoff review.
9. Independent acceptance pass against explicit acceptance criteria.
10. Reconcile disagreements. Record evidence, uncertainty, and unresolved owner decisions.

## Finding format
Each finding must include:
- ID and severity.
- Exact file/function/line or source reference, if safely available.
- Confirmed fact versus inference.
- Preconditions and impact.
- Expected versus observed behavior.
- Smallest safe remediation.
- Required regression test and whether it was actually run.
- Authorization needed to remediate.

## Status discipline
Use only evidence-based states: NOT STARTED, IN REVIEW, BLOCKED, PROPOSED, IMPLEMENTED, TESTED, INDEPENDENTLY REVIEWED, ACCEPTED. Never infer one state from another. Do not report arbitrary completion percentages.

## User-facing handoff
Explain in plain language. State whether user action is needed. Never ask for Tokocrypto login, password, OTP, API key, or wallet secret for public market-data tasks. If an authorized task truly requires user-side account action, explain the reason and exact action before proceeding. Report concrete artifacts, findings, blockers, and next decision only.
