# Stage 2 — Claude skills and workflow guidance

## Target surfaces

This PR is intended to support the user's regular Claude web/mobile app (claude.ai), not assume Claude Code is installed.

Claude.ai supports custom Skills uploaded by the individual user when Code execution and file creation is enabled. The repository's `.claude/skills/<name>/SKILL.md` tree is a version-controlled source layout; it is **not** automatically discovered by Claude.ai from GitHub. See [claude-web-setup.md](claude-web-setup.md) for setup, upload, and fallback instructions.

Official guidance: https://support.claude.com/en/articles/12512180-use-skills-in-claude

## Upstream workflow reference material

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

These upstream files are retained as reference material. Some instructions assume Claude Code, terminal access, Git worktrees, plugin skill namespaces, or subagents. They must not be treated as ready-to-use Claude.ai skills until adapted and validated for that surface.

## Repository-specific guidance

- trading-architecture-review
- security-review
- offline-testing
- data-provider-integration
- risk-engine-invariants
- documentation-consistency
- skill-authoring

The six trading/review guides are the recommended first candidates for individual Claude.ai Skill packaging. Skill upload and runtime behavior have not been verified in this PR. The skill-authoring guide is reference material, not a mandatory upload.

## Verification limits

- Source files use `.claude/skills/<name>/SKILL.md` for version control.
- Claude.ai does not automatically load these files from GitHub.
- No Claude.ai skill ZIP upload, enablement, or invocation test has been performed.
- No live Claude Code pressure tests were run.
- Skills are guidance, not sandbox controls or access permissions.
- No scripts, dependencies, tests, or repository-controlled code were executed.

## Scope

Shared guidance may support both workstreams, but this PR does not inspect or modify Workstream B implementation/data. It does not access `P1/`, `signal/data/`, or any `signal/` path.
