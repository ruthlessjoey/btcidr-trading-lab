---
name: independent-acceptance
description: Use before accepting a milestone, security correction, pull request, or release candidate.
---

# Independent Acceptance Review

## Independence
Review against the stated acceptance criteria, not the implementer's summary. Do not modify the candidate. If possible, use a reviewer who did not author the implementation; otherwise disclose that independence is limited.

## Required evidence
- Exact base and head commit, branch, and changed-file list.
- Explicit authorized scope and protected-path exclusions.
- Approved requirements and unresolved decisions.
- Direct source/diff inspection for every changed file.
- Tests actually executed, exact command, interpreter/runtime, exit status, and complete relevant output.
- CI evidence tied to the exact head SHA; stale runs do not count.
- Security, failure-mode, regression, and documentation review.
- Explicit evidence for every acceptance criterion.

## Verdicts
- PASS: all mandatory criteria are evidenced; no unresolved blocking findings.
- PASS WITH FINDINGS: core criteria evidenced, but non-blocking findings remain and are explicitly accepted by the owner.
- BLOCKED: required evidence is missing, a mandatory decision is unresolved, or a prerequisite is not satisfied.
- FAIL: evidence demonstrates a mandatory criterion is violated.

## Prohibitions
- Do not infer acceptance from tests passing.
- Do not infer security from a design document.
- Do not mark tests passed if they were not run on the exact candidate.
- Do not waive an unresolved owner decision.
- Do not merge, approve, deploy, or change a milestone state unless separately authorized.
- Never inspect protected paths to complete an acceptance review.

## Output
Map each acceptance criterion to evidence and status. List blocking and non-blocking findings separately. State exactly what would change the verdict. Record the reviewer's limitations and whether the review was genuinely independent.
