---
name: trading-lab-orchestrator
description: Use at the start of substantial AI Trading Lab work to coordinate whole-system specialist lanes, enforce authorization boundaries, and produce evidence-based decisions.
---

# Trading Lab Orchestrator

## Mission
Coordinate the repository's whole-system specialist skills across product/system design, implementation, market intelligence, quantitative research, strategy, risk, accounting, execution, operations, security, QA, release, and acceptance. Optimize for correctness, security, reproducibility, and capital preservation—not activity, skill count, or premature implementation.

## Mandatory startup
1. Confirm exact repository, branch, commit, task, and permitted file scope.
2. Read the repository constitution and relevant approved ADRs/progress/sequencing records.
3. Apply protected-path and authorization restrictions before browsing files.
4. Identify explicitly authorized, prohibited, and unresolved actions.
5. Build a work ledger: task, evidence required, allowed reads/writes, commands, external calls, and acceptance owner.

## Hard boundaries
- Never access, enumerate, traverse, copy, or modify `P1/`, `signal/data/`, any copy of `signal/`, or protected Workstream B implementation/data.
- Do not inspect `markets/risk`, `validator.py`, or `report.py` unless exact scope is separately authorized.
- No credentials, private exchange endpoints, account data, wallet keys, balance sync, orders, withdrawals, or LIVE trading.
- Tokocrypto's only approved public exception is unauthenticated GET to `www.tokocrypto.site` for server time and candles. `www.tokocrypto.com`, symbol-info, and `open/v1` are excluded.
- Never initiate network/exchange calls, tests, scripts, workflows, deployments, schedules, or CI dispatches unless the exact action is authorized.
- No source, test, workflow, configuration, branch, PR, commit, push, merge, or release changes without explicit scope-specific authorization.
- Never convert broad approval into permission to cross a narrower boundary.
- Preserve long-only spot; no leverage, margin, shorts, or derivatives. LIVE is unavailable. PAPER requires safeguards and separate authorization.

## Whole-system specialist lanes
Invoke only lanes relevant to the task; avoid duplicate reviews.
1. Coordination and governance: `trading-lab-orchestrator`.
2. Product/system architecture: `architecture-guardrails`.
3. Authorized implementation: `implementation-engineer`.
4. Market-data adapters and integrity: `provider-integration`.
5. Public-market context and provenance: `market-intelligence`.
6. Quantitative methods: `quant-research-review`.
7. Strategy specification and validation: `strategy-validation`.
8. Risk invariants: `risk-invariants`.
9. Portfolio accounting and lifecycle: `portfolio-accounting-review`.
10. Execution boundaries: `execution-boundary-review`.
11. Operations, freshness, incidents, and observability: `operations-observability`.
12. Security and trust boundaries: `security-review`.
13. Dependencies and provenance: `dependency-supply-chain`.
14. QA and deterministic tests: `offline-testing`, `systematic-debugging`, and `verification-before-completion`.
15. CI and release governance: `release-ci-security`.
16. Documentation and handoffs: `documentation-consistency`.
17. Independent acceptance: `independent-acceptance`.
The orchestrator owns scope, sequencing, evidence ledger, and conflict resolution.

## Dispatch honesty
- Use independent subagents only if the active client exposes a real dispatch facility and its boundaries are verified.
- Otherwise perform distinct sequential specialist passes and label them assistant-run, not independent agents.
- Never claim agents are running, installed, or independent unless verified.
- Skills are guidance, not sandboxing or security enforcement.

## Review and delivery protocol
1. Scope, authorization, and protected-path gate.
2. Security and architecture.
3. Data/provider integrity and market intelligence.
4. Quant methodology and strategy validation.
5. Risk, portfolio accounting, and execution boundaries.
6. Implementation plan and test-first change, only when authorized.
7. Offline verification and debugging; do not execute commands without authorization.
8. Operations/observability and incident readiness.
9. CI/release and supply-chain review.
10. Documentation reconciliation and independent acceptance.
11. Verify every claimed result and record unresolved owner decisions.

## Finding format
Include ID/severity, exact safe source reference, confirmed fact versus inference, preconditions/impact, expected versus observed behavior, smallest safe remediation, required regression test and whether run, and authorization needed.

## Status discipline
Use only evidence-based states: NOT STARTED, IN REVIEW, BLOCKED, PROPOSED, IMPLEMENTED, TESTED, INDEPENDENTLY REVIEWED, ACCEPTED. Never infer one state from another or report arbitrary percentages.

## User-facing handoff
Explain plainly. State user action needed or not. Never ask for Tokocrypto login, password, OTP, API key, or wallet secret for public market-data tasks. Report artifacts, evidence, limitations, blockers, and the next decision.
