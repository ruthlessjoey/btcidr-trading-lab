# Incident, rollback, and recovery runbook

**Status:** Draft operational guidance; not yet independently accepted or exercised  
**Repository:** `ruthlessjoey/btcidr-trading-lab`  
**Selected integration baseline:** `main` at `731fc9fbb892dadccc64bf52da2f91ff069da124`  
**Historical M6 baseline:** `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`

This runbook governs repository, review, CI, and evidence recovery. It is not authorization to run a trading system, exchange client, dataset publisher, TEST evaluation, PAPER workflow, or LIVE workflow.

## 1. Non-negotiable operating controls

- Spot-only and long-only. No shorts, leverage, margin, derivatives, or borrowing.
- Research-only / PAPER-only; LIVE remains disabled. PAPER is not ready and must not be enabled by this document.
- No real-money orders, order modifications, withdrawals, transfers, payments, funding, account access, credentials, or private exchange endpoints.
- The only approved public market-data route is unauthenticated HTTPS GET candles at `www.tokocrypto.site/api/v3/klines`; do not contact any other host or route without separate approval. This runbook does not authorize even that public request.
- Do not access, traverse, inspect, import, execute, or modify `P1/`, `signal/data/`, any copy of `signal/`, `markets/risk/`, `validator.py`, `report.py`, or protected Workstream B artifacts without a separate authorization naming the exact scope.
- Never run tests whose import closure reaches protected modules. Prefer the exact sparse-checkout workflow and its explicitly enumerated test modules.
- No force push, reset, branch deletion, direct default-branch commit, PR merge, workflow permission escalation, secret change, or repository setting change without separate approval.
- A successful narrow offline test proves only its checked-out files and named test command. It does not establish integrated correctness, market identity, profitability, TEST acceptance, PAPER readiness, or LIVE readiness.

## 2. Incident severity and first response

### Critical — possible boundary breach or financial/control action

Examples: unexpected exchange request, credential exposure, protected-path access, publishing/TEST workflow unexpectedly started, or any attempted order/account action.

1. Stop the affected workflow or process using its ordinary cancellation/disable control, if available and safe. Do not dispatch another run.
2. Do not retry, investigate by reading protected files, or reproduce the event against a live provider.
3. Preserve the exact repository SHA, workflow/run URL and ID, event type, branch, actor, timestamps, job logs, artifact IDs and SHA-256 digests. Redact secrets and personal/account data; never paste secret values into issues or tracker entries.
4. Keep LIVE disabled and PAPER unavailable. Do not run dataset publication, backtests, TEST, or provider requests.
5. Escalate to the repository owner and appropriate GitHub/security administrator for any credential revocation, secret rotation, permission change, or account-level action. This runbook does not authorize those changes.
6. Record the incident as unresolved until independent security review establishes cause, scope, containment and recovery evidence.

### High — integrity, test-scope, or provenance failure

Examples: a test imports a protected module, unexpected files enter a sparse checkout, a reviewer runs against the wrong SHA, checkpoint identity is mismatched, or a workflow has write permissions where read-only is expected.

1. Treat the run as failed and unaccepted. Do not infer success from partial steps.
2. Preserve the failing run, exact head/base SHA, changed-path comparison, workflow file SHA, job logs and artifact hashes.
3. Do not weaken import guards, allowlists, identity checks, retry ceilings or permission scopes to make the run pass.
4. Correct the smallest unprotected source/workflow defect on a dedicated branch and rerun only the exact approved bounded workflow.

### Medium — ordinary candidate CI or documentation failure

1. Identify the exact failing test/step and commit SHA.
2. Determine whether the failure is a source defect, stale run/head, infrastructure issue, missing sparse-checkout dependency, or quota block.
3. Make a minimal forward-only correction, then require a new run on the exact resulting SHA.
4. Preserve both the failed run and corrected passing run; never overwrite or relabel historical evidence.

## 3. Repository and branch recovery

Before every repository write:

1. Refresh the live default branch, relevant PR state, head SHA, base branch and base SHA. Do not rely on an old handoff for current refs.
2. Confirm the intended topic branch head still equals the parent SHA used for the proposed commit.
3. Compare the parent and proposed head. Review every changed path and ensure only the intended files changed.
4. Verify protected paths and modules are absent from the changed-path list and all test import closures.
5. Use a normal fast-forward commit on the existing topic branch or a new branch based on the selected baseline. Never write directly to `main`.
6. Use a compare-and-swap/expected-head update where available. If the expected SHA no longer matches, stop and re-inspect rather than forcing the update.
7. Leave PRs draft/open until exact-head tests and independent review support a separate acceptance decision. Never merge through this runbook.

### Baseline distinctions

- `main` is the selected integration baseline. Its currently recorded SHA is `731fc9fbb892dadccc64bf52da2f91ff069da124`; refresh before use.
- `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a` is a historical engineering baseline, not current main.
- PRs based on M6, stacked PRs, holdout-design branches and clean-main candidates are distinct candidate lines. Do not treat separate passing suites as one integrated system.
- A PR base that is not current `main` is not ready for direct mainline acceptance. Reconcile dependencies and exact changed paths before any future integration proposal.

## 4. CI and test-evidence recovery

For each run, record:

- Workflow name/path and workflow file SHA.
- Exact event, branch, run ID, attempt, and head SHA.
- Python runtime version.
- Sparse-checkout paths and exact test command(s).
- Per-suite counts, pass/fail/error totals, and relevant failure excerpts.
- Artifact name/ID, ZIP SHA-256, extracted file SHA-256, schema and retention expiry.
- Whether the run is synthetic, selected/offline, component-only, integration, or end-to-end.

Do not sum overlapping suites from different workflows into a project-wide test count. Do not claim a run tests a commit unless the log confirms the exact checked-out SHA. A skipped, cancelled, timed-out, stale-head, syntax-only, synthetic-only or partially completed job is not a passing source review.

### Independent scanners and repository-scope verification

A workflow's sparse checkout constrains only that workflow job's checkout. Do not assume it also constrains a separate CodeQL, static-analysis, dependency-scanning, GitHub App, or third-party scanner that may obtain source independently.

Before enabling or dispatching an independent scanner on a candidate PR:

1. Identify the scanner workflow/action or external app, exact version/commit pin, event trigger, token permissions, source acquisition method, and exact commit SHA it analyzes.
2. Establish from its documented/configured behavior and run evidence whether it reads a sparse working tree, a full repository checkout, or a remote Git tree/API. Treat an unknown source scope as **unverified**, not as safe.
3. Check whether any protected/excluded path can be fetched or analyzed, including through a full checkout, archive download, Git API, CodeQL database creation, or a separate job. A sparse checkout in the offline-test job is not evidence about a different scanner job.
4. If the scanner's source scope cannot be proven to exclude protected paths, keep that scan disabled and escalate to the repository owner/admin for a specific scope decision. Do not weaken protected-path controls or grant broader permissions to make it run.
5. Preserve the scanner workflow SHA, action/tool pin, event, branch, analyzed commit, permissions, source-scope evidence, and result/artifact identifiers. Do not report scanner acceptance based only on a green unrelated offline test.

This section is a stop/escalation rule; it does not authorize enabling scanners, modifying repository security settings, or running scans.


### Quota and retry handling

- Retain the approved model/provider, credentials configuration, four bounded retries and 120-second maximum wait.
- If the provider returns HTTP 429 and requests a reset longer than 120 seconds, stop and preserve the checkpoint artifact. Do not increase the wait, switch provider/model, rotate credentials or change secrets to force progress.
- Retry only after the last reported reset window has passed. Do not start parallel or duplicate reviews.
- Keep each review bound to one exact PR head. A checkpoint from an earlier SHA must never be resumed against a newer SHA.
- If a review workflow uses a derivative recovery workflow, validate the complete lineage: exact artifact source run ID, original approved review run, repository, workflow ID/path, approved branch, base SHA, review head SHA, immutable reviewer commit and approved model.
- Treat every checkpointed report as untrusted input. Validate schema and identity, independently inspect the roles and verdicts, and require all specialists, Commander synthesis, independent acceptance and final verification. A partial PASS WITH FINDINGS report set is not acceptance.
- Save artifact hashes and run lineage into the completion tracker before the seven-day Actions artifact retention expires. Never record secret values.

## 5. Rollback and forward recovery

### Unmerged topic-branch change

1. Stop further writes to the affected branch until the parent and changed paths are rechecked.
2. Identify the bad commit and its parent. Preserve the bad diff and failed run evidence.
3. Prefer a normal, reviewable forward revert commit or a minimal corrective commit on the same topic branch. Inspect the full resulting diff and run bounded tests on the new head.
4. Do not reset, rewrite history, force-push, delete the branch, or close the PR merely to hide a failed attempt.
5. If the correction would touch protected paths or requires changing an approved security boundary, stop and request a separate specific authorization.

### Merged or default-branch incident

This project’s operating rule is that no PR may be merged under this runbook. If an already-merged/default-branch incident is discovered, do not improvise a reset or direct production fix. Preserve the exact merge commit and evidence, then request owner/admin authorization for a forward revert PR and independent review.

### Workflow or artifact recovery

- Prefer rerunning only failed jobs when the workflow and source head are unchanged and the rerun is safe.
- For a changed head, create a new exact-head run; never relabel a prior run.
- For missing/corrupt/mismatched checkpoint artifacts, fail closed and restart only from a valid checkpoint for the exact same SHA or from a fresh run after cooldown.
- Expired artifacts cannot be treated as recoverable evidence. Preserve available hashes, logs and tracker entries and report the limitation.

## 6. Provider, dataset and trading boundaries

- Offline tests must use synthetic fixtures or local socket pairs. They must not call Tokocrypto or any other provider.
- Do not execute the research-data workflow, cross-check acquisition, dataset publication, TEST evaluation, or backtest pipeline while the approved identity, protected import boundary and publication controls remain unaccepted.
- The independent Coinbase/Bitstamp cross-check authorization set is empty. Do not fetch those providers or create evidence suggesting that data was acquired.
- The system has no accepted evidence of instrument/venue identity, realistic current fees/slippage, positive chronological out-of-sample profitability, integrated FIFO/partial-close accounting, portfolio controls, or independent emergency-stop lifecycle.
- PAPER remains NOT READY. LIVE remains DISABLED. An incident must never be “tested” by submitting an order, funding an account, or connecting credentials.

## 7. Recovery acceptance checklist

An incident is closed only when all applicable items are evidenced:

- [ ] Exact incident scope, baseline, branch, head SHA and timeline recorded.
- [ ] All relevant workflow logs, run IDs, attempts and artifact hashes preserved.
- [ ] Protected-path and operating-boundary checks completed without protected access.
- [ ] Root cause and impact are independently reviewed.
- [ ] Minimal correction is on a dedicated branch with a complete changed-path review.
- [ ] Exact-head Python/runtime/test evidence passes for the stated bounded scope.
- [ ] Immutable reviewer identity, model, role coverage and checkpoint provenance are verified where applicable.
- [ ] All 16 specialists, Commander, independent acceptance and final verification pass for a Q0.8 review; otherwise the review remains inconclusive.
- [ ] Rollback/recovery procedure is documented and reviewed; any destructive or account-level action has separate owner/admin approval.
- [ ] Tracker and handoff are updated with verified evidence and remaining blockers.
- [ ] Profitability, PAPER readiness and LIVE status are assessed separately; no CI result is substituted for them.

## 8. Current known state at runbook drafting

This file is a draft on a branch based on `main`. It has not been operationally exercised and earns no verified project-maturity credit until accepted.

At the recorded baseline: project scope contains 40 owner-approved requirements / 100 points; overall completion is UNRATED; the historical first-pass candidate maturity is 15.00/100 and is not a completion percentage; profitability is NOT PROVEN; PAPER is NOT READY; LIVE is DISABLED. Candidate PR and Actions states must be re-read before acting because they can change after this document is written.
