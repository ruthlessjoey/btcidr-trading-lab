---
name: documentation-consistency
description: Use when reviewing or updating ADRs, progress reports, sequencing documents, interface notes, and project handoffs for consistency.
---
# Documentation Consistency

## Scope
Use only authorized documentation outside protected paths. Never inspect `P1/`, `signal/data/`, any `signal/`, or protected Workstream B documents/data.

## Process
1. Identify authoritative decision records and their status.
2. Compare approved ADRs, progress, sequencing, open interfaces, README, and handoffs.
3. Distinguish approved decisions, proposals, completed work, blocked work, and unverified claims.
4. Check dates, commit hashes, branch names, workflow triggers, permissions, and paths.
5. Keep deferred items deferred; do not describe proposals as installed or tested.
6. Preserve history; propose explicit superseding records rather than silently rewriting decisions.
7. Never claim full-system completion when protected areas were excluded.

## Output
Provide a conflict table with source, exact statement, authoritative status, and minimal correction. List every changed document. Never change source code in a documentation-only task.
