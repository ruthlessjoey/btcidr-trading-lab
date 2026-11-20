---
name: documentation-consistency
description: Use when changing ADRs, project status, milestone sequencing, handoffs, or technical documentation.
---

# Documentation Consistency

## Source-of-truth order
1. Explicit user-approved decision records and ADRs.
2. Current implementation and verified test/workflow evidence.
3. Current progress and sequencing documents.
4. Handoffs and summaries, which may be stale.
5. Proposals and assistant-generated notes, which are not approvals.

When sources conflict, do not silently reconcile them. Identify the conflict, use the highest-authority source, and record the unresolved discrepancy.

## Required checks
- Every architectural decision has an explicit status: proposed, approved, rejected, superseded, or deferred.
- Distinguish implemented, tested, independently reviewed, accepted, and deployed states.
- Keep milestone dependencies accurate; do not mark a blocked step complete because a later artifact exists.
- Record exact commit, branch, file scope, test command, interpreter, result, and known gaps when applicable.
- Preserve security restrictions, approval boundaries, and unresolved risks.
- Do not rewrite history or remove negative evidence.
- Do not claim a tool, skill, MCP server, or plugin is installed unless repository configuration and exact files have been verified.
- Keep handoffs concise, dated, and reproducible. Mark superseded files clearly.

Compare ADRs, progress, sequencing, and handoff language for contradictions. Report conflicts rather than choosing a convenient interpretation.
