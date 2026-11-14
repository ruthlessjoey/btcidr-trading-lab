# Stage 2 — Claude skills installation

## Upstream workflow skills

Selected Superpowers v7.0.2 content is pinned to commit `22f0b463e7a5e579904dd6211a520321035526f7`:

- using-superpowers
- brainstorming
- writing-plans
- test-driven-development
- systematic-debugging
- verification-before-completion
- requesting-code-review
- receiving-code-review
- finishing-a-development-branch

Only Markdown skill instructions and referenced Markdown support documents are included. Executable scripts, hooks, plugin configuration, telemetry, and subagent-only workflows are excluded. The MIT license and upstream provenance are preserved. The release tag is unsigned.

## Repository-specific skills

- trading-architecture-review
- security-review
- offline-testing
- data-provider-integration
- risk-engine-invariants
- documentation-consistency
- skill-authoring

## Verification limits

- Files follow the Claude project layout `.claude/skills/<name>/SKILL.md`.
- Runtime discovery and invocation are not verified in this session.
- No live Claude Code pressure tests were run.
- Skills are guidance, not sandbox controls.
- No scripts, dependencies, tests, or repository-controlled code were executed.

## Scope

Shared skills may support both workstreams, but this PR does not inspect or modify Workstream B implementation/data. It does not access `P1/`, `signal/data/`, or any `signal/` path.
