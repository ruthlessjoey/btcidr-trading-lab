# AI Trading Lab — Project Subagents

**Status:** Project-scoped, read-only subagent definitions.  
**Runtime:** Claude Code with custom subagent support.  
**Count:** 19 named subagents mapped one-to-one to the 19 repository specialist skills.

## What this installs
The Markdown files in this directory define 19 reusable Claude Code subagents. Each has its own context and focused system prompt. `lab-commander` coordinates the other 18 specialists using Claude Code's Agent dispatch tool.

These are actual runtime-recognized definitions, not just role descriptions. They become available when this repository is opened in a compatible Claude Code session. They do not execute automatically and are not running inside GitHub or this ChatGPT conversation.

## Agent roster
| Agent | Preloaded skill | Responsibility |
|---|---|---|
| `lab-commander` | `trading-lab-orchestrator`, `firecrawl-research` | Coordinates bounded specialist reviews, assigns tasks to named project agents, reconciles findings, and maintains the evidence ledger. |
| `architecture-architect` | `architecture-guardrails`, `firecrawl-research` | Reviews system architecture, ownership boundaries, interfaces, dependencies, and ADR consistency. |
| `implementation-engineer` | `implementation-engineer` | Reviews implementation feasibility and proposes minimal scoped changes; never edits or executes code. |
| `provider-integration` | `provider-integration`, `firecrawl-research` | Reviews public market-data provider contracts, URL containment, parsing, timestamps, and candle integrity. |
| `market-intelligence` | `market-intelligence`, `firecrawl-research` | Reviews market-data provenance, source quality, freshness, coverage, and proxy-market limitations. |
| `quant-research` | `quant-research-review`, `firecrawl-research` | Challenges quantitative research design, statistical validity, leakage, baselines, and reproducibility. |
| `strategy-validation` | `strategy-validation` | Reviews strategy hypotheses, signal definitions, parameter controls, and out-of-sample validation. |
| `risk-invariants` | `risk-invariants` | Reviews fail-closed risk rules, sizing, stops, stale-input handling, and invariant coverage. |
| `portfolio-accounting` | `portfolio-accounting-review` | Reviews exact-decimal portfolio accounting, partial closures, event idempotency, and conservation. |
| `execution-boundary` | `execution-boundary-review` | Reviews simulator/PAPER/LIVE boundaries, execution lifecycle, bypass risks, and kill-switch requirements. |
| `operations-observability` | `operations-observability` | Reviews health, data freshness, sanitized observability, incident handling, and recovery design. |
| `security-review` | `security-review`, `firecrawl-research` | Threat-models trust boundaries, untrusted inputs, permissions, sanitization, and secret exposure. |
| `dependency-supply-chain` | `dependency-supply-chain`, `firecrawl-research` | Reviews dependency provenance, pinning, transitive exposure, and tool installation risks. |
| `offline-testing` | `offline-testing` | Designs deterministic offline test matrices and checks test isolation requirements. |
| `systematic-debugging` | `systematic-debugging` | Analyzes documented failures and traces likely root causes without running commands. |
| `release-ci-security` | `release-ci-security` | Reviews CI triggers, workflow permissions, artifacts, branch controls, and release gates. |
| `documentation-consistency` | `documentation-consistency`, `firecrawl-research` | Checks ADRs, progress, sequencing, work queues, specifications, and handoffs for consistency. |
| `independent-acceptance` | `independent-acceptance`, `firecrawl-research` | Independently challenges evidence and acceptance claims; does not implement the reviewed work. |
| `verification-before-completion` | `verification-before-completion`, `firecrawl-research` | Checks that completion claims match artifacts and verification evidence actually available. |

## Least-privilege design
- All 19 agents retain `permissionMode: plan`.
- All agents retain read-only repository access: no agent receives `Edit`, `Write`, or `Bash`.
- Most specialists receive only `Read`, `Grep`, and `Glob`.
- The Commander and selected research/verification specialists additionally receive an explicit allowlist of Firecrawl MCP tools for public web research only; no other MCP server tools are granted to specialists.
- The Commander additionally receives `Agent` solely to dispatch named project specialists and is the only agent granted Firecrawl Interact browser controls.
- Firecrawl tools do not grant access to repository files, private exchange/account data, protected paths, or financial actions. The shared `firecrawl-research` skill imposes free-credit caps and source-provenance rules.
- The implementation-engineer agent is intentionally read-only.
- Commander instructions prohibit built-in Explore, Plan, general-purpose, or unnamed agents.
- Project settings deny reads of protected paths and block built-in agent types. Review the active permission state before relying on it.

**Limitation:** Claude Code permission rules are client-enforced, not an OS sandbox. Read-deny rules protect built-in file tools and related searches, but not arbitrary external processes. Agents have no shell or MCP tools. Human review and repository access controls remain necessary.

## Activation
1. Open this repository in a compatible Claude Code environment.
2. Review `CLAUDE.md`, `.claude/settings.json`, and this directory before trusting the project.
3. Confirm settings with `/status`, `/permissions`, and agent discovery with `/agents`.
4. In `/mcp`, confirm Firecrawl is connected through OAuth and its approved tools are visible; check the free credit balance before research.
5. Restart Claude Code after first creating `.claude/agents/` if the agents are not detected.
6. Ask: `Use lab-commander to coordinate a read-only review of [specific task and safe scope].`

Agent requests consume usage under the user's own Claude Code/model-provider arrangement. No runtime or usage allowance is bundled.

## Authorization gates
Definitions do not authorize source changes, tests, scripts, workflows, network requests, deployment, PAPER, or LIVE activity. All actions remain subject to the repository constitution and task-specific owner authorization. An agent cannot approve its own work or grant itself more permissions.

The implementation-engineer agent is intentionally read-only in this initial release. A future write-capable implementation agent requires separate scoped design and approval, plus enforceable runtime controls.
