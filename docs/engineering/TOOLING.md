# Repository Engineering Tooling

## Installation scope
This project-scoped tooling setup lives on branch `chore/claude-engineering-tooling`, based on `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`.

It includes:
- `CLAUDE.md`: repository constitution and non-negotiable safety boundaries.
- `.claude/skills/`: 19 repository-local specialist skill instructions.
- `.claude/agents/`: 19 project-scoped Claude Code subagents, including a read-only commander and 18 specialist reviewers.
- `.claude/settings.json`: shared deny rules for protected paths and built-in/general-purpose subagent types.
- `.mcp.json`: project-scoped Context7 remote MCP using OAuth.

This tooling-only branch changes no trading implementation, trading tests, workflows, exchange integrations, credentials, protected paths, or execution settings.

## Project subagents
The `.claude/agents/` directory contains 19 Claude Code subagent definitions mapped one-to-one to the 19 specialist skills. `lab-commander` can dispatch the named project agents through Claude Code's Agent tool and reconcile their reports.

Least privilege:
- All agents use `permissionMode: plan`.
- Specialist agents have only `Read`, `Grep`, and `Glob`.
- The commander additionally has `Agent` to dispatch named project agents.
- No agent has `Edit`, `Write`, `Bash`, web, or MCP tools.
- The implementation-engineer agent is review/planning-only; it cannot edit code.
- The commander is instructed not to spawn built-in Explore, Plan, general-purpose, or unnamed agents.

The project settings deny Read access to protected path patterns and disable built-in Explore, Plan, and general-purpose agent types. Claude Code permission rules are client-enforced, not an OS-level sandbox. Read-deny rules do not protect against arbitrary external processes; agents therefore have no shell or MCP tools. Human review remains required.

To activate: open the repository in Claude Code, review the project trust prompt and configuration, check `/status`, `/permissions`, and `/agents`, and restart after first creating the agents directory if it is not detected. Agent model usage follows the user's own Claude Code/provider arrangement; this repository includes no runtime or usage allowance.

See [REVIEW-ARMY.md](REVIEW-ARMY.md) and [agent README](../../.claude/agents/README.md) for the roster and invocation guide.

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
- Skills and agent prompts are instructions; only Claude Code's configured permission system enforces tool/path restrictions. Neither is an OS sandbox.
- Review these files when ADRs, security boundaries, or milestone gates change.
- No paid API, hosted agent, or subscription runtime is bundled or required by these static definitions.
- Never claim agents are running until a compatible runtime has loaded and actually dispatched them.

## Whole-system specialist army
See [REVIEW-ARMY.md](REVIEW-ARMY.md) for the 19-skill and 19-subagent roster. Start substantial work with `lab-commander` or the `trading-lab-orchestrator` skill. Use only named project agents for bounded read-only reviews.
