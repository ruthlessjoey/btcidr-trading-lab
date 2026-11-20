---
name: trading-architecture-review
description: Use when reviewing proposed changes to architecture, module boundaries, ADR alignment, or milestone sequencing within explicitly authorized, unprotected files.
---
# Trading Architecture Review

## Scope gate
- Review only explicitly authorized files outside `P1/`, `signal/data/`, every `signal/` path, and protected Workstream B implementation/data.
- Do not enumerate or search protected trees. If the task requires them, stop and request narrowly scoped authorization.
- Shared-tooling permission does not authorize Workstream B source inspection.

## Method
1. Record exact changed files and baseline commit.
2. Read applicable approved ADRs and project instructions outside protected paths.
3. Map changes to owning layers and interfaces.
4. Check dependency direction, state ownership, fail-closed behavior, and error propagation.
5. Preserve spot-only/long-only policy, PAPER/LIVE separation, emergency-stop requirement, partial-close accounting, stop ownership, and custody boundaries.
6. Check for hidden coupling, duplicate sources of truth, new permissions, network access, background work, or irreversible side effects.
7. Report findings by severity with exact authorized file/line references.

## Output
Scope and baseline; applicable decisions; findings (Critical/High/Medium/Low); unverified assumptions and exclusions; minimal remediation proposal. Never claim whole-repository validation when protected areas were excluded.
