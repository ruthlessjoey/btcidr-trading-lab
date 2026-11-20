---
name: trading-lab-orchestrator
description: Use at the start of substantial AI Trading Lab work to coordinate whole-system specialist lanes, enforce authorization boundaries, and produce evidence-based decisions.
---

# Trading Lab Orchestrator

## Mission
Coordinate the repository's whole-system specialist skills and the 19 project-scoped Claude Code subagents across product/system design, implementation, market intelligence, quantitative research, strategy, risk, accounting, execution, operations, security, QA, release, and acceptance. Optimize for correctness, security, reproducibility, and capital preservation—not activity, skill count, or premature implementation.

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

## Whole-system specialist agents
Invoke only agents relevant to the task; avoid duplicate reviews. The 19 project subagents are documented in `.claude/agents/README.md`:
1. `lab-commander` — coordination and governance.
2. `architecture-architect` — architecture guardrails.
3. `implementation-engineer` — read-only implementation feasibility and change planning.
4. `provider-integration` — provider contracts and candle integrity.
5. `market-intelligence` — public market provenance and freshness.
6. `quant-research` — quantitative methods.
7. `strategy-validation` — strategy specifications and validation.
8. `risk-invariants` — risk rules.
9. `portfolio-accounting` — accounting and lifecycle.
10. `execution-boundary` — execution boundaries.
11. `operations-observability` — operations and incidents.
12. `security-review` — security and trust boundaries.
13. `dependency-supply-chain` — dependencies and provenance.
14. `offline-testing` — deterministic test design only.
15. `systematic-debugging` — root-cause analysis without running commands.
16. `release-ci-security` — CI and release governance.
17. `documentation-consistency` — documentation and handoffs.
18. `independent-acceptance` — independent evidence challenge.
19. `verification-before-completion` — completion claim verification.

## Dispatch honesty
- In Claude Code, use only the named project subagents in `.claude/agents/`; the commander has the Agent tool solely to dispatch named project agents.
- Do not dispatch built-in Explore, Plan, general-purpose, or unnamed agents.
- In ChatGPT or any client without a real dispatch facility, perform distinct sequential specialist passes and label them assistant-run, not independent agents.
- Never claim agents are running, installed, or independent unless verified by the active runtime.
- Agent prompts and skills are not an OS sandbox. Project permission rules are client-enforced; maintain human review and least privilege.

## Review and delivery protocol
1. Scope, authorization, and protected-path gate.
2. Security and architecture.
3. Data/provider integrity and market intelligence.
4. Quant methodology and strategy validation.
5. Risk, portfolio accounting, and execution boundaries.
6. Implementation plan and test-first change, only when separately authorized.
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
