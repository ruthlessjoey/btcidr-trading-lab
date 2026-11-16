# Repository Engineering Tooling

## Installation scope
This tooling setup is project-scoped and isolated on branch `chore/claude-engineering-tooling`, based on `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`.

It adds:
- `CLAUDE.md`: repository constitution and safety boundaries.
- `.claude/skills/`: six repository-specific skills plus systematic debugging and verification-before-completion workflows.
- `.mcp.json`: project-scoped Context7 remote MCP using OAuth.

No trading code, workflows, exchange integrations, credentials, protected paths, or execution settings are changed.

## Context7
The project MCP entry uses the hosted OAuth endpoint: `https://mcp.context7.com/mcp/oauth`.

On a machine with Claude Code:
1. Open the repository and review these files before approving its project trust prompt.
2. Open Claude Code MCP management with `/mcp`.
3. Select `context7` and complete the OAuth authentication flow.
4. Confirm the server exposes documentation lookup tools before relying on it.

No API key or secret is stored in this repository. Context7's published privacy documentation says its service receives the MCP-generated search query, library identifier, client/session metadata, and optional authentication data; it does not receive the full prompt, conversation, or source code. Continue to keep queries generic and never include private code, credentials, personal data, or secrets.

## Superpowers evaluation
Reviewed Superpowers `v6.4.2` from `obra/superpowers`, pinned to commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d`. GitHub reports the commit signature as verified. The annotated tag object itself is unsigned.

The upstream plugin repository includes executable `index.js`, `hooks/`, and `scripts/` in addition to Markdown skills. The full plugin was not installed because this repository only needs process guidance; executing third-party hooks/scripts would add unnecessary runtime surface. Instead, repository-local skills implement the relevant practices: test-first changes, root-cause debugging, verification before completion, and domain-specific guardrails. No upstream Superpowers code is redistributed by this setup.

## Security and maintenance
- Context7 is remote and requires interactive OAuth authentication in the Claude Code client.
- Ask Context7 generic library/documentation questions only. Do not submit repository source or sensitive data.
- Skills are instructions, not enforcement mechanisms. They do not replace code-level validation, CI, branch protection, or human review.
- Review and update these files when ADRs, security boundaries, or milestone gates change.


## Review army

The repository now includes a coordinated set of 16 skill folders under `.claude/skills/`: the existing architecture, documentation, offline-testing, provider, risk, security, systematic-debugging, and verification skills, plus the trading-lab orchestrator, quantitative research review, release/CI security review, and independent acceptance review, portfolio accounting review, strategy validation, execution-boundary review, and dependency/supply-chain review.

See [REVIEW-ARMY.md](REVIEW-ARMY.md) for the roster and invocation order. The orchestrator is designed to use genuine subagent dispatch only when the active coding client exposes it; otherwise it requires separate sequential passes and honest disclosure. Skills remain guidance, not technical sandboxing or permission enforcement.
