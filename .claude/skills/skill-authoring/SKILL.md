---
name: skill-authoring
description: Use when creating or revising repository-local Claude skills, including triggers, safety constraints, references, and verification cases.
---
# Skill Authoring

## Design
- A skill solves a recurring task, not a one-off event.
- Use precise frontmatter and a description beginning “Use when…” that states triggers.
- Put hard access boundaries first, then workflow, then output expectations.
- Keep instructions actionable and consistent with `CLAUDE.md`.
- Do not grant tools, permissions, network access, or approval authority.
- Never instruct agents to inspect protected paths.

## Verification
1. Check frontmatter syntax and directory/name agreement.
2. Check that every referenced local file exists.
3. Check contradictory instructions and unsupported tool names.
4. Run a read-only pressure scenario against the written rules without opening protected files or executing repository code.
5. Record scenario, expected behavior, observed behavior, and limitations.
6. If Claude Code runtime is unavailable, mark skill discovery and triggering as unverified.

A skill file is guidance, not a sandbox or permission boundary. Enforce access controls separately.
