# AI Trading Lab Whole-System Specialist Army

## Purpose
A repository-local specialist skill set spanning the complete trading-system lifecycle: product and architecture, coding, public market intelligence, quant research, strategy, risk, portfolio accounting, execution boundaries, operations, security, QA, release, and acceptance. These are reusable instruction sets—not autonomous agents, a live trading system, or proof of profitability.

## How to invoke
Open the repository in a Claude Code-compatible client that supports repository skills. Start substantial tasks with `trading-lab-orchestrator`. It applies the repository constitution, scopes the work, selects relevant specialist lanes, and maintains an evidence ledger. If genuine subagent dispatch is unavailable, specialist passes must be sequential and disclosed as assistant-run.

## Complete specialist roster
The tooling branch contains 19 repository skill folders. Each is an instruction set; none independently executes work or grants permissions.

| Lane | Skill | Responsibility |
|---|---|---|
| Coordination | `trading-lab-orchestrator` | Scope, authorization, sequencing, evidence, conflict resolution |
| Architecture | `architecture-guardrails` | System boundaries, ownership, dependency direction |
| Implementation | `implementation-engineer` | Authorized code changes, test-first workflow, minimal diffs |
| Market data | `provider-integration` | Provider contracts, URL policy, timestamps, candle integrity |
| Market intelligence | `market-intelligence` | Public-source provenance, market context, falsifiable hypotheses |
| Quant research | `quant-research-review` | Research design, statistical validity, bias controls |
| Strategy | `strategy-validation` | Strategy specification, leakage, out-of-sample validation |
| Risk | `risk-invariants` | Fail-closed risk rules, sizing and stop ownership |
| Portfolio | `portfolio-accounting-review` | Exact-decimal accounting, partial closures, conservation |
| Execution | `execution-boundary-review` | PAPER/LIVE boundary, emergency stop, bypass analysis |
| Operations | `operations-observability` | Health, freshness, incidents, auditability, runbooks |
| Security | `security-review` | Threat model, trust boundaries, sanitization |
| Supply chain | `dependency-supply-chain` | Dependency provenance, pinning, install/runtime exposure |
| QA | `offline-testing` | Deterministic offline regression design |
| Debugging | `systematic-debugging` | Reproduction, root-cause analysis, minimal correction |
| CI/release | `release-ci-security` | Workflow triggers, permissions, artifacts, release controls |
| Documentation | `documentation-consistency` | ADR, progress, sequencing, handoff consistency |
| Acceptance | `independent-acceptance` | Evidence-based milestone, PR, and release verdicts |
| Verification | `verification-before-completion` | Verify actual results before completion claims |

## Safety contract
All lanes inherit `CLAUDE.md`. No skill grants permission to inspect protected paths, access exchange credentials, call private endpoints, run workflows, execute tests, deploy, or make trading decisions. The user does not need to log in to Tokocrypto for approved public market-data work. Never request passwords, OTPs, API keys, wallet secrets, or private account access.

Skills are advisory instructions, not technical access controls. They do not sandbox file access, enforce least privilege, or prevent a client/agent from disobeying. Use restricted environments and human-reviewed change gates for enforcement. Do not claim parallel independent reviews unless the active client actually dispatches separate agents and returns their results.

## Work protocol
1. Confirm repository, branch, commit, scope, authorizations, and protected exclusions.
2. Apply security and architecture gates before task-specific work.
3. Select only relevant specialist lanes; do not invoke every skill mechanically.
4. Separate design, implementation, test execution, external access, deployment, and trading authorization.
5. Record source evidence, uncertainty, tests actually run/not run, blockers, and acceptance owner.
6. Require independent acceptance for milestone gates; implementation is not acceptance.

## Evidence ledger
Record repository/branch/base/head; authorized and excluded paths; requirements and owner decisions; findings and evidence; tests/workflows actually run or not run; unresolved blockers; acceptance verdict and reviewer limitations.

## Honest capability statement
Skills do not install a runtime, create independent agents, sandbox file access, enforce permissions, or automatically execute work. Actual parallel review requires a real dispatch facility in the active coding client. Without it, work is sequential and assistant-run.
