# AI Trading Lab Review Army

## Purpose
A repository-local specialist skill set for safer architecture, security, data, research, risk, testing, CI, and acceptance work. These are reusable review mandates, not autonomous trading agents and not a claim that independent background agents are running.

## How to invoke
Open the repository with a Claude Code-compatible client that supports repository skills. Ask it to use `trading-lab-orchestrator` first. The orchestrator applies the repository constitution and invokes the specialist skills in a controlled sequence. If actual subagent dispatch is available, it may assign narrow read-only tasks; otherwise it must run separate sequential passes and disclose that limitation.

## Complete specialist roster
The tooling branch contains exactly 16 skill folders. Every folder is listed below; no skill is an independent runtime or grants additional permissions.

| Lane | Repository skill | Main responsibility |
|---|---|---|
| Coordinator | `trading-lab-orchestrator` | Scope, authorization, sequencing, evidence ledger, reconciliation |
| Security | `security-review` | Threat model, trust boundaries, input/output sanitization |
| Architecture | `architecture-guardrails` | Component boundaries, ownership, dependency direction |
| Market data | `provider-integration` | Provider contracts, URL policy, timestamps, candle integrity |
| Quant research | `quant-research-review` | Research design, bias, statistical validity, evidence quality |
| Strategy validation | `strategy-validation` | Strategy assumptions, out-of-sample discipline, overfitting controls |
| Risk | `risk-invariants` | Fail-closed risk rules, sizing and stop ownership boundaries |
| Portfolio accounting | `portfolio-accounting-review` | Exact-decimal accounting, partial closures, conservation and idempotency |
| QA | `offline-testing` | Deterministic offline regression design and test isolation |
| Debugging | `systematic-debugging` | Reproduction, root-cause analysis, minimal corrective scope |
| Execution safety | `execution-boundary-review` | PAPER/LIVE boundary, emergency stop, execution bypass analysis |
| CI/release | `release-ci-security` | Workflow triggers, permissions, artifacts, release controls |
| Supply chain | `dependency-supply-chain` | Dependency provenance, pinning, install scripts and runtime exposure |
| Documentation | `documentation-consistency` | ADR, progress, sequencing, handoff and decision consistency |
| Acceptance | `independent-acceptance` | Evidence-based milestone, PR and release verdicts |
| Verification | `verification-before-completion` | Verify actual commands/results before making completion claims |

## Safety contract
All lanes inherit the repository's `CLAUDE.md` boundaries. No skill grants permission to inspect protected paths, access exchange credentials, call private endpoints, run workflows, execute tests, deploy, or make trading decisions. The user does not need to log in to Tokocrypto for public market-data work. Never request passwords, OTPs, API keys, wallet secrets, or private account access.

Skills are advisory instructions, not technical access controls. They do not sandbox file access, enforce least privilege, or prevent an agent/client from disobeying. Use a restricted environment and human-reviewed change gates for enforcement. Do not claim parallel independent reviews unless the active client actually dispatches separate agents and returns their results.

## Review order
1. Scope, authorization and protected-path gate.
2. Security and architecture.
3. Market-data provider and transport review.
4. Quant research and strategy validation.
5. Risk and portfolio accounting review (only within approved readable scope).
6. Offline test design and root-cause review.
7. CI/release and supply-chain review.
8. Documentation reconciliation.
9. Independent acceptance against explicit criteria.
10. Verification of every claimed result.

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
