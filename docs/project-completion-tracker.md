# AI Trading & Automation Laboratory — project-wide completion tracker

**Status:** Provisional scope register; not yet a valid percentage score  
**Last checked:** 2026-11-20  

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
| M1 public market-data transport | Read-only BTC/USDT public candle retrieval, parsing, and reporting | Implemented as a candidate; current approved Tokocrypto scope is unauthenticated GET candles only at `www.tokocrypto.site/api/v3/klines`; server-time is not authorized | Q0 offline suite historically passed 35/35 on commit `6678b3d06fc780bbeef21894c9650827a9e52904`; this is not evidence for later heads | Transport allowlist and fail-closed checks exist on the Q0 branch; live-check workflow is blocked where it imports protected modules | Re-run only the sparse, approved offline suite on the exact current Q0 head; independently review transport boundary |
| Provider-response sanitization | Prevent provider-controlled values and exceptions from reaching reports, logs, summaries, or output sinks | Integrated candidate is in draft PR #60 on top of the Q0 allowlist; PR #56 is superseded | Prior project notes report a local isolated snapshot passed 50/50 tests across six approved offline modules; this result was not independently reproduced in the current review and is not a byte-for-byte checkout or exact-head GitHub Actions result. Historical 53/53 run on old PR #56 head remains historical only | Old PR #56 workflow checked out protected `validator.py` and `report.py`; its replacement now blocks before checkout. PR #60 keeps the Tokocrypto-only allowlist and excludes protected imports from the sanitizer test | Q0.8 run #44262541867 passed 51/51 on earlier head `2d6698a2292ecec57a72b74b3f7de7c49d989bc8`; latest head is now `18d02375577aefe39a0a13fabd0a5529f82ac01c` (37 commits ahead, 26 changed paths), and an exact-head rerun is pending after reviewer-scope, protected-test-description, and HTTP 429 retry corrections. The transport now fails closed on HTTP 429 because its response interface does not preserve `Retry-After`; this avoids premature retries that could violate Tokocrypto's documented backoff requirement. The latest PR #60 change places the empty provider-authorization gate inside `research.crosscheck.run_crosscheck` before filesystem or network side effects, shares that gate with the research pipeline, and records the exact sources returning data in the artifact schema expected by the pipeline validator. Official Tokocrypto docs confirm `/api/v3/klines` and millisecond candle timestamps, but do not document `/api/v3/time`; server-time access is excluded from the current authorization, not merely awaiting verification. Keep unapproved providers disabled and retain PR #56 as historical only. |
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


### Q0.8 checkpoint and dispatch-form revalidation (2026-11-19)

- PR #60 remains open/draft/unmerged at exact review head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, based on M6 baseline `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Run `44374650548` remains the latest specialist attempt on that SHA; job is completed with failure due the previously established free-provider HTTP 429. It did not complete a specialist role.
- Checkpoint artifact remains available: `q08-review-checkpoint-44374650548`, artifact ID `14460422014`, `expired=false`, expiry `2026-11-25T18:54:17Z`. The artifact's earlier SHA-256 and successful restore evidence remain in the preceding Q0.8 addendum.
- Live workflow YAML comparison found:
  - Default-branch `.github/workflows/q08-specialist-review.yml` blob `f017b5aa44bbfaa5f8fcefb24cbca9cc8fe49267` exposes `review_head_sha` and `mode`, but not `resume_from_run_id`.
  - PR #60 branch workflow blob `a32e4e78b9987c133934ce86a64be367468e839d` exposes all three inputs and pins the immutable self-contained runner commit `c0ed377c82d4f0586dceb20eeaffd3725b568101`.
  - PR #64 branch workflow blob `5ad241f6fd7777dbc449818874b8981786cc6054` also exposes all three inputs and adds the extra guard that checkpoint restoration is only attempted in `review` mode. The PR #60 branch version's restore condition still checks only for a non-empty resume ID; with required `mode=review`, that is the intended restore path.
- Therefore the safe dispatch target remains branch `security/q0-provider-sanitization-2026-11-18`, review SHA `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, resume run ID `44374650548`, mode `review`. The checkpoint is not expired. Provider capacity after reset is still not confirmed.
- GitHub documents that the workflow must exist on the default branch for manual dispatch, and the Actions UI allows selecting a branch and filling its inputs. A current GitHub Community thread (2026-10-17) reports that the UI may fail to refresh input fields after changing the selected branch; when using iPhone, refresh/reopen the Run workflow form after selecting the PR #60 branch and do not submit unless the `resume_from_run_id` field is visible. Sources: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow and https://github.com/orgs/community/discussions/210506.
- No dispatch was performed; no workflow or reviewer code was executed during this state check.


### MEME_INTEL repository capability audit (2026-11-19)

- Reconciled the current candidate architecture by static inspection of unprotected files at PR #60 head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`. No protected path was opened, imported, or executed.
- The provider registry (`markets/providers/registry.py`, blob `144568cbb9206e2fb55f3c1bb789b386f078c2b0`) registers only Binance Vision and Kraken. The explicit symbol tables (`markets/providers/symbols.py`, blob `a12f19b47cf8bab5cfb22a04929bf80747ffa75e`) contain only Binance BTC/USDT and Kraken BTC/USD. This is not a broad token-universe or newly-listed-asset discovery capability.
- The strategy registry (`markets/strategies/registry.py`, blob `3138b56b981d159cb274a804671989b6ffdcc644`) loads only `BtcS1DailyTrend`. Its adapter (`markets/strategies/btc_s1.py`, blob `0d2dc992d6830be680a18200f78ede8800b0d2a5`) explicitly supports only `crypto:binance-spot:BTC-USDT` at 86,400-second intervals. No meme-asset strategy, ranking model, or opportunity lifecycle is demonstrated.
- The identity model (`markets/identity.py`, blob `db3d9053b9f5d7144505a8a19dc93db55ed29fa4`) currently enumerates crypto, equity, and FX asset classes; it does not explicitly model indices or commodities. Even equity/FX identity support does not demonstrate provider coverage or working scanning for those markets.
- The repository code search on the default branch returned only the master handoff / repository instructions for `meme` and `token discovery`, and no results for `universe` or `ranking`. The PR #60 candidate tree contains no paths named for meme intelligence, token discovery, universe scanning, or opportunity ranking. These searches are bounded evidence, not proof that no concept exists under a different name or in external/uncommitted work.
- Result: MEME_INTEL remains **NOT DEMONSTRATED / UNVERIFIED** in the repository. The existing provider-neutral contracts and exact registries are a possible foundation, not an implemented scanner.
- No new market-data provider, token-listing feed, DEX source, external API, package, or network permission was added or used. Before implementation, the owner must approve the research universe and source categories; engineering must then define deterministic eligibility/anti-scam rules, provenance, stale/partial handling, ranking evaluation, and synthetic acceptance tests. This is a requirements/data-source approval dependency, not a reason to bypass the current provider allowlist.


### Q0.8 checkpoint artifact byte-level revalidation (2026-11-19)

- Downloaded artifact ID `14460422014` from failed run `44374650548` and independently inspected the ZIP bytes.
- ZIP SHA-256 exactly matches the previously recorded artifact digest: `45f96c901b9ceac0dee624dcfa3f3b06fb4ae3dc99884f15dd2e3fb9b0854f32`.
- ZIP contains only `q08-review-checkpoint.json` (302 bytes; SHA-256 `2e05c50a545083c1180d816fc07d26eb04f9acb5ffaa3cafe43e4edbfda1614c`).
- Parsed checkpoint identity: schema 1; repository `ruthlessjoey/btcidr-trading-lab`; base `cd451972e3a641ad6fa78e64abf3968655a4b82a`; head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; model `inclusionai/ling-3.2-flash:free`.
- Checkpoint contains **0 completed specialist reports**, no Commander synthesis, no independent acceptance, and no final verification. It is valid as a resume starting point but contains no specialist work to preserve.
- This confirms the quota-blocked review did not complete any role. The next review run must use exact head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f` and may reference run ID `44374650548` as the resume source; expected restored report count is zero.


### Q0.8 complete specialist review result — run 44470636642 (2026-11-19)

- GitHub Actions run: https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44470636642; workflow conclusion **success**, on branch `security/q0-provider-sanitization-2026-11-18`, exact PR #60 head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, exact M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- The run restored checkpoint artifact from run `44386019954` (artifact `14465936877`, ZIP SHA-256 `c7f67ce13f0127d683f26c7a14cc1454bde0fa0e90f24f14a78deae490f37a7a`), passed Python 3.11 setup, trusted-runner syntax compilation, and the synthetic policy smoke test, then completed all 16 specialist prompts plus Commander, independent-acceptance, and final-verification prompts.
- Final checkpoint artifact: `q08-review-checkpoint-44470636642`, artifact ID `14506637538`, retained until `2026-11-26T07:09:05Z`; ZIP size 48,081 bytes; ZIP SHA-256 `e41db1d59a3a59bdab559905af847f5223596b0e67262563b5ec6ecf909325b6`. Downloaded ZIP was independently hashed and parsed. Inner JSON is 193,821 bytes; SHA-256 `a4db7155855591afc38afb9345291790fefb1ab66774063667c6373540135c30`.
- Checkpoint identity is schema 1, repo `ruthlessjoey/btcidr-trading-lab`, base `cd451972e3a641ad6fa78e64abf3968655a4b82a`, head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`, model `inclusionai/ling-3.2-flash:free`. It contains all 16 specialist reports and all three synthesis/acceptance/verification reports.
- Specialist verdicts: **12 PASS WITH FINDINGS**, **3 BLOCKED** (`implementation-engineer`, `strategy-validation`, `systematic-debugging`), and **1 INCONCLUSIVE** (`architecture-architect`; the runner inserted this verdict because the response omitted the required verdict line). Commander: **BLOCKED**. Independent acceptance: **BLOCKED**. Final verification: **BLOCKED**. No specialist returned an unqualified PASS. Therefore the Actions workflow succeeded in executing the review pipeline, but **Q0.8 independent acceptance did not pass**.
- All 16 specialist prompts used the same configured free OpenRouter model/provider. Role separation is not independent model/provider diversity. Findings are static review opinions based on supplied diffs, not executed tests or native Claude Code subagents.

#### Source-level recheck of disputed import-closure claims

- Re-read the exact PR #60 head source for the six modules in `.github/workflows/q08-offline-tests.yml`, plus the Step 1 entrypoint and module, without importing or executing repository code.
- `tests/test_pipeline.py` imports only Python standard-library modules; it reads `run.py` as text and explicitly does not import it.
- `tests/test_live_check.py` imports only `providers` and `fetcher` plus standard-library modules; it does not import `live_check.py`.
- `tests/test_history.py` imports only standard-library modules and reads `research/history.py` as text. `research/history.py` imports only standard-library modules. `fetch_history.py` imports `research.history`; the visible entrypoint chain therefore does not reach `research.engine` or `validator.py`.
- `tests/test_fetcher.py` imports `fetcher`; `tests/test_probe.py` imports `probe` (which imports only `sys`); `tests/test_sanitization.py` imports `fetcher`, `providers`, and `research.crosscheck`; `research.crosscheck` imports `fetcher` and `providers`, while `providers` imports `fetcher`. These visible imports do not reach `research.pipeline`, `research.engine`, or `validator.py`.
- The static source check resolves the review's contradictory statements about `tests/test_pipeline.py`, `tests/test_live_check.py`, and `fetch_history.py` for the visible import statements. It is not a runtime/import-hook proof and does not authorize execution of any protected dependency.
- The separate source boundary remains: `research/pipeline.py` contains imports from `research.engine`, and the known chain reaches protected `validator.py`. That dependency was not opened, imported, executed, or tested. Its change within PR #60 remains a genuine acceptance blocker until separately authorized review or a safe refactor removes the edge.
- The specialist-review runner itself was also re-read at immutable commit `c0ed377c82d4f0586dceb20eeaffd3725b568101`: its exact 27-path allowlist excludes protected paths; source snapshots are secret-screened; checkpoint identity is bound to repository/base/head/model and reports are screened; the GitHub token is used for repository GET requests and the LLM key is placed in the HTTP Authorization header, not in the model payload. This is bounded static evidence, not a full red-team or independent security acceptance. Secret-pattern screening is not proof against every possible secret format.

#### Current disposition

- PR #60 remains open/draft/unmerged. Keep all research/backtest/live/probe/cross-check execution blocked where its import closure or approval is unresolved. Do not treat the successful Actions conclusion as a Q0.8 acceptance pass.
- The existing exact-head offline run `44373013889` remains the recorded 51/51 result on Python 3.11 for this PR #60 head; the specialist-review run did not execute those project tests.
- No repository code, workflow, protected module, exchange endpoint, credential, account, order, or trading function was accessed/executed/changed during this review recheck. No PR was merged. Overall project completion remains **UNRATED** pending owner-approved scope/weights and complete evidence.


### Q0.8 reviewer diff and acceptance-gate correction (2026-11-19)

- A post-run audit found that the immutable reviewer defined `MAX_DIFF = 160_000` and a synthetic test for `enforce_diff_limit()`, but the production `review()` path did not call that helper. Run `44470636642` logged `diff_chars=176188`, proving the intended diff ceiling was bypassed (the separate 256,000-byte serialized-request limit still applied).
- A second correctness issue: the runner returned exit code 0 after completing all prompts regardless of verdicts. Thus run `44470636642` was green even though Commander, independent acceptance, and final verification all returned `BLOCKED`.
- Corrected the runner on PR #64 branch `security/q08-reviewer-pin-correction-2026-11-18`:
  - New immutable runner commit: `33df164138afc7d6037097357e073cec97ddda34`
  - Runner blob: `700cdb856f424f2973060c1fb6c9f229a9e75fec`
  - The diff ceiling is now 192,000 characters, which admits the measured 176,188-character PR #60 diff while retaining a hard bound; the serialized request remains capped at 256,000 bytes.
  - The actual review path now calls `enforce_diff_limit(review_diff)` before any model request.
  - Added `review_verdict_failures()` and synthetic cases for accepted verdicts, blocked/inconclusive roles, and missing specialist roles.
  - After the full review summary is written, any missing role or verdict other than `PASS` / `PASS WITH FINDINGS` causes a nonzero exit. The workflow's `if: always()` artifact step still preserves the checkpoint for diagnosis/resume.
- Updated both workflow copies to pin that exact immutable runner commit and to restore checkpoints only in `review` mode:
  - PR #64 head: `71ef3b721d095cefd5561d24d86f5ab30561fff9`
  - PR #60 head: `a72c5287b5df64bfb1fb9385e0e1423f89ea8722`
  - Both workflow blobs are byte-identical: `a24836a478d5c6cfc06e93def5eac943e59b3be5`.
- Re-fetched both PRs and their changed-file lists: PR #60 remains exactly 26 changed paths; PR #64 remains exactly two changed paths. Both remain open/draft/unmerged. Re-fetched the new runner blob and statically verified the cap, production call site, acceptance gate, and synthetic test cases.
- **Runtime verification pending:** no Python 3.11 `py_compile` or synthetic workflow has yet run against commit `33df164...`; no Actions dispatch was available through the connected GitHub tools. The owner must manually run `Q0.8 immutable 19-role specialist review` in `synthetic` mode on PR #64 branch first. This mode does not call the LLM. Then run the approved offline tests against the new PR #60 head and, after synthetic succeeds, run the specialist review against exact head `a72c5287b5df64bfb1fb9385e0e1423f89ea8722` with `resume_from_run_id` blank. The old artifacts from runs `44386019954` and `44470636642` are bound to the previous head and must not be resumed against the new SHA.
- The earlier 51/51 Q0.8 offline result is tied to old head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; it is not promoted to a pass for the new head until the offline workflow is rerun.
- No protected file/path was opened or changed; no repository module was imported/executed; no exchange, account, credential, or trading operation occurred. PRs were not merged.


### Q0.8 unchanged entrypoint context correction (2026-11-19)

- Re-parsed the actual checkpoint artifact from run `44470636642` (ZIP SHA-256 `e41db1d59a3a59bdab559905af847f5223596b0e67262563b5ec6ecf909325b6`; inner checkpoint SHA-256 `a4db7155855591afc38afb9345291790fefb1ab66774063667c6373540135c30`). The `architecture-architect` response omitted its required verdict and was correctly downgraded to `INCONCLUSIVE`; the remaining results were 12 `PASS WITH FINDINGS`, 3 `BLOCKED`, with Commander, independent acceptance, and final verification all `BLOCKED`.
- A further review-harness gap was confirmed: `fetch_history.py` was in the exact 27-path snapshot allowlist and was fetched/secret-screened, but it was unchanged at base/head and only its empty unified diff was transmitted. Reviewers therefore could not inspect its actual import chain. The full file was independently re-fetched from the exact PR #60 head and is a short entrypoint importing only `research.history.run_step1`; `research/history.py` itself imports only standard-library modules. No runtime import was executed.
- Corrected the reviewer on PR #64 branch:
  - Runner commit `4dae2943a716a42056f075bd79ddaf1930a63944`, blob `644d3f61707ce807a113019cd2bef22c7a078be0`.
  - Added a fixed `UNCHANGED_CONTEXT_PATHS` allowlist and `build_unchanged_context()`, which requires each context file in both snapshots and fails unless base/head contents are byte-identical.
  - The full head source for `fetch_history.py` is now passed separately as `unchanged_context_files` alongside the bounded diff; source has already passed the normal snapshot secret-screen and size limits.
  - Synthetic tests cover inclusion and reject unexpected changes to a file declared as unchanged.
- Both PR #60 and PR #64 workflow copies now pin runner commit `4dae2943a716a42056f075bd79ddaf1930a63944`, with byte-identical workflow blob `284a1f4f36e36a60764e955fdf32e0f4f9fe31ef`. Their checkpoint restore remains restricted to explicit review mode.
- Latest PR heads:
  - PR #60: `bda4627cbfa11d4669b3df8d828d7000ac52377d` (26 changed paths, open/draft/unmerged).
  - PR #64: `7532e8e5e449c9db7d4a507bee8119674083461f` (two changed paths, open/draft/unmerged).
  - PR #65: this tracker remains open/draft/unmerged; current previous head was `80d3ffb8046fe81ff099e229cfc1d353c25df1b6` before this addendum.
- Runtime verification is still pending for the new reviewer commit and both new PR heads. The old Q0.8 review artifact and old 51/51 offline test evidence are bound to SHA `0dd17609305d1e738d4c4c2f65129ccf30f39d7f` and must not be reused as proof for the new PR #60 head.
- PR #60 remains unaccepted because the protected `research.pipeline.py -> research.engine -> validator.py` dependency boundary is unresolved and unauthorized, regardless of the improved reviewer context. Do not test or access that chain. No PRs were merged and no workflow dispatch performed.


### PR #66 isolated test correction (2026-11-19)

- Static inspection of PR #66 (`security/q08-unprotected-live-check-tests-2026-11-18`) found its original test both asserted that Tokocrypto's `time_url()` passed URL validation and expected a Tokocrypto-only `live_providers` list not present in its `main` base. The latter meant the test could fail on its own target branch; the former conflicted with the currently approved candle-only `/api/v3/klines` route.
- Updated only `tests/test_live_check.py` on PR #66:
  - Commit `269fc112d13d6a0ed92195156ff22d55263e927b`
  - Blob `cf0fdc200865d4f9692aa8b9f1666b2547db77ff`
  - Tests now cover local Tokocrypto adapter construction (no network), unknown-provider rejection, and read-only default configuration while checking inclusion (not exclusivity) of Tokocrypto on the existing `main` baseline.
  - Removed every `time_url()` or endpoint-authorization assertion from this default-branch isolation PR; endpoint security assertions remain within Q0 transport tests.
- Re-fetched exact PR #66 head and file. The visible test imports only standard-library modules and `providers`; `providers` imports `fetcher`, so the visible closure stays outside protected modules. No test was run. PR #66 remains open/draft/unmerged.


### Q0 Step 1 entrypoint import-closure regression (2026-11-19)

- Exact PR #60 `fetch_history.py` blob `75fcaa6cbe0539f6dde5dcf8a69778c07f28513b` was re-read. It imports `argparse`, `json`, `sys`, and `research.history.run_step1`; it does not visibly import a protected module, HTTP client, or other provider.
- Added a static Python AST import-closure regression to `tests/test_history.py`:
  - PR #60 commit `cef049ebbf9f1390a4f14c618e6a12a53621761e`
  - Test blob `5237398fc8b24283e4d0654246d66e8279270886`
  - The test asserts the exact direct/transitive-source import names for `fetch_history.py` and `research/history.py`, rejects dynamic `__import__` / `importlib.import_module` calls, and parses files as text only. It does not import or execute the entrypoint or protected code.
  - `tests/test_history.py` is already part of the Q0 offline workflow's six-module approved subset. The expected behavior is now machine-checkable on future workflow runs.
- PR #60 current head at this update: `cef049ebbf9f1390a4f14c618e6a12a53621761e`, still open/draft/unmerged with exactly 26 changed paths and M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- The new static regression has not yet been run under Python 3.11; the previous 51/51 run belongs to old head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f` and is not evidence for this head.


### Current security-instruction alignment and CI state (2026-11-19)

- Rechecked current main commit 9bf95e28171447faa910ecd5185b59a349555a52 and root CLAUDE.md blob fff092011f7fb67a2c413909991b32ab9dda560a. The shared instruction still authorized Tokocrypto server-time and candles, conflicting with the current owner mandate that permits only unauthenticated HTTPS GET candles at www.tokocrypto.site/api/v3/klines; it also omitted the additional protected paths markets/risk/, validator.py, report.py, and copies of signal/.
- Created documentation-only PR #77 from main:
  - URL: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/77
  - Branch: docs/align-current-security-boundaries-2026-11-19
  - Commit: aa71ecfb9d1a3aad955f3cea68ffcb5fbd498e8a
  - Blob: ee5506ce725cc4eb9c41b4c7bae23d3cfa2be236
  - One changed file: CLAUDE.md (13 additions, 10 deletions).
  - The replacement text aligns protected paths, PAPER-only/LIVE-disabled, the exact Tokocrypto candle-only endpoint, no server-time, no .com, no private endpoints, and no test/import execution closure into protected modules. Re-fetched and statically checked each required statement. No tests/network operations were run for this documentation-only change.
- PR #77 remains open/draft/unmerged. GitHub Actions run 44484065388 completed: Actions analysis succeeded, Python CodeQL analysis succeeded, and CodeQL reported success. These are static-analysis jobs, not functional tests.
- Latest Q0.8 branches were re-fetched:
  - PR #60 head advanced to cef049ebbf9f1390a4f14c618e6a12a53621761e (one commit after bda4627...), changing only tests/test_history.py. The new AST-based test statically asserts the import closure of fetch_history.py and research/history.py, rejecting dynamic imports; it parses source as text and does not import or execute protected code. This new test has not yet been run on Python 3.11. The earlier 51/51 offline result and run 44470636642 remain tied to the older SHA and cannot verify this head.
  - PR #64 head is 7532e8e5e449c9db7d4a507bee8119674083461f. Its CodeQL Python and Actions analyses completed successfully, but the review status check was skipped. The immutable runner still needs a manual synthetic-mode workflow run before the new review can be treated as runtime-verified; the full specialist review remains unaccepted until all verdict gates pass.
  - PR #66 head 269fc112d13d6a0ed92195156ff22d55263e927b has successful CodeQL Python and Actions analyses; these are static-analysis results, not execution of its revised unit tests.
- Current CI observations for the holdout stack: PR #34 head 301b90dca0fd1622d3ff69ee3bbf47d2b401d448, PR #68 head e280af8e9224ff3dd5ce282d7e9da3224c6a4136, and PR #76 head 5970d6d7b6bd99b83cb5dfb0eb502013b2f69678 had no check runs returned for those exact commits at the last query. PR #76 retains prior exact-blob local Python 3.13.5 evidence of 19/19 isolated publisher tests; Python 3.11 CI and integration remain unverified.
- No workflow dispatch was available through the connected GitHub tools. No PR was merged. No protected source/data was opened, imported, executed, or changed. No exchange, account, credential, or trading action occurred.
- Project-wide completion remains UNRATED. The current evidence is insufficient to claim 100%: mandatory Q0.8 synthetic/runtime review and new-head offline tests remain pending; holdout integration CI and protected Workstream B acceptance remain blocked; MEME_INTEL is not demonstrated; full owner-approved scope/weights still require approval.


### Q0.8 non-final model completion rejection (2026-11-19)

- A further static audit of the current reviewer source found that ask_model logged the OpenRouter finish_reason but did not reject non-final completions. A truncated response with finish_reason=length could still be accepted if it contained a verdict line. This regressed the earlier fail-closed truncation correction and would undermine the new acceptance gate.
- Added require_complete_finish_reason() to the immutable reviewer:
  - Runner commit: 1def3be27a6870fd356119d4794b4ac887b1623d
  - Runner blob: 8a88bd857fba9a65dec6e06e6a9824e16adfb10a
  - The production ask_model path now rejects every finish_reason except exact "stop" before parsing or checkpointing the response.
  - Synthetic cases accept "stop" and reject "length", "content_filter", "tool_calls", missing, and empty finish reasons.
  - Existing diff bound (192,000 characters), production enforce_diff_limit call, request cap (256,000 bytes), unchanged fetch_history.py context, and all-role verdict gate remain present in the exact fetched blob.
- Updated both workflow copies to pin runner commit 1def3be27a6870fd356119d4794b4ac887b1623d; workflow blob is identical on both branches: 97e11a4d5efaad20948ab56a2218d60c8884213d.
  - PR #60 latest head: 6f9ab508710272f99c34508a565c214f6adbc9ee.
  - PR #64 latest head: 4af6478a29110115d94e46d755035bb451c5d62f.
  - Both remain open/draft/unmerged. PR #64's latest CodeQL, Python analysis, and Actions analysis checks have now completed successfully; its automatic review status was skipped, and no synthetic/runtime test has run. PR #60 has only an automatic skipped review status at its new head.
- **Runtime remains unverified:** no local Python 3.11 runtime was available through the connected GitHub tools and no workflow dispatch action is exposed. The required next checks are PR #64 synthetic mode against the pinned runner, followed by PR #60's six-module offline workflow on exact head 6f9ab508710272f99c34508a565c214f6adbc9ee, then a fresh full review on that same SHA with resume_from_run_id blank. Do not reuse artifacts or test results from previous PR #60 heads.
- No protected file/path was opened or changed; no repository code was executed; no model API, exchange endpoint, account, credential, or trading operation was used. No PR was merged.


### PR #77 provider-scope clarification (2026-11-19)

- Tightened PR #77 wording so the Tokocrypto-specific candle-only rule cannot be misread as revoking separately approved providers such as existing Binance Vision/Kraken adapters. The instruction now says other providers remain governed by their own current ADR/provider allowlists.
- Also clarified that any copy of validator.py or report.py remains protected, not just the root-named files.
- Latest PR #77 head: c90c890ad78e97609f8a56842a3b419b64d89011; CLAUDE.md blob 44b524cd34a1da7f5145c2208cdf4a5f14469022; still one changed file, open/draft/unmerged and GitHub reports mergeable. Static-analysis run 44484810228 completed with CodeQL, Python analysis, and Actions analysis all successful; the automatic review status was skipped. No functional tests or repository runtime were executed for this documentation-only PR.


### Q0 current-head transport boundary source audit (2026-11-19)

- Static inspection of exact current PR #60 head 6f9ab508710272f99c34508a565c214f6adbc9ee confirmed:
  - config.json blob b35b6c236921fcfad1b2be18fc558d48bc3c2dc6 permits only the Tokocrypto Binance-style source at https://www.tokocrypto.site and has read_only mode.
  - fetcher.py blob bab797835ef2fdbff616847d7eb6ba887124fe7e sets APPROVED_HOST=www.tokocrypto.site and APPROVED_PATHS={"/api/v3/klines"}, enforces HTTPS/GET URL validation, exact BTCUSDT candle query fields, no redirects, and a 1 MiB response cap. fetch_server_time() raises DisallowedRequestError before any request; symbol-metadata routes are also refused.
  - HTTP 429 fails closed without retry because this transport does not retain Retry-After headers; network errors and bounded 5xx retry separately.
  - research/history.py blob a6a56d25fe60a255841e27c1b72b7d910eab19d9 imports only standard-library modules, makes zero network requests, writes no dataset, and keeps backtesting disabled while market identity remains unverified.
  - research_config.json blob 58ff32379a7f4fbc0ca5d75ff10e20e82bbaf3ff is read-only and scoped to Tokocrypto BTC/USDT.
- providers.py contains a Tokocrypto documentation URL on .com, but the inspected runtime transport allowlist rejects .com hosts; the documentation URL is not an API request or authorization.
- This was static source inspection only. No repository code was imported or executed, no test was run, and no external network/exchange request was made. Exact-head Python 3.11 offline tests remain pending.


### Q0.8 unambiguous verdict and refusal handling (2026-11-19)

- A final source-level review found two further ways a model response could be misclassified: the verdict regex accepted a verdict anywhere in the response even though the prompt requires the first non-empty line to be the verdict; and refusal metadata was logged but not rejected.
- Added strict helpers to the immutable runner:
  - Runner commit: 41c824d31e679b7b81a3821b7740eeab35539f0f
  - Runner blob: bf4979a52034b47fdaa7cd06f181dfdad2dc0284
  - extract_verdict() accepts exactly one verdict line and requires it to be the first non-empty line. Model-response classification, checkpoint validation, and final acceptance now share this parser.
  - require_no_refusal() rejects non-empty refusal metadata before the response can be checkpointed or counted.
  - Synthetic cases cover first-line verdicts, verdicts buried after body text, contradictory multiple verdicts, missing verdicts, and refusal metadata.
  - A fixture newline-escaping issue in the first draft was caught by static source inspection and corrected in a follow-up commit before pinning.
- Both workflow copies now pin runner commit 41c824d31e679b7b81a3821b7740eeab35539f0f; identical workflow blob b59bd037640a29f3510d0722c34989289dc193fc.
  - PR #60 latest head: 6ce6857ee2cb9638d71c6b92598f2e6af261fa1a.
  - PR #64 latest head: cd8596b3036daa57b0730731b3e2f49fbed37376.
  - Both remain open/draft/unmerged. Static checks for these newest heads are pending; no reviewer synthetic or offline workflow has run against them.
- Runtime verification remains a hard gate. Run the synthetic workflow first, then the six-module Python 3.11 offline suite on the latest PR #60 head, then the full 19-role review against that same exact head with no checkpoint resume. Do not reuse prior-head artifacts.
- No protected source/data was opened, imported, executed, or changed; no LLM request, exchange request, account, credential, or trading action occurred. No PR was merged.


### Clean-main security tooling successor review (2026-11-19)

- Confirmed PR #57 was merged on 2026-11-18; its merge is part of the current main baseline 9bf95e28171447faa910ecd5185b59a349555a52. Earlier tracker passages that described PR #57 as still open are historical snapshots, not current state.
- Reviewed current clean-main successors:
  - PR #71, head ec011a0cf16eeb3a4eaae3df924d96e8a0f99511: protected-path Claude Code Read/Edit deny rules, root instructions, and roadmap. Static CodeQL, Python analysis, and Actions analysis passed. These settings are defense in depth, not an OS sandbox; Claude Code documentation explicitly notes that arbitrary subprocesses can bypass file-tool deny rules and that OS-level sandboxing is needed for stronger enforcement. No protected path was accessed or tested.
  - PR #72, head c9cc452fd9d6ccb44aa4bbbbaa825b69fa6e31b1: repository security-review skill updated to match current owner scope—P1, signal/data, copies of signal, markets/risk, any validator.py/report.py copies, PAPER-only/LIVE-disabled, and Tokocrypto candle-only access. Its CodeQL and Actions analysis passed; Python analysis was still running at the last check. The skill is guidance, not a sandbox or completed audit.
  - PR #74, head 6a8997d4881c85b9ebdf73ec60be54a765362d91: manual-only free security-lint workflow hardens Actionlint archive download, checks a pinned SHA-256, extracts one bounded regular-file member to a fixed path, and pins zizmor. CodeQL, Python analysis, and Actions analysis passed. The actual manual Actionlint/zizmor workflow has not been dispatched or executed.
  - PR #75, head 61a15ee8007d8588294dac7e7086b27c598bcb4c: pinned Cloudflare security-audit skill plus a repository-local guidance-only safety overlay. The upstream license is MIT; the upstream source commit is explicitly recorded as unsigned/unverified. The overlay forbids executing target-controlled code, network calls, workflow dispatch, and full audit mode until a suitable OS-enforced sandbox and agent capability are verified and separately authorized. It was updated to protect any copies of validator.py/report.py. Python and Actions analysis were still running at the last check. No upstream validator or test code was run.
- PR #59 is an older security-review skill branch; PR #72 is its clean-main successor. PR #62 is an older signal-path deny branch; PR #71 is the clean-main protected-path successor. PR #38 is an older Cloudflare skill branch; PR #75 is its clean-main successor. PR #39 remains on an older base and is not evidence of current workflow lint execution. PR #73 is another clean-main tracker draft; PR #65 remains the more current tracker branch with the latest Q0.8, holdout, and security-documentation evidence. Keep these PRs unmerged pending owner review.
- Claude Code permission rules are not sufficient to enforce the protected-path boundary against arbitrary scripts/subprocesses. This project continues to prohibit running tests/imports with protected import closures; no sandbox capability was established here. (Official docs: https://code.claude.com/docs/en/permissions)
- No workflow dispatch, settings change, secret change, merge, protected-path access, exchange call, account action, or trading action occurred.


### Q0 runtime integration blocker — approved candle route is unreachable from the current runner (2026-11-19)

- Static inspection of exact PR #60 head 6ce6857ee2cb9638d71c6b92598f2e6af261fa1a, file run.py blob c59b276207a084a30d339e6f7481f6c7ca6b5abd, confirms the current application path calls fetcher.fetch_server_time() before fetcher.fetch_candles(). In the same candidate, fetch_server_time() deliberately raises DisallowedRequestError without making a network request because the server-time endpoint is not authorized.
- Therefore the current run.py path cannot reach the otherwise approved /api/v3/klines candle request. This is a genuine integration blocker, not a provider quota issue. run.py also imports the protected root modules validator.py and report.py, so executing it or tests with that import closure remains prohibited.
- No workaround was applied. Using local system time, deriving time from a response header, or changing the application boundary would alter the time/freshness architecture and requires a separately reviewed acceptance decision. The approved candle endpoint itself remains the only Tokocrypto network scope; no server-time endpoint or other host was called.
- Exact current offline tests and Q0.8 specialist review remain pending. The safe offline workflow can test the unprotected transport/sanitization/history subset, but cannot establish end-to-end run.py behavior while the protected imports and server-time dependency remain.
- Required owner decision before end-to-end Q0 integration can be accepted: authorize a precise safe review/refactor scope that preserves protected modules, or approve a documented candle-freshness design that does not call an unapproved endpoint. Do not test or modify validator.py/report.py without separate explicit authorization.


### Q0.8 review disposition and import-boundary remediation (2026-11-19)

#### Run 44470636642 — review completed, acceptance BLOCKED

- Workflow URL: https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44470636642
- GitHub job conclusion: `success`, but this was a false-positive process result, not review acceptance. Job logs show it checked out reviewer source commit `c0ed377c82d4f0586dceb20eeaffd3725b568101`, which did not contain the all-role acceptance gate. The checkpoint itself is authoritative for the review outcome:
  - ZIP SHA-256: `e41db1d59a3a59bdab559905af847f5223596b0e67262563b5ec6ecf909325b6`
  - JSON SHA-256: `a4db7155855591afc38afb9345291790fefb1ab66774063667c6373540135c30`
  - Repository/base/head: `ruthlessjoey/btcidr-trading-lab` / `cd451972e3a641ad6fa78e64abf3968655a4b82a` / `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`.
  - 16 specialist reports completed. Architecture = INCONCLUSIVE (finish_reason=length); implementation-engineer, strategy-validation, systematic-debugging = BLOCKED. Commander, independent acceptance, and final verification = BLOCKED.
- Therefore Q0.8 review is **NOT ACCEPTED**. The earlier 51/51 offline result and this review are both tied to the older head `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`.

#### Reviewer workflow correction

- Updated the same immutable reviewer workflow on PR #60 and PR #64:
  - PR #60 commit `4a3f9cebe36280d75b6b4cc4402147a6ff1e8e3e`; PR #64 commit `c9adf486dea64c70a5c5a534d59545bae4f222fb`.
  - Shared workflow blob: `4089b8524099cb0266c6ab06a7174b9229888465`.
  - Pin now targets corrected self-contained reviewer commit `1def3be27a6870fd356119d4794b4ac887b1623d`, blob `8a88bd857fba9a65dec6e06e6a9824e16adfb10a`, which rejects every model finish reason except exact `stop` and fails the job unless all 16 specialist roles plus Commander, independent acceptance, and verification return PASS or PASS WITH FINDINGS.
  - Checkpoint restore and persistence now use a dedicated directory under `runner.temp`, not the repository workspace. Runner validates exact repository/base/head/model identity, strict schema, progress ordering, report size, secret-screen patterns, and explicit verdicts before reuse.
- Workflow edits have not yet been run in GitHub Actions. PR #60 latest head at this tracker update: `17025e55577a6654370080c6db610825060f2062`; PR #64 latest head: `60ac64069e06e15af30ae974f76df94539e9021d`.

#### Current-head offline import-closure hardening

- On PR #60, disabled the dormant Coinbase/Bitstamp cross-check acquisition path:
  - `research/crosscheck.py` commit `8dc2ab2e838584c4895a763a9d9894d989ce6fc7`, final blob `948004fda318c4958f4d17eb69783d11feaa0506`.
  - Removed Coinbase/Bitstamp fetch functions and URLs, the mutable `AUTHORIZED_CROSSCHECK_PROVIDERS` gate, and provider transport imports. `run_crosscheck()` now unconditionally raises a fixed safe authorization error before filesystem or network activity. Pure comparison/report helpers remain.
  - `tests/test_sanitization.py` commit `4deafcb031dc958e2a108c378c044d487edd2e64`, blob `2559b11288011bf31996ef436d4516de59af4a8b`, replaces the prior monkeypatch-enabled cross-check test with a regression proving that injecting the legacy authorization attribute cannot enable network or artifact writes.
- Added a static AST import-closure assertion to `tests/test_history.py`:
  - Commit `2902581071025bb0cf4cedb11d1cc16a6e01d588`; blob `615ee8041fab1b7d63537d3827ab2fcc4e9d6684`.
  - The test checks the exact local import edges for all six modules selected by `q08-offline-tests.yml` and `research-data.yml`, plus their unprotected transitive dependencies and the `fetch_history.py` entrypoint. It parses source only, rejects dynamic imports, and rejects edges into `validator`, `report`, `markets`, `research.engine`, and `research.pipeline`.
  - Static source inspection of the exact current files shows the intended closure: `test_fetcher -> fetcher`; `test_live_check -> providers -> fetcher`; `test_history` and `test_pipeline` use only standard-library/static source inspection; `test_probe -> probe`; `test_sanitization -> fetcher/providers/research.crosscheck -> fetcher`; `fetch_history.py -> research.history` (standard library only).
- These changes have **not yet been executed under Python 3.11**. No test pass is claimed for PR #60's current head. Workflow dispatch is not available through the connected GitHub tools; a fresh offline run and fresh specialist review must be started manually on the latest PR #60 SHA, with no checkpoint reused from the older head.

#### Remaining Q0.8 acceptance blockers

- Obtain separate owner authorization for any review that would access protected modules or Workstream B artifacts; none were opened, imported, or executed.
- Run the exact six-module offline workflow on current PR #60 head.
- Run PR #64 synthetic mode against the pinned reviewer and inspect its runtime result.
- Run a fresh 19-stage review on the exact same current PR #60 head. Do not reuse run `44470636642` because its head differs and its workflow used the older reviewer source.
- Overall project completion remains UNRATED; no project-wide 100% claim is supported.


### Latest Q0.8 runner/workflow reconciliation (2026-11-19)

- Re-fetched both Q0.8 PRs after concurrent updates; the current state supersedes the earlier 1def3 pin note:
  - PR #60 head: d89f4c007f034d0639c55db1c3e6da1d9a18e5d4, 26 changed paths, open/draft/unmerged.
  - PR #64 head: 51a89922c1f5e0f2aad62aa24af4ed527b432774, two changed paths, open/draft/unmerged.
  - Both workflow files are now byte-identical at blob ef58dc8dcf99e90cc336a09c7c9ccd6615e150d1 and pin reviewer source commit c9adf486dea64c70a5c5a534d59545bae4f222fb.
  - That pinned immutable source has blob bf4979a52034b47fdaa7cd06f181dfdad2dc0284 and includes the 192,000-character production diff bound, 256,000-byte request bound, unchanged fetch_history.py review context, strict finish_reason == "stop", refusal rejection, exactly one first-nonempty-line verdict parser, checkpoint validation, and a nonzero acceptance gate for missing/BLOCKED/INCONCLUSIVE roles.
  - Both workflows store/restore checkpoint artifacts under runner.temp, not the repository workspace. Checkpoint restoration and upload remain restricted to review mode; synthetic mode runs syntax compilation and policy smoke tests without model requests.
- PR #60's latest AST import-closure test blob is 615ee8041fab1b7d63537d3827ab2fcc4e9d6684. The branch also removed the dormant Coinbase/Bitstamp acquisition path from research.crosscheck and added a regression that an injected legacy authorization attribute cannot enable network or artifact writes. The offline workflow remains a sparse six-module Python 3.11 suite; it does not import run.py or the protected validator/report modules. The exact current-head suite has not run.
- PR #64's CodeQL, Python analysis, and Actions analysis checks completed successfully on head 51a89922c1f5e0f2aad62aa24af4ed527b432774. These are static-analysis checks only. PR #60 currently has only the automatic review status skipped; its manual offline tests have not run.
- Exact manual sequence, with no checkpoint reuse:
  1. Run the Q0.8 specialist workflow on branch security/q08-reviewer-pin-correction-2026-11-18 with review_head_sha=d89f4c007f034d0639c55db1c3e6da1d9a18e5d4, resume_from_run_id blank, mode=synthetic.
  2. Run Q0.8 Offline Tests on branch security/q0-provider-sanitization-2026-11-18.
  3. Only after both pass, run the specialist workflow on branch security/q0-provider-sanitization-2026-11-18 with the same exact SHA, resume_from_run_id blank, mode=review.
  4. If a fresh review stops on quota after uploading a checkpoint artifact, resume only from that new run ID and exact same SHA.
- The old review run 44470636642 is not an acceptable checkpoint source for these new heads. No manual workflow dispatch or runtime test has occurred.


### Original handoff scope and still-prohibited Workstream B actions (2026-11-19)

- Recovered the current main-branch PROJECT_HANDOFF.MD (blob 5ff795aa384302bece43c7f40e3edcec30e8e6a3; 16,458 bytes). It describes the long-term vision as multi-market research/signals across crypto (including meme/new listings/DEX pairs), stocks/ETFs, forex, indices, commodities, BUY/SELL candidates, risk management, and up to 10 simultaneous positions. It explicitly says the immediate next task is the Milestone 3 safety review, not building the multi-market scanner yet. It also describes research-only as the older operating mode; current owner instructions supersede that with PAPER-only and LIVE-disabled.
- The handoff explicitly prohibits running the research backtest workflow, manual dispatch of that workflow, evaluating the holdout test window, real registry migration, and modification of the frozen research dataset. Those actions remain unperformed and are not authorized by the general 100% completion mandate; no research-backtest workflow was dispatched.
- The Milestone 3 registry/holdout safety artifacts remain within protected Workstream B scope under the current owner boundary. No protected source, data, validator/report module, P1, signal/data, or copy of signal was accessed. Therefore the earlier handoff's requested line-by-line M3 registry audit cannot be completed without separate exact-scope owner authorization; no tests whose import closure reaches protected code were run.
- The proposed 100-point inventory remains a planning decomposition only. The original handoff is not a complete acceptance specification, and the owner has not approved the weights or a current requirement-by-requirement acceptance matrix. Project-wide completion therefore remains UNRATED, not 100%.


### Final shared Claude safety instruction reconciliation (2026-11-19)

- PR #71 and PR #77 now carry identical root CLAUDE.md content at blob 53e9a86cb14cc0af28a957d0180b30ad6be068c5, preventing the two open documentation PRs from reintroducing conflicting protected-path policy if reviewed/merged in either order.
- The shared text explicitly protects P1, every signal path (including nested copies), markets/risk, any validator.py/report.py copies, and Workstream B; it states that Read/Edit denials are defense-in-depth and not an OS sandbox; it prohibits protected import/execution closures; it is PAPER-only/LIVE-disabled; and it limits Tokocrypto to unauthenticated HTTPS GET candles at www.tokocrypto.site/api/v3/klines, explicitly excluding server-time, .com, and private endpoints while leaving other providers governed by their own current ADR/allowlists.
- PR #71 latest head: b33e9c6bb6755473ec6f35e6bc425fdc820805f1. PR #77 latest head: 2b1dd6ce139f6a626128afaaff9bbc8a0ad24445. Both remain open/draft/unmerged; static analysis was still in progress/queued after the matching content update.
- No protected paths were accessed or tested. No repository runtime, workflow dispatch, exchange request, or trading operation occurred.

### Security tooling and protected-path boundary follow-through (2026-11-19)

#### PR #69 — Ruff artifact handling hardening

- PR #69 current head: `1c277eb0112758b652fc4a3b0578d1b6d53a0476`; remains open/draft/unmerged.
- Updated `.github/workflows/python-static-quality.yml`:
  - Workflow commit `6f9b9563b1867e36a574a834b93de0e16dba1d07`, then path-validation hardening commit `1c277eb0112758b652fc4a3b0578d1b6d53a0476`; final workflow blob `b213321b4a99f1da34f8cef18e243d57a81bb8c8`.
  - 16 MiB maximum archive size, checked both by curl and a post-download `stat` check before SHA-256 verification.
  - Reads exactly one regular-file member whose basename is `ruff`; rejects absolute, backslash, empty, dot, or parent path components; rejects links, duplicate matches, zero-size, truncated, and over-64-MiB binaries.
  - Writes only to a fixed temporary destination; no archive-controlled member path is extracted.
- Official GitHub release metadata for Ruff 0.17.5 confirms the archive is 10,215,036 bytes with SHA-256 `7d261fc981a784668e19e9fa6ad437bfd95b67f2dc263fc1eab87d54d72fcc90`; release tag commit `c91de8a012cb87efe279b762020a0d28dd75ddb5` is signed/verified.
- Documentation updated in commit `510b48c45b36595b7a1fde935cb8cfef64bd52e1` and line-break correction `51e43b3d4d8c84776ecee27fd173c121aadb2e58`; final docs blob `28831ac1d9e0b530ff949e5818c8e9c95fde408d`.
- Ruff was not downloaded or executed; workflow remains manual-only and runtime result UNVERIFIED.

#### PR #71 — nested protected-copy denial

- PR #71 current head: `b33e9c6bb6755473ec6f35e6bc425fdc820805f1`; remains open/draft/unmerged.
- `.claude/settings.json` blob `f4456d8db81e4d8b7c61e299b2012d2142e8d223` now contains 16 deny rules, including root protections and recursive patterns `Read/Edit(**/signal/**)`, `Read/Edit(**/validator.py)`, and `Read/Edit(**/report.py)`.
- `CLAUDE.md` includes the explicit nested-copy restrictions and clarifies that permission denials are defense-in-depth, not an OS sandbox; arbitrary subprocesses and indirect file access are not constrained.
- Static settings JSON parse succeeded. Current official Claude Code permission documentation confirms Read/Edit paths use gitignore-style glob matching, `**` spans directories, deny patterns match nested directories, and Read denials also cover Grep/Glob and recognized shell file reads. It explicitly says these rules do not cover arbitrary subprocesses; OS sandboxing is required for that level of enforcement. Source: https://code.claude.com/docs/en/permissions
- No Claude Code runtime session was available to verify loaded settings with `/status` or `claude doctor`; enforcement remains UNVERIFIED at runtime.

#### PR #75 — Cloudflare security-audit skill provenance review

- PR #75 current head: `61a15ee8007d8588294dac7e7086b27c598bcb4c`; remains open/draft/unmerged.
- Provenance pins upstream `cloudflare/security-audit-skill` commit `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`; GitHub reports the commit as unsigned (`verified: false`). The pin is reproducibility evidence, not signature verification.
- Compared 19 copied upstream files against raw GitHub content at that exact commit: all 19 matched byte-for-byte. The local `SKILL.md` is exactly the upstream file plus the documented local safety-overlay pointer; the included MIT LICENSE matches upstream.
- Static inspection of the two Node validator scripts found only built-in `fs`, `path`, and `util` modules; no `child_process`, network client, `eval`, or dynamic code execution use was found.
- Repository-local `PROJECT-SAFETY.md` correctly limits use to read-only guidance. Full audit mode and validator/test execution remain prohibited until a suitable OS-enforced sandbox and separate authorization are established. No validator or test script was run. Tool presence is not audit evidence.

- PR #70 is an earlier overlapping protected-path settings/documentation change; PR #71 carries the more complete current scope and nested-copy patterns. Neither PR has been merged.
- Overall project completion remains UNRATED. These are implementation/static-review results, not project-wide acceptance or 100% completion.

### Q0.8 final pin, checkpoint-source validation, PR #66, and PR #74 reconciliation (2026-11-19)

- Latest re-fetch after concurrent changes:
  - PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, base `cd451972e3a641ad6fa78e64abf3968655a4b82a`, open/draft/unmerged, exactly 26 changed paths.
  - PR #64 head `795fa89e7041363715db42963709d7c856b2c78e`, base `9bf95e28171447faa910ecd5185b59a349555a52`, open/draft/unmerged.
  - PR #66 head `269fc112d13d6a0ed92195156ff22d55263e927b`, open/draft/unmerged.
  - PR #74 head `6a8997d4881c85b9ebdf73ec60be54a765362d91`, open/draft/unmerged.
- PR #60 and #64 Q0.8 workflow files are byte-identical (blob `178b041e1a1e4e37c552b301f8eea2dc0e700d0a`) and pin immutable reviewer commit `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9`, runner blob `92fc820128bba8cf8fa9e7d3de51838fe2672a1c`.
- The pinned runner rejects every model finish reason except exact `stop`, rejects refusal metadata, requires a single explicit verdict on the first non-empty line, enforces diff/request/response bounds, and fails the job unless all 16 specialist roles plus Commander, independent acceptance, and verification return PASS or PASS WITH FINDINGS.
- Checkpoint resume is now bound to its source run before checkpoint JSON is trusted. `Q08_RESUME_FROM_RUN_ID` is passed to the runner, which uses read-only GitHub Actions metadata and requires: the exact repository; workflow ID `421573712`; workflow path `.github/workflows/q08-specialist-review.yml`; `workflow_dispatch`; completed run status; exact review head SHA; and the approved PR #60 branch. Failure conclusion is allowed because a quota-blocked run may still hold a valid partial checkpoint. The source run must not be the current run.
- Checkpointed specialist reports are explicitly treated as untrusted evidence, never instructions; Commander, acceptance, and verification are told to independently validate claims.
- Checkpoint artifact restore now writes directly into the isolated `runner.temp` directory, outside the repository workspace. The runner rejects symlinked/non-regular checkpoint files, checks the 2 MB size limit before reading, reads at most limit+1 bytes, and saves through a random `mkstemp` file with flush/fsync/atomic replace rather than a predictable `.tmp` path.
- Local isolated checks exercised the checkpoint-source metadata validator (valid run accepted; mismatched ID, workflow, path, event, status, repository, branch, and head rejected) and checkpoint I/O logic (symlink and oversized files rejected; predictable temporary symlink not followed). These checks do not replace the full reviewer synthetic workflow; that workflow has not yet been dispatched.
- PR #66 corrected isolated test blob remains `cf0fdc200865d4f9692aa8b9f1666b2547db77ff`; no test has yet been run against its current head.
- PR #74 bounded Actionlint installer remains at commit `6a8997d4881c85b9ebdf73ec60be54a765362d91`, blob `4886f77be36e969677e063041ccc23e3d11292b6`; exact 16 MiB archive/32 MiB executable ceilings and fixed-destination extraction were statically and locally synthetic-tested. Full workflow execution remains pending.
- These changes remain draft pull requests. No PR was merged, no workflow dispatched, no protected file inspected or executed, and no live exchange or account operation performed.
- Required manual Q0.8 verification must use current PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`: first run PR #64 synthetic mode; then PR #60's six-module offline tests; then PR #60 specialist review with blank resume ID. If that fresh review later stops on quota after uploading its checkpoint, a subsequent review may use that new run ID only if it is for the same exact PR #60 head and branch; the runner now verifies source-run metadata before reuse. Never reuse run `44470636642` or any artifact tied to an older PR #60 head.

#### Additional fail-closed workflow regression tests (PR #60 current head)

- Added two static tests to `tests/test_pipeline.py` (blob `d9c5543f3af5030e5cbed2df182d4821520531e0`; six test methods total):
  - Assert `market-data-check.yml` remains disabled without checkout or execution of `live_check.py`, because `live_check.py` imports protected `validator.py` and `report.py`.
  - Assert `research-data.yml` runs only the approved offline `fetch_history.py` Step 1 gate and the six-module offline tests; it must not execute `run.py` or `live_check.py`.
- Static inspection reconfirmed `run.py` imports protected `validator.py` and `report.py`, and currently calls the intentionally refused Tokocrypto server-time helper before candle retrieval. No change was made to this path because the protected validation/report modules cannot be inspected or executed under current authorization, and substituting local time without validating those semantics would be unsafe.
- `fetcher.py` allows only `/api/v3/klines`; `fetch_server_time()` refuses before transport. `market-data-check.yml` performs no checkout or network request and exits with an explicit protected-boundary explanation. `research-data.yml` sparse-checks the approved source/test files and runs only `fetch_history.py` after offline tests.
- No tests were run against the new PR #60 head. The new static tests are included in the six-module Q0 offline workflow and require a fresh Python 3.11 Actions result.
### PR #76 holdout publisher symlink-file regression coverage (2026-11-19)

- Added three isolated tests to `tests/test_holdout_publish.py` for symlinked local completion records, symlinked branch completion records, and symlinked backtest report files. Each asserts publication refuses cleanup and the durable pending reservation remains.
- PR #76 head/commit: `bb31ede4886e24231f9428fbbda0291984d19ab8`; test blob `7d63089c11ca5c7331f76f55e2e49ec91cdf052b`. Publisher source remains blob `b2c27931b5b4a86b84cd9dc0892d2c8032a6c0b5`. Exactly two paths remain changed in PR #76.
- Test suite now contains 22 cases. The prior 19/19 local result belongs to the earlier 19-test version at head `5970d6d7b6bd99b83cb5dfb0eb502013b2f69678`; it does not verify the three new tests. No test has yet been run on the current 22-test head; Python 3.11 CI is still pending.
- Import closure remains limited to `research.holdout_publish.py` and Python standard library. No protected module is imported or executed.
### PR #69 Ruff installer local syntax and synthetic safety checks (2026-11-19)

- The exact Ruff installer block authored in PR #69 was copied into an isolated local shell fixture and passed `bash -n`; its embedded Python extractor passed `compile()`.
- Synthetic tar tests accepted a bounded regular `ruff` member and rejected parent traversal, symlink, duplicate basename, and over-limit binary entries. The test exercised the same fixed-destination extraction algorithm; it did not download or execute the Ruff binary.
- PR #69 Actions workflow itself has not run; full CI and Ruff lint results remain UNVERIFIED.
### Q0.8 checkpoint resume retry semantics (2026-11-19)

- Found and fixed a resume correctness gap: prior checkpoint loading accepted BLOCKED/INCONCLUSIVE reports as completed stages, so a resumed run would skip them and could never recover from a truncated model response or a transient role failure.
- Runner commit `22f06d9940440cceefde93e0b4e8f7f08d262f84` (blob `e09dba3cc5b2dec38be2e7648996ddad4955064c`) now reuses only `PASS` or `PASS WITH FINDINGS` reports. A BLOCKED/INCONCLUSIVE specialist is omitted from restored state and retried; Commander/acceptance/verification are invalidated whenever an upstream specialist must be retried. A blocked synthesis stage is retried while accepted upstream stages are retained.
- Added synthetic runner cases for one blocked specialist with blocked synthesis, a blocked independent-acceptance stage, and an inconclusive verification stage. Separate local logic checks confirmed accepted stages are retained and blocked/inconclusive stages plus dependent downstream synthesis are retried. Full runner synthetic mode has not yet been run.
- PR #60 and #64 workflow files now both pin runner commit `22f06d9940440cceefde93e0b4e8f7f08d262f84`; workflow blob `96b80575983292c268253649b6343f01e4f627d1`. Latest PR heads: #60 `aedeebd506200c3d70fb626501fa3c49c3c18265`; #64 `a39faf771aaaf890e87bc16a3a833ac5b46ec66e`.
- Manual next step remains: run PR #64 synthetic mode, then Q0 offline tests on PR #60 head `aedeebd506200c3d70fb626501fa3c49c3c18265`, then fresh 19-stage review on that exact head with blank resume ID. If it quota-blocks, use only that new run ID for resume.
### PR #72 repository-specific security-review skill (2026-11-19)

- Updated `.claude/skills/security-review/SKILL.md` on PR #72: commit `42e7fa1bdf9d5a808d2ac290ed45881f2629bd28`, blob `61b44c7dc967cf1efa8422559d02b326da296a1e`. PR #72 remains open/draft/unmerged and changes one file only.
- The 3.8 KB skill is repository-specific guidance with no scripts, package dependencies, or external service calls. It requires exact path/baseline scoping, protected-path exclusions, import/checkout-closure review, untrusted-input handling, evidence separation, supply-chain review, and no unapproved workflow dispatch/merge/settings/branch actions.
- Trading boundaries explicitly cover spot-only/long-only, no shorts/leverage/margin/derivatives, PAPER-only with LIVE unavailable, no real-money/account/order/funding/payment/withdrawal activity, emergency-stop enforcement, and Tokocrypto candle-only access.
- The skill also prohibits manufactured project completion percentages and keeps overall completion UNRATED until scope, weights, and evidence criteria are approved. No Claude Code runtime installation/load test occurred; PR remains unmerged.

### Latest manual-CI inventory (2026-11-19)

- Read-only GitHub Actions lookup returned no PR-triggered workflow runs for the latest heads of PRs #60, #64, #69, #71, #72, #74, #75, or #76. These workflows are manual-only or have no matching PR event; do not infer CI success from their definitions.
- Current review/quality evidence therefore remains limited to the exact historical runs and local isolated checks recorded above. Fresh Python 3.11 Q0 tests, reviewer synthetic mode, full Q0.8 review, Ruff, Actionlint/zizmor, and the updated 22-case holdout suite still need manual or authorized runtime execution.
### Open-PR overlap and supersession map (2026-11-19)

These relationships are based on the current changed-file lists. They do not authorize merging or closing any PR; no PR was closed or merged.

- PR #69 supersedes the older PR #61 variant for the same two files (`python-static-quality.yml` and `stage-3-python-quality.md`); #69 contains the bounded Ruff installer hardening.
- PR #71 supersedes the overlapping protected-path variants #62 and #70: it changes the same `.claude/settings.json` and `CLAUDE.md` files and additionally includes the staged development-stack roadmap.
- PR #77 changes only `CLAUDE.md`; its current blob `53e9a86cb14cc0af28a957d0180b30ad6be068c5` is byte-identical to PR #71's `CLAUDE.md`. PR #71 additionally contains permission settings and roadmap, so #77 is a duplicate documentation variant.
- PR #74 supersedes the older PR #39 variant for the same `free-security-lint.yml` workflow file; #74 contains bounded Actionlint download and fixed-destination extraction.
- PR #75 supersedes the older PR #38 Cloudflare audit-skill copy for the same 23 paths; #75 has the newer clean-main branch and explicit upstream pin/local overlay provenance. The upstream commit is unsigned, so its provenance is reproducible but not cryptographically verified.
- PR #72 supersedes the older PR #59 security-review skill variant for the same single `SKILL.md`; #72 now includes the current project trading and protected-path rules.
- PR #65 is the current detailed tracker variant and supersedes the older one-file tracker variants #58 and #73 by changed-path overlap and newer evidence. PR #73's latest stored Q0.8 section still refers to the older `0dd176...` review head; use PR #65's updated head/evidence instead.
- PR #76 is a successor stacked on PR #34's durable publisher implementation; it changes only `research/holdout_publish.py` and `tests/test_holdout_publish.py`. PR #68 is a separate stacked test-suite alignment PR whose tests remain blocked by protected import dependencies.
- All listed PRs remain open/draft. Treat superseded branches as historical review candidates, not parallel changes to merge together.
#### Final checkpoint-stage retry test refinement (2026-11-19)

- Refined the runner's synthetic cases so they separately verify: blocked specialist invalidates all downstream synthesis; blocked Commander invalidates Commander/acceptance/verification while retaining PASS specialists; blocked acceptance retains accepted specialists and Commander but retries acceptance/verification; inconclusive verification retains accepted upstream stages and retries only verification.
- Final reviewer commit is `75685c7aa75633bd090a7a63ab14b687432b7d31`, runner blob `0aef46357709ad81d256bfd5712c73da24cecbce`. PR #60 workflow commit `84b9d6ba0af8d9ed18d2658e2a724d889df00d9d`; PR #64 workflow commit `1fc7c3047201a0276d7ea5c7182b1d413a7303ff`; shared workflow blob `5252a57ef24285c57a6fed69b1c64263389b39cc`.
- Separate local checks of the stage-filter logic passed all four dependency scenarios. Full Python 3.11 runner compilation and synthetic workflow execution remain pending.
#### Final checkpoint path confinement (2026-11-19)

- Latest reviewer source commit `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9` (blob `92fc820128bba8cf8fa9e7d3de51838fe2672a1c`) requires `Q08_CHECKPOINT_PATH` to be exactly `RUNNER_TEMP/q08-review-checkpoint.json`; it rejects a symlinked temp root/parent, wrong filename, nested directory, or path outside the job temp directory.
- Synthetic local path checks accepted the canonical direct-child path and rejected wrong filename, nested/outside paths, and a symlink parent. Full runner synthetic mode remains pending.
- PR #60 workflow head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; PR #64 workflow head `795fa89e7041363715db42963709d7c856b2c78e`; both pin the same immutable runner and share workflow blob `178b041e1a1e4e37c552b301f8eea2dc0e700d0a`.
- Fresh offline tests and specialist review must use PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; all earlier run/checkpoint SHAs are stale.

### Q0.8 checkpoint provenance mismatch on manual retry (2026-11-19)

- PR #60 remains open/draft at exact review target `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, branch `security/q0-provider-sanitization-2026-11-18`. PR #64 remains open/draft at `795fa89e7041363715db42963709d7c856b2c78e`, branch `security/q08-reviewer-pin-correction-2026-11-18`.
- Actions runs [44496231009](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44496231009) and [44510092322](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44510092322) were both dispatched from the PR #64 branch at workflow SHA `795fa89e7041363715db42963709d7c856b2c78e`, not from the approved PR #60 branch. Their checkpoint payload targets PR #60 SHA `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, but the source Actions-run metadata does not identify that target branch/SHA.
- The downloaded checkpoint payload is structurally readable and identifies repository `ruthlessjoey/btcidr-trading-lab`, base `cd451972e3a641ad6fa78e64abf3968655a4b82a`, and target head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`. It contains six specialist reports only (two `VERDICT: BLOCKED`, four `VERDICT: PASS WITH FINDINGS`); `commander`, `acceptance`, and `verification` are null. It is not a completed 19-role review.
- Run 44510092322 successfully restored run 44496231009's artifact, passed Python 3.11 setup, trusted-runner compilation, and synthetic policy smoke test, then stopped before additional specialist calls. Its log reports: `Checkpoint resume is allowed only from the approved PR #60 branch`. The upload step then saved the unchanged checkpoint as artifact `q08-review-checkpoint-44510092322` (artifact ID `14521501425`).
- The immutable runner at commit `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9` (blob `92fc820128bba8cf8fa9e7d3de51838fe2672a1c`) deliberately requires the current branch to equal `security/q0-provider-sanitization-2026-11-18`; it also requires source-run metadata to match the repository, workflow, event, exact head SHA, and current branch. Therefore runs 44496231009 and 44510092322 are not eligible checkpoint sources for the approved PR #60 review, even though the checkpoint payload itself contains the intended target SHA. Do not resume either run.
- Correct next dispatch: select branch `security/q0-provider-sanitization-2026-11-18`; set `review_head_sha=d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; set `mode=review`; leave `resume_from_run_id` blank. If that correctly scoped run later stops after uploading a checkpoint, resume only from that run's ID, preserving the same branch and SHA.
- The separate offline test run 44495395970 failed because its sparse checkout omitted the two workflow fixture files read by `tests/test_pipeline.py`: `.github/workflows/market-data-check.yml` and `.github/workflows/research-data.yml`. The reported failure was `FileNotFoundError`, not a failed assertion. This sparse-checkout allowlist correction remains pending; do not change PR #60 while its exact-head review attempt is being restarted.
- No repository application code changed, no protected path was accessed, no PR was merged, and no live or real-money operation was performed in these review attempts. Review acceptance remains **UNVERIFIED / BLOCKED**.


### PR #76 bounded holdout publisher static review (2026-11-19)

- PR #76 head remains `bb31ede4886e24231f9428fbbda0291984d19ab8` on `security/holdout-publisher-bounded-scan-2026-11-19`; it is a draft stacked on PR #34's durable publisher.
- The change is limited to `research/holdout_publish.py` and `tests/test_holdout_publish.py`. It replaces full materialization of all `*.json` matches with `itertools.islice(..., MAX_COMPLETED_FILES + 1)`, rejects the 1,001st match before sorting or validation, then sorts the bounded list.
- Four added tests cover symlinked completed output, symlinked branch completion, symlinked report, and proving enumeration stops after exactly 1,001 yielded matches. The test module imports only the publisher; the publisher imports only standard-library modules; `research/__init__.py` is empty.
- Its manual workflow `.github/workflows/manual-offline-unit-tests.yml` has read-only contents permission, `persist-credentials: false`, and sparse-checks out only `research/__init__.py`, `research/holdout_publish.py`, and `tests/test_holdout_publish.py`; it runs the isolated test module under Python 3.11. This import closure does not reach a protected path.
- Static review found the bound is applied before sorting/processing, and the regression test asserts the iterator is consumed only 1,001 times. No new test execution was performed in this review; PR #76 remains **IMPLEMENTED CANDIDATE / UNTESTED**, not accepted or merged. Manual dispatch of its isolated workflow remains required for exact-head test evidence.


### PR #71 protected-path and Tokocrypto instruction alignment (2026-11-19)

- PR #71 head `b33e9c6bb6755473ec6f35e6bc425fdc820805f1` contains the expanded shared instruction file (blob `53e9a86cb14cc0af28a957d0180b30ad6be068c5`) and permission file (blob `f4456d8db81e4d8b7c61e299b2012d2142e8d223`). PR #77's `CLAUDE.md` is byte-identical to PR #71's; PR #71 is the more complete candidate because it also includes the permission configuration and roadmap.
- The PR #71 instructions explicitly restrict Tokocrypto to unauthenticated HTTPS GET candles at `https://www.tokocrypto.site/api/v3/klines`, prohibit server-time endpoints, `.com`, and private/authenticated endpoints, and preserve PAPER-only / LIVE-disabled operation.
- The PR #71 instructions also prohibit access to `P1/`, every `signal/` path including nested copies, `markets/risk/`, any `validator.py` or `report.py`, and protected Workstream B content. They explicitly warn that Claude Read/Edit denies are not an OS sandbox and that scripts/tests with protected import closures must not run without an enforced boundary.
- Its permission deny list covers root `P1/`, `signal/`, `markets/risk/`, root `validator.py`/`report.py`, and nested signal/validator/report copies. The project-level deny settings are defense-in-depth only.
- Static review confirms this candidate aligns with the current user-provided Tokocrypto boundary and protected-path policy. It has not been merged. The `main` branch's current `CLAUDE.md` blob `fff092011f7fb67a2c413909991b32ab9dda560a` still describes server-time as approved; this remains a documentation mismatch on `main` until the corrected candidate is separately accepted. Do not merge PR #71 or #77 without the owner's separate review/merge authorization.


### Q0.8 specialist-review quota checkpoint (2026-11-20)

- Manual review run [#44542281860](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44542281860) ran on the approved PR #60 branch `security/q0-provider-sanitization-2026-11-18`, exact head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, and approved M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`. PR #60 remained open/draft at that exact head when checked.
- Python 3.11 setup, immutable-runner compilation, synthetic policy smoke test, pull-request head validation, immutable comparison/snapshot, approved model configuration, and bounded diff construction all completed. The specialist stage stopped at `quant-research` because OpenRouter returned HTTP 429. The runner waited 15, 30, 60, and 120 seconds; the next advertised retry delay was 240 seconds, above its 120-second per-retry wait cap. This is a provider quota interruption, not a repository test assertion failure.
- The run uploaded checkpoint artifact `q08-review-checkpoint-44542281860`, artifact ID `14539975752`, ZIP SHA-256 `401c4168701506a46ca60d1280e8274ab5188d0e1c8f45f7a6549c1e621c5fdd`. The checkpoint payload was downloaded and inspected: repository, base SHA, target head SHA, schema version, and approved model match the run; four reports are retained (`architecture-architect`, `implementation-engineer`, `provider-integration`, `market-intelligence`), each `PASS WITH FINDINGS`. No `quant-research` report was committed before the 429. Commander, independent acceptance, and verification are null.
- The immutable runner's restore path reuses only accepted `PASS` / `PASS WITH FINDINGS` reports and retries missing or non-accepting stages. It independently validates source-run ID, repository, workflow ID/path, dispatch event, completed status, approved branch, and exact review SHA. Therefore this run is eligible as a checkpoint source; previous wrong-branch runs `44496231009` and `44510092322` remain ineligible and must never be resumed.
- Exact continuation dispatch: branch `security/q0-provider-sanitization-2026-11-18`; mode `review`; `review_head_sha=d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; `resume_from_run_id=44542281860`. This resumes the four accepted specialist reports, retries `quant-research`, then runs the remaining specialists and three final review stages. Do not change PR #60 while this exact-head review is in progress.
- No source code was changed in this review cycle, no tests were executed by this inspection, no protected path was accessed, and no PR was merged. Full 19-role completion and acceptance remain UNVERIFIED.


### PR #76 holdout publisher symlink-test fixture correction (2026-11-20)

- Static execution review of the current PR #76 test fixture found three symlink tests attempting to unlink paths that `setUp()` had not created. Added `self.install_pair()` before the symlink substitutions in the completed-output, branch-completion, and report-symlink cases. The existing path-component guard also rejects the report symlink before the leaf-file reader, so its assertion now expects the actual `symlinked path component` refusal.
- Test-only commits: `af7aeda3476c6681e4d28e2890d2ea68d6b5d73f` aligns the report-symlink assertion; `fe3182730f8a4a19327d5fd6bb25693f22416ae2` initializes the three fixtures. Current PR #76 head is `fe3182730f8a4a19327d5fd6bb25693f22416ae2`; current test blob `4a1a296d8dd45c7ec7778665c6fe11cc499ea7ef`; publisher implementation remains unchanged at blob `b2c27931b5b4a86b84cd9dc0892d2c8032a6c0b5`. PR remains open/draft and still changes two files.
- An isolated local reproduction of the 22-case suite passed 22/22 on Python 3.13.5, and `py_compile` passed. The local files were reconstructed from the inspected source and fixture logic rather than materialized byte-for-byte from GitHub, so this is preliminary local evidence, not an exact-head repository test result. Python 3.11 Actions execution remains required; do not mark PR #76 accepted or tested by CI until that run passes.
- No protected path was accessed or executed; no publisher runtime network or trading behavior was invoked; no PR was merged.


### Q0.8 specialist-review continuation checkpoint (2026-11-20)

- Continuation run [#44597856180](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44597856180) completed with **failure** on the same approved PR #60 branch and exact head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, based on M6 `cd451972e3a641ad6fa78e64abf3968655a4b82a`. It is an external OpenRouter HTTP 429 quota interruption, not a repository test assertion failure.
- The runner validated the exact PR head and checkpoint source, restored run #44542281860's artifact with the expected SHA-256, set up Python 3.11.18, compiled the immutable runner, and passed the synthetic policy smoke test. It reused the four previously accepted reports.
- The continuation checkpoint now contains eight specialist report entries: six `PASS WITH FINDINGS` (`architecture-architect`, `implementation-engineer`, `market-intelligence`, `provider-integration`, `portfolio-accounting`, `risk-invariants`) and two `BLOCKED` (`quant-research`, `strategy-validation`). The `execution-boundary` request stopped after bounded 15/30/60/120-second retries when the next provider reset was 240 seconds, above the runner's 120-second per-retry cap. Commander, independent acceptance, and verification remain null; the complete 19-role review is not passed.
- The run uploaded `q08-review-checkpoint-44597856180`, artifact ID `14567402585`, ZIP SHA-256 `9bb91ddc836412660dcf503487d657dfed3ca171cbd18b736950a81d3de3edbe`; the checkpoint payload SHA-256 is `e6b8c7db6d0bd9d9f85060914112dbd172fb60414a59823185e2e8a029407789`. The payload identity matches the approved repository, M6 base, exact PR #60 head, schema version 1, and approved model.
- Next manual continuation, after provider quota reset: use the same branch, mode `review`, `review_head_sha=d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, and `resume_from_run_id=44597856180`. The runner will reuse accepted reports and retry blocked/missing stages. Do not use prior wrong-branch runs `44496231009` or `44510092322`. PR #60 has not been modified; keep its exact review head frozen until the review sequence is complete.

### Q0 cross-check allowlist import correction — PR #78 (2026-11-20)

- Static inspection of exact PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4` confirmed `research/pipeline.py` reads `crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS`, while `research/crosscheck.py` did not define the symbol. The resulting missing attribute is a source-level import-time defect if the pipeline path is reached.
- Created draft stacked PR [#78](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/78), based on the frozen PR #60 branch. Head `fb9da3e70e7fd32701c5796a04d3c12e8768b4d8`; exactly two files changed: `research/crosscheck.py` defines the empty immutable `frozenset()` (no independent provider is authorized), and `tests/test_sanitization.py` preserves the constant after its mutation-resistance test and asserts the default allowlist is empty and immutable.
- Compare confirms two commits ahead and zero behind PR #60's frozen head. Both changed blobs were re-fetched and statically checked. No test was run; PR #78 is not included in the active Q0.8 specialist review and remains draft/unmerged. Do not merge it independently; reassess after PR #60 review.

### PR #76 holdout publisher exact-source status (2026-11-20)

- Re-fetched both files at PR #76 head `fe3182730f8a4a19327d5fd6bb25693f22416ae2`. Publisher blob remains `b2c27931b5b4a86b84cd9dc0892d2c8032a6c0b5`; current test blob is `4a1a296d8dd45c7ec7778665c6fe11cc499ea7ef`. The test module contains 22 cases and imports only standard-library modules plus `research.holdout_publish`; `research/__init__.py` at this branch is empty. The publisher source itself imports only standard-library modules.
- No exact-head Python 3.11 Actions test result was located. The prior reconstructed local 22/22 run is preliminary only, not byte-for-byte test execution. PR #76 remains draft/unverified pending exact-source CI.
- Whole-project completion remains **UNRATED**. No protected path was accessed or executed, no trading activity occurred, and no PR was merged.


### PR #78 Q0.8 sparse-checkout fixture correction (2026-11-20)

- Further review of the approved Q0.8 offline workflow showed that `tests/test_pipeline.py` opens two workflow fixture files, `.github/workflows/market-data-check.yml` and `.github/workflows/research-data.yml`, but the workflow's sparse checkout omitted both. The test itself is static/file-based; it does not import `research.pipeline` or protected trading modules. The empty `research/__init__.py` is also now explicitly included for deterministic package resolution.
- Updated draft stacked PR #78 to head `b0dd81ebd3dd3439839a71684fbc6e52ac1e2c3f`, adding only the two unprotected fixture paths and `research/__init__.py` to `.github/workflows/q08-offline-tests.yml` sparse checkout. The existing two source/test file changes remain. Compare against frozen PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4` confirms 3 commits ahead, 0 behind, exactly three changed files.
- Re-fetched the exact workflow and fixtures; confirmed the two files contain the markers required by the static tests and the workflow sparse checkout still excludes protected paths. PR #78 description was updated to three-file scope. Python 3.11 workflow has not been dispatched on this head; no test pass is claimed. PR #60 remains unchanged and frozen.



### Q0.8 specialist-review continuation run #44603985942 (2026-11-20)

- [Run #44603985942](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44603985942) is the Q0.8 immutable specialist-review workflow, not the Q0.8 offline test workflow. It ran on approved PR #60 branch `security/q0-provider-sanitization-2026-11-18`, exact head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`; PR #60 remains open/draft and unchanged.
- Run conclusion is **failure**. PR-head validation, checkpoint-source identity validation, prior artifact restore, Python 3.11.18 setup, immutable-runner compilation, and synthetic policy smoke test succeeded. Four accepted reports were reused from run #44542281860. The new model request for `quant-research` saw 15- and 30-second rate-limit retry responses, then returned a non-final OpenRouter completion with `finish_reason=error`. The specialist stage stopped; no Commander or final acceptance/verification ran.
- Downloaded artifact `q08-review-checkpoint-44603985942`, ID `14569837964`; verified ZIP SHA-256 `3c849cb98a824d70efae18757fa60800810543c3fbf8483048df0c4235466920`. The checkpoint payload SHA-256 is `47d50fd2b2af316dfd26e403bf2d8e56c8803a2949caa09366cc927ed42a789d`. Payload identity matches schema 1, repository `ruthlessjoey/btcidr-trading-lab`, M6 base, exact PR #60 head, and model `inclusionai/ling-3.2-flash:free`.
- Six persisted role reports are `PASS WITH FINDINGS`: `architecture-architect`, `implementation-engineer`, `market-intelligence`, `portfolio-accounting`, `provider-integration`, and `risk-invariants`. No `quant-research`, `strategy-validation`, or other missing role report is present. `commander`, `acceptance`, and `verification` remain null. Full 19-role review and independent acceptance remain **UNVERIFIED**.
- This run is eligible as a checkpoint source under the immutable runner's same-repository, exact-branch/SHA restore validation. Next continuation must use `resume_from_run_id=44603985942`, the same approved Q0 branch, mode `review`, and exact `review_head_sha=d5d5db6cc5d3f11bf579eed45c873b630ed560a4`. Do not use wrong-branch runs #44496231009 or #44510092322.

### PR #78 focused runtime coverage and current exact head (2026-11-20)

- Extended draft stacked PR [#78](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/78) to head `eb1f6e3f762c8510ab55a7cf0c4bf4fe8824539c`, 4 commits ahead and 0 behind frozen PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`. Exactly four unprotected files changed: `.github/workflows/q08-offline-tests.yml`, `research/crosscheck.py`, `tests/test_history.py`, and `tests/test_sanitization.py`.
- In addition to the empty immutable cross-check allowlist and the sparse-checkout fixture correction, `tests/test_history.py` now includes two synthetic runtime cases for `research.history.run_step1`: the exact configured Tokocrypto scope still fails closed without market-identity evidence, and an unapproved configuration fails closed. Both supply opener/sleep callbacks that raise if used and assert exit code 1, `gate=FAIL`, no dataset, no backtest permission, zero network requests, empty HTTP log, and only the two expected report files.
- `research/history.py` has only standard-library imports. The test module's only project import is `research.history`; its source-import closure assertion has been updated accordingly. Q0.8 sparse checkout already includes the empty package initializer and `research/history.py`.
- The six offline test modules contain 56 test methods in total: fetcher 21, provider/live config 4, history 8, probe 2, pipeline containment 6, sanitization 15. This is test inventory, **not** a test-pass count. Exact-head Python 3.11 Actions execution has not yet been performed.
- User-supplied run #44603985942 was the specialist-review workflow, not the Q0.8 offline workflow. PR #78's offline tests therefore still require a separate manual dispatch on branch `security/q0-empty-crosscheck-authset-followup-2026-11-20`. No test pass is claimed.
- No protected paths were accessed or executed, no network/exchange calls were made, and no PR was merged. Project-wide completion remains **UNRATED**.
