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
