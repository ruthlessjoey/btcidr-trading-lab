# AI Trading Lab Whole-System Specialist Army

## Purpose
The repository contains 19 specialist skills and 19 corresponding project-scoped Claude Code subagents. Skills provide reusable domain guidance; subagents provide actual runtime-recognized, separately contextualized workers when loaded by Claude Code. They are not a live trading system or proof of profitability.

## How to invoke
Open the repository in a compatible Claude Code client. Start substantial work by asking Claude Code to use `lab-commander`. The commander can dispatch named project specialists through Claude Code's Agent tool, collect findings, request independent challenge, and maintain an evidence ledger.

If the runtime is unavailable, the files remain installed definitions but no agents have run. This ChatGPT conversation cannot launch Claude Code subagents. Never claim dispatch or independent results without runtime evidence.

## Specialist roster
| Lane | Agent | Skill | Responsibility |
|---|---|---|---|
| Coordination | `lab-commander` | `trading-lab-orchestrator` | Coordinates bounded specialist reviews, assigns tasks to named project agents, reconciles findings, and maintains the evidence ledger. |
| architecture architect | `architecture-architect` | `architecture-guardrails` | Reviews system architecture, ownership boundaries, interfaces, dependencies, and ADR consistency. |
| implementation engineer | `implementation-engineer` | `implementation-engineer` | Reviews implementation feasibility and proposes minimal scoped changes; never edits or executes code. |
| provider integration | `provider-integration` | `provider-integration` | Reviews public market-data provider contracts, URL containment, parsing, timestamps, and candle integrity. |
| market intelligence | `market-intelligence` | `market-intelligence` | Reviews market-data provenance, source quality, freshness, coverage, and proxy-market limitations. |
| quant research | `quant-research` | `quant-research-review` | Challenges quantitative research design, statistical validity, leakage, baselines, and reproducibility. |
| strategy validation | `strategy-validation` | `strategy-validation` | Reviews strategy hypotheses, signal definitions, parameter controls, and out-of-sample validation. |
| risk invariants | `risk-invariants` | `risk-invariants` | Reviews fail-closed risk rules, sizing, stops, stale-input handling, and invariant coverage. |
| portfolio accounting | `portfolio-accounting` | `portfolio-accounting-review` | Reviews exact-decimal portfolio accounting, partial closures, event idempotency, and conservation. |
| execution boundary | `execution-boundary` | `execution-boundary-review` | Reviews simulator/PAPER/LIVE boundaries, execution lifecycle, bypass risks, and kill-switch requirements. |
| operations observability | `operations-observability` | `operations-observability` | Reviews health, data freshness, sanitized observability, incident handling, and recovery design. |
| security review | `security-review` | `security-review` | Threat-models trust boundaries, untrusted inputs, permissions, sanitization, and secret exposure. |
| dependency supply chain | `dependency-supply-chain` | `dependency-supply-chain` | Reviews dependency provenance, pinning, transitive exposure, and tool installation risks. |
| offline testing | `offline-testing` | `offline-testing` | Designs deterministic offline test matrices and checks test isolation requirements. |
| systematic debugging | `systematic-debugging` | `systematic-debugging` | Analyzes documented failures and traces likely root causes without running commands. |
| release ci security | `release-ci-security` | `release-ci-security` | Reviews CI triggers, workflow permissions, artifacts, branch controls, and release gates. |
| documentation consistency | `documentation-consistency` | `documentation-consistency` | Checks ADRs, progress, sequencing, work queues, specifications, and handoffs for consistency. |
| independent acceptance | `independent-acceptance` | `independent-acceptance` | Independently challenges evidence and acceptance claims; does not implement the reviewed work. |
| verification before completion | `verification-before-completion` | `verification-before-completion` | Checks that completion claims match artifacts and verification evidence actually available. |

## Least-privilege runtime configuration
- All 19 agents use Claude Code `permissionMode: plan`.
- Specialists have only `Read`, `Grep`, and `Glob`.
- `lab-commander` additionally has `Agent` to dispatch named project subagents.
- No agent has Edit, Write, Bash, Web, or MCP tools.
- The implementation-engineer agent is read-only and can only analyze and plan.
- Commander instructions prohibit spawning built-in Explore, Plan, general-purpose, or unnamed agents.
- `.claude/settings.json` adds Read deny rules for protected paths and disables built-in/general-purpose subagent types.

Claude Code permission rules are client-enforced, not OS-level isolation. Read deny rules cover Claude Code's built-in file tools and best-effort search paths, but not arbitrary external processes. Agents have no shell or MCP tools. Do not describe this as a complete sandbox.

## Safety contract
All lanes inherit `CLAUDE.md`. No agent may access `P1/`, `signal/data/`, any copy of `signal/`, protected Workstream B artifacts, `markets/risk`, `validator.py`, or `report.py`. No credentials, private endpoints, account data, orders, withdrawals, LIVE trading, network calls, tests, workflows, scripts, or deployments. No source changes or repository writes.

No skill or agent grants authorization. User approval must be specific to the exact action. Broad approval does not override a narrower boundary.

## Work protocol
1. Commander records task, authorization, exact safe scope, exclusions, and evidence requirements.
2. Commander assigns bounded, non-overlapping questions to named specialists.
3. Specialists return evidence, confirmed facts versus inference, severity, confidence, and unresolved questions.
4. Commander reconciles disagreements and records unreviewed scope.
5. Independent acceptance challenges consequential conclusions.
6. Commander reports verdict, dispatched agents, evidence, limitations, tests not run, and next decision.

## Evidence ledger
Record repository/branch/base/head; authorized and excluded paths; requirements and owner decisions; assigned agents; findings and evidence; tests/workflows actually run or not run; unresolved blockers; acceptance verdict and reviewer limitations.

## Runtime and usage
Project agents load when this repository is opened in Claude Code. A compatible runtime and the user's own model/provider access are required; the repository does not bundle compute or usage credits. On first creating `.claude/agents/`, restart Claude Code if the watcher does not detect the new directory. Use `/agents`, `/status`, and `/permissions` to inspect agent discovery and active permissions.

## Honest capability statement
The 19 project subagents are actual Claude Code definitions, but they do not run automatically. They are not available as autonomous processes in GitHub or this ChatGPT conversation. Skills and prompts do not replace technical access controls or human review.
