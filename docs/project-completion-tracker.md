# AI Trading & Automation Laboratory — project-wide completion tracker

**Status:** Provisional scope register; not yet a valid percentage score  
**Last checked:** 2026-11-18  

> **Snapshot rule:** Sections dated later in this document are authoritative for current PR heads, merge state, workflow pins, and verification status. Earlier PR descriptions and status tables preserve historical snapshots; when they conflict with a later reconciliation addendum, the later addendum supersedes them.
**Repository:** `ruthlessjoey/btcidr-trading-lab`

## Why the overall percentage is currently unrated

The repository's `PROJECT_HANDOFF.MD` on `main` is the recovered master continuation brief (blob `5ff795aa384302bece43c7f40e3edcec30e8e6a3`). It establishes the broad whole-project vision and several historical milestones, but it is an older handoff rather than a complete, current acceptance specification: it does not decompose every future subsystem into testable requirements or assign weights. The Workstream B handoff is separate and does not authorize access to its protected implementation.

The recovered vision is materially broader than the current BTC/USDT research implementation: multi-market research and signal coverage, cross-market opportunity ranking, BUY/SELL signals, risk management, and eventual support for up to 10 simultaneous positions. The current operating scope remains research-only; the handoff explicitly excludes account connections, credentials, automatic orders, and real-money execution.

A numeric whole-project completion percentage would still require inventing detailed acceptance criteria and weights or silently omitting protected work. This tracker therefore remains provisional and UNRATED while it records the recovered requirements, implementation evidence, and blockers.

## Authority, baselines, and exclusions

### Evidence sources

- `main`: `3d478a37ce2963abbc9d89f6843d6f806d6d28f5` at the time of this tracker.
- M6 engineering baseline: `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Q0.3–Q0.8 corrections plus provider sanitization are integrated as a candidate in draft PR #60, based on `feature/m6-risk-engine`; it is not merged.
- PR #56 is retained as a historical draft and is explicitly superseded by PR #60.
- PR #63 (opt-in gating for the legacy Workstream A immutable reviewer) is merged to `main` at merge commit `fbfe7429128a0e251b281a54fad138b513481b55`; the default-branch workflow now requires the explicit `workstream-a-review` label and preserves its fixed 25-path allowlist. - PR #57 (default-branch workflow protected-path isolation) remains open, non-draft, head `b475a7116cc81d63af670237e5c6d13676763feb`; it is 11 commits ahead and 2 behind current `main`, with exactly seven workflow files changed. Its Q0.8 specialist workflow now pins the corrected immutable reviewer commit `b6c966c4b55bd175ed91f10202b069b0f6dfb43c`. The PR remains unmerged; the old Workstream A failure predates PR #63.
- The repository's `CLAUDE.md` and `docs/development-stack/roadmap.md` define the current access, trading, and tooling constraints.

These are distinct baselines. Do not treat a feature branch, draft PR, or successful historical run as if it were integrated into `main`.

### Protected and excluded scope

No work in this tracker authorizes access to:

- `P1/`
- `signal/data/` or any other `signal/` path
- protected Workstream B implementation, data, or artifacts
- `validator.py`, `report.py`, or any other separately protected module

Those areas are not inspected, tested, checked out, or scored here. Their status remains **UNVERIFIED / EXCLUDED** until the owner provides separate, exact-scope authorization or independent evidence that can be assessed without access.

Trading constraints remain: spot-only and long-only; no shorts, leverage, margin, or derivatives; no credentials or private exchange/account access; no wallet, order, withdrawal, or LIVE execution. PAPER remains unavailable until its safeguards and emergency-stop boundary are separately accepted.

## Proposed whole-project requirement inventory and weights

The following is a proposed decomposition of the recovered master vision into testable requirements. It is intentionally separate from the current component-status register. **Weights are proposed, not owner-approved; no percentage may be calculated from them until the owner accepts or revises them.**

| ID | Requirement / subcomponent | Proposed weight | Minimum acceptance evidence |
|---|---|---:|---|
| A1 | Mission, operating modes, and phase boundaries | 2 | Versioned scope distinguishes research, signals, PAPER readiness, and excluded LIVE/account operations |
| A2 | Provider-neutral, modular architecture | 2 | Stable interfaces and dependency-direction tests across approved market-data and research modules |
| A3 | ADRs, ownership, and invariants | 3 | Current ADR matrix; strategy/risk/portfolio ownership proven by interface tests |
| B1 | Crypto market-data coverage | 3 | Approved public adapters for explicitly supported established, meme, newly listed, and DEX-pair data; each source has a separate authorization and test set |
| B2 | Non-crypto market-data coverage | 3 | Approved public adapters for stocks/ETFs, forex, indices, commodities, and any other owner-selected instruments |
| B3 | Common instrument and candle schema | 2 | Provider-neutral normalized schema preserves venue, instrument identity, quote currency, source timestamps, and provenance |
| B4 | Provider reliability and freshness | 2 | Timeouts, rate limits, bounded responses, retries, stale/partial/unavailable states, and no silent gap filling are tested |
| C1 | Market identity and source provenance | 3 | Dataset identity is bound to venue, instrument, quote asset, timeframe, and source evidence |
| C2 | Data-quality validation | 3 | Ordering, duplicates, gaps, candle closure, numeric finiteness, timestamp units, and completeness have positive and negative tests |
| C3 | Immutable dataset versioning and publication | 3 | Hash-bound manifests, atomic publication, path confinement, rollback, and tamper detection pass exact-head tests |
| D1 | Strategy research framework | 2 | Reproducible strategy interfaces and deterministic synthetic fixtures |
| D2 | Chronological splits, causality, and selection | 3 | No look-ahead leakage; train/validation/test boundaries and selection are reproducible and tested |
| D3 | Fees, slippage, and execution assumptions | 2 | Cost scenarios are explicit, sensitivity-tested, and never presented as verified venue rules without evidence |
| D4 | Holdout reservation and backtest integrity | 3 | Once-only/overlap protection, frozen choices, refusal-with-no-output behavior, and migration safety pass independent tests |
| E1 | Multi-market universe discovery and eligibility | 3 | Supported instrument universe is bounded, provenance-backed, deduplicated, and excludes unsupported/unsafe instruments |
| E2 | Cross-market opportunity ranking | 4 | Ranking is reproducible, explainable, benchmarked, and evaluated for coverage, false positives, and stale data |
| E3 | Scanner orchestration and opportunity lifecycle | 3 | Bounded scan cadence, deterministic candidate handling, failure isolation, and no hidden order execution |
| F1 | Standard signal contract | 2 | BUY/SELL candidate schema includes instrument, timeframe, timestamp, rationale, invalidation, confidence/uncertainty, and provenance |
| F2 | Signal generation | 3 | Signal engines are deterministic under fixtures and evaluated out-of-sample across approved markets |
| F3 | Signal validation and explainability | 2 | Invalid, conflicting, unsupported, or stale signals are rejected with auditable reasons |
| F4 | Signal expiry and stale-data handling | 2 | Signals expire deterministically and cannot be revived by delayed or partial data |
| G1 | Risk limits and sizing | 3 | Risk constraints are explicit, unit-tested, and fail closed for invalid sizing or exposure |
| G2 | Stop proposal, validation, and ownership | 3 | Strategy proposes; risk validates; portfolio owns accepted stop; interface tests enforce the boundary |
| G3 | Portfolio-level exposure and concentration | 2 | Aggregate risk, correlation/concentration constraints, and position limits are tested |
| G4 | Fail-closed risk gates | 2 | Missing, stale, malformed, or unauthorized inputs cannot produce an approved action |
| H1 | FIFO portfolio ledger and partial closes | 4 | Quantity, cost basis, realized/unrealized P&L, and partial-close conservation pass independent tests |
| H2 | Fee and slippage accounting | 2 | Costs are recorded consistently across entries, partial exits, and final closures |
| H3 | Up to 10 simultaneous positions | 2 | Position cap, allocation, concentration, and concurrent lifecycle tests prove the stated capacity |
| H4 | Risk-to-portfolio approval bridge | 2 | A valid approval reference and exact approved quantity bind each paper fill; duplicates and mismatches fail closed |
| I1 | PAPER lifecycle | 3 | End-to-end paper lifecycle is deterministic, restartable, and cannot be confused with LIVE |
| I2 | Independent emergency stop | 3 | Emergency stop blocks paper execution independently of strategy generation and is tested under failure conditions |
| I3 | Audit, replay, and recovery | 2 | Event history, restart/replay, corruption handling, and recovery behavior are independently verified |
| J1 | Mobile-first operator dashboard | 2 | Clear mobile presentation of market status, candidates, signal state, and risk state |
| J2 | Monitoring and health reporting | 2 | Stale data, provider failures, scan health, and system degradation are visible and testable |
| J3 | Safe manual controls | 1 | Manual pause/stop/review controls cannot bypass risk gates or trigger LIVE actions |
| K1 | Access, secrets, and network boundaries | 3 | Protected paths remain excluded; no secrets/private account access; network is allowlisted and least-privilege |
| K2 | Test and verification system | 3 | Offline unit, integration, regression, mutation, and security tests run on exact commits with preserved outputs |
| K3 | Supply-chain integrity | 2 | Actions/dependencies are pinned, provenance and hashes verified, licenses and compatibility recorded |
| K4 | CI and review automation | 2 | Manual/automated workflows are least-privilege, protected-path-safe, bounded, and independently checked |
| K5 | Documentation, rollback, and incident recovery | 2 | Current runbooks, ADRs, known limitations, rollback procedures, and incident evidence are maintained |

**Proposed total: 100 points.** The component register above maps current evidence to this inventory; it does not grant access to protected Workstream B files or change any trading authorization.

### Explicit exclusions from this completion denominator

- LIVE trading, real-money execution, deposits, withdrawals, and account funding.
- Exchange credentials, private endpoints, account login, balance synchronization, and wallet custody automation.
- Shorts, leverage, margin, and derivatives.
- Any feature that requires bypassing protected paths or an unapproved provider/host.

Public DEX-pair market-data discovery is only a future research possibility under B1; wallet access, signing, swaps, and DEX execution are excluded. A SELL signal means reducing or closing a long spot position, not opening a short.

### Evidence-based scoring rubric

For each requirement row, the proposed maturity scale is:

- **0.00:** no implementation evidence.
- **0.25:** candidate implementation exists, but exact-head tests or integration evidence are missing. Draft PRs and documentation alone cannot score above this level.
- **0.50:** implementation is present on the selected baseline and focused offline tests pass on that exact commit.
- **0.75:** integration tests and scoped security review pass on the exact commit; required dependencies are accepted.
- **1.00:** integrated behavior is independently verified, all acceptance tests pass, and operational evidence exists where the requirement is operational.

A requirement may instead be marked **UNVERIFIED / EXCLUDED** when protected scope prevents assessment; it remains in the denominator and earns no verified numerator credit until evidence is available. A blocked upstream dependency caps dependent requirements at 0.25. Documentation-only completion earns zero implementation credit.

The weighted percentage, once weights are owner-approved, is:

`sum(requirement_weight × verified_maturity) / 100`

The 80% target is met only when that result is at least 80.00 and an independent review confirms the inventory, evidence, and exclusions.

## Component register

| Component | Intended outcome / dependency | Implementation status | Test / verification status | Security status | Remaining work |
|---|---|---|---|---|---|
| Project architecture and ADRs | One provider-neutral architecture with explicit ownership, risk, portfolio, and execution boundaries | Broad vision recovered in `PROJECT_HANDOFF.MD`; current architecture and ADRs are distributed across milestone records and repository instructions | Master brief has no complete decomposed acceptance matrix or weights | Core invariants documented; full architecture reconciliation incomplete | Reconcile the recovered vision with current ADRs and produce a versioned, testable requirement inventory |
| Multi-market data coverage | Read-only, normalized research data for crypto (including established/new/meme/DEX markets), stocks/ETFs, forex, indices, commodities, and other explicitly supported instruments | The verified implementation scope here is BTC/USDT crypto only; broad market categories are vision-level requirements, not evidenced implementations | No cross-market adapter/integration matrix or exact-head validation is established | Public-data and provider approvals remain market-specific; no credentials or private account access | Define a staged provider matrix, instrument identity/schema, source provenance, freshness, and per-provider approval/tests before adding markets |
| Cross-market opportunity scanner and ranking | Discover, evaluate, and rank strongest opportunities across supported markets | No integrated scanner/ranking engine is evidenced in the verified baseline | No ranking evaluation, coverage, latency, or false-positive acceptance criteria are established | Must remain research-only and fail closed on stale/missing/ambiguous data | Define universe discovery, eligibility, ranking objectives, reproducibility, and independent benchmark criteria |
| BUY/SELL signal generation | Produce explainable BUY/SELL candidates from validated research signals | Existing historical strategy work is a single BTC moving-average candidate; a general multi-market signal system is not evidenced | No integrated signal contract, calibration, or cross-market evaluation is established | Signals must not bypass risk validation or imply execution authority | Define signal schema, confidence/uncertainty, invalidation, expiry, stale-data handling, and out-of-sample evaluation |
| Multi-position capacity and portfolio coordination | Eventually support up to 10 simultaneous positions with portfolio-level constraints | Long-term goal recorded in master handoff; protected portfolio implementation is not inspected or scored here | Capacity, allocation, concentration, and portfolio-risk acceptance evidence is unavailable under current access scope | Preserve Workstream B and custody boundaries; PAPER unavailable pending safeguards | Reconcile portfolio-level requirements through separately authorized review without opening protected implementation |
| M1 public market-data transport | Read-only BTC/USDT public candle retrieval, parsing, and reporting | Implemented as a candidate; current approved Tokocrypto scope is only `www.tokocrypto.site` server-time/candles | Q0 offline suite historically passed 35/35 on commit `6678b3d06fc780bbeef21894c9650827a9e52904`; this is not evidence for later heads | Transport allowlist and fail-closed checks exist on the Q0 branch; live-check workflow is blocked where it imports protected modules | Re-run only the sparse, approved offline suite on the exact current Q0 head; independently review transport boundary |
| Provider-response sanitization | Prevent provider-controlled values and exceptions from reaching reports, logs, summaries, or output sinks | Integrated candidate is in draft PR #60 on top of the Q0 allowlist; PR #56 is superseded | Prior project notes report a local isolated snapshot passed 50/50 tests across six approved offline modules; this result was not independently reproduced in the current review and is not a byte-for-byte checkout or exact-head GitHub Actions result. Historical 53/53 run on old PR #56 head remains historical only | Old PR #56 workflow checked out protected `validator.py` and `report.py`; its replacement now blocks before checkout. PR #60 keeps the Tokocrypto-only allowlist and excludes protected imports from the sanitizer test | Q0.8 run #44262541867 passed 51/51 on earlier head `2d6698a2292ecec57a72b74b3f7de7c49d989bc8`; latest head is now `18d02375577aefe39a0a13fabd0a5529f82ac01c` (37 commits ahead, 26 changed paths), and an exact-head rerun is pending after reviewer-scope, protected-test-description, and HTTP 429 retry corrections. The transport now fails closed on HTTP 429 because its response interface does not preserve `Retry-After`; this avoids premature retries that could violate Tokocrypto's documented backoff requirement. The latest PR #60 change places the empty provider-authorization gate inside `research.crosscheck.run_crosscheck` before filesystem or network side effects, shares that gate with the research pipeline, and records the exact sources returning data in the artifact schema expected by the pipeline validator. Official Tokocrypto docs confirm `/api/v3/klines` and millisecond candle timestamps, but do not document `/api/v3/time`; the `.site` server-time route remains UNVERIFIED. Keep unapproved providers disabled and retain PR #56 as historical only. |
| Market identity and historical dataset gate | Verify market identity before publishing a historical dataset | Step 1 deliberately fails closed; it writes no dataset and makes zero network requests | Static/offline tests exist on the Q0 branch; no successful dataset publication is evidenced | Fail-closed gate preserves the current public-route restriction | Owner-approved market-identity method or formal descope; only then implement and verify dataset creation |
| Research cross-check | Compare approved sources without allowing unapproved providers or provider-controlled data to bypass gates | Current cross-check authorization set is empty; cross-checks are blocked | No successful authorized cross-check run is evidenced | Empty provider set is intentionally fail-closed | Keep empty until a separate host/provider authorization and review |
| Dataset integrity and publication | Immutable dataset identity, manifests, hashes, atomic publication, rollback, path confinement | Candidate work exists across stacked PRs #17–#21, #25, and #27; not integrated into the authoritative baseline | Most PR descriptions report static review or tests not yet run; no single integrated exact-head result established here | Security work is present as separate draft changes; end-to-end assurance remains incomplete | Reconcile stack order and bases; run only approved offline tests; verify atomicity, rollback, symlink/path handling, and hash binding |
| Strategy and backtest research | Reproducible strategy selection and backtest evaluation with chronological splits, fees, slippage, and frozen test inputs | Candidate work exists in PR #2 and stacked PRs #16, #18, #20, #23–#24, #28–#36 | No complete integrated backtest verification is established; no profitability claim is permitted | Current backtest execution path reaches protected modules; the backtest workflow is blocked | Resolve protected import boundary without reading protected files; validate full lookback, split integrity, fee/slippage, holdout reservations, and independent out-of-sample evaluation |
| M6 risk engine | Fail-closed risk validation and separation of strategy proposals, risk decisions, and portfolio-owned accepted stops | Implemented on the M6 feature baseline; further security correction is in progress | Exact current-head test evidence and independent acceptance are not established by this tracker | Fail-closed architecture is retained; PAPER/LIVE remain gated | Finish security review, exact-head tests, and interface reconciliation with the portfolio/risk bridge |
| Portfolio ledger and accounting | FIFO accounting, partial closes, fees, slippage, and conservation of quantity/cost/P&L | Protected Workstream B; not inspected or modified here | Not independently verified in this workstream | Protected boundary preserved | Require a separate scope authorization or independent review evidence that does not expose protected implementation |
| Risk bridge and approval boundary | Bind accepted risk decisions to exactly authorized paper fills; reject duplicate, stale, mismatched, or unauthorized events | Protected Workstream B; not inspected or modified here | Not independently verified in this workstream | PAPER remains unavailable until this boundary is accepted | Separate authorization and independent review; preserve one-approval-per-fill and stop ownership |
| Paper-trading lifecycle and emergency stop | Controlled PAPER-only lifecycle with an independently enforced emergency stop and auditability | No accepted integrated paper-execution lifecycle is evidenced | No paper-execution verification is established | PAPER is not authorized merely because code exists; LIVE is unavailable | Complete safeguards, emergency-stop independence, audit trail, replay/recovery and operational acceptance before any paper operation |
| Operations, CI, and security automation | Safe offline testing, bounded specialist review, static workflow audit, least privilege, reproducible evidence | Default-branch workflow isolation is in draft PR #57; integrated Q0 test/review candidate is in draft PR #60 | Prior notes report local YAML parsing and a 50/50 isolated snapshot, neither independently reproduced in this review; exact-head GitHub Actions, Actionlint/zizmor, and specialist review remain unrun | Unsafe legacy workflows block before checkout; safe workflows use sparse allowlists and read-only permissions | The Q0.8 workflow definitions already exist on `main`, so manual dispatch can target the Q0 branch. The corrected specialist-review runner is pinned at immutable commit `b6c966c4b55bd175ed91f10202b069b0f6dfb43c`. Dispatch exact-head tests and specialist review against the latest PR #60 head; the GitHub connector cannot dispatch workflows. |
| Development skills and quality tools | Reproducible, free-first Claude/ChatGPT development support | Guidance-only `security-review` skill is in draft PR #59; protected-path-safe Ruff workflow is in draft PR #61. Context7 and GitHub are already available as ChatGPT tools; repository MCP configuration remains optional | Skill runtime discovery and Ruff execution are unverified; Ruff 0.17.5 GitHub release tag signature and asset digest were checked; its manual workflow YAML parsed locally | Skills are guidance, not a sandbox; Ruff workflow excludes protected files and uses a read-only manual trigger | Review one skill/tool at a time; require explicit approval to merge; verify runtime behavior, license, provenance, dependency hashes, free usage, and permissions |
| UI, monitoring, and operator experience | Clear visibility into multi-market coverage, ranked candidates, signal state, stale-data warnings, auditability, and safe operator controls | Required at vision level; complete implementation evidence is not established in the verified baseline | UNVERIFIED | Must not expose credentials or provide an execution bypass | Decompose into mobile operator views, health/status, signal explanations, audit history, and safe controls; define acceptance tests |

## Dependency map

The known critical path is:

1. Approved public market-data transport
2. Market identity and historical dataset publication
3. Research/backtest integrity and strategy validation
4. Risk engine and risk-to-portfolio interface
5. Portfolio accounting and approved-fill boundary
6. PAPER lifecycle with independent emergency stop
7. Operational auditability and controlled paper readiness

Security, offline tests, documentation, supply-chain review, and CI isolation are cross-cutting gates. A downstream component cannot receive verified-completion credit while a required upstream gate is blocked.

## Current integration picture

Historical inventory: GitHub previously reported **52 open pull requests: 47 draft and 5 non-draft**. This count has not been refreshed after PR #63 merged and must not be treated as current. Many research and hardening changes are stacked on earlier branches rather than integrated into one accepted baseline. This is evidence of substantial candidate work, not evidence that the whole project is complete.

Important current review items:

- PR #56 — Batch 1 provider-response sanitization; draft and superseded by PR #60. Its old workflow explicitly checked out protected files. The default-branch Batch 1 workflow remains unsafe until PR #57 is merged; PR #57's replacement fails closed before checkout.
- PR #57 — default-branch workflow protected-path isolation; open and non-draft, latest head `b475a7116cc81d63af670237e5c6d13676763feb`. Seven workflow files changed; no application source changed. It now pins the corrected immutable Q0 specialist reviewer commit `b6c966c4b55bd175ed91f10202b069b0f6dfb43c`. Its Q0.8 workflow restores six approved offline modules via a 16-path sparse checkout, excluding protected imports. The existing failed Workstream A check was generated before PR #63's merge; the current workflow now gates that reviewer by the `workstream-a-review` label. PR #57 has not been merged. Actionlint/zizmor execution remains pending; the Actionlint 1.7.12 release asset digest was independently matched to GitHub metadata, and all six GitHub Action pins used by PR #57 (checkout v4.2.2/v7.0.1, setup-python v6.3.0/v7.1.0, upload-artifact v4.6.2, and zizmor-action) were confirmed as valid signed commits with matching tag refs where applicable.
- PR #58 — provisional project-wide completion tracker; draft, one documentation file. Its status inventory requires refresh for PR #63 merged and PR #57 still open.
- PR #59 — first repository-specific `security-review` skill; draft, one guidance-only file. Runtime discovery/invocation remains unverified.
- PR #60 — draft Q0 transport allowlist and provider sanitization candidate; latest head `6171486914694a95cde11ef2bc97b0613e3f1b5e`, 26 changed paths, 35 commits ahead of the M6 baseline. Q0.8 run **44265313990** passed the six-module offline suite on the manually selected PR #60 revision; all workflow steps completed successfully. The immutable reviewer scope mismatch was corrected in runner commit `b6c966c4b55bd175ed91f10202b069b0f6dfb43c`; static comparison confirms its 26 expected paths and statuses exactly match PR #60. Specialist review run **44268354049** passed syntax and synthetic policy checks and completed all 19 model calls against exact PR #60 head `18d02375577aefe39a0a13fabd0a5529f82ac01c`. However, diagnostics show 15 of 16 specialist responses ended with `finish_reason=length` at 1,600 tokens. The runner incorrectly accepted truncated responses, so the green job is not a valid complete review and its synthesized verdict must not be relied upon. Corrective runner branch `security/q08-review-truncation-fail-closed-2026-11-18` introduced strict rejection of truncated completions (commit `cc6c9a13808ad4f9a87ed34baba5cd4f48d85f04`). Rerun **44284117830** verified the guard works: syntax and synthetic policy checks passed, but the first `architecture-architect` completion reached the 2,200-token ceiling (`finish_reason=length`) and the run correctly failed closed. A second corrective branch `security/q08-review-token-budget-2026-11-18` raises the bounded per-call budget to 5,000 tokens and response cap to 24,000 characters; immutable runner commit `92bda8aef7e3243062e038f157d44374801ab41e`. PR #57's sparse, read-only specialist workflow now pins this runner at workflow commit `92ab726dc17e6bdcf66caec67e25956776d6a7e7` and retains the explicit `review_head_sha` input. Run **44285252753** exercised the 5,000-token runner against exact PR #60 head `18d02375577aefe39a0a13fabd0a5529f82ac01c`. GitHub Actions job concluded success; logs confirm all 19 model responses had `finish_reason=stop`, all 19 request-complete markers were emitted, and the comparison/model-configuration/diff stages completed. This verifies a complete non-truncated 19-role orchestration run. The actual Commander, independent-acceptance, and verification verdict text is written to `GITHUB_STEP_SUMMARY`, which the available GitHub job-log/artifact interface does not expose; therefore final reviewer acceptance remains **PENDING HUMAN SUMMARY INSPECTION**, not automatically accepted. `tests/test_research_gates.py` imports `research.pipeline`/`research.engine`, whose import chain reaches protected `validator.py`; its header now explicitly marks it excluded from the approved offline suite. No protected implementation was read or executed.
- PR #61 — protected-path-safe Ruff 0.17.5 static-quality workflow; draft, two files, five unprotected root modules, manual-only. The original stacked Ruff PR #42 includes protected paths and is superseded.
- PR #62 — extend Claude Code Read/Edit denies from `signal/data/**` to all `signal/**`; draft, two shared instruction/configuration files. This is defense in depth, not an OS sandbox; the earlier stacked path-hardening PR #46 is superseded.
- PR #43 — optional Context7/GitHub MCP configuration for Claude Code; not adopted here because GitHub and Context7 are already available in ChatGPT and the repo config requires a separate Claude Code runtime and user-side OAuth/API-key setup.
- PR #48 — Robin review automation remains blocked by its identified TOCTOU race; do not enable until the immutable review target is revalidated at checkout and immediately before comments or other side effects.
- PR #2 — Milestone 3 dataset/backtest; open against an older main base. Provider authorization and current integration status require reconciliation before use.
- PRs #16–#36 — stacked backtest, dataset integrity, and holdout-reservation changes; most remain draft and several descriptions explicitly say tests were not run.
- PRs #38–#48 — development tooling, skills, and review automation; remain separate draft stages.

PR #63 was merged separately at `fbfe7429128a0e251b281a54fad138b513481b55`. Q0.8 workflow run `44262541867` was manually dispatched and passed on the exact PR #60 head. No exchange request, account access, or trading action was performed.


## Latest holdout publisher review (2026-11-18)

- PR #34 (durable holdout reservations) is draft, latest head `486eb30e3989f4db3a74d4ed497d83c35ce465a3`, 60 commits ahead of its stacked base, nine changed paths.
- Independent static review found that `research/holdout_publish.py` compared only report identity fields with the completed TEST record, while `tests/test_holdout_publish.py` explicitly expects a report/results mismatch to block cleanup. The implementation has been corrected to require exact equality of the full report TEST object and completed record before deleting a pending reservation.
- The branch's previously full-checkout offline workflow was replaced with a sparse, read-only test workflow containing only `research/__init__.py`, `research/holdout_publish.py`, and `tests/test_holdout_publish.py`. These paths do not import protected modules. Exact GitHub Actions test execution remains pending; no test result is claimed.
- PR #36 remains draft and its branch is three commits behind the current PR #34 base. It must be reconciled with the publisher correction, test update, and safe workflow before it can be considered an integrated successor.
- The full PR #34 research-backtest workflow has not been dispatched or accepted. Its workflow currently grants `contents: write` for append-only research-data reservation/result publication; this is a separate integration/security review item. No TEST backtest or branch publication has been executed in this review.

## Completion-credit rules

A component receives verified credit only when all applicable conditions are met:

1. Its requirement exists in the authoritative master scope.
2. Its implementation is present in the selected authoritative integration baseline, not merely in a draft or disconnected branch.
3. Required tests pass on the exact commit being scored.
4. Security review covers the exact changed paths and dependencies.
5. Required upstream dependencies are accepted and verified.
6. Protected-path exclusions and trading boundaries remain intact.
7. Any operational claim is supported by an observed run, not by workflow YAML or documentation alone.

Documentation-only work, historical test results on older commits, draft PRs, synthetic tests that do not exercise the real boundary, and unverified protected components do not count as completed functionality.

## 80% target and next gates

**Whole-project completion percentage: UNRATED — requirement decomposition and weights are not yet authoritative.** This is not a zero-percent claim. The master vision is now recovered, but the handoff is not a complete acceptance matrix and protected components cannot be independently scored under the current access boundary.

Before publishing a numeric percentage:

1. Decompose `PROJECT_HANDOFF.MD` vision into versioned, testable requirements and identify any current ADR conflicts.
2. Establish one authoritative integration baseline and map every stacked PR to it.
3. Confirm which Workstream B components can be scored using independent evidence without opening protected implementation.
4. Propose explicit weights for every requirement; obtain owner acceptance before using them for the 80% score.
5. Score only implementation and verification evidence on exact commits.

The next engineering priorities are: redispatch the inspect the Commander, independent-acceptance, and verification sections in Actions run `44285252753` job summary before determining whether PR #60 has an acceptable review outcome using workflow branch `security/workflow-protected-path-isolation-2026-11-18` (workflow head `92ab726dc17e6bdcf66caec67e25956776d6a7e7`); independently review remaining changed paths and reconcile the Q0 security branch with the M6 baseline; then proceed through dataset identity, research integrity, strategy/backtest, and risk/portfolio interfaces without crossing protected boundaries.


## 2026-11-18 Q0.8 reviewer scope correction

- PR #60 remains a 26-changed-path proposal against immutable baseline `cd451972e3a641ad6fa78e64abf3968655a4b82a`; GitHub compare confirms exactly 26 changed paths at the latest branch snapshot.
- The immutable Q0.8 review context now includes 27 source paths: those 26 changed paths plus unchanged `fetch_history.py`, because `.github/workflows/research-data.yml` executes that entrypoint. The unchanged file is review context only and is not added to the changed-path allowlist.
- Corrected immutable reviewer commit: `8c6f5dd9f35ae4cbe3513d32aab1539d64ecebd7`; PR #60 branch workflow pin was re-fetched and verified to reference this exact commit.
- Reviewer policy now requires import-chain claims to be supported by literal imports in supplied source and explicitly prevents the false claim that `research/history.py` imports `validator.py`. The protected `research/pipeline.py` runtime chain remains static-only.
- Static verification only: runner blob `8df36ba8f2ac60a94f451dff945dc3b629b67a3f`; 27-path assertion, 26-status assertion, inclusion of `fetch_history.py`, and workflow pin all confirmed by re-fetch. No synthetic smoke test, exact-head test suite, or 19-role review has been rerun. Q0.8 acceptance remains **INCONCLUSIVE**.
- Workflow dispatch is still unavailable from the connected GitHub tools. In addition, PR #57 (which places the manual-only Q0.8 workflows on the default branch) remains unmerged and requires the owner's separate merge approval. Do not claim the tests or specialist review passed until the owner dispatches the workflows after that prerequisite is met.
- No protected paths were accessed, checked out, imported, or executed. No exchange requests, credentials, private account operations, PAPER/LIVE execution, or financial transactions occurred.


## 2026-11-18 holdout publisher review follow-up

- PR #34 current branch compare against `security/durable-holdout-reservations`: 61 commits ahead, exactly 9 changed paths.
- Static review of `research/holdout_publish.py` confirms exact report TEST-record equality, exact branch/local completion equality, reservation identity/shape checks, and validate-all-before-unlink behavior. Focused tests include report-result mismatch and multi-record atomicity regressions. No test execution has been observed on this head; runtime status remains **UNVERIFIED**.
- Separate blocker remains in `.github/workflows/research-backtest.yml`: workflow-wide `contents: write`, full repository checkout, and unrestricted `unittest discover -s tests`. This is not protected-path-safe and must not be dispatched or merged until checkout/test scope and write permission are narrowed and reviewed.
- Focused sparse/read-only publisher test workflow is a useful isolated verification path, but dispatch still depends on a workflow present on the default branch. Do not confuse that focused workflow with safety or verification of the backtest workflow.
- No protected implementation/data was read, checked out, imported, or executed. No holdout reservation or TEST evaluation was created, and no research-data publication occurred.



## 2026-11-18 repository-state reconciliation (authoritative latest check)

This section supersedes earlier PR-state, workflow-pin, and dispatch-prerequisite statements in this document where they conflict.

### Verified repository state

- PR #57 is **MERGED**. Merge commit: `9bf95e28171447faa910ecd5185b59a349555a52`; final PR head: `92ab726dc17e6bdcf66caec67e25956776d6a7e7`. Its seven workflow-only changes are now on `main`. This does not establish that any newly available workflow has been dispatched or passed.
- The merged `.github/workflows/q08-specialist-review.yml` was found to pin reviewer checkout to `92bda8aef7e3243062e038f157d44374801ab41e`. That commit contains a later token-budget adjustment but does **not** contain `tools/q08_specialist_review.py`; the workflow checkout therefore had a real pin/path mismatch.
- Corrected reviewer commit `8c6f5dd9f35ae4cbe3513d32aab1539d64ecebd7` exists and contains `tools/q08_specialist_review.py`. Its source statically asserts 27 review-context paths (26 changed paths plus unchanged `fetch_history.py`), 26 expected changed-path statuses, and the corrected import-chain policy.
- PR #64 is open, draft, and mergeable at head `823a45a0e02733a249e24eced71d279bb1f7abb5`. It changes only `.github/workflows/q08-specialist-review.yml`, pinning checkout to the corrected immutable reviewer commit `8c6f5dd9f35ae4cbe3513d32aab1539d64ecebd7`. Static re-fetch confirms the new pin is present and the old pin absent. No Actions run has tested this corrected workflow yet. PR #64 has not been merged.
- PR #60 remains open and draft at head `35023704b14666e47f98395b23b8d35b1e18dc3f`, based on M6 baseline `cd451972e3a641ad6fa78e64abf3968655a4b82a`, with 26 changed paths. Q0.8 exact-head tests and independent review are still **UNVERIFIED / PENDING**. Prior green runs refer to earlier heads or reviewer versions and do not verify this current head.
- The default-branch Q0.8 offline workflow is now present on `main` and uses a 16-path sparse checkout, read-only permissions, and checkout credential persistence disabled. The default-branch specialist workflow is manual-only, sparse-checks out the pinned runner and guidance, and requires an explicit target SHA. The specialist workflow remains non-operational until PR #64's corrected pin is accepted and merged, and then manually dispatched.
- The available GitHub connector has no workflow-dispatch operation. No Actions dispatch, exact-head suite, or specialist-review run is claimed from this reconciliation.

### Holdout workstream current state

- PR #34 remains open at head `3295b3d1390d8cd56ebeb65455a369db1dafe633`, with nine changed paths. Its unsafe `.github/workflows/research-backtest.yml` was deleted in this head so the candidate cannot reintroduce the workflow removed from `main` by PR #57. The focused publisher-test workflow is sparse and read-only, but no exact-head test run has been observed.
- PR #34's `.github/workflows/research-backtest.yml` remains unsafe for execution under current boundaries: workflow-wide `contents: write`, full repository checkout, and unrestricted `unittest discover -s tests`. Do not dispatch or merge that workflow until the protected import/test scope and publication permissions are redesigned and reviewed. No holdout TEST evaluation or research-data publication has occurred.
- PR #36 remains open at head `d673f93ce88230886563c9326408d328e632500d`, 21 commits ahead and 5 behind its current PR #34 base (`3295b3d1390d8cd56ebeb65455a369db1dafe633`). Its broad full-checkout test workflow was replaced by the focused sparse/read-only publisher test workflow, and its unsafe `.github/workflows/research-backtest.yml` was deleted. Pipeline/engine tests remain unverified because their import chain reaches protected `validator.py`; PR #36 still needs careful stack reconciliation before integration.

### Next engineering priorities

1. Corrected PR #64 reviewer pin: obtain merge approval if required, then run the synthetic policy check and specialist review against the exact current PR #60 head.
2. Dispatch the Q0.8 offline workflow against exact PR #60 head `35023704b14666e47f98395b23b8d35b1e18dc3f`; inspect all test outputs and failures.
3. Resolve PR #34's unsafe backtest workflow boundary without checking out, importing, or executing protected modules; retain the focused publisher test as a separate safe gate.
4. Reconcile PR #36 with the current PR #34 head and rerun only the isolated, approved publisher tests.
5. Continue whole-project requirement decomposition and independent architecture review. The overall 80% completion score remains **UNRATED**; proposed weights are not owner-approved and protected components remain unverified/excluded.

No protected paths were accessed, checked out, imported, or executed during this reconciliation. No exchange requests, credentials, private account operations, PAPER/LIVE execution, holdout evaluation, or financial transactions occurred.


### Holdout workflow alignment update (2026-11-18)

- PR #34 commit `3295b3d1390d8cd56ebeb65455a369db1dafe633` removes the unsafe backtest workflow. Re-fetch of that path on the branch returns 404. Its focused publisher workflow remains sparse/read-only and runs only `tests/test_holdout_publish.py`.
- PR #36 commit `d673f93ce88230886563c9326408d328e632500d` applies the same focused publisher-only workflow and deletes the unsafe backtest workflow. The previous Python socket monkey-patching plus full test discovery was not accepted as a protected-path boundary.
- PR #36 is still 5 commits behind its current base PR #34 and diverged; do not merge it until its stack is reconciled. The only safe runtime test claim it can make at present is the focused publisher test, which remains undispatched/unverified.


### Q0.8 and holdout boundary follow-up (2026-11-18, latest)

- PR #60 latest head is `5bc20cc449cbd0f79a3d50331cafbf3d4bbee0dd`; GitHub compare against M6 baseline reports 46 commits ahead, 0 behind, exactly 26 changed paths. Exact-head tests and independent review remain unverified.
- A second protected-boundary defect was found: PR #60's Q0 workflows sparse-checked out `live_check.py`, while `tests/test_live_check.py` imported it/read its source; that wrapper imports protected `validator.py` and `report.py`. The Q0 branch has now removed those two source-dependent tests and removed `live_check.py` from all three sparse checkout lists (Q0.8, Step 1, blocked Step 2). The remaining provider/config tests import only `providers` and `fetcher`. Live-check guard behavior is explicitly unverified.
- The same test-file correction has been proposed for `main` in draft PR #66, head `580b1a8ac17c3630ae82e79597753020c639785f`, one changed file, mergeable. This is needed because the default-branch Q0.8 workflow excludes `live_check.py` but its original test module imported it.
- PR #64 remains a one-file draft correction of the default-branch immutable reviewer pin, head `0c6a9e9464303ac675017e3671497099a6c3d317`, mergeable. It pins the workflow to combined reviewer `5323cb4f9f09ce5ea3a3709310270191ce06da5e`. It has not been merged or run.
- PR #65 is this tracker reconciliation branch, latest head `13673fbb8f48ab78b8297bdb9e9ef60c391eb884`, draft and mergeable.
- PR #34 head `7213f2ffbf4804214e8f99840305d756f8c87b6b` deletes the unsafe backtest workflow and adds strict JSON parsing/tests; focused publisher tests remain unrun/unverified.
- PR #36 head `6564f145a219adcd02573fd8b9a3f8eea5f83919` also deletes the unsafe backtest workflow, replaces broad discovery with focused publisher-only testing, and shares PR #34's strict publisher/test blobs. It remains draft and mergeable but is 7 commits behind/diverged from its base; pipeline/engine tests remain unverified due protected import dependencies.
- No workflows were dispatched. No protected source was checked out/imported/executed. No market-data requests, account access, reservations, TEST evaluation, or trading occurred.


### Latest Q0.8 review hardening (2026-11-18)

- PR #60 advanced to `5bc20cc449cbd0f79a3d50331cafbf3d4bbee0dd`; GitHub compare against M6 baseline reports 46 commits ahead, 0 behind, exactly 26 changed paths. This is still a draft candidate; no exact-head test or specialist review run has been observed.
- The public URL allowlist now rejects query strings over 256 characters, more than five parsed fields, timestamp/limit strings longer than their bounded decimal lengths, zero timestamps, and timestamps above 10,000,000,000,000 ms. Regression cases cover a zero timestamp, over-range timestamp, 5,000-digit timestamp, and excessive query fields. Commits `f8f7bea397ed799666f7f025333863e1ac6a86e1` and `f69ca4aad36e5d12a80936b34da088ee047d94da`; source/test re-fetch confirms the guards and cases. Runtime test result remains UNVERIFIED.
- The default-branch `tests/test_live_check.py` was found to import protected `live_check.py`, while PR #57's Q0.8 sparse workflow intentionally excludes that module. Draft PR #66 (`580b1a8ac17c3630ae82e79597753020c639785f`) replaces the broad tests with provider/configuration-only tests; static re-fetch confirms no live_check import or file read. PR #66 is mergeable but not merged, and its tests have not been run.
- PR #60's workflow/test correction is on its current branch, but the main branch remains dependent on PR #66 for a safe default-branch test module. PR #64 corrects the default-branch pin for runs selecting `main`; PR #60's own branch already pins the same combined reviewer, so selecting the Q0 branch does not require PR #64 to be merged.


### Holdout publisher strict-JSON integrity update (2026-11-18)

- PR #34 advanced to `7213f2ffbf4804214e8f99840305d756f8c87b6b`; it remains draft and mergeable. `research/holdout_publish.py` now rejects duplicate JSON keys and non-standard numeric constants; new regression tests assert pending reservations remain after either parse failure. Publisher and test files were re-fetched from GitHub and statically verified; no test run is claimed.
- PR #36 advanced to `6564f145a219adcd02573fd8b9a3f8eea5f83919`; it remains draft and mergeable but is still seven commits behind its current base and diverged. Its publisher and test blobs are now identical to PR #34's strict versions. It retains unverified pipeline/engine changes, which cannot be exercised under the current protected import boundary.
- PR #34 and PR #36 both remove `.github/workflows/research-backtest.yml` and retain only the focused sparse/read-only publisher test workflow. Neither workflow has been dispatched.


### Specialist reviewer pin integration (2026-11-18)

- PR #64 now pins the combined immutable reviewer commit `5323cb4f9f09ce5ea3a3709310270191ce06da5e`, not the earlier 4,096-token scope-only revision. The combined source retains the 27-path review scope, exact 26-path changed-file/status allowlist, `fetch_history.py` workflow-entrypoint context, corrected import-chain policy, truncation rejection, and the previously observed 5,000-token / 24,000-character response budget.
- PR #64 latest workflow correction commit: `0c6a9e9464303ac675017e3671497099a6c3d317`; draft, mergeable. Static re-fetch confirms the exact pin and combined reviewer assertions. No Actions run has exercised this combined revision.


### Q0 branch workflow pin synchronization (2026-11-18)

- PR #60 advanced to `5bc20cc449cbd0f79a3d50331cafbf3d4bbee0dd`. Its own `.github/workflows/q08-specialist-review.yml` now pins combined immutable reviewer `5323cb4f9f09ce5ea3a3709310270191ce06da5e`, matching PR #64's proposed default-branch workflow correction.
- This removes the workflow-ref discrepancy for a dispatch performed against the selected PR #60 branch. Both the default-branch workflow proposal and Q0 branch workflow point to the same reviewer source. Static re-fetch only; no run has been dispatched.


### Manual dispatch clarification (2026-11-18)

- PR #57's merge placed the manual-only Q0.8 workflows on `main`. GitHub's manual dispatch can select the PR #60 branch; in that case the workflow definition from the selected Q0 branch is used.
- PR #60's branch workflow now pins the combined reviewer commit `5323cb4f9f09ce5ea3a3709310270191ce06da5e`. Therefore PR #64's merge is not a prerequisite for dispatching against PR #60; PR #64 only fixes the default-branch pin for runs that select `main`.
- The connected GitHub tools cannot dispatch Actions workflows. A human must run the Q0.8 offline tests and specialist review from GitHub Actions with branch `security/q0-provider-sanitization-2026-11-18`; the specialist review input must be exact head `5bc20cc449cbd0f79a3d50331cafbf3d4bbee0dd`.


### Q0 branch exact-SHA workflow alignment (2026-11-18)

- PR #60 advanced to `8d076b3a19270b164018cdd33543317714466c1e`. Its specialist-review workflow now matches the corrected workflow proposed by PR #64: requires explicit `review_head_sha`, grants only `contents: read` and `pull-requests: read`, pins combined reviewer `5323cb4f9f09ce5ea3a3709310270191ce06da5e`, sparse-checks out reviewer/guidance, and disables persisted checkout credentials.
- This fixes the prior Q0 branch workflow's missing explicit SHA input and missing job-level pull-request read permission. Static re-fetch only; no review run has been dispatched.


### Latest repository reconciliation — 2026-11-18 (authoritative at this checkpoint)

This entry supersedes prior PR head SHAs and any earlier status that conflicts with the following current fetches.

- PR #60 (Q0 provider sanitization) is open/draft at head `8d076b3a19270b164018cdd33543317714466c1e`, base M6 `cd451972e3a641ad6fa78e64abf3968655a4b82a`; GitHub compare reports 47 commits ahead, 0 behind, 26 changed paths. Its Q0 offline workflow sparse-checks out the six explicit test modules and their unprotected dependencies. Static import/source review confirms:
  - `test_fetcher.py` imports only `fetcher`;
  - `test_live_check.py` on the Q0 branch imports only `providers` and `fetcher` (3 tests; no `live_check.py` import or read);
  - `test_history.py` and `test_pipeline.py` are static source/config checks;
  - `test_probe.py` imports only the deliberately disabled `probe.py`;
  - `test_sanitization.py` imports `fetcher`, `providers`, and `research.crosscheck`, whose imports are standard library plus those same unprotected modules.
  - The workflow does not sparse-check out `live_check.py`, `research/pipeline.py`, `validator.py`, or `report.py`. No tests have run on this head.
- The immutable Q0 reviewer commit used by the Q0 branch is `5323cb4f9f09ce5ea3a3709310270191ce06da5e` (runner blob `a07562d0946364ab96bd701b752948af7ced60da`). It includes the 27-path scope (26 expected changed-path statuses plus unchanged `fetch_history.py` entrypoint). The default-branch pin correction PR #64 now points to this same immutable commit. Static fetch confirms the runner exists and the scope includes `fetch_history.py`; neither synthetic smoke nor specialist review has been run.
- PR #64 remains open/draft, one workflow file, head `0c6a9e9464303ac675017e3671497099a6c3d317`; it corrects the default-branch specialist workflow pin. No merge or Actions run.
- PR #66 remains open/draft, one test file, head `580b1a8ac17c3630ae82e79597753020c639785f`; its provider-only `tests/test_live_check.py` has three tests and no import/read of protected `live_check.py`. No merge or Actions run. It is required before the default-branch Q0.8 offline workflow can safely run because `main` still has the old test module that imports `live_check.py`.
- PR #34 is open/draft at head `7213f2ffbf4804214e8f99840305d756f8c87b6b`. It contains strict JSON duplicate-key/non-standard-constant rejection in the holdout publisher, with regression cases. Its unsafe backtest workflow is deleted from the candidate; the focused publisher workflow checks out only three paths and runs only `test_holdout_publish.py`. No test run on this exact head.
- PR #36 is open/draft at head `6564f145a219adcd02573fd8b9a3f8eea5f83919`, stacked on PR #34. Current compare against the moving PR #34 base reports 23 commits ahead and 7 behind (diverged). The publisher, focused test, and publisher workflow blobs exactly match PR #34; the broader pipeline/engine/report test changes remain unverified because the full suite reaches protected `validator.py`. Do not merge until stack reconciliation and safe verification are completed.
- GitHub connector discovery confirms only GET/read operations for workflow runs and artifacts; no workflow-dispatch operation is available. No Actions workflow has been dispatched in this work session. Manual GitHub mobile web dispatch is still needed for exact-head Q0 tests and the 19-role reviewer.
- A non-mutating `git ls-remote` attempt from the execution container failed because DNS/network access to github.com is unavailable. This does not affect GitHub connector reads, but prevents using a local Git clone/test run in this environment.

### Current completion evidence

- Implementation progress and verification progress must be tracked separately. No new test passes are awarded from static inspection.
- Project-wide completion remains **UNRATED**; the tracker’s 40 proposed weighted requirements are not yet owner-approved and several foundational/runtime areas remain blocked or unverified.
- No protected files were fetched, checked out, imported, or executed. No exchange endpoint was contacted; no account, credentials, PAPER/LIVE execution, holdout TEST evaluation, or publication occurred.


### Correction: Q0.8 reviewer-pin diagnosis (2026-11-18)

A prior reconciliation incorrectly stated that reviewer commit `92bda8aef7e3243062e038f157d44374801ab41e` did not contain `tools/q08_specialist_review.py`. That statement was false and is superseded here.

- Re-fetch at the exact immutable commit confirms the runner exists (blob `199c5cff32ab34274f014750b7ceb4b31068fab0`), has the 5,000-token / 24,000-character budget, and was successfully checked out and compiled in Actions run `44285252753`.
- The actual defect was scope completeness: that runner's 26-path list omitted unchanged `fetch_history.py`, an entrypoint executed by `research-data.yml`. The previous run completed 19 non-truncated model calls but did not review this execution-context file; it is not a complete review of the current 27-path scope.
- Corrected combined runner `5323cb4f9f09ce5ea3a3709310270191ce06da5e` (blob `a07562d0946364ab96bd701b752948af7ced60da`) adds `fetch_history.py` as a 27th review-context path while preserving the exact 26 changed-path/status allowlist and the 5,000-token / 24,000-character budget.
- PR #64 changes the default-branch workflow pin to this combined runner. It is a scope-completeness correction, not a missing-script repair. No run has exercised the corrected 27-path runner yet.
- Run `44285252753` remains historical evidence for runner execution against old PR #60 head `18d02375577aefe39a0a13fabd0a5529f82ac01c`; its model calls all ended with `finish_reason=stop`, but it does not satisfy current exact-head or 27-path acceptance.


### Holdout publisher bounded-input hardening (2026-11-18)

- PR #34 advanced to head `b5699a35bbc1b5102b098b748fc7e9a092420d7a`; GitHub's REST PR state reports open/draft and `mergeable_state=clean`. The connector's normalized `mergeable` field briefly returned false, but the direct PR metadata fetch reports mergeable=true/clean.
- Static review found that the publisher rejected symlinks only at the final directory/file path and loaded JSON without a byte limit. The publisher now rejects symlink components in registry/output/report paths, opens JSON inputs with `O_NOFOLLOW` where available, verifies regular-file descriptors, caps each JSON object at 1 MiB, and caps completed records at 1,000.
- Added regression tests for symlinked registry parent, symlinked output parent, and oversized completion records preserving pending markers.
- Exact changed blobs: publisher `923acda6fb731a0d1ad4f8c3936a3a825ea54e8a`; tests `7d9ec617ee034f17bbd18db60b2b90552cd08968`. Test module contains 16 methods. Focused workflow still checks out only the publisher, its package initializer, and the test module, with read-only permissions and credential persistence disabled.
- These are **STATICALLY VERIFIED, NOT TESTED** changes. No exact-head Actions run has executed the new tests. Historical publisher test run #44268479449 targeted older head `26e5d43e20aa8488f4d935619e1de567100a514c` and cannot verify this new code.
- PR #36's publisher and test blobs still match the prior strict-JSON version, not this new hardening. PR #36 must be reconciled with PR #34 before it can be treated as a successor; no merge.


### Holdout publisher regression expansion (2026-11-18)

- PR #34 latest head: `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`.
- Added two tests in `tests/test_holdout_publish.py`: reject more than 1,000 completed JSON records; reject a symlinked report-parent directory. Both assert the pending reservation remains.
- Latest test blob: `e84f4978ac8a72202c017cb88dbee5ee7dafea22`; publisher remains `923acda6fb731a0d1ad4f8c3936a3a825ea54e8a`; isolated workflow remains `7b132b23649db98c2b36608dec9dda923c4d9fdc`.
- Static re-fetch confirms 18 test methods, only the publisher module is imported, and workflow sparse checkout/test command remain narrowly scoped. Exact-head tests are **NOT RUN / UNVERIFIED**.
- No production/pipeline files changed; no protected source, live exchange endpoint, account, credentials, or trading functionality accessed.


### PR status snapshot after holdout regression expansion (2026-11-18)

Fresh GitHub metadata fetch, superseding older heads/statuses above:

| PR | Current head | Base | State | Mergeability | Current interpretation |
|---|---|---|---|---|---|
| #34 | `301b90dca0fd1622d3ff69ee3bbf47d2b401d448` | `security/durable-holdout-reservations` | Open draft | Mergeable | Focused publisher; 18 tests statically inspected; exact-head runtime not run |
| #36 | `f9ee385504ba822823319acf27ec4e74b42c4694` | `security/implement-durable-holdout-reservations` | Open draft | Not mergeable | Diverged from moving #34 branch: 25 ahead / 10 behind; protected pipeline/engine/report tests remain unverified |
| #60 | `8d076b3a19270b164018cdd33543317714466c1e` | `feature/m6-risk-engine` | Open draft | Mergeable | Q0 sanitization; exact-head tests/review not run |
| #64 | `0c6a9e9464303ac675017e3671497099a6c3d317` | `main` | Open draft | Mergeable | Corrects 27-path reviewer pin; no corrected review run |
| #65 | `730eb98985057baf0cf4c971066a7843d591e9ff` | `main` | Open draft | Mergeable | Tracker reconciliation only |
| #66 | `580b1a8ac17c3630ae82e79597753020c639785f` | `main` | Open draft | Mergeable | Provider-only replacement for unsafe legacy live-check test imports |

- PR #34's latest test blob `e84f4978ac8a72202c017cb88dbee5ee7dafea22` contains 18 test methods, including the two newly added count-limit and symlinked-report-parent regressions. Static inspection only.
- GitHub check-runs for exact head `301b90dca0fd1622d3ff69ee3bbf47d2b401d448` contain only the unrelated pull-request review check marked skipped; no manual publisher workflow run exists for this head.
- PR #36 remains blocked for integration because it is diverged and includes tests whose import closure reaches protected code. No broad tests or protected paths were accessed.
- No PR other than previously approved PR #57 has been merged. PR #34, #36, #60, #64, #65, and #66 remain drafts.


### Latest holdout stack reconciliation (2026-11-18)

- PR #34 current head is `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`. It includes the publisher's 1 MiB JSON bound, 1,000 completed-record cap, symlink-ancestor rejection for registry/output/report paths, and regression tests for symlinked registry/output/report parents, oversized records, and record-count overflow. All are static-only until the focused workflow runs on this exact head.
- PR #34's focused workflow remains the only permitted runtime gate for publisher code: three-path sparse checkout, read-only `contents`, checkout credentials disabled, Python 3.11, only `tests/test_holdout_publish.py`. No full backtest, TEST evaluation, or research-data publication.
- PR #36 remains open/draft but is superseded; it is based on an older merge base and diverges from the moving PR #34 parent. Its unique six-file pipeline/test changes were ported to clean PR #68. Do not merge PR #36.
- PR #67 was closed as a duplicate/superseded draft because its base became one commit behind while PR #34 advanced concurrently. Its work was recreated on the latest parent in PR #68; no code was lost.
- PR #68 is open/draft at head `e280af8e9224ff3dd5ce282d7e9da3224c6a4136`, based on PR #34 head `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`; compare confirms six commits ahead, zero behind, exactly six changed files. Direct GitHub PR metadata reports `mergeable_state=clean`. It carries the six PR #36 pipeline/test changes while inheriting the parent's current publisher and focused workflow.
- PR #68's pipeline/backtest test modules remain **UNVERIFIED / NOT RUN** because their import chain reaches protected `validator.py`. The inherited publisher-only workflow does not validate these six files. No test execution, holdout evaluation, or publication is claimed.
- PR #34 advanced while this work was in progress, confirming the parent branch is actively changing concurrently. Re-fetch branch heads and compare ancestry immediately before every subsequent stacked change; do not assume a baseline remains current across multiple tool calls.


### Exact-source holdout publisher test result (2026-11-18)

- Re-fetched PR #34 current publisher/test files and reconstructed them in an isolated temporary test directory. GitHub blob hashes matched byte-for-byte: publisher `923acda6fb731a0d1ad4f8c3936a3a825ea54e8a`; tests `e84f4978ac8a72202c017cb88dbee5ee7dafea22`.
- Executed the exact focused suite using `python -m unittest discover -s tests -p test_holdout_publish.py -v`: **18 passed, 0 failed, 0 errors**, 0.182 seconds.
- Runtime Python was 3.13.5. The repository's GitHub Actions workflow specifies Python 3.11, so Python 3.11 exact-head CI remains pending manual dispatch. Do not mark CI as passed or the entire holdout workstream independently verified yet.
- This test used only `research/holdout_publish.py`, `research/__init__.py`, and `tests/test_holdout_publish.py` in a temporary isolated directory. No protected files, exchange endpoints, datasets, or research-data branches were accessed or modified.


### PR #68 test import-chain correction (2026-11-18)

Static import inspection of all six PR #68 test modules confirms none can be executed under the current protected-path boundary:
- `tests/test_backtest_pipeline.py` and `tests/test_holdout_reporting.py` import `research.pipeline`, which reaches the protected engine/validator chain.
- `tests/test_engine.py` imports the research engine/pipeline chain.
- `tests/test_history.py` imports `research.history`, which imports protected `validator.py`.
- `tests/test_pipeline.py` imports `run.py`, which imports protected `validator.py` and `report.py`.
- The sixth changed file is `research/pipeline.py` itself; it can be statically inspected but must not be imported/executed.
The PR body has been corrected to state this precisely. PR #68's inherited publisher-only workflow does not test these pipeline changes. All six modules remain **UNVERIFIED / NOT RUN** until the owner separately authorizes the protected import boundary or a safe non-importing test design is implemented.


### Q0.8 immutable reviewer reference audit (2026-11-18)

- PR #64 current head: `0c6a9e9464303ac675017e3671497099a6c3d317`; base is merged PR #57 commit `9bf95e28171447faa910ecd5185b59a349555a52`. GitHub compare reports exactly two commits ahead, zero behind, and one changed workflow file.
- The workflow's immutable reviewer pin is `5323cb4f9f09ce5ea3a3709310270191ce06da5e`; exact-SHA retrieval confirms the runner file exists (blob `a07562d0946364ab96bd701b752948af7ced60da`). Its parent is `8c6f5dd9f35ae4cbe3513d32aab1539d64ecebd7`.
- Recursive tree inspection confirms 20 `.claude/agents/` files and 38 `.claude/skills/` files exist at the pinned commit, matching the workflow's sparse checkout.
- Static runner assertions confirm 27 review paths (26 changed paths plus unchanged `fetch_history.py`), 26 exact changed-path/status entries, 19 role prompts, 5,000 max completion tokens per role, and 24,000-character output cap. Request/diff/response bounds and missing-verdict-to-INCONCLUSIVE behavior are present.
- PR #64 head checks: CodeQL success, Actions analysis success, Python analysis success; Workstream A review check skipped. These do not execute the manual Q0.8 review.
- PR #60 current exact head remains `8d076b3a19270b164018cdd33543317714466c1e`; its Q0.8 offline test and corrected 19-role review have no exact-head workflow run. Historical 51/51 and earlier 19-role runs are not acceptance evidence for this head.
- No GitHub workflow-dispatch action is available through the connected GitHub tools. The Q0.8 runs are `workflow_dispatch` only. Exact-head runtime verification therefore remains pending owner dispatch from GitHub Actions mobile/web UI.
- No merge of PR #64 or PR #60 is authorized by this tracker update.

### Tokocrypto endpoint readiness — public documentation cross-check (2026-11-18)

- Current official documentation: https://www.tokocrypto.com/apidocs/
- The docs explicitly document candle data at `https://www.tokocrypto.site/api/v3/klines`, including millisecond open/close timestamps.
- The documented server-time route is `GET /open/v1/common/time` under the general API endpoint, not `https://www.tokocrypto.site/api/v3/time`.
- The latter route remains **UNVERIFIED**. The documented `/open/v1/common/time` route remains excluded by the approved transport boundary. Do not probe either route, widen the allowlist, or claim server-time readiness without a separate authorization/verification path.
- Official docs state clients must back off on HTTP 429 and that repeated violations can trigger HTTP 418 bans. The current Q0 fetcher fails closed on 429 because it does not preserve/interpret `Retry-After`; no exchange request has been made.


### Manual-dispatch routing correction (2026-11-18)

- Default branch `main` contains both Q0.8 manual workflow files, so GitHub's manual dispatch prerequisite is satisfied.
- Important: `main` still pins the older reviewer `92bda8aef7e3243062e038f157d44374801ab41e` until PR #64 is separately approved and merged. Do not dispatch the 19-role workflow on `main`.
- PR #60's branch `security/q0-provider-sanitization-2026-11-18` contains the corrected workflow pin `5323cb4f9f09ce5ea3a3709310270191ce06da5e` and exact-SHA input. Dispatch both Q0.8 workflows using that branch. For the specialist workflow, pass exact target SHA `8d076b3a19270b164018cdd33543317714466c1e`.
- PR #34's branch `security/implement-durable-holdout-reservations` contains the isolated three-file publisher workflow. The same workflow path exists on `main`, so it can be manually dispatched using the PR #34 branch selector; it runs only the publisher test module on Python 3.11.
- No dispatch has been made by the connected tools. Exact-head CI is still pending owner action; selecting the wrong branch would either run the wrong test scope or use the stale reviewer pin.


### Q0 route correction and local verification (2026-11-18)

- PR #60 head: `e9fa88a6e87a33277f280dd1140baef7de727ae4`, 26 changed paths, 47 ahead/0 behind M6.
- The undocumented `.site/api/v3/time` route is now blocked. Only the documented `.site/api/v3/klines` route remains in the allowlist. Both server-time entrypoints fail before network access. The Step 1 report explicitly remains fail-closed; symbol metadata is still unapproved.
- Exact-source local run of all six Q0 offline test modules: **51 passed, 0 failed, 0 errors** on Python 3.13.5. All test/source blobs were checked against current GitHub blobs. Exact `fetch_history.py` run returned expected exit 1 with zero network requests, no dataset, and backtest disallowed.
- GitHub Actions Python 3.11 run and corrected 27-path specialist review remain pending manual dispatch. No exchange requests were made. `.com/open/v1/common/symbols` remains outside the approved host boundary.


### Final live-state reconciliation (2026-11-18)

- PR #36's current head is now `f9ee385504ba822823319acf27ec4e74b42c4694`, still dirty/non-mergeable and superseded by PR #68. Do not merge it.
- PR #68 remains open/draft at `e280af8e9224ff3dd5ce282d7e9da3224c6a4136`, based on current PR #34 head `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`; direct GitHub metadata reports clean/mergeable. Its six pipeline/test files remain unverified due protected import chains.
- PR #60 remains open/draft at `e9fa88a6e87a33277f280dd1140baef7de727ae4`; the current Actions run listing contains no Q0.8 offline test or specialist-review run for this SHA. Only skipped Workstream A pull-request checks are present. Manual workflow dispatch is still required.
- PR #64 and PR #66 remain open/draft, unmerged. PR #64 fixes the reviewer scope omission by adding unchanged `fetch_history.py` to the 27-path review context. PR #66 makes the default-branch live-check test provider-only. For current PR #60, use the Q0 branch workflows directly; neither PR needs to be merged first.
- PR #34 remains open/draft at `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`, direct GitHub metadata clean/mergeable. Its 18-test exact-source local suite passed on Python 3.13.5; Python 3.11 Actions run still pending.
- PR #65 tracker branch now includes the exact-source 51-test Q0 verification and the 18-test publisher verification, with Python 3.11 CI limitations recorded. No workflow dispatch or PR merge occurred in this checkpoint.



### Q0.8 exact-head workflow results and rate-limit correction (2026-11-19)

- PR #60 specialist review run **44337003905** targeted the earlier PR #60 head `e9fa88a6e87a33277f280dd1140baef7de727ae4`. It completed 10 of 16 specialist calls; the 11th role (`security-review`) received HTTP 429. Commander, independent acceptance, and final verification did not run. The review is **INCONCLUSIVE**, not accepted.
- The provider returned `x-ratelimit-reset=1795046400000`, a Unix epoch timestamp in **milliseconds**, with `remaining=0`. The old runner treated it as seconds, producing an incorrect delay of approximately 1.79 trillion seconds. The actual reset is 2026-11-19 00:00 UTC (2026-11-19 08:00 WIB), about 8 hours after the failed request.
- Corrected the immutable reviewer source: `tools/q08_specialist_review.py` now detects millisecond epoch values (>= 100,000,000,000) and converts them to seconds before calculating delay; seconds-based reset headers remain supported. Synthetic checks now cover both units and a future timestamp.
- Corrected runner commit: `14ab3644c2da0de41290c73dfe66a8a2f499f858`; runner blob: `4fe0f72907e3933bd98e0fa019f03a7bd76189bb`.
- PR #64 now contains the corrected runner and pins its workflow to that exact immutable commit. PR #64 head: `ba79c9cf9b0d0da9d9fc816d49ee6f2da70a79d2`.
- PR #60's specialist workflow also pins the corrected immutable runner. PR #60 head is now `5a5fc80637cef68a15fafa1af8ae36d800ec5bff`; compare against M6 baseline reports 60 commits ahead, zero behind, and the same exact 26 changed paths/statuses. The prior exact-head Q0 offline test (run 44336842911) passed on `e9fa88...`; it does not validate the new workflow-only head.
- No new run has executed the corrected runner. The timestamp parser correction is statically verified from the exact GitHub blob; Python syntax/synthetic runtime and full 19-role review remain pending manual workflow dispatch.
- The corrected parser makes the provider's actual long reset delay visible; it does not bypass the quota, increase provider limits, or guarantee that a full review fits one quota window. Review completion remains blocked until quota availability and the review process can complete all 19 roles.
- No exchange requests, credentials, private account operations, protected-path access, PR merge, or trading actions occurred.


### Q0.8 checkpoint-resume implementation (2026-11-19)

- The prior 19-role attempt (#44337003905) stopped at role 11 due OpenRouter HTTP 429 after 10 completed specialist reports. The reset header was milliseconds, not seconds; corrected conversion is in the immutable runner.
- Added per-role atomic checkpoints to the reviewer. Checkpoints bind to repository, immutable base SHA, exact review head SHA, and approved model. They reject duplicate JSON keys, invalid schema, unexpected roles, mismatched identity, oversized content, missing explicit verdicts, and secret-screen matches. Completed roles are skipped when resuming.
- Added a manual `resume_from_run_id` input. The workflow downloads the named checkpoint artifact from that exact earlier run and uploads the new checkpoint after every run outcome. Artifacts are immutable and retained for 7 days. The workflow uses pinned official download/upload action commits and grants `actions:read` only for restore; source and PR access remain read-only.
- Immutable reviewer commit: `e28279fc22c3bdb6fb730242a2e1beaad53e0b8a`; source blob: `5c4c6ee5362d9e23bfd776bab943a6d03989ba58`.
- PR #64 head: `8662ab103170279c3d8b706f42a1640eef45cae4`; two changed files (reviewer source and workflow), open/draft/unmerged, GitHub reports mergeable.
- PR #60 latest head: `3c3373836663704a5d979eec97aac3e7f145fbd1`; 26 changed paths remain, base M6 SHA `cd451972e3a641ad6fa78e64abf3968655a4b82a`. Its Q0.8 workflow pins the immutable reviewer and supports checkpoint restore.
- This implementation has only been statically verified against exact GitHub blobs. Python 3.11 syntax, synthetic checkpoint tests, artifact round-trip, and resumed/full 19-role runtime remain **UNVERIFIED** pending manual workflow dispatch. Do not claim the review passes.
- For first run, dispatch specialist review with `review_head_sha=3c3373836663704a5d979eec97aac3e7f145fbd1` and leave `resume_from_run_id` blank. If it stops after a quota limit, start a new dispatch with the same `review_head_sha` and set `resume_from_run_id` to the failed run ID whose artifact was uploaded. Do not change the head SHA during resume.
- Q0 offline tests previously passed on head `e9fa88...`, but the latest head is workflow-only different; exact-head Python 3.11 offline test is still pending. Whole-project completion remains UNRATED.


### Final Q0.8 reviewer pin and checkpoint bounds (2026-11-19)

- Final immutable reviewer commit: `f42ba20c92413c94dcde82aebfba8d8c8aaf8bc5`; exact runner blob: `df736eb2b29bd6856e18357e334a34260ebb6b46`.
- Final PR #64 workflow pin is `f42ba20c92413c94dcde82aebfba8d8c8aaf8bc5`; PR #64 head: `a2b30ba30f12d69b91a8b98f5221ef9fe3c7b69e`, open/draft/unmerged, two changed files, GitHub reports mergeable.
- Final PR #60 head: `a1b13e829bbc6b1a7c44d4c8e7e2fcbf9f066851`; compare against M6 baseline is 65 ahead/0 behind with exactly 26 changed paths/statuses.
- Checkpoint hard limit was set to 2,000,000 bytes to accommodate the worst-case UTF-8 expansion of 19 role reports, each capped at 24,000 characters. The checkpoint remains bounded and validates exact head/model/repository/base identity.
- The previous failed run #44337003905 predates checkpoint support and produced no resumable artifact. Its 10 reports cannot be recovered by the new workflow; the first run on the new implementation must start fresh. Later interrupted runs can resume from their uploaded artifact by run ID without repeating completed roles.
- The final runner/workflow have been statically checked through exact GitHub blob retrieval, including action pins and checkpoint logic. Full Python 3.11 syntax/synthetic execution, artifact upload/download round-trip, exact-head Q0 offline tests, and all 19 review roles remain **UNVERIFIED** until manually dispatched. No PR merge is authorized.
- The project-wide completion rating remains **UNRATED**. No new feature completion credit is awarded for reviewer tooling alone.


### Final Q0.8 reviewer checkpoint-stage validation (2026-11-19)

- Final runner commit: `0b1d357ccffa8395f611833da1e4bb50ac52fd26`; exact source blob: `036e9a3a17e508654f79e10975388d5b4c125937`. The runner enforces synthesis dependencies: Commander requires all 16 specialist reports; independent acceptance requires Commander; final verification requires independent acceptance.
- Final PR #64 head: `dd01298dc0da0fc45bc31d8df4a313207d45a4bd`; open/draft/unmerged, two changed files, mergeable per GitHub.
- Final PR #60 head: `c3b593da446835716d54b964e6be5c53981a87a9`; 26 changed paths/statuses, 65 ahead/0 behind the M6 baseline. The final workflow pins the immutable runner and includes checkpoint restore/upload.
- The prior failed run #44337003905 cannot be resumed because it predates checkpoint support. First execution on the new workflow must start without `resume_from_run_id`. For a later interruption, use a new manual dispatch with the same `review_head_sha` and the failed run ID whose checkpoint artifact exists.
- Final source and workflow are statically verified only. Python 3.11 syntax/synthetic execution, checkpoint artifact round-trip, exact-head offline tests, and complete 19-role review are UNVERIFIED pending manual dispatch. No merge, exchange access, protected-path modification, or trading operation occurred.


### PR #60 ancestry refresh

- Final live compare at head `c3b593da446835716d54b964e6be5c53981a87a9` reports **66 commits ahead, 0 behind**, with exactly 26 changed paths/statuses. The prior 65-ahead tracker entry was one commit stale; no additional changed paths were introduced.


### Live-state refresh after clean-main successor PRs (2026-11-19)

- PR #69 is the clean-main successor to stale draft PR #61 (Ruff static quality). Head `fa2a5b7760757ee92fb690b08f57ae23060eaa08`; exactly two added files; 2 commits ahead/0 behind `main` at `9bf95e28171447faa910ecd5185b59a349555a52`. It preserves the read-only manual workflow, immutable checkout action, five-file unprotected sparse checkout, and verified Ruff binary digest. Ruff has not yet run; manual workflow execution remains pending.
- PR #70 is the clean-main successor to stale draft PR #62 (deny all signal paths). Head `17c853e9d6d927e8708fcea31120da766e0af860`; exactly two changed instruction/configuration files; 2 commits ahead/0 behind `main`. JSON parsing confirms the four intended deny rules: Read/Edit for `P1/**` and Read/Edit for all `signal/**`. This is defense in depth, not an OS sandbox.
- PR #61 and PR #62 remain open/draft for traceability but are superseded by #69 and #70. Do not merge the superseded PRs.
- Both successor branches were created directly from current `main`, avoiding the 3-commit divergence present in the older branches. Exact file content and compare metadata were re-fetched after creation.
- PR #60 remains at `c3b593da446835716d54b964e6be5c53981a87a9`; PR #64 remains at `dd01298dc0da0fc45bc31d8df4a313207d45a4bd`. Neither exact-head Q0.8 offline tests nor the corrected 19-role review have been dispatched. The old specialist run #44337003905 has no checkpoint artifact.
- No source execution, protected-path access, workflow dispatch, PR merge, exchange request, account operation, or trading action occurred in this refresh. Whole-project completion remains UNRATED; no numeric progress claim is supported by these tooling/documentation changes.


### Q0.8 checkpoint-input validation (2026-11-19)

- Added a workflow guard before artifact restoration: a non-empty `resume_from_run_id` must match 1–20 decimal digits before it is used in the artifact name or download action.
- The exact workflow blob is `4e704851011a6b10f66d22804edf91aad41af5eb` on both PR #60 and PR #64 branches; runner pin remains immutable commit `0b1d357ccffa8395f611833da1e4bb50ac52fd26`.
- PR #60 head is now `03bdff51c23a68a57ea2947904cf6f3c0c1e9dcf` (26 changed paths); PR #64 head is now `e1c4c1d3f308275d644151f375eef0b4f5d9cf23` (two changed files). Both remain open/draft/unmerged.
- GitHub reports mergeable for both branches, but the Q0.8 workflow has not been dispatched on either updated head. Python 3.11 syntax/synthetic tests, checkpoint artifact round-trip, exact-head offline tests, and full 19-role review remain unverified.

### Complete protected-path guard successor (2026-11-19)

- New PR #71: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/71
- Branch: `security/complete-protected-path-guard-2026-11-19`; head `dbad9ff47974f93f6ae179ffb208ad298fe67c95`; based directly on current `main` `9bf95e28171447faa910ecd5185b59a349555a52`.
- Exactly two shared policy files changed: `.claude/settings.json` and `CLAUDE.md`. GitHub compare confirms 2 commits ahead, 0 behind, and exactly those two paths.
- The Claude Code Read/Edit deny configuration now covers `P1/**`, all `signal/**`, `markets/risk/**`, root `validator.py`, and root `report.py`. JSON parsing succeeded and all 10 expected deny rules were present after re-fetching the committed file.
- The repository instructions now explicitly prohibit processing those paths, require exclusions before broad checkout/search/test discovery, narrow Tokocrypto to unauthenticated GET candles at `www.tokocrypto.site/api/v3/klines`, and state PAPER-only/LIVE-disabled boundaries.
- PR #71 is open/draft/unmerged. It supersedes PR #70 for the overlapping signal-path policy because it includes the same all-`signal/**` rules plus the additional protected modules and endpoint correction. PR #70 remains open/draft for traceability; do not merge it separately.
- PR #69 remains the clean-main Ruff workflow successor to #61; Ruff runtime execution is still pending. PR #61/#62 remain stale drafts and are superseded by #69/#71 respectively.
- Verification is limited to exact-file retrieval, JSON parsing, expected-rule assertions, instruction-content checks, and GitHub compare metadata. Claude Code rule semantics and resistance to shell/tool bypass are not independently verified; this is defense in depth, not an OS sandbox.
- No protected implementation/data was accessed, no application code or tests were run, no workflow was dispatched, and no PR was merged. This policy improvement earns no feature implementation or project-completion credit. Overall completion remains UNRATED pending owner-approved scope/weights and evidence.


### Security-review skill successor (2026-11-19)

- PR #72 is the clean-main successor to stale draft PR #59. It adds only `.claude/skills/security-review/SKILL.md`, head `e7883eccdba34fe1754d0bb4fd76401412c78b7b`, 1 commit ahead/0 behind `main`.
- The skill makes exact-scope recording, untrusted-input handling, sparse-checkout review, least privilege, supply-chain checks, and protected-path/trading boundaries explicit. It is guidance only; runtime discovery is unverified and it is not an OS-level sandbox.
- PR #59 remains open/draft for traceability and is superseded; do not merge it separately.


### Protected-path Read/Edit deny alignment (2026-11-19)

- Expanded successor PR #70 to align Claude Code permission denies with the complete current protected-path list: Read/Edit denied for `P1/**`, all `signal/**`, `markets/risk/**`, and root `validator.py` / `report.py`.
- Re-fetched and parsed `.claude/settings.json`; all ten exact Read/Edit entries are present. The mandatory `CLAUDE.md` instructions now explicitly identify all five protected locations/modules and retain the Workstream B boundary.
- PR #70 head: `d9483900a97f8c809946b0a3a947cac82f4efdeb`; exactly two files changed, 4 commits ahead/0 behind `main`. GitHub reports mergeable. These permission rules remain defense in depth, not an OS sandbox.


### Security-review skill protected-scope alignment (2026-11-19)

- PR #72 now explicitly lists `P1/`, all `signal/`, `markets/risk/`, `validator.py`, and `report.py` as protected exclusions, matching the expanded policy candidate in PR #70.
- PR #72 head: `3eaed39a83a66804018ef8069cf0cd0f63821e98`; one file changed, 2 commits ahead/0 behind `main`. Runtime skill discovery remains unverified.


### Ruff release download hardening (2026-11-19)

- PR #69's release download now follows GitHub's HTTPS-only release-asset redirects and uses bounded connection (10s), total (90s), and retry (2) timeouts. The previously authored curl command did not follow redirects; it would not reliably retrieve the actual release asset.
- Extracted shell step passed local `bash -n` syntax validation. The archive hash check remains mandatory. Ruff itself has not been downloaded or executed, and the manual workflow has not been dispatched.
- PR #69 still changes exactly two files, 4 commits ahead/0 behind `main`; no application code or protected paths changed.


### Authoritative PR head snapshot (2026-11-19)

- PR #60: `03bdff51c23a68a57ea2947904cf6f3c0c1e9dcf`, 26 changed paths; Q0.8 offline tests and specialist review not yet dispatched on this exact head.
- PR #64: `e1c4c1d3f308275d644151f375eef0b4f5d9cf23`, two changed files; same updated Q0.8 workflow blob as PR #60.
- PR #65 tracker: this update records the current snapshot.
- PR #69: `ad7213f17df08f3b748bd32d7b93c016fc29025a`, two added files, 4 ahead/0 behind `main`; bounded HTTPS release download shell syntax checked, Ruff execution pending.
- PR #70: `d9483900a97f8c809946b0a3a947cac82f4efdeb`, two changed files, 4 ahead/0 behind `main`; ten Read/Edit deny entries parsed and verified.
- PR #72: `3eaed39a83a66804018ef8069cf0cd0f63821e98`, one added file, 2 ahead/0 behind `main`; skill content re-fetched and protected exclusions verified.
- All listed PRs remain open/draft/unmerged. No new manual workflow run has supplied Python 3.11, Ruff, checkpoint artifact, or 19-role acceptance evidence. Whole-project completion remains UNRATED; the 80% target is not yet evidenced.


### Q0.8 Actions evidence and reviewer checkout blocker (2026-11-19)

- PR #60 current head is `aecb8d9c14cc9cb79c81e629b51216175142ddca`, open/draft/unmerged, 70 commits ahead/0 behind M6 baseline, with exactly the same 26 approved changed paths/statuses. No protected paths were added to the compare.
- Exact-head offline workflow run [44366173956](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44366173956) completed successfully on the earlier PR #60 head `4cc229fb09b1030100101ad873944ea07c4f1982`: Python 3.11 and all 16 approved tests passed. This is not an exact-head result for current head `aecb8d9c14cc9cb79c81e629b51216175142ddca`; rerun is required.
- Specialist workflow run [44366331563](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44366331563) failed before model calls. Python 3.11 setup and syntax compilation passed, but the synthetic smoke test stopped at `Required trusted agent definition missing`. The immutable runner checkout `2695d51d3387f789a784561c1b572f4ceddf6d9f` contains no tracked `.claude/agents/` or `.claude/skills/` definitions. No specialist roles ran and no checkpoint artifact was uploaded.
- PR #64 now contains a self-contained reviewer source with embedded `ROLE_GUIDANCE` at immutable commit `c0ed377c82d4f0586dceb20eeaffd3725b568101` (source blob `5466bf6039e9653ef79cbbbb65b15753ce5cd723`). Its current workflow branch is `security/q08-reviewer-pin-correction-2026-11-18`, head `acc6e1311fdc80fbf12fe7c0e1d87bd2e7d9fa32`; the workflow pins that exact self-contained reviewer and no longer sparse-checks the missing guidance directories. PR #64 remains open/draft/unmerged.
- Next exact-head manual dispatches: (1) Q0.8 Offline Tests on PR #60 branch `security/q0-provider-sanitization-2026-11-18`; (2) Q0.8 Specialist Review on PR #64 branch `security/q08-reviewer-pin-correction-2026-11-18`, with `review_head_sha=aecb8d9c14cc9cb79c81e629b51216175142ddca` and blank `resume_from_run_id`. The previous failed run has no artifact and must not be resumed.
- Neither run is an acceptance pass for the specialist review. No PR was merged, no protected implementation was accessed, and no exchange/account/trading action occurred. Whole-project completion remains UNRATED.


### Q0.8 specialist review attempt and resumable quota checkpoint (2026-11-19)

- Specialist workflow run [44373786425](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44373786425) targeted the exact current PR #60 head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, with the approved M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Python 3.11.18 setup, immutable reviewer checkout at `c0ed377c82d4f0586dceb20eeaffd3725b568101`, syntax compilation, synthetic policy smoke, PR-head validation, comparison, and snapshot construction all passed.
- The first model request (`architecture-architect`) received OpenRouter HTTP 429 with `remaining=0`; the reported reset was `1795046400000` (Unix milliseconds; 2026-11-19 00:00 UTC / 08:00 WIB). The bounded retries stopped because the provider reset was beyond the runner's 120-second retry window. No specialist report completed; the 19-role review, Commander, independent acceptance, and final verification did not run. This is a provider-quota interruption, not a review verdict.
- The workflow successfully uploaded artifact `q08-review-checkpoint-44373786425`, artifact ID `14460481249`, SHA-256 `a974246bca61789b8dd0a1f45e63f0bc8936bf2b25f522abf1394c7ec19c2de8`, with 7-day retention (expires 2026-11-25 18:49:30 UTC).
- Downloaded and inspected the checkpoint JSON. Identity matches repository `ruthlessjoey/btcidr-trading-lab`, base SHA, exact review head, and model `inclusionai/ling-3.2-flash:free`; schema version is 1. The `reports` map is empty and acceptance/Commander/verification are null, as expected because the first model request failed before any role completed.
- Resume is supported: dispatch the same Q0.8 specialist workflow from branch `security/q0-provider-sanitization-2026-11-18`, keep `review_head_sha=0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, and set `resume_from_run_id=44373786425`. The checkpoint will restore but has no completed roles to skip; the review will retry from the first specialist. Do not change the target SHA. If another quota interruption uploads a newer checkpoint, resume from that newer run ID.
- Exact-head offline tests passed separately in run [44373013889](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44373013889): Python 3.11.18 and 51/51 approved tests on the same exact PR #60 head.
- Specialist review remains **INCONCLUSIVE / NOT ACCEPTED** until all 19 roles, Commander synthesis, independent acceptance, and final verification pass. No PR merge, protected-path access, exchange request, account operation, or trading action occurred. Overall project completion remains UNRATED.


### Q0.8 repeated quota interruption and reset-time correction (2026-11-19)

- Specialist workflow run [44374650548](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44374650548) resumed from run `44373786425` against the unchanged PR #60 head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f` and approved M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Checkpoint restore succeeded; Python 3.11.18 setup, immutable reviewer checkout (`c0ed377c82d4f0586dceb20eeaffd3725b568101`), syntax compilation, synthetic policy smoke, PR-head validation, comparison, and snapshot construction all passed.
- The first specialist request again received OpenRouter HTTP 429 (`limit=50`, `remaining=0`). The reset timestamp was `1795046400000` milliseconds, which converts to **2026-11-19 00:00 UTC / 08:00 WIB**. At the time of this run (2026-11-19 02:54 WIB), that reset was still about five hours in the future. The runner correctly stopped rather than waiting beyond its bounded 120-second retry window.
- No specialist role completed; Commander synthesis, independent acceptance, and final verification did not run. This is a provider free-tier quota interruption, not a reviewer verdict or code regression.
- A new checkpoint artifact was uploaded: `q08-review-checkpoint-44374650548`, artifact ID `14460422014`, SHA-256 `45f96c901b9ceac0dee624dcfa3f3b06fb4ae3dc99884f15dd2e3fb9b0854f32`, retention through 2026-11-25 18:54:17 UTC. The prior checkpoint had an empty reports map; this attempt failed at the same first specialist, so no completed role is evidenced.
- **Next step:** do not dispatch again before 08:00 WIB on 2026-11-19. After reset, run the same workflow on branch `security/q0-provider-sanitization-2026-11-18`, with `review_head_sha=0dd17609305d1e738d4c4c2f65129ccf30f39d7f` and `resume_from_run_id=44374650548`. Preserve the $0 budget: do not switch to paid models or add paid credits. If another quota interruption occurs, use the newest run's uploaded checkpoint ID.
- Exact-head offline tests remain passed 51/51 in run [44373013889](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44373013889). Specialist review remains **INCONCLUSIVE / NOT ACCEPTED** until all 19 roles, Commander, independent acceptance, and final verification pass. No protected-path access, PR merge, exchange/account operation, or trading action occurred. Whole-project completion remains UNRATED.


### Independent static review of PR #71 and PR #69 workflow dispatchability (2026-11-19)

- Re-fetched PR #71 at head `ec011a0cf16eeb3a4eaae3df924d96e8a0f99511` (open/draft/unmerged; base `main` at `9bf95e28171447faa910ecd5185b59a349555a52`). Exact files re-fetched:
  - `.claude/settings.json` blob `9c3ea53e38be278adb71f43983ec10003751da36`
  - `CLAUDE.md` blob `92df0f3fd9aba46800df77d006a45a4ca92ac198`
  - `docs/development-stack/roadmap.md` blob `4ca1bff17e62075211cf4c72ce640215e5ca26d8`
- Parsed the settings JSON independently. It contains exactly the ten expected Read/Edit deny rules for `P1/**`, all `signal/**`, `markets/risk/**`, root `validator.py`, and root `report.py`; no extra deny entries were present. Rechecked the instruction and roadmap text for those protected boundaries, PAPER-only/LIVE-disabled policy, and the exact approved Tokocrypto candle route.
- Cross-checked the rules against Anthropic's current permission documentation: Read/Edit path rules use gitignore-style matching; Read denials are best-effort for built-in search tools and do not stop arbitrary subprocesses from opening files. The repository's own documentation correctly labels these controls defense-in-depth, not an OS sandbox. Runtime effectiveness in an actual Claude Code session is **UNVERIFIED**. Source: https://code.claude.com/docs/en/permissions
- PR #69 adds `.github/workflows/python-static-quality.yml` with only `workflow_dispatch`. That workflow file is not on `main` at the current default-branch baseline `9bf95e28171447faa910ecd5185b59a349555a52`; GitHub requires a workflow_dispatch file to exist on the default branch before it can be manually triggered from the Actions UI. Therefore its Ruff check cannot be dispatched against the PR branch until the workflow is first present on the default branch. No merge is authorized by this addendum. Source: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch
- Verified the official Ruff 0.17.5 GitHub release metadata: tag commit `c91de8a012cb87efe279b762020a0d28dd75ddb5`; Linux x86-64 archive digest `sha256:7d261fc981a784668e19e9fa6ad437bfd95b67f2dc263fc1eab87d54d72fcc90`. The local lint run was **NOT EXECUTED** because the current container cannot resolve external hosts; no Ruff result is claimed.
- This was static inspection only. No protected path was opened, no application module was imported/executed, no workflow was dispatched, and no PR was merged. PR #71's config syntax/content checks are passed; effective runtime enforcement remains unverified. PR #69 Ruff execution remains pending an approved route to run the check.


### Isolated durable holdout publisher tests (2026-11-19)

- Re-fetched PR #34 source at exact head `301b90dca0fd1622d3ff69ee3bbf47d2b401d448` (open/draft/unmerged).
- Executed only `tests/test_holdout_publish.py` against `research/holdout_publish.py` in an isolated temporary directory using Python 3.13.5: **18 tests passed, 0 failures, 0 errors**.
- Exact Git blob identity was verified for both executed files before the final run:
  - `tests/test_holdout_publish.py`: `e84f4978ac8a72202c017cb88dbee5ee7dafea22`
  - `research/holdout_publish.py`: `923acda6fb731a0d1ad4f8c3936a3a825ea54e8a`
  - `research/__init__.py` is empty (blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`).
- Static import review found only Python standard-library imports plus the publisher module; the publisher itself imports only `argparse`, `json`, `os`, `stat`, and `pathlib`. No protected module is imported or executed by this test closure.
- Test cases exercise synthetic temporary files only. No frozen dataset, real registry, backtest pipeline, holdout evaluation, exchange endpoint, credential, or protected path was accessed.
- This is a focused local Python 3.13.5 pass for the publisher only. Python 3.11 CI, complete PR #34 integration, and dependent pipeline suites remain **UNVERIFIED**. PR #34 remains open/draft/unmerged; no Actions workflow was dispatched and no merge occurred.


### Holdout test workflow and dependent-suite boundaries (2026-11-19)

- Re-fetched PR #34's `.github/workflows/manual-offline-unit-tests.yml` (blob `7b132b23649db98c2b36608dec9dda923c4d9fdc`). It has only `workflow_dispatch`, repository `contents: read`, a pinned checkout action with `persist-credentials: false`, and sparse checkout of exactly `research/__init__.py`, `research/holdout_publish.py`, and `tests/test_holdout_publish.py`. It provisions Python 3.11 and runs only that isolated test file. No workflow was dispatched.
- PR #34's diff deletes the prior `.github/workflows/research-backtest.yml` workflow, whose old trigger included both `workflow_dispatch` and a `push` on `milestone-3-data` affecting research/backtest paths. The deletion is present only in the open draft candidate; it is not integrated into `main`.
- PR #68's six-module suite remains blocked from execution under the current protected-path boundary. Static import tracing shows `tests/test_engine.py` reaches `research.engine` -> protected root `validator.py`; `tests/test_history.py` reaches `research.history` -> protected `validator.py`; `tests/test_pipeline.py` imports `run.py` -> protected `report.py` and `validator.py`; and the backtest-pipeline / holdout-reporting tests reach `research.pipeline` -> `research.engine` -> protected `validator.py`. No test in that blocked suite was run.
- The only completed local execution for this holdout publisher is the isolated 18/18 Python 3.13.5 run recorded above (also repeated with warnings treated as errors: 18/18 passed). Exact Git blob hashes matched before execution. Python 3.11 Actions evidence remains pending.
- The manual publisher workflow lives on the unmerged PR #34 branch, not on current `main`; under GitHub's `workflow_dispatch` default-branch requirement it is not yet manually dispatchable through the Actions UI. No merge authority is implied.
- No protected files were opened, no actual research-data registry or frozen dataset was touched, no TEST evaluation/backtest ran, no exchange request was made, and no PR was merged.


### Q0 provider workflow static review (2026-11-19)

- Re-fetched PR #60 at exact head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; it remains open/draft/unmerged against M6 baseline `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Static review of `.github/workflows/research-data.yml` (blob `0fa6cd03da7fa0f7a26fd81fc2229241f8fbaae0`) found:
  - `contents: read` only; pinned checkout and upload-artifact actions; checkout uses `persist-credentials: false`.
  - Sparse checkout is limited to fetcher/provider/probe/config/history files and the named offline test files; it does not include protected root `validator.py`, root `report.py`, `P1/`, `signal/`, or `markets/risk/`.
  - The included tests were statically inspected: `tests/test_pipeline.py` explicitly reads source text rather than importing `run.py`; `tests/test_live_check.py` imports only `providers` and `fetcher`; `tests/test_history.py` reads the unprotected history gate source/config. The workflow then invokes `fetch_history.py`, whose import closure is `research.history` and Python standard library only. That gate explicitly records zero network requests, writes no dataset, and returns FAIL while market identity remains unverified.
  - This workflow is a fail-closed offline gate, not proof that Tokocrypto market identity or data availability has been verified. It was not dispatched or executed in this review.
- Static review of `.github/workflows/research-backtest.yml` (blob `9c1fa840bb70d5c285a0ac5d730f4aac65e7046b`) found read-only permissions, pinned actions, credential persistence disabled, and an explicit stop after the approved offline subset to avoid importing protected `validator.py` through the backtest engine. No backtest, dataset checkout, TEST evaluation, or exchange request is performed by this blocked workflow.
- This is static configuration/import-closure evidence only. It does not replace the pending 19-role specialist review, actionlint/zizmor execution, or manual Actions runs. No protected file was opened, no test or workflow was executed in this audit, and no PR was merged.


### Q0 public transport policy source review (2026-11-19)

- Reviewed exact PR #60 source blobs at head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`:
  - `fetcher.py`: `bab797835ef2fdbff616847d7eb6ba887124fe7e`
  - `providers.py`: `4d0fd1115d44f6e427954809a99332a087169cc8`
  - `tests/test_fetcher.py`: `f3b08e3957ad1b49d90b0f36817e74accf2ba602`
  - `tests/test_sanitization.py`: exact content was statically inspected as part of PR #60.
- Bounded static review found the transport policy restricts HTTPS to exact host `www.tokocrypto.site`, exact path `/api/v3/klines`, exact BTCUSDT query shape, supported intervals, bounded timestamps/limit, and rejects userinfo, non-default ports, fragments, duplicate/unknown query parameters, unapproved routes, and malformed URLs.
- Production opener constructs a default GET request with only User-Agent and Accept headers, disables redirects, reads at most 1 MiB + 1 byte, and closes the response. HTTP errors are closed without reading provider-controlled bodies. Retry policy stops immediately on 429 and does not retry non-5xx responses. Parser rejects non-finite values, booleans, malformed rows, and non-standard JSON constants. Provider factory authorizes only Tokocrypto; legacy provider classes cannot bypass the central URL allowlist.
- No actionable defect was established by this bounded static review. This is **not** an independent specialist acceptance: dynamic behavior, TLS/DNS/runtime properties, complete call graph, Python 3.11 test rerun, and the 19-role review remain unverified/pending. The existing 51/51 offline result remains tied only to its exact recorded SHA.
- No source was modified, no module was imported/executed, no network/exchange request was made, and no protected path was accessed.


### MEME_INTEL scope reconciliation (2026-11-19)

- The proposed B1/E1/E2 requirements already include meme/newly listed asset coverage, universe eligibility, and opportunity ranking. The named `MEME_INTEL` initiative should be tracked as a research-only work package under those requirements, not counted as a completed standalone subsystem or given an extra weight before scope approval.
- A path-name search of the default-branch tree at `9bf95e28171447faa910ecd5185b59a349555a52` and Q0 candidate tree at `0dd17609305d1e738d4c4c2f65129ccf30f39d7f` found no paths named for meme intelligence, token discovery, universe scanning, or opportunity ranking. The open-PR title search also returned no MEME_INTEL work item. This is only a path/title search; it does not prove no related logic exists under other names or in an uncommitted external workspace.
- Therefore MEME_INTEL implementation status remains **UNVERIFIED / NOT DEMONSTRATED IN REPOSITORY**. Required scope, approved public data sources, token eligibility/anti-scam criteria, provenance, ranking model, stale-data behavior, and synthetic evaluation criteria still need to be specified before implementation can receive acceptance credit. No new provider or network source is authorized by this note.


### Exact-blob local verification of Step 1 fail-closed market-identity gate (2026-11-19)

- Reconstructed only the following unprotected files in an isolated temporary directory from PR #60 head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, and verified each Git blob SHA-1 before execution:
  - `research/history.py`: `a6a56d25fe60a255841e27c1b72b7d910eab19d9`
  - `tests/test_history.py`: `6a3ea9b26a93b60059bda56347bd4ea211dcb574`
  - `research_config.json`: `58ff32379a7f4fbc0ca5d75ff10e20e82bbaf3ff`
  - `fetch_history.py`: `75fcaa6cbe0539f6dde5dcf8a69778c07f28513b`
  - Empty `research/__init__.py` matched the empty-blob hash `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391`.
- Python 3.13.5: `tests/test_history.py` **4/4 passed**.
- Ran the exact `fetch_history.py` entry point against the exact checked-in `research_config.json`, with output redirected to an isolated temporary directory. Exit code **1 was expected** because market identity is deliberately unverified. The generated JSON reported `gate=FAIL`, `network_requests=0`, `dataset=null`, and `backtest_allowed=false`; only `dataset_report.json` and `dataset_report.md` were created, and no dataset directory was created.
- The command emitted an unrelated environment startup warning from the local spreadsheet warmup hook; it did not affect the 4/4 test result or the expected fail-closed report.
- This verifies the local fail-closed Step 1 gate on Python 3.13.5 only. It does not validate Tokocrypto market identity, candle retrieval, Python 3.11 compatibility, or any backtest. No network call or protected-module import occurred.


### Q0.8 workflow state recheck (2026-11-19)

- Re-read the repository Actions API after the previously reported provider quota reset window. The latest specialist-review run is still `44374650548` on exact SHA `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; no later specialist-review dispatch appears in the latest 100 workflow runs.
- The latest exact-head offline test remains run `44373013889`, conclusion `success`, on the same SHA. No newer offline run appears.
- Therefore Q0.8 remains: offline tests passed; specialist review quota-blocked/incomplete; all 19 roles, Commander synthesis, independent acceptance, and final verification remain pending. No assumption is made that provider capacity automatically returned after reset.
- Workflow dispatch remains unavailable through the connected GitHub read-only API. The owner must manually dispatch the specialist workflow when ready; use the same branch and review SHA, and resume from run `44374650548` if its checkpoint artifact is still retained and downloadable. Recheck PR #60 head and artifact identity immediately before dispatch. No merge or code execution was performed by this recheck.


### Q0.8 reviewer workflow checkpoint-restore guard (2026-11-19)

- Rechecked PR #64 before editing. Its prior head was `41390c5d56513cf5157c6971e8e30994dd7d4e63`; only the intended workflow and immutable runner files are in its change set. The pinned runner remains `c0ed377c82d4f0586dceb20eeaffd3725b568101` / blob `5466bf6039e9653ef79cbbbb65b15753ce5cd723`.
- Identified a minor workflow hygiene issue: the checkpoint-download step ran whenever `resume_from_run_id` was non-empty, even in `synthetic` mode, although the ID validation step was correctly conditional on `mode == review`.
- Updated only `.github/workflows/q08-specialist-review.yml` on PR #64 branch `security/q08-reviewer-pin-correction-2026-11-18`. New commit: `7638be6c0eeb6a63f819e47d016c983cd2487854`; new blob: `5ad241f6fd7777dbc449818874b8981786cc6054`.
- The artifact restore now requires both `inputs.mode == 'review'` and a non-empty `resume_from_run_id`, matching the validation step. Re-fetched the committed workflow and verified both conditions, the immutable reviewer pin, default synthetic mode, read-only permissions, and pinned artifact action.
- This is a narrow static workflow edit; Actionlint/GitHub runtime verification is **PENDING**. PR #64 remains open/draft/unmerged. No checkpoint was restored, no workflow dispatched, no reviewer code executed, and no PR merged.


### Bounded holdout publisher enumeration successor PR #76 (2026-11-19)

- Static review found the prior implementation sorted/materialized every `*.json` entry before enforcing `MAX_COMPLETED_FILES = 1000`; the nominal cap therefore did not bound enumeration memory or iteration.
- Created a separate draft successor, PR #76: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/76
  - Branch: `security/holdout-publisher-bounded-scan-2026-11-19`
  - Head: `5970d6d7b6bd99b83cb5dfb0eb502013b2f69678`
  - Base: PR #34 branch at exact parent `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`
  - Exactly two changed paths: `research/holdout_publish.py` and `tests/test_holdout_publish.py`.
- Implementation now uses `itertools.islice(..., MAX_COMPLETED_FILES + 1)`, stops after 1,001 matches, rejects overflow, and sorts only the bounded list. Added a deterministic regression test whose iterator offers 10,000 entries and asserts exactly 1,001 were consumed.
- Re-ran the focused synthetic test suite against the exact content committed in PR #76, Python 3.13.5 with warnings treated as errors: **19/19 passed**. Exact changed blobs:
  - `research/holdout_publish.py`: `b2c27931b5b4a86b84cd9dc0892d2c8032a6c0b5`
  - `tests/test_holdout_publish.py`: `4ca2aa5465b8ab0c07d2a84e6f1de9fe59182150`
- Re-fetched both blobs from PR #76 after commit and confirmed exact SHA matches. The focused suite imports only the empty `research/__init__.py`, the publisher, and standard-library modules; no protected path/module is part of its execution closure.
- PR #76 is open/draft/unmerged and GitHub reports the branch mergeable relative to its stacked PR #34 base. No Action workflow run or commit status was reported for its head at the verification check. No PR #34/#68 branch was changed, no TEST evaluation or backtest workflow was run, and no exchange/network operation occurred.
- This is local Python 3.13.5 evidence only. Python 3.11 CI and integration into `main` remain pending; PR #76 depends on the PR #34 parent chain and earns no whole-project completion percentage by itself.
