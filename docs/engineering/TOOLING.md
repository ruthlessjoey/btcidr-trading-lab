# Repository Engineering Tooling

## Installation scope
This project-scoped tooling setup lives on branch `chore/claude-engineering-tooling`, based on `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`.

It includes:
- `CLAUDE.md`: repository constitution and non-negotiable safety boundaries.
- `.claude/skills/`: 19 repository-local specialist skill instructions spanning architecture, implementation, market data and intelligence, quant research, strategy, risk, accounting, execution, operations, security, QA, CI/release, documentation, and acceptance.
- `.mcp.json`: project-scoped Context7 remote MCP using OAuth.

This tooling-only branch changes no trading implementation, tests, workflows, exchange integrations, credentials, protected paths, or execution settings.

## Context7
The project MCP entry uses the hosted OAuth endpoint: `https://mcp.context7.com/mcp/oauth`.

On a machine with Claude Code:
1. Open the repository and review these files before approving its project trust prompt.
2. Open Claude Code MCP management with `/mcp`.
3. Select `context7` and complete the OAuth authentication flow.
4. Confirm the server exposes documentation lookup tools before relying on it.

No API key or secret is stored in this repository. Use generic documentation queries only; never include private source, credentials, personal data, or secrets.

## Superpowers evaluation
Superpowers `v6.4.2` from `obra/superpowers` was reviewed at commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d`. The full plugin was not installed because it includes executable hooks/scripts that add unnecessary runtime surface for this project. The repository-local skills encode the relevant process practices without redistributing upstream code.

## Security and maintenance
- Context7 is remote and requires interactive OAuth authentication in the Claude Code client.
- Skills are instructions, not enforcement mechanisms. They do not replace code-level validation, CI, branch protection, restricted environments, or human review.
- Review these files when ADRs, security boundaries, or milestone gates change.
- No paid API, hosted agent, or subscription runtime is required by this skill set.

## Whole-system specialist army
See [REVIEW-ARMY.md](REVIEW-ARMY.md) for the 19-skill roster and task-selection protocol. Start substantial work with `trading-lab-orchestrator`; invoke only relevant specialists. The skills are not autonomous agents and do not automatically execute code or trading actions. The current client must provide a genuine dispatch facility before parallel independent reviews can be claimed.
