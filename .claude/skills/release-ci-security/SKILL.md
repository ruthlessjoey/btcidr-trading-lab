---
name: release-ci-security
description: Use when reviewing GitHub Actions, CI permissions, deployment, scheduled jobs, artifact publishing, or release processes.
---

# Release and CI Security Review

## Review boundaries
This skill authorizes read-only inspection only. It does not authorize workflow dispatch, reruns, deployment, publishing, schedule creation, or repository changes.

## Checklist
- Enumerate exact workflow triggers: push, pull_request, workflow_dispatch, schedule, repository_dispatch, and reusable workflows.
- Trace every job's permissions, token use, checkout credential persistence, third-party actions, scripts, artifacts, caches, and environment secrets.
- Prefer least-privilege permissions; default to read-only. Identify any write token and the exact operation requiring it.
- Inspect whether untrusted pull-request code can access write permissions or secrets.
- Review pinning of third-party actions to immutable commit SHAs and update policy.
- Check whether workflows can contact exchanges or other external hosts and whether this is explicitly authorized.
- Inspect artifact destinations, branch publishing, force-push, deletion, retention, and overwrite behavior.
- Treat scheduled jobs and push triggers as autonomous operations with ongoing network and write impact.
- Check concurrency, cancellation, retries, and duplicate execution behavior.
- Identify commands that run user-controlled scripts or install mutable dependencies.
- Never execute a workflow or script to "see what happens" during a review.

## Output
For each workflow: triggers; permissions; external calls; write effects; untrusted-input exposure; third-party action risk; schedule behavior; severity-ranked findings; minimum safe remediation. Separate configuration facts from assumptions. No workflow is safe merely because it has not yet been triggered.
