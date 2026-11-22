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


### Manual Q0.8 specialist-review dispatch (GitHub web / iPhone)

The default branch contains `.github/workflows/q08-specialist-review.yml` with `workflow_dispatch` and the three inputs `review_head_sha`, `resume_from_run_id`, and `mode`. GitHub requires the manually triggered workflow to exist on the default branch; the Actions page then allows the operator to select the topic branch for the run.

1. Open the repository in GitHub, tap **Actions**, and select **Q0.8 immutable 19-role specialist review**.
2. Tap **Run workflow** and select `security/q0-provider-sanitization-2026-11-18` in the branch dropdown.
3. Re-fetch PR #60 immediately before dispatch. Copy its exact current head SHA into `review_head_sha`; do not copy an older tracker/handoff SHA.
4. For a resume, verify the source run has an uploaded checkpoint and inspect its artifact identity: repository, workflow, approved branch, base SHA, exact same review-head SHA, model and schema. Enter that source run's numeric ID in `resume_from_run_id`. Leave it blank only for a fresh review with no checkpoint.
5. Set `mode=review`, confirm the latest 429 reset window has elapsed, and tap **Run workflow** once. Do not create duplicate parallel reviews.

If PR #60 advances after verification, stop: refresh the SHA and use only a checkpoint bound to the new exact head. Never resume an earlier-head checkpoint against a newer commit. A partial report set remains inconclusive; acceptance requires all specialists, Commander synthesis, independent acceptance and final verification. This procedure does not authorize changes to the model/provider, retry ceiling, secrets, permissions, protected paths or any trading workflow.

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


## 9. Superseding Q0.8 trusted-workflow dispatch correction — 23 November 2026

**This section supersedes the branch-selection instruction in §4 for any review that uses the LLM secrets. Do not select the PR #60 topic branch for a secret-bearing review.**

- PR #97 is the trusted-default-branch workflow correction. Its current draft head is `3dba39b969db376211906ee5e7d35631a1af74b1`; it pins immutable reviewer `cf9f319bc86155e7669f2cf0ced5d4df53cebffa`, matching the latest PR #60 branch workflow. PR #97 is still open/draft/unmerged.
- The current default `main` workflow still pins the older reviewer `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9`. Do not treat it as the current bounded reviewer for the latest PR #60 diff.
- Until PR #97 is separately approved and merged, **do not dispatch review mode from the unprotected PR #60 topic branch**: that branch's workflow definition receives `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`. A manual-only trigger does not make an unprotected workflow definition trusted.
- After PR #97 is merged and the updated workflow is present on protected `main`, open Actions and select **Q0.8 immutable 19-role specialist review**. Select **`main`** in the branch dropdown so GitHub runs the trusted default-branch workflow; do not select the PR #60 topic branch.
- Immediately before dispatch, re-fetch PR #60 and copy its exact current head SHA into `review_head_sha`. At this 23 November refresh the head is `e8674dbfe3efd2339ddb028484362f9466f7b058`; this is a snapshot, not a permanent value.
- For that head, use a fresh review: leave `resume_from_run_id` blank because no checkpoint has been verified for SHA `a68b759b...`. Set `mode=review` and submit once. Never reuse a checkpoint from an earlier SHA.
- If a 429 interrupts the run, preserve the artifact and run ID. Resume only after the reported reset window and only when repository, workflow, branch, base SHA, exact review SHA, reviewer, model and checkpoint schema all match. Keep the approved four retries and 120-second maximum wait; do not switch providers/models or increase limits.
- PR #97's merge is an owner/admin decision and is not authorized by this runbook. This section does not authorize merging, changing secrets/permissions, or accessing protected paths.


### 9.1 Automatic-resume workflow audit — 23 November 2026

- PR #60 advanced to `e8674dbfe3efd2339ddb028484362f9466f7b058`. Exact-head offline run [#45055081357](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45055081357) passed **103/103** selected tests on Python 3.11.18. The Q0.8 review check remains skipped; no specialist review is claimed.
- Commits `49f9810...`, `8f9f952...`, and `e8674db...` added and iteratively hardened an `auto_resume` job. The latest follow-up corrected the HTTP 429 grep expression, secret-screening expressions, dispatch input type, and added the missing pull-request read scope. The earlier `GITHUB_OUTPUT` override was removed. Those earlier defects are not current findings.
- The remaining automatic-resume implementation is not authorized and must not be dispatched:
  1. It dispatches the next run immediately; it does not parse or wait for `Retry-After` / provider reset time.
  2. It permits up to three extra workflow runs, each of which can repeat the review runner's four bounded model attempts. This multiplies the approved retry budget and conflicts with the user's explicit manual-resume/no-repeated-dispatch instruction.
  3. The topic branch is unprotected and the auto-resume job grants `actions: write`; do not expose or use that workflow with secrets.
- The prior user instruction remains controlling: preserve the $0 budget, wait until the provider's stated reset, then manually resume the same exact review SHA from an eligible identity-matching checkpoint. Do not repeatedly dispatch, increase the retry ceiling, or add paid fallback.
- The current PR #60 head `e8674db...` has no verified same-head checkpoint. After PR #97 is merged, start a fresh trusted-main review with `resume_from_run_id` blank. If that run later stops at HTTP 429, wait for the actual reset and manually resume from its newest verified checkpoint run ID, keeping the SHA unchanged.
- PR #98 remains based on the earlier PR #60 SHA `a68b759b...`; it is three commits behind current PR #60 and must be synchronized before integration. Its 16/16 test result remains evidence for its own exact head only.


### 9.2 Trusted-main automatic trigger review — 23 November 2026

**This section supersedes the assumption in §9.1 that PR #97 remains manual-dispatch-only.**

- PR #97 has advanced to `62352cca01fbff8a1fc6924620b2a3a7d0600c62` and now includes a `workflow_run` trigger. After PR #97 is merged to protected `main`, every matching successful PR #60 offline workflow completion can automatically start the 19-role LLM review using the trusted-main workflow and its LLM secrets.
- Positive controls: the gate helper checks repository, branch, workflow identity and immutable offline-workflow blob; the trusted reviewer remains pinned; the candidate is fetched through the API and is not checked out or executed; the review job is read-only.
- **This automatic LLM-trigger behavior is not authorized by the owner. Do not merge or enable the current PR #97 head until the owner explicitly chooses manual-only or automatic review.** The new trigger has no demonstrated same-head idempotency/deduplication gate; concurrency serializes runs but does not prevent duplicate reviews from repeated successful offline runs or reruns. It can consume the configured LLM quota automatically.
- The gate-test workflow run [#45055262845](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45055262845) failed with zero job records; no gate tests executed and no passing result is claimed. CodeQL Actions passed; CodeQL Python was still in progress at the last check.
- GitHub documents that `workflow_run` only triggers when its workflow file exists on the default branch, and that the resulting workflow can access secrets/write tokens even when the triggering workflow cannot. Therefore the new behavior becomes active after PR #97 is merged. See [GitHub workflow_run event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run).
- If the owner chooses **manual-only**, remove the `workflow_run` trigger and its automatic-review assumptions before merge; then select `main` in the Actions branch dropdown and manually dispatch with the exact current PR #60 SHA. If the owner chooses **automatic**, first add and test an exact-SHA idempotency gate, explicit opt-in/activation control, duplicate-run suppression, and safeguards preserving the approved $0/retry/reset policy. Do not combine automatic and manual dispatch for the same head.
- Current PR #60 head remains `e8674dbfe3efd2339ddb028484362f9466f7b058`; no Q0.8 specialist review has run. PR #97 remains draft/open/unmerged. No merge or automatic LLM invocation is authorized by this runbook.
