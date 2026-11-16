# AI Trading Lab Review Army

## Purpose
A repository-local specialist skill set for safer architecture, security, data, research, risk, testing, CI, and acceptance work. These are reusable review mandates, not autonomous trading agents and not a claim that independent background agents are running.

## How to invoke
Open the repository with a Claude Code-compatible client that supports repository skills. Ask it to use `trading-lab-orchestrator` first. The orchestrator applies the repository constitution and invokes the specialist skills in a controlled sequence. If actual subagent dispatch is available, it may assign narrow read-only tasks; otherwise it must run separate sequential passes and disclose that limitation.

## Specialist roster

| Lane | Repository skill | Main responsibility |
|---|---|---|
| Coordinator | `trading-lab-orchestrator` | Scope, dispatch, evidence ledger, reconciliation |
| Security | `security-review` | Threat model, trust boundaries, sanitization |
| Architecture | `architecture-guardrails` | Component boundaries and ownership |
| Market data | `provider-integration` | Provider contracts, timestamps, candle integrity |
| Quant research | `quant-research-review`, `strategy-validation` | Bias, strategy evidence, backtests, statistical validity |
| Risk | `risk-invariants`, `portfolio-accounting-review` | Fail-closed risk, ledger and partial-closure invariants |
| QA | `offline-testing`, `systematic-debugging` | Deterministic regression design and root cause |
| Execution safety | `execution-boundary-review` | PAPER/LIVE boundary, emergency stop, bypass analysis |
| CI/release | `release-ci-security`, `dependency-supply-chain` | Workflow triggers, permissions, dependencies, provenance |
| Documentation | `documentation-consistency` | ADR, progress, sequencing, handoff consistency |
| Acceptance | `independent-acceptance` | Evidence-based milestone and PR verdicts |

## Safety contract
All lanes inherit the repository's `CLAUDE.md` boundaries. No skill grants permission to inspect protected paths, access exchange credentials, call private endpoints, run workflows, execute tests, deploy, or make trading decisions. The user does not need to log in to Tokocrypto for public market-data work. Never request passwords, OTPs, API keys, wallet secrets, or private account access.

## Review order
1. Scope and authorization gate.
2. Security and architecture.
3. Market-data and quantitative research.
4. Risk invariants (within approved readable scope).
5. Offline test design.
6. CI/release review.
7. Documentation reconciliation.
8. Dependency and supply-chain review.
9. Independent acceptance against explicit criteria.

## Evidence ledger
For every task, record:
- repository, branch, base/head commit;
- authorized and excluded paths;
- requirements and owner decisions;
- findings with severity and source evidence;
- tests and workflows actually run (or explicitly not run);
- open blockers and required authorization;
- acceptance verdict and reviewer limitations.

## Honest capability statement
A repository skill is an instruction set. It does not install a runtime, create independent agents, sandbox file access, enforce permissions, or automatically execute work. Actual parallel review is possible only when the active coding client provides a real subagent facility. Without it, reviews are sequential and assistant-run.
