# AI Trading Lab — Safety Review Register

**Status:** OPEN — READ-ONLY FINDINGS, NOT AN ACCEPTANCE  
**Review branch:** `chore/claude-engineering-tooling`  
**Reviewed project baseline:** `feature/m6-risk-engine`, previously recorded baseline `cd451972e3a641ad6fa78e64abf3968655a4b82a`  
**Related correction candidate:** PR #56, head `fc1804b60bec69f46c5bbd17a9a0d0a538e9f311`

This register records concrete issues found during source and workflow inspection. It is a planning and review artifact only. It does not change runtime behavior, approve a workflow, accept a milestone, or establish that the system is safe.

## Plain-language status

The trading lab is **not yet verified safe for automated operation**. Several existing paths can make external requests, write reports or datasets, or bypass an expected research check. The approved Tokocrypto boundary is narrower than some existing code paths.

No Tokocrypto login is needed for the public market-data work described here. Never provide passwords, OTPs, API keys, wallet secrets, or private account access.

## Findings

### SAF-001 — Excluded Tokocrypto host remains a configured fallback

- **Severity:** CRITICAL
- **Evidence:** `config.json` blob `8d697eafacdb6b7132209bbad4db8b8f3f9f122d`; `run.py` blob `26fca501cd10dda3dbaf26bb59060791f6bf8dbc`.
- **Observed:** Configuration includes `https://www.tokocrypto.com` with the `open_v1` style. The runner loops through configured sources and continues to the next source after an API failure.
- **Impact:** The excluded host is an executable fallback, not merely stale documentation. This conflicts with the approved Tokocrypto exception, which is limited to unauthenticated GET server-time and candle requests on `www.tokocrypto.site`.
- **Required disposition:** Remove or disable the excluded source and make unauthorized provider configuration fail closed before any request. Do not implement without a separately authorized exact change scope.

### SAF-002 — Diagnostic probe includes endpoints and output outside the approved boundary

- **Severity:** CRITICAL
- **Evidence:** `probe.py` blob `d59f3c8c26d6c4adccb75bab133d01844762be31`.
- **Observed:** Probe code calls symbol-information endpoints, reads response bodies without the bounded-read rule, and records raw URLs, response snippets, and raw network exception text.
- **Impact:** It can contact endpoints not included in the approved Tokocrypto exception and expose provider/request details in reports.
- **Required disposition:** Keep this probe unrun. Replace it with a narrowly scoped, sanitized, bounded diagnostic only after explicit authorization and review.

### SAF-003 — Market-data workflow has autonomous network and write behavior

- **Severity:** CRITICAL
- **Evidence:** `.github/workflows/market-data-check.yml` blob `e427427bd142676904860e24026e984684eb7576`.
- **Observed:** The workflow has a daily schedule and a push-to-main trigger; it runs live provider checks, the Tokocrypto probe and runner, and a broad network diagnostic. It requests `contents: write` and force-pushes reports to the `data` branch.
- **Impact:** A routine push or schedule can initiate external requests and publish artifacts without a fresh human decision for each run. The force-push can replace the report branch history.
- **Required disposition:** Keep workflow execution disabled pending a reviewed trigger/permission/publishing design. Proposed direction: manual-only, least-privilege read-only permissions, no broad network lab, and no destructive force-push. Exact workflow changes require separate authorization.

### SAF-004 — Research history path uses symbol-info endpoint

- **Severity:** HIGH
- **Evidence:** `research/history.py` blob `cfe494f326ec217dbea127b9e297e8cb64f5b705`.
- **Observed:** The history fetch path calls `/api/v3/exchangeInfo` before fetching server time and candles.
- **Impact:** If configured for Tokocrypto, this is outside the approved server-time/candles-only exception.
- **Required disposition:** Do not use this path against Tokocrypto under the current approval. A provider-neutral allowlist must reject this path before network access.

### SAF-005 — Research cross-check still contains Bitstamp and Coinbase request paths

- **Severity:** HIGH
- **Evidence:** `research/crosscheck.py` on the M6 branch, blob `16e0558640128ae061a12bb840a9f110e813a888`.
- **Observed:** The implementation contains Coinbase and Bitstamp data requests. The owner-approved D2 decision excludes Bitstamp from the correction scope and disallows introducing new external hosts.
- **Impact:** The active research path may make requests to providers not approved by the current provider policy.
- **Required disposition:** Keep the cross-check path blocked until its allowed-provider contract and implementation scope are reconciled with the approved decisions. No request was made during this review.

### SAF-006 — Research backtest continues after cross-check failure

- **Severity:** HIGH / POLICY DECISION REQUIRED
- **Evidence:** `.github/workflows/research-backtest.yml` blob `7a546b0b49e4faab777bf3be8656230342b78152`.
- **Observed:** The cross-check step uses `continue-on-error: true`; the backtest step can continue afterward. The workflow also has write permission and publishes results to the `research-data` branch.
- **Impact:** If cross-checking is a mandatory data-integrity gate, the current workflow does not enforce that gate. If it is informational only, that policy needs to be explicit.
- **Required disposition:** Owner must decide whether cross-check failure blocks a backtest. Until decided, do not describe cross-check as a hard gate.

### SAF-007 — Transport and parsing hardening remains incomplete in PR #56 candidate

- **Severity:** HIGH
- **Evidence:** PR #56 head files: `fetcher.py` blob `c8aa23fbd0b4c16cacb47bc9b806fa48d255e9f2`; `providers.py` blob `ee19ae8b4c597281f597de85117976700bd5c810`.
- **Observed:** The candidate still has unbounded response reads, no complete exact-host/path allowlist and explicit redirect rejection, timestamp coercion through `int()`, and silent duplicate deduplication. The HTTP helper also retries network exceptions and has a `None` status path that needs an explicit contract.
- **Impact:** The candidate does not yet satisfy the full owner-approved hardening policy D1–D8.
- **Required disposition:** Keep PR #56 not merge-ready. Complete the v7 specification/test-plan reconciliation first, then implement only after scope-specific authorization.

### SAF-008 — Documentation handoff drift

- **Severity:** MEDIUM
- **Evidence:** Previously inspected default-branch `PROJECT_HANDOFF.MD` at commit `bd86e8c503b4210978f6dc587cb2abbfe52ec0c4`.
- **Observed:** The handoff describes an older Milestone 3 state and does not represent the current M6 architecture and gates.
- **Impact:** A future contributor or agent could follow stale milestones or misunderstand the current project state.
- **Required disposition:** Prepare a reconciled current handoff from authoritative ADR/progress/sequencing records. Do not overwrite the authoritative records or protected material.


### SAF-009 — Existing regression tests encode behavior that conflicts with approved hardening decisions

- **Severity:** HIGH
- **Evidence:** PR #56 head test blobs: `tests/test_fetcher.py` `b2a3865a23f3e05c6b88dda225f65c3b2e0ac014`; `tests/test_live_check.py` `2fcf82389dd465341821b77a38fe7417fceae763`; `tests/test_research_sanitization.py` `23b6acd7d1e31cf4fe10e4368752d497e0e4df17`.
- **Observed:**
  - `test_network_errors_exhaust_retries` expects network exceptions to be retried, while approved D6 wording says retry only HTTP 429 and 5xx.
  - Provider adapter tests expect paginated candles to be deduplicated; current `_dedupe_sorted()` silently keeps one row for each timestamp. D5 requires rejecting duplicates within a response; cross-page duplicate behavior remains a separate owner decision.
  - Research sanitization tests still exercise Bitstamp, although approved D2 excludes Bitstamp from the correction scope.
  - The tests do not close the known gap around a response object returning `status=None`.
- **Impact:** A green test suite could preserve behavior that violates the approved policy. Tests must be reconciled with the decision record before they can serve as acceptance evidence.
- **Required disposition:** Update the v7 test plan and expected test behavior first. Do not run or modify tests without exact authorization.

## Mandatory safety gates before any automated operation

1. Exact provider host, method, path, port, redirect, and query allowlist enforced before network access.
2. No Tokocrypto account authentication, private endpoints, symbol-info, or `open/v1`.
3. Bounded response reads, deterministic response closure, strict status handling, and sanitized failures.
4. Strict timestamp and OHLCV validation; duplicates rejected rather than silently discarded.
5. No autonomous workflow or schedule until triggers, permissions, external hosts, and publishing behavior are explicitly approved.
6. Research and backtest gates must fail closed when a mandatory integrity check fails.
7. Portfolio accounting must use exact decimal arithmetic and preserve partial-closure conservation/idempotency.
8. Risk must fail closed on invalid/stale/incomplete inputs; strategy cannot bypass risk or portfolio ownership.
9. Emergency stop and PAPER safeguards must be independently evidenced before any PAPER execution authorization.
10. LIVE trading remains unavailable.

## Work deliberately not performed

- No tests, scripts, CI workflows, deployments, or scheduled jobs were run.
- No exchange or external provider requests were made.
- No credentials, account data, wallets, or private endpoints were accessed.
- No protected path or Workstream B implementation/data was accessed.
- `validator.py` and `report.py` remain unread.
- No source, test, workflow, or runtime configuration was changed.
- No branch merge, PR approval, or milestone acceptance was performed.

## Acceptance state

- PR #56: **NOT MERGE-READY** pending v7 correction and complete evidence.
- Step 6: **NOT ACCEPTED**.
- Step 7: **BLOCKED**.
- Step 10: **DESIGN-ONLY**.
- Overall automated-operation safety: **NOT ESTABLISHED**.

This register is a set of review findings and a proposed remediation sequence, not a certification or guarantee of safety.
