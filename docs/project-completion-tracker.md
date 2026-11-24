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

- PR #69 is the clean-main successor to stale draft PR #61 (Ruff static quality). Latest head `ad7213f17df08f3b748bd32d7b93c016fc29025a`; exactly two added files; 2 commits ahead/0 behind `main` at `9bf95e28171447faa910ecd5185b59a349555a52`. It preserves the read-only manual workflow, immutable checkout action, five-file unprotected sparse checkout, verified Ruff 0.17.5 GitHub release asset digest, HTTPS-only download with redirect following and bounded retries. Ruff has not yet run; manual workflow execution remains pending.
- PR #70 is the clean-main successor to stale draft PR #62 (deny all signal paths). Head `d9483900a97f8c809946b0a3a947cac82f4efdeb`; exactly two changed instruction/configuration files; 2 commits ahead/0 behind `main`. JSON parsing confirms the four intended deny rules: Read/Edit for `P1/**` and Read/Edit for all `signal/**`. This is defense in depth, not an OS sandbox.
- PR #61 and PR #62 remain open/draft for traceability but are superseded by #69 and #70. Do not merge the superseded PRs.
- Both successor branches were created directly from current `main`, avoiding the 3-commit divergence present in the older branches. Exact file content and compare metadata were re-fetched after creation.
- PR #60 remains at `c3b593da446835716d54b964e6be5c53981a87a9`; PR #64 remains at `dd01298dc0da0fc45bc31d8df4a313207d45a4bd`. Neither exact-head Q0.8 offline tests nor the corrected 19-role review have been dispatched. The old specialist run #44337003905 has no checkpoint artifact.
- No source execution, protected-path access, workflow dispatch, PR merge, exchange request, account operation, or trading action occurred in this refresh. Whole-project completion remains UNRATED; no numeric progress claim is supported by these tooling/documentation changes.


### Q0.8 checkpoint-input validation (2026-11-19)

- Added a workflow guard before artifact restoration: a non-empty `resume_from_run_id` must match 1–20 decimal digits before it is used in the artifact name or download action.
- The exact workflow blob is `4e704851011a6b10f66d22804edf91aad41af5eb` on both PR #60 and PR #64 branches; runner pin remains immutable commit `0b1d357ccffa8395f611833da1e4bb50ac52fd26`.
- PR #60 head is now `4cc229fb09b1030100101ad873944ea07c4f1982` (26 changed paths); PR #64 head is now `a3c845102746196a6865cd1ae481875d954f24aa` (two changed files). Both remain open/draft/unmerged.
- GitHub reports mergeable for both branches, but the Q0.8 workflow has not been dispatched on either updated head. Python 3.11 syntax/synthetic tests, checkpoint artifact round-trip, exact-head offline tests, and full 19-role review remain unverified.

### Complete protected-path guard successor (2026-11-19)

- New PR #71: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/71
- Branch: `security/complete-protected-path-guard-2026-11-19`; head `ec011a0cf16eeb3a4eaae3df924d96e8a0f99511`; based directly on current `main` `9bf95e28171447faa910ecd5185b59a349555a52`.
- Exactly three shared policy files changed: `.claude/settings.json`, `CLAUDE.md`, and `docs/development-stack/roadmap.md`. GitHub compare confirms 3 commits ahead, 0 behind, and exactly those three paths.
- The Claude Code Read/Edit deny configuration now covers `P1/**`, all `signal/**`, `markets/risk/**`, root `validator.py`, and root `report.py`. JSON parsing succeeded and all 10 expected deny rules were present after re-fetching the committed file.
- The repository instructions now explicitly prohibit processing those paths, require exclusions before broad checkout/search/test discovery, narrow Tokocrypto to unauthenticated GET candles at `www.tokocrypto.site/api/v3/klines`, and state PAPER-only/LIVE-disabled boundaries.
- PR #71 is open/draft/unmerged. It supersedes PR #70 for the overlapping signal-path policy because it includes the same all-`signal/**` rules plus the additional protected modules and endpoint correction. PR #70 remains open/draft for traceability; do not merge it separately.
- PR #69 remains the clean-main Ruff workflow successor to #61; Ruff runtime execution is still pending. PR #61/#62 remain stale drafts and are superseded by #69/#71 respectively.
- Verification is limited to exact-file retrieval, JSON parsing, expected-rule assertions, instruction-content checks, and GitHub compare metadata. Claude Code rule semantics and resistance to shell/tool bypass are not independently verified; this is defense in depth, not an OS sandbox.
- No protected implementation/data was accessed, no application code or tests were run, no workflow was dispatched, and no PR was merged. This policy improvement earns no feature implementation or project-completion credit. Overall completion remains UNRATED pending owner-approved scope/weights and evidence.


### Current verified repository reconciliation (2026-11-19)

- Current `main` baseline: `9bf95e28171447faa910ecd5185b59a349555a52`.
- PR #60 latest head: `03bdff51c23a68a57ea2947904cf6f3c0c1e9dcf`; 26 changed files; open/draft/unmerged; GitHub reports mergeable. Exact-head Q0.8 offline tests and corrected specialist review have not been dispatched.
- PR #64 latest head: `e1c4c1d3f308275d644151f375eef0b4f5d9cf23`; two changed files; open/draft/unmerged; GitHub reports mergeable. Its corrected reviewer and checkpoint workflow remain runtime-unverified pending exact-head dispatch.
- The prior specialist run #44337003905 targeted an earlier PR #60 head, stopped after 10 of 19 review stages on HTTP 429, and has no checkpoint artifact. It is inconclusive and cannot be resumed.
- PR #69 is the clean-main successor for the protected-path-safe Ruff workflow; head `ad7213f17df08f3b748bd32d7b93c016fc29025a`, two added files, open/draft/unmerged, mergeable. Ruff has not yet executed against repository source.
- PR #70 is the clean-main successor for all-`signal/**` deny rules; head `d9483900a97f8c809946b0a3a947cac82f4efdeb`, two changed files, open/draft/unmerged, mergeable. PR #71 supersedes #70's overlapping policy scope.
- PR #71 adds complete shared policy boundaries for `P1/**`, all `signal/**`, `markets/risk/**`, root `validator.py`, and root `report.py`; it also narrows Tokocrypto to unauthenticated GET candles at `www.tokocrypto.site/api/v3/klines` and states PAPER-only/LIVE-disabled. Head `ec011a0cf16eeb3a4eaae3df924d96e8a0f99511`; three changed files; open/draft/unmerged; current-main compare is 3 ahead/0 behind.
- PR #61 and #62 are stale drafts superseded by #69 and #71 respectively. PR #70 is retained as a draft for traceability but should not be merged separately from #71.
- PR #34 remains open/draft at `301b90dca0fd1622d3ff69ee3bbf47d2b401d448`; local 18/18 tests were reported on Python 3.13.5, while Python 3.11 CI remains pending. PR #68 remains open/draft at `e280af8e9224ff3dd5ce282d7e9da3224c6a4136`; six associated test modules remain blocked by protected import dependencies.
- PR #65's tracker branch has accumulated 60 commits ahead and 3 behind current `main`; this clean-main successor preserves its 557-line requirement register and evidence history without inheriting that divergence.
- No workflow was dispatched, no protected implementation/data was accessed, and no PR was merged in this reconciliation. The proposed 100-point weights remain owner-unapproved. Overall project completion remains **UNRATED**; policy and tracker changes do not count as implemented trading functionality.

### Follow-up live-state correction (2026-11-19)

- PR #71 advanced after its initial tracker entry. Its latest head is `ec011a0cf16eeb3a4eaae3df924d96e8a0f99511`, with 3 commits ahead/0 behind current `main` and exactly 3 changed files: `.claude/settings.json`, `CLAUDE.md`, and `docs/development-stack/roadmap.md`. The latest commit updates the roadmap to match the protected-path rules. PR #71 remains open/draft/unmerged; its body now records the latest head and verification limits.
- The Ruff workflow on PR #69's actual head `ad7213f17df08f3b748bd32d7b93c016fc29025a` was re-fetched by immutable commit SHA. It already uses HTTPS-only redirects, bounded connect/total timeouts, retries, an official SHA-256 check, immutable checkout, sparse checkout of five unprotected modules, and lint-only execution. An apparent mismatch was caused by inspecting a different older branch; no redundant fix was created.
- PR #69 remains 4 commits ahead/0 behind current `main`, with exactly two files. Ruff has not been executed because its workflow is manual-only and no owner-dispatched run is available.
- The project-wide completion score remains UNRATED. These policy, roadmap, and tooling changes do not establish functional trading-system completion.

### Q0.8 exact-current-head enforcement (2026-11-19)

- Static review of the immutable reviewer found it validated the M6 merge base and 26-path allowlist but did not independently prove the supplied SHA was still the current PR #60 head. This could permit a stale or unrelated commit with the same path/status pattern to be presented as the intended PR review.
- Added immutable runner commit `2695d51d3387f789a784561c1b572f4ceddf6d9f`; source blob `98f8ea2b186ab287fe79a8626acedcdf801bfc6f`.
- The runner now fetches PR #60 metadata and requires PR #60 to remain open/unmerged, exact equality between the supplied SHA and current PR head, the approved same-repository head branch, and the exact M6 base ref/SHA. It rejects stale SHAs, fork heads, closed PRs, wrong PR numbers, and wrong bases. The compare response continues to require the exact base and merge base; no unsupported `head_commit` field is assumed.
- Added synthetic negative cases for stale head and wrong base. A separate local isolated check of the validator logic passed valid-head, stale-head, wrong-base, closed-PR, fork-head, and wrong-PR cases. This is not a run of the full immutable runner.
- Both PR #60 and PR #64 specialist workflows now pin the new immutable runner. PR #60 head is `4cc229fb09b1030100101ad873944ea07c4f1982` (26 changed paths; 69 ahead/0 behind M6). PR #64 head is `a3c845102746196a6865cd1ae481875d954f24aa` (two files; 21 ahead/0 behind main).
- The runner's Tokocrypto reviewer instruction is narrowed to unauthenticated GET candles only at `www.tokocrypto.site/api/v3/klines`.
- Full Python 3.11 syntax/synthetic execution, exact-head offline tests, checkpoint artifact round-trip, and all 19 review stages remain UNVERIFIED. Manual GitHub Actions dispatch is still required; the previous run #44337003905 cannot be resumed.
- No protected implementation/data was accessed, no workflow was dispatched, and no PR was merged. Overall completion remains UNRATED.

### Ruff workflow supply-chain recheck (2026-11-19)

- Re-fetched PR #69's latest workflow at head `ad7213f17df08f3b748bd32d7b93c016fc29025a`. The download command now uses HTTPS-only protocols, follows GitHub's release-asset redirect, and applies bounded connect/total timeouts and retries before SHA-256 verification.
- GitHub's official Ruff 0.17.5 release API confirms the Linux x86-64 archive digest is `7d261fc981a784668e19e9fa6ad437bfd95b67f2dc263fc1eab87d54d72fcc90`; tag commit is `c91de8a012cb87efe279b762020a0d28dd75ddb5`.
- PR #70 latest head is `d9483900a97f8c809946b0a3a947cac82f4efdeb`; it remains superseded by PR #71. PR #71 head remains `ec011a0cf16eeb3a4eaae3df924d96e8a0f99511`.
- PR #73 tracker head before this addendum: `ada4bac634f694ce6c3e3472e257e47ce869de3f`; clean-main compare was 3 commits ahead/0 behind with exactly one tracker file.
- No Ruff execution, workflow dispatch, PR merge, protected-path access, or trading action occurred.

### Additional clean-main engineering successors (2026-11-19)

- PR #74: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/74 — hardens the current manual free workflow-security check. Head `85a848d56c159ba1eafd909f1160f5ab8aa2091d`; exactly one workflow changed; 1 commit ahead/0 behind current `main`; open/draft/unmerged and mergeable. The Actionlint release download now requires HTTPS for redirects, has bounded connection/total timeouts and retries, verifies the published SHA-256 before extraction, extracts only the root-level `actionlint` member to `RUNNER_TEMP`, and runs the binary from there. Static assertions and exact-file re-fetch passed; Actionlint/zizmor have not run. PR #39 is stale (one commit ahead/80 behind old base) and is superseded by #74.
- PR #75: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/75 — clean-main successor for the pinned Cloudflare security-audit skill. Head `8b4f0b72aa85ffc866d167f2ea543d72513dd327`; 23 new files, all under `.claude/skills/security-audit/`; 1 commit ahead/0 behind current `main`; open/draft/unmerged and mergeable. Preserves upstream MIT license and pinned commit `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (unsigned; pin is for reproducibility only). Updated local safety overlay now covers `P1/`, all `signal/`, `markets/risk/`, root `validator.py`, root `report.py`, Workstream B, exact Tokocrypto public candles endpoint, spot-only/long-only, and PAPER-only/LIVE-disabled. Skill remains read-only guidance; full audit and target-controlled execution remain disabled until an OS-enforced sandbox and required agent capabilities are verified and separately authorized. Exact file, tree, protected-boundary, and scope checks passed. Its JavaScript validators/tests were not executed and remain unverified. PR #38 is stale (one commit ahead/80 behind old base) and is superseded by #75.
- PR #74/#75 are tooling/security improvements only and receive no trading-feature completion credit. No protected code or data was accessed, no workflow dispatched, and no PR merged.
- PR #73 tracker branch now has a second documentation commit after its initial clean-main creation; it remains one-file-only, based on current `main`, and records the latest #71/#74/#75 evidence. Project-wide completion remains **UNRATED**.

### Q0.8 exact-head workflow evidence and self-contained reviewer repair (2026-11-19)

- Current PR #60 head: `aecb8d9c14cc9cb79c81e629b51216175142ddca`; exactly 26 changed paths; current compare to M6 baseline is 70 commits ahead/0 behind. Current PR #64 head: `acc6e1311fdc80fbf12fe7c0e1d87bd2e7d9fa32`; two changed files; compare to current `main` is 23 ahead/0 behind. Both remain open/draft/unmerged.
- Q0.8 offline workflow run #44366173956 succeeded on prior PR #60 head `4cc229fb09b1030100101ad873944ea07c4f1982`: 51/51 tests passed (21 fetcher, 4 provider/live-check, 4 history, 2 probe, 4 static pipeline, 16 sanitization). These tests used Python 3.11.18 and the six-module sparse unprotected scope. The latest PR #60 head changed only the specialist-review workflow pin/checkout since that tested head; exact-current-head offline rerun remains pending.
- Specialist review run #44366331563 targeted PR #60 head `4cc229fb09b1030100101ad873944ea07c4f1982`. Python 3.11 compilation passed, but the synthetic smoke test failed before any model request because the immutable runner expected `.claude/agents/` and `.claude/skills/` files that did not exist in the pinned commit. No specialist roles ran and no checkpoint artifact was uploaded. This was a packaging failure, not an OpenRouter quota failure.
- Corrected immutable runner commit: `c0ed377c82d4f0586dceb20eeaffd3725b568101`; source blob: `5466bf6039e9653ef79cbbbb65b15753ce5cd723`. It embeds all 19 role/skill guidance pairs directly, removing the external file dependency. Both PR #60 and #64 workflows pin this exact commit and sparse-checkout only `tools/q08_specialist_review.py`.
- The runner also binds the review to the current open PR #60 head, same-repository branch, and exact M6 base; stale SHAs, forks, closed PRs, wrong PR numbers, and wrong bases fail closed. Tokocrypto reviewer guidance remains restricted to unauthenticated GET candles at `www.tokocrypto.site/api/v3/klines`.
- The latest synthetic smoke test on the self-contained runner has not yet run. Neither the 19 specialist roles nor Commander, independent acceptance, final verification, or checkpoint artifact round-trip has passed. A fresh manual dispatch is required: branch `security/q0-provider-sanitization-2026-11-18`, `review_head_sha=aecb8d9c14cc9cb79c81e629b51216175142ddca`, and blank `resume_from_run_id`. Also rerun Q0 offline tests on this exact current head. Do not resume run #44366331563; it has no artifact.
- No protected source/data was accessed, no PR was merged, and no exchange/account/trading operation occurred. Whole-project completion remains **UNRATED**; no feature completion credit is awarded for reviewer tooling.

### Q0 exact-current-head integration and research dependency review (2026-11-19)

- Re-fetched the exact latest PR #60 head `aecb8d9c14cc9cb79c81e629b51216175142ddca`. The unprotected source blobs for `fetcher.py`, `providers.py`, `run.py`, and `live_check.py` still show the same clock-source integration gap: `fetcher.fetch_server_time()` and the Tokocrypto provider's `server_time()` fail closed, while both `run.py` and `live_check.py` still require those calls before requesting candles. The pipeline therefore cannot currently reach the approved candle route.
- PR #60 offline run #44366173956 passed 51/51 tests on prior head `4cc229fb09b1030100101ad873944ea07c4f1982` under Python 3.11.18. Logs confirm the 21 fetcher tests, 4 provider authorization tests, 4 history tests, 2 disabled-probe tests, 4 static pipeline-containment tests, and 16 sanitization tests passed. The tests intentionally avoid importing `run.py` because it imports protected `validator.py`; pipeline tests inspect source text only. This is good containment evidence, not end-to-end pipeline functionality.
- Specialist run #44366331563 failed before any model call at synthetic smoke test with `Required trusted agent definition missing`; logs confirm checkpoint upload found no file, and GitHub artifact listing is empty. It cannot be resumed.
- Latest self-contained reviewer pin is commit `c0ed377c82d4f0586dceb20eeaffd3725b568101`, source blob `5466bf6039e9653ef79cbbbb65b15753ce5cd723`. Both PR #60 and #64 workflows pin it and sparse-checkout only `tools/q08_specialist_review.py`. Synthetic smoke on this corrected runner and all 19 roles remain UNVERIFIED. A fresh manual dispatch must use current PR #60 head `aecb8d9c14cc9cb79c81e629b51216175142ddca`, with blank `resume_from_run_id`.
- Static review of unprotected research modules shows `research/history.py` intentionally returns GATE FAIL and makes zero requests because market identity is unverified; no dataset is published. `research/engine.py` and `research/dataset.py` import protected root `validator.py`, so tests importing `research.pipeline` have a protected import closure and must not be run under current restrictions.
- A one-shot unauthenticated GET to the exact approved Tokocrypto candle route was attempted only to check response metadata for a possible same-route clock source; the runner could not resolve `www.tokocrypto.site` (DNS error), so no HTTP request reached the host and no market data was received. No other exchange endpoint was contacted.
- Architecture blocker remains: choose a separately approved server-time source, or approve a design that safely validates completed-candle freshness without pretending local clock equals exchange time. Do not access or modify protected `validator.py` without separate scope authorization. The project remains PAPER-only and no trading action occurred.

### Actionlint workflow local syntax check (2026-11-19)

- The exact PR #74 workflow source was copied into an isolated local parser input and parsed with installed PyYAML 6.0.3. Parsing succeeded; the expected job and three steps were present, and the bounded HTTPS download/digest-before-extract sequence was asserted.
- PyYAML uses YAML 1.1 and therefore represents the GitHub Actions `on` key as a boolean in its parsed mapping. This check is syntax-only; it does not validate GitHub Actions expression semantics. Actionlint and zizmor have not run. PR #74 remains manual-only and runtime-unverified.

### Q0.8 synthetic-only preflight workflow improvement (2026-11-19)

- Updated the specialist workflow on both PR #60 and PR #64 to add a required `mode` choice: `synthetic` or `review`, defaulting to `synthetic`.
- In default synthetic mode, the workflow still compiles the immutable runner and runs the offline synthetic policy suite, but skips model requests, checkpoint restoration, and checkpoint upload. The full 19-role model review and checkpoint steps run only when the owner explicitly selects `mode=review`; that mode repeats the synthetic preflight first.
- PR #60 latest head is now `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; 26 changed paths, 71 commits ahead/0 behind the M6 base. PR #64 latest head is `41390c5d56513cf5157c6971e8e30994dd7d4e63`; two changed files, 24 commits ahead/0 behind current `main`. Both remain open/draft/unmerged.
- Exact workflow file re-fetch on both branches confirmed the same blob SHA `a32e4e78b9987c133934ce86a64be367468e839d`, synthetic default, review-step gate, review-only checkpoint restore, and review-only checkpoint upload.
- This is workflow static evidence only. No workflow was dispatched. Python 3.11 compilation, synthetic runtime, checkpoint round-trip, and all 19 roles remain UNVERIFIED.
- Owner dispatch sequence: first select `mode=synthetic` with current PR #60 SHA `0dd17609305d1e738d4c4c2f65129ccf30f39d7f`; only after success, dispatch again with `mode=review`, same SHA, and blank `resume_from_run_id`. Later resume only from a failed review run that actually uploaded a checkpoint artifact.

### Q0.8 workflow YAML structure check (2026-11-19)

- Parsed the revised specialist workflow structure with local PyYAML 6.0.3. The eight-step structure is valid; synthetic smoke is unconditional; model review is gated by `inputs.mode == 'review'`; checkpoint restore and upload are gated to review mode.
- This is a local YAML syntax/structure check only. PyYAML uses YAML 1.1 and does not validate GitHub Actions expression semantics. No Python 3.11 runner execution or GitHub Actions dispatch has occurred.


## 2026-11-20 Q0.8 exact-head offline regression result

- PR #78 current head: `8198834324f33d16840a770ccd9557a31e844505` (9 commits ahead of its frozen PR #60 base, 0 behind; six changed files). PR #60 remains open/draft at the exact frozen review head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4` (26 changed paths; 89 commits ahead/0 behind M6).
- Exact-head Python 3.11.18 workflow run [#44636088778](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44636088778) checked out the then-current PR #78 head `770fd64368d93b81344e6bd4b239714332cb2e34` and failed one source-text assertion in `tests/test_history.py`: the assertion expected a hard-coded `"backtest_allowed": False`, while `research/history.py` correctly derives the field from `gate == "PASS" and dataset is not None`. Other tests reached before the failure passed; later modules were not executed in that run.
- Corrected only the stale assertion to match the derived fail-closed expression. Commit: `8198834324f33d16840a770ccd9557a31e844505`; re-fetched the updated test and implementation from GitHub.
- Exact-head Python 3.11.18 workflow run [#44636629805](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44636629805) completed successfully on the exact new PR #78 head. GitHub job record: `offline-tests`, conclusion `success`; decoded logs confirm all six selected test modules passed: fetcher 21, provider/live config 4, history 9, probe 3, pipeline containment 6, sanitization 15 — **58 passed, 0 failures**. The workflow sparse checkout excluded protected paths/modules. The tests used synthetic fixtures and no live exchange requests; Step 1 remained GATE FAIL with zero network requests, no dataset, and backtest_allowed false. This verifies only the six approved offline modules, not the full trading system or end-to-end pipeline.
- The specialist workflow remains blocked from safe dispatch through the current GitHub UI because the default-branch `main` workflow file exposes only the legacy required `review_head_sha` input and old reviewer pin. The PR #60 branch copy contains the newer `review_head_sha`, optional `resume_from_run_id`, and `mode` (synthetic/review) inputs and pins the newer immutable runner, but the browser dispatch form loads the default-branch workflow schema. PR #64 is open/draft and contains the default-branch workflow correction. Merging it into `main` is an externally visible repository operation and remains subject to explicit owner approval; no merge was performed.
- Q0.8 specialist review is therefore still **INCONCLUSIVE / UNVERIFIED** beyond the six checkpointed reports from run #44603985942. Do not resume until the default-branch workflow correction is approved and merged, then dispatch exact PR #60 SHA `d5d5db6cc5d3f11bf579eed45c873b630ed560a4` with `mode=review` and `resume_from_run_id=44603985942`. Do not resume old run #44337003905.
- Overall project completion remains **UNRATED**; the 58/58 Q0.8 offline result is not project-wide acceptance evidence. No PR merge, protected-path access, private account access, exchange request, PAPER/LIVE execution, or financial operation occurred.


## 2026-11-20 Q0.8 default-branch workflow correction and resumed review

- PR #64 was explicitly approved by the owner, marked ready, and squash-merged into `main` at `731fc9fbb892dadccc64bf52da2f91ff069da124`. The merged PR had exactly two changed files: `.github/workflows/q08-specialist-review.yml` and `tools/q08_specialist_review.py`. The immutable reviewer runner is pinned by the workflow to commit `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9`; its source blob is `92fc820128bba8cf8fa9e7d3de51838fe2672a1c`.
- Re-fetched both files from the merge commit. The default-branch workflow now exposes required `review_head_sha`, optional `resume_from_run_id`, and required `mode` choice (`synthetic` / `review`, default `synthetic`). It uses least-privilege read permissions, sparse-checks out only the immutable runner, and gates checkpoint restore, model review, and checkpoint upload to review mode.
- Inspected the GitHub Actions dispatch form after the merge. The exact target branch `security/q0-provider-sanitization-2026-11-18` was available. The form displayed all three expected inputs and choices; no dispatch was attempted before those inputs were verified.
- Dispatched the read-only review with branch `security/q0-provider-sanitization-2026-11-18`, exact target SHA `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, checkpoint source run ID `44603985942`, and `mode=review`. New run [#44638204119](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44638204119), run number 22, workflow_dispatch event, exact head SHA confirmed by GitHub.
- Run #44638204119 job `135962144613`: checkpoint-run-ID validation, sparse checkout, checkpoint restore, Python 3.11 setup, trusted-runner syntax verification, and synthetic policy smoke test all completed successfully. At this snapshot the read-only 19-role specialist-review step is still **IN PROGRESS**; checkpoint artifact persistence is pending. No specialist-stage completion, independent acceptance, or final verification claim is made yet. Continue monitoring this exact run. Do not resume old run #44337003905.
- PR #60 remains open/draft at frozen head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; PR #78 remains open/draft at `8198834324f33d16840a770ccd9557a31e844505`. PR #78's exact-head Python 3.11.18 offline suite remains limited to the six approved modules: 58 passed, 0 failed in run #44636629805. This is scoped offline test evidence, not full-system or end-to-end acceptance.
- The current `main` baseline is `731fc9fbb892dadccc64bf52da2f91ff069da124`. The proposed 40-requirement inventory and weights remain unapproved; overall project completion remains **UNRATED**. Protected Workstream B and other protected paths remain outside this review and unverified.


## 2026-11-20 Q0.8 specialist review outcome and post-review audit

- Read-only review run [#44638204119](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44638204119) completed with **failure / acceptance BLOCKED**, not because of a workflow setup or provider quota failure. All setup, checkpoint restore, Python 3.11, syntax, and synthetic preflight steps passed. The review step completed its responses; checkpoint persistence then succeeded.
- The exact source checkpoint was uploaded as artifact `q08-review-checkpoint-44638204119`, artifact ID `14586150476`, SHA-256 `9d735ad735116c20db50b9bf16419e207d513478b8ff49dfd35b2ec2bdfc30f1`. ZIP contains one `q08-review-checkpoint.json` (181,650 bytes; payload SHA-256 `0abaff77a81638aabf769cfe0f26b376f9887fe2b9a9db9ca76758b9f411b29f`). Checkpoint identity validates schema 1, repository `ruthlessjoey/btcidr-trading-lab`, M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`, exact PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, and model `inclusionai/ling-3.2-flash:free`.
- All 16 specialist reports, Commander, independent acceptance, and verification were persisted. Nine specialist roles returned `PASS WITH FINDINGS`; seven reports/stages were blocked: `quant-research`, `operations-observability`, `systematic-debugging`, `release-ci-security`, `lab-commander`, `independent-acceptance`, and `verification-before-completion`. No review PASS is claimed.
- The runner completed model responses for every role. OpenRouter HTTP 429 retries were observed for several roles; retries recovered within the immutable runner policy (at most four retries, each delay bounded to 120 seconds). The run ended at the acceptance gate because required verdicts were BLOCKED, not because quota or network access was exhausted.
- Substantive findings include: (1) an added test module `tests/test_research_gates.py` statically documents that its imports of `research.pipeline` and `research.engine` reach protected `validator.py`; it is excluded from approved workflow test allowlists but creates a latent broad-discovery hazard; (2) authorization-constant evidence was inconsistent on PR #60; (3) `tests/test_history.py` contained a stale route assertion on PR #60; (4) `tests/test_backtest_pipeline.py` retains an assertion expecting a return/report from `run_crosscheck` even though the new implementation raises an unconditional `ApiError`; (5) stale report prose requires clarification; (6) the reviewer context was supplied as a JSON object keyed by path, and one specialist incorrectly treated the `unified_diff_files` values as absent/malformed rather than parsing the supplied structured payload.
- Post-review static re-fetch found PR #78 (head `8198834324f33d16840a770ccd9557a31e844505`) already adds the explicit empty `AUTHORIZED_CROSSCHECK_PROVIDERS = frozenset()` and corrects the `tests/test_history.py` assertion. Its six approved offline Python 3.11.18 test modules passed 58/58 in run #44636629805. That result is evidence for PR #78's six modules only; it does not prove protected pipeline behavior or reaccept the separate PR #60 review.
- Separately inspected the immutable reviewer source at commit `ed28a0ace6ddd19fb5a1bdb97ec2c21ab7cebae9` (blob `92fc820128bba8cf8fa9e7d3de51838fe2672a1c`). Static evidence shows `model_config()` requires the exact `https://openrouter.ai/api/v1` base URL and fixed model; checkpoint source validation binds run ID, repository, workflow ID/path, dispatch event, completed status, exact review head and approved branch; checkpoint payload validation requires exact repository/base/head/model/schema, report verdicts, secret-screening, duplicate-key rejection and a bounded regular file. This provides additional mitigating evidence for the runner-secret/checkpoint findings, but that source was outside the PR #60 review payload; the original independent acceptance verdict remains BLOCKED pending a review that includes this trusted runner evidence.
- No protected file or import chain was accessed or executed. In particular, no test importing `research.pipeline` or `research.engine` was run. PR #60 remains open/draft at frozen head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`; the failed review checkpoint is resumable but should not be rerun unchanged until the evidence-format and source-scope issues are addressed.
- The overall project remains **UNRATED**. Proposed 40-requirement weights are still not owner-approved; full multi-market coverage, verified market identity/data, integrated strategy/backtest, protected Workstream B, accepted PAPER lifecycle, mobile dashboard/monitoring, and independent end-to-end acceptance remain unverified or outside current authorization.


## 2026-11-20 static audit of security/tooling successor PRs

- PR #71 `b33e9c6bb6755473ec6f35e6bc425fdc820805f1` is the strongest current protected-path instruction package. Static re-fetch confirmed valid JSON in `.claude/settings.json`, Read/Edit denies for `P1/**`, all `signal/**`, `markets/risk/**`, root `validator.py`/`report.py`, plus nested copies of `signal/`, `validator.py`, and `report.py`. Re-fetched `CLAUDE.md` matches the current exact Tokocrypto candles-only endpoint, rejects server-time and `.com`, states PAPER-only/LIVE unavailable, and preserves Workstream B and protected-path restrictions. Roadmap language keeps dispatch, secrets, repository settings, and PR merges behind explicit authorization. No protected path was accessed. PR #71 remains open/draft; CodeQL and both GitHub code-scanning analysis checks are successful; the generic review check is skipped.
- PR #70 `d9483900a97f8c809946b0a3a947cac82f4efdeb` is an earlier subset. Its own body already identifies #71 as superseding it; keep it for traceability and do not merge it separately.
- PR #69 `1c277eb0112758b652fc4a3b0578d1b6d53a0476` adds a manual, read-only Ruff workflow that sparse-checks out five named unprotected Python modules and runs lint only. Static inspection found immutable checkout pin, `persist-credentials: false`, pinned Ruff 0.17.5 archive digest, bounded HTTPS download and archive/binary sizes, controlled single-file extraction, and no auto-fixes. CodeQL and both analysis checks succeeded. Ruff itself has **not** run against this PR; the workflow is manual-only and the PR branch's workflow is not yet on default `main`.
- PR #72 `42e7fa1bdf9d5a808d2ac290ed45881f2629bd28` adds a concise security-review skill with protected-path exclusions, authority and workflow boundaries, evidence discipline, and the current spot/long-only, PAPER-only, Tokocrypto candles-only rules. CodeQL and both analysis checks succeeded; no separate runtime test is applicable to the Markdown skill.
- PR #74 `6a8997d4881c85b9ebdf73ec60be54a765362d91` hardens the manual Actionlint download: HTTPS-only bounded fetch, pinned SHA-256, single regular-file extraction to a fixed path with a decompressed-size cap, then Actionlint; its workflow also keeps zizmor offline with a pinned action. CodeQL and both analysis checks succeeded. The patched Actionlint workflow itself has **not** been executed against this branch because it is manual-only and still needs default-branch workflow availability.
- These static reviews are not merge acceptance or runtime verification. All four successor PRs remain open/draft. No merge, dispatch, protected-path access, or live exchange request occurred.


## 2026-11-20 PR #78 protected-import test cleanup and exact-head CI

- PR #78 remains open/draft, stacked on frozen PR #60. Its exact updated head is `e0bb7a03ae1260a29ca8abf9dfb09556a34aad6d`; seven changed paths include deletion of `tests/test_research_gates.py`.
- The removed module explicitly imported `research.pipeline` and `research.engine`; its own docstring acknowledged that the import chain reaches protected root-level `validator.py`. No code or protected dependency was executed. The approved offline workflow sparse-checkout allowlist now includes that exact filename only for a static presence/absence guard, and safe `tests/test_history.py` asserts the module is absent. The deleted module is not imported or executed.
- Updated PR #78 exact-head Python 3.11.18 workflow run [#44641648608](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44641648608) succeeded. Verified run metadata confirms branch `security/q0-empty-crosscheck-authset-followup-2026-11-20` and exact head SHA above. Six approved modules passed: fetcher 21, provider/live config 4, history 10, probe 3, pipeline containment 6, sanitization 15 — **59 passed, 0 failed**.
- The Step 1 synthetic tests intentionally verify safe refusal: GATE FAIL, zero network requests, no dataset output, and backtest disallowed. No real exchange call was made; the PR remains offline-only.
- PR #78 body was refreshed with the exact head, seven changed paths, deletion, scope, and run evidence. No merge occurred. This follow-up improves the evidence/containment of the PR #60 successor stack but does not change PR #60's separate blocked specialist acceptance outcome.


## 2026-11-20 exact-head holdout publisher verification (PR #76)

- PR #76 now has exact head `1a966ddcfef686918bdb257b73874779776c80ba` and three changed files: `research/holdout_publish.py`, `tests/test_holdout_publish.py`, and `.github/workflows/manual-offline-unit-tests.yml`. It remains open/draft and stacked on PR #34.
- Updated the existing isolated holdout workflow to trigger on PR updates constrained to the exact parent branch `security/implement-durable-holdout-reservations` and publisher/test/workflow paths. The job checks out the exact PR head SHA, has only contents/read, disables credential persistence, and sparse-checks out only the isolated publisher, empty package initializer, and corresponding test module.
- Exact-head Python 3.11.18 workflow run [#44642158427](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44642158427) completed success: **22 passed, 0 failed**. GitHub run metadata confirms exact branch and SHA. Verified exact blobs: publisher `b2c27931b5b4a86b84cd9dc0892d2c8032a6c0b5`, test `4a1a296d8dd45c7ec7778665c6fe11cc499ea7ef`, workflow `1bad99c65eeffa83bb0c4fead20b8b514058f300`.
- Test cases cover bounded enumeration at 1,001, oversized/excess records, duplicate/nonstandard JSON, reservation and identity/report mismatches, symlinked files/directories, and all-before-cleanup validation. The publisher import closure is standard-library-only; no protected modules were imported or executed.
- This establishes scoped publisher correctness under Python 3.11.18 only. It does not independently accept PR #34 parent integration, test end-to-end holdout production, or authorize/execute protected TEST/backtest/financial flows. PR #34/#76 remain unmerged drafts.


## 2026-11-20 Cloudflare security-audit skill package static review (PR #75)

- PR #75 remains open/draft at head `450ddee97b6bc2d4f5d0747b9cf2e5200b1bd756`, with exactly 23 new files confined to `.claude/skills/security-audit/`. Its upstream source is pinned to `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`, MIT license included. GitHub reports the pinned upstream commit as unsigned; this is recorded, not presented as verified signature provenance.
- Re-fetched and statically reviewed the skill entrypoint, local safety overlay, provenance, JSON schema, both validator scripts, and tests. Corrected `UPSTREAM-PIN.md` to name the actual local path `.claude/skills/security-audit/`.
- The local overlay explicitly confines this repository to read-only guidance mode. The environment lacks a verified OS-enforced sandbox and parallel sub-agent facility; validator scripts and tests must not execute until suitable isolation and authorization are available. Therefore the package's runtime correctness and an actual full audit remain **UNVERIFIED**.
- Static source checks show bounded input, structural limits, UTF-8 handling, final-component no-follow/nonblocking input opening, diagnostic escaping, strict data/schema invariants, and test cases for hostile encodings, oversized input, symlinks, and resource limits. These are static observations only, not execution evidence.
- No protected path, Workstream B artifact, trading code, or exchange endpoint was accessed. No validator/test execution, audit artifact, workflow dispatch, or agent delegation occurred. This is tooling only and contributes no trading-feature completion credit.


## 2026-11-20 Q0.8 test-isolation and holdout-pipeline static audit (PRs #66 and #68)

- PR #66 `269fc112d13d6a0ed92195156ff22d55263e927b` replaces the old `tests/test_live_check.py` suite that imported `live_check.py` (and its protected dependency chain) with three synthetic provider/configuration tests. Re-fetched exact test blob `cf0fdc200865d4f9692aa8b9f1666b2547db77ff`; it imports only `providers` and standard-library modules, makes no network request, checks Tokocrypto adapter construction and read-only config, and does not import/read `live_check.py`. CodeQL and both analysis checks succeeded; generic review skipped. No runtime tests were run and protected live-check wrapper behavior remains unverified.
- PR #68 `e280af8e9224ff3dd5ce282d7e9da3224c6a4136` statically inspected for its no-eligible-candidate holdout behavior. It avoids reservation/TEST evaluation when `selected_n` is null and only evaluates TEST when a committed reservation is required. Its associated pipeline/engine/history test modules have protected import chains (including root `validator.py`); they remain unexecuted. No runtime acceptance is inferred from the static patch.
- No protected files were read, imported, checked out, or executed in this review. No dataset, TEST evaluation, external API, trade, or PAPER/LIVE operation occurred.


## 2026-11-20 late-day authorization and evidence reconciliation

### Q0.8 reviewer v2

- PR #83 latest head: `91ab93c5ae0957a32b9bc007d252b92388fe450f`; draft/open, not merged. The workflow pins its sparse-checkout runner to immutable commit `0ebe25b4aa4a0f9c04fa86a28303d107429cf655`.
- Exact-head synthetic preflight [#44728221555](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44728221555) passed on the PR #83 branch with Python 3.11, runner syntax, and the synthetic policy smoke test. This mode used mocked transport only; it did not call OpenRouter, read model secrets, fetch PR #60 source, or access protected files.
- Earlier synthetic run [#44726707742](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44726707742) failed against stale runner pin `e9d9825`; it is not counted as passing evidence.
- Full review [#44728818302](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44728818302) restored a provenance-checked checkpoint, passed synthetic preflight and exact source snapshot, then stopped at `architecture-architect` after four bounded OpenRouter HTTP 429 retries. It uploaded checkpoint artifact `14624753539`. The checkpoint has one specialist report (`implementation-engineer`, PASS WITH FINDINGS); Commander, independent acceptance, and final verification are absent. Overall Q0.8 specialist acceptance remains **BLOCKED**, not passed.
- The checkpoint is bound to repository `ruthlessjoey/btcidr-trading-lab`, M6 base `cd451972e3a641ad6fa78e64abf3968655a4b82a`, frozen PR #60 head `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`, model, schema v2, and the evidence-manifest SHA-256. No PR merge occurred.

### Workstream B access authorization and Step 6 v11 candidate

- On 2026-11-20 the owner explicitly authorized access to Workstream B and directed continuation of the work. This supersedes the earlier blanket Workstream B exclusion for the specifically authorized Workstream B artifacts. It does **not** supersede the separate protected-path restrictions: `P1/`, `signal/data/`, copies of `signal/`, `markets/risk/`, `validator.py`, and `report.py` remain excluded absent separate authorization.
- The latest v11 handoff and checksum manifest are readable in the Library. However, the raw-byte materialization service denied the v11 package, patch/diff, manifest, and mutation-runner files. The exact expected archive `workstream-b-step6-candidate-v11-full.tar.gz` is not present in the Library file listing; the handoff expects `step6-candidate-v11-vs-v9.patch`, while the indexed Library item is named `step6-candidate-v11-vs-v9.diff`. Their required SHA-256 values therefore remain unverified. No v11 tests, patch application, mutation suite, or bypass probes were run.
- Static-only review of the v11 diff identified a candidate medium-severity edge case in `markets/portfolio/ledger.py::apply_fill` / `_revalidated_event`: `apply_fill` reads `event.quantity`, `event.price`, and `event.fee` before rebuilding the event, and `_revalidated_event` also performs its `getattr` field-copy comprehension before its `try` block. If a caller deletes a frozen dataclass field via `object.__delattr__`, either access can raise raw `AttributeError`, not `LedgerError`. Minimal regression: delete `quantity` and separately `approval_ref` on scratch events, then assert `LedgerError("INVALID_INPUT")` and unchanged state. The fix should perform guarded revalidation before reading individual fields and convert missing-field `AttributeError` to `LedgerError`. This is a static finding, not a reproduced test against the candidate package.
- Step 6 remains **BLOCKED / NOT ACCEPTED** pending the exact v11 archive and patch bytes, checksum verification, clean reconstruction, Python 3.11 test execution, mutation results, bypass probes, and independent acceptance. The author-reported 88-test output is not independent evidence.
- The v11 decision record says Step 10 decisions 1–7 were approved, but Step 10 implementation still requires Step 6 acceptance, the user's exact external journal storage path, and separate written build approval. No journal build or Step 7 work was started.

### Project-wide status

- The proposed 40-requirement / 100-point weights remain unapproved. Project completion is **UNRATED**; no implementation, verification, or project-wide percentage is asserted.
- Historical strategy evidence remains negative: prior handoff reported `-11%` return and `0.36` profit factor on proxy data with incompletely verified costs. Profitability is **NOT PROVEN**. The objective remains reproducible out-of-sample and PAPER-only evaluation; no profit guarantee or LIVE trading.
- No protected path was accessed, modified, imported, or executed. No exchange request, real-money action, order, withdrawal, or LIVE/PAPER trade occurred.


### PR #86 offline-test boundary correction and exact-head verification (20 November 2026)

- PR #86 latest head is `e1be9595ed4808218e94bb1d8e45d1271bf3621e`. Its Q0.8 offline workflow originally sparse-checked out root `validator.py` and ran `tests/test_research_gates.py`, whose imports reach the protected `validator.py` dependency chain. Workstream B authorization did not grant access to that separate protected module.
- Corrected the workflow to run only the six approved offline modules and removed the protected import closure from the sparse checkout. Updated `tests/test_history.py` to assert that the workflow excludes `validator.py`, `report.py`, `P1/`, `signal/`, `markets/`, and `tests/test_research_gates.py`.
- First run [#44730839583](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44730839583) exposed one missing sparse-checkout entry: the new containment test read its own workflow file. Added that workflow file to the bounded allowlist.
- Exact-head run [#44731107861](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44731107861) completed successfully on exact head `e1be9595ed4808218e94bb1d8e45d1271bf3621e`: **57 passed, 0 failed**, Python 3.11 (fetcher 21, provider authorization 4, history 8, probe 3, pipeline containment 6, sanitization 15).
- This verifies only the six selected unprotected offline modules. The protected research-gate module and protected pipeline integration remain **UNVERIFIED / BLOCKED**. PR #86 remains open/draft; no merge.


### Q0.8 checkpoint resume attempt #2 and latest checkpoint reconciliation (20 November 2026)

- Resume attempt [#44731612974](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44731612974) completed **BLOCKED** after restoring the older one-report checkpoint from run `44728818302`. The model provider returned HTTP 429 and then requested a 240-second reset, beyond the runner's 120-second retry cap. Artifact `14627220743` contains only the earlier `implementation-engineer` report; it is not the latest-progress checkpoint.
- The more complete checkpoint remains run [#44730063361](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44730063361), artifact `14625709210`, independently downloaded and parsed as schema v2 with four specialist reports (`architecture-architect`, `implementation-engineer`, `market-intelligence`, `provider-integration`), all PASS WITH FINDINGS. Commander, independent acceptance, and final verification remain absent.
- Next resume must use run `44730063361` / artifact `14625709210`, not the less-complete run `44731612974`, and should wait until the provider's indicated reset window has passed. Q0.8 remains **BLOCKED / NOT ACCEPTED**.
- Clarification on synthetic run [#44726707742](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44726707742): the HTTP 429 entries were generated by a fully mocked offline transport test, not a real provider request. That old runner's synthetic expectation incorrectly retried a mocked 240-second delay beyond the 120-second policy. The corrected runner tests a 120-second success boundary and a 121-second refusal, with no model API call in synthetic mode.


### Q0.8 resume attempt #3 — latest-progress checkpoint (20 November 2026)

- Dispatched review run [#44732925668](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/44732925668) on the current PR #83 workflow commit `91ab93c5ae0957a32b9bc007d252b92388fe450f`, immutable runner `0ebe25b4aa4a0f9c04fa86a28303d107429cf655`, frozen PR #60 target `d5d5db6cc5d3f11bf579eed45c873b630ed560a4`.
- Correctly resumed from run `44730063361` / artifact `14625709210`, which contains four accepted specialist reports. Checkpoint restore and synthetic preflight passed; model review remains **IN PROGRESS** at this snapshot. No additional role or acceptance is claimed.
- Run `44731612974` is explicitly superseded for resume purposes because it restored the less-complete one-report checkpoint from `44728818302` and added no report.


## Multi-market scope and research integration update — 23 November 2026

### Approved target-market scope

Twin Money Maker is a multi-market research/trading platform, not a BTC-only product. The target scope is:
- Crypto spot across multiple assets, trading pairs and venues, with meme coins as a core capability.
- Equities and ETFs.
- FX.
- Commodities and cash-market research; futures may be researched as cash-market context only, not traded as derivatives.
- Signal-only research such as Olymptrade; no execution integration is implied.
- BTC/IDR is the initial engineering foundation, not the final market boundary.
- MEME_INTEL remains a separate project; no import or integration until independently ready and separately approved.

The operating mode remains spot-only, long-only, PAPER-only. LIVE trading remains disabled. No real-money orders, deposits, withdrawals, payments, funding, margin, leverage, shorts or derivatives. Existing protected paths remain off-limits without separate approval.

### PR #100 — multi-market crypto spot foundation

- PR #100 remains open/draft/unmerged: [Install isolated crypto spot research core foundation](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/100).
- Base: `main` at `0426e1ecd5bd01913a568272792c355c4b7059c7`.
- Head: `integration/crypto-spot-core-foundation-2026-11-23` at `d7487c97eac4abebef89fbd9ea59067dccbabfd6`.
- 24 changed files; 41 commits ahead / 0 behind at the last exact comparison.
- The isolated package provides shared-cash multi-market allocation, quote-currency conversion, venue constraints, synthetic next-open backtesting, latched drawdown controls, point-in-time covariance overlay, instrument lifecycle metadata and a fail-closed token eligibility screen.
- Exact isolated-copy verification previously recorded: Python 3.13.5, 40 synthetic tests, static boundary check and compileall passed. No exchange/network request, credentials, wallet, order or paper execution.
- The package is an engineering foundation, not a complete trading system; no authentic multi-period strategy profitability is demonstrated.

### Approved dataset retrieval and restrictions

The user approved two research sources on 23 November 2026:
1. Binance Public Data spot archives for personal, non-commercial, non-production historical backtesting only.
2. The pumpdata.fun one-day sample for offline meme-coin parser and execution/microstructure testing only; no payment, full-history purchase or redistribution.

Current terms impose a strict separation:
- Binance Vision's current CC BY-NC-SA 4.0 terms expressly restrict use to personal non-production research and prohibit commercial order generation or integration into commercial trading-bot products. Any Binance research must remain isolated from Twin Money Maker's product, model-training, validation and trading pipeline unless a separate written commercial license is obtained.
- pumpdata.fun's sample declares CC BY 4.0 with attribution. It covers 15 October 2026 only and is not point-in-time evidence that its parsed archive was available to a strategy at event time.

Observed retrieval:
- A 100-row Hugging Face preview was successfully retrieved from dataset revision `60ab4739e4a0d4f99e1aae7486e9b6320602c50b`. The preview included curve and PumpSwap venues, landed and failed rows, token-quoted trades, migration-pool trades and a multi-hop leg. Basic schema checks passed. Four representative records (curve landed, token-quoted curve, PumpSwap multi-hop and failed attempt) were also passed through the Python parser.
- The paginated rows endpoint returned HTTP 503. No Parquet shard or full Pump.fun archive was downloaded. The dataset card reports 42,230,410 trade rows; four trade shards total 1,489,189,804 bytes; the separate signature archive adds about 2.77 GB.
- Binance archive retrieval was not completed in this runtime. No Binance data is represented as downloaded or tested.

### PR #101 — offline Pump.fun/PumpSwap parser

- PR #101 remains open/draft/unmerged: [Add offline Pump.fun and PumpSwap trade parser](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/101).
- Stacked on PR #100's integration branch, not directly on `main`.
- Head: `integration/solana-dex-ingest-2026-11-23` at `ee2a19afbd541e9ac3910a63f0dd533694f38a31`.
- Three additive files: offline parser, 18 isolated tests, and a source/license/point-in-time research note. No raw dataset rows are committed.
- The parser validates the exact 29-field schema, timestamps, integer bounds, landed/failed semantics, ordering and transaction metadata; preserves raw units; counts transaction fees once; does not retain wallet addresses; does not guess missing multi-hop mint identity; and flags float64 reserve precision risk.
- Exact local copy verified with Python 3.13.5: 18 tests passed, compileall passed, and static import scan found no network/process imports. No workflow was dispatched.
- This parser is not a DEX execution engine, strategy, paper runner, chain verifier or profitability result.

### Current evidence limits and project rating

- No Binance archive data has been downloaded in this runtime.
- The full pumpdata.fun sample has not been downloaded; only a 100-row preview was retrieved.
- No independent chain receipt verification, multi-day meme-coin history, current market universe, paper execution, external security acceptance or profitability proof is established by this work.
- Overall project completion remains **UNRATED** pending owner-approved scope weights and evidence criteria.
- Profitability remains **NOT PROVEN**.
- PRs #100 and #101 remain draft/unmerged; no workflow was dispatched and no protected paths were accessed or modified.



## 2026-11-23 profitability research, promotion gate, and integration status

### Research-only market data and strategy results

- Under the user's 23 November approval, Binance Public Data spot archives were retrieved only for isolated personal, non-commercial, non-production historical backtesting. No Binance data, raw rows, or derived strategy data were integrated into Twin Money Maker's runtime, model-training or trading pipeline.
- Retrieved BTCUSDT 1d archives: 111 monthly ZIPs, 3,363 validated daily rows, 17 August 2017 through 31 October 2026; no missing monthly archives or daily gaps were found.
- Retrieved seven additional spot pairs on 1d: ETHUSDT, BNBUSDT, DOGEUSDT, SOLUSDT, SHIBUSDT, PEPEUSDT and BONKUSDT. 494 monthly archives were retrieved; all observed per-symbol daily series were contiguous after listing. The fixed-currently-listed universe has survivorship/listing bias and is not a point-in-time market universe.
- Retrieved 1h archives for BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT, SHIBUSDT, PEPEUSDT and BONKUSDT. 423 monthly archives were retrieved. Missing hourly intervals were recorded; no forward-filling was used.
- Research ran a 46-variant BTC daily trend/momentum family and a 36-variant seven-asset cross-sectional momentum family with next-open execution and explicit transaction-cost assumptions. The best validation-selected candidates failed the later test period; the seven-asset strategy also failed to beat cash and buy-and-hold on its later test period.
- A 486-variant 1h mean-reversion family on PEPEUSDT and BONKUSDT did not meet the predeclared minimum trade-count, profitability, win-rate and drawdown criteria. No strategy was selected.
- These are isolated research findings, not an approved production strategy, not DEX/Pump.fun execution evidence, and not an independent profitability acceptance. No strategy is promoted as profitable. Do not reuse the already inspected periods as an untouched holdout.

### Isolated research-engine hardening

- The separately supplied offline prototype bundle was revalidated from a clean disposable copy using Python 3.13.5: **183/183 tests passed**, static boundary check passed across 18 modules, compilation passed, and the isolated virtual-environment `pip check` passed with no broken requirements.
- The prototype's stale Tokocrypto policy reference to `www.tokocrypto.site/api/v3/klines` was corrected in that local copy to the exact currently approved NextMe BTCIDR endpoint `https://cloudme-toko.2meta.app/api/v1/klines`; all request headers are rejected. Its example config is `RESEARCH_ONLY`, network/private APIs/LIVE are disabled, and paper execution is disabled by default. This corrected prototype bundle is not yet integrated into the repository.
- The earlier global Python environment's `pip check` reported an unrelated pre-existing `moviepy`/Pillow version conflict; the clean isolated environment passed. Do not conflate the global environment warning with the clean package result.

### PR #102 — fail-closed profitability evidence gate

- PR #102 is open/draft/unmerged: [Add fail-closed profitability evidence promotion gate](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/102).
- Branch: `integration/profitability-evidence-gate-2026-11-23`, head `eba2afb61c95248555df834c1f45cffa72fe1426`; base is PR #101 head `ee2a19afbd541e9ac3910a63f0dd533694f38a31`. GitHub currently reports mergeable true; the comparison is 10 commits ahead / 0 behind and exactly three changed files.
- Adds a strict, standard-library-only evidence gate and 10 local unit tests. Required criteria include a sealed untouched holdout, source rights, point-in-time integrity, full coverage, no-lookahead, replay-verified experiment registry, calibrated costs and same-cost benchmark, at least 30 registered trials, 250 out-of-sample observations, 100 closed trades, >=55% win rate, positive expectancy, profit factor >=1.30, drawdown <=25%, Sharpe >=1.0, DSR >=0.95, positive paired-bootstrap lower bound, positive 2x-cost result, and four chronological walk-forward folds with at least 75% profitable.
- A pass returns only `READY_FOR_INDEPENDENT_REVIEW`; it never authorizes orders, PAPER execution, LIVE trading or a profitability claim. The gate validates the supplied evidence structure and attestations; independent review must still verify the underlying artifacts and claims.
- The 10 local unit tests and compile check passed. No GitHub Actions workflow run is associated with the PR head; no workflow was dispatched.

### Current integration and authorization state

- PR #100 (crypto spot foundation), PR #101 (offline Solana DEX parser) and PR #102 (profitability evidence gate) remain separate open draft PRs; none is merged or installed into `main`.
- No protected path was accessed, modified, imported or executed. No exchange account, credentials, wallet, order, payment, deposit, withdrawal, PAPER execution or LIVE execution occurred.
- Binance archives remain restricted to isolated personal non-commercial historical research. The pumpdata.fun one-day sample approval remains limited to offline parser and microstructure testing; no payment, full-history purchase or redistribution.
- Target market remains multi-market, not BTC-only: crypto spot across assets/pairs/venues with meme coins as a core capability; broader research includes equities, ETFs, FX, commodities/cash markets and signal-only research. BTC/IDR remains the initial engineering foundation. MEME_INTEL remains separate pending independent readiness and separate integration approval.
- Overall project completion remains **UNRATED** pending owner-approved scope weights and evidence criteria. Profitability remains **NOT VERIFIED**.


### 23 November — integrated validation and meme-token gate hardening

- PR #103: [Harden mandatory meme-token eligibility checks](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/103), open/draft/unmerged, stacked on PR #102. Head `9215d2103c2a65ceda56a4fa4e1ce4458343ab9b`; base PR #102 head `2570a6f142f0fefccfe6bde52321660e23458384`; GitHub reports mergeable true, 3 commits ahead / 0 behind, 2 files changed.
- Security finding: PR #100's original meme-token gate let callers choose a subset of required boolean controls. That allowed an overly permissive policy to omit contract verification, mint/freeze/upgrade authority, honeypot and market-active checks while still reaching human-review eligibility.
- Correction: PR #103 now requires the exact six mandatory checks and rejects non-string token/source identifiers. The gate remains only a preliminary human-review screen; it does not authenticate evidence or authorize orders.
- Exact PR #103 branch snapshot was fetched to a disposable Python 3.11.8 environment. **80/80 integrated tests passed**, including the two new security regression tests; static boundary check passed across all 12 core modules; compileall passed. No workflow was dispatched.
- PR #103 changes exactly three files: `crypto_engine/tmm_core/token_risk.py`, `crypto_engine/tests/test_token_risk.py`, and `crypto_engine/README.md`.
- No protected files accessed; no network, chain, wallet, account, paper execution or live execution occurred.


### 24 November — shared multi-market session-loss guard (PR #104)

- PR #104: [Enforce shared multi-market session loss stops](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/104), open/draft/unmerged, stacked on PR #100's crypto spot foundation. Branch `security/multi-market-session-loss-stop-2026-11-24`; latest recorded head `6e387b3063341cdc212b54061ed1f58ea5275445`; base PR #100 branch head `d7487c97eac4abebef89fbd9ea59067dccbabfd6`. GitHub reports mergeable true.
- Adds `crypto_engine/tmm_core/session_risk.py`: thread-safe shared-session guard, opening-equity loss latch, global BUY rejection after stop, SELL quantity caps, outstanding sell reservations against concurrent stale proposals, explicit settlement, hash-chained audit journal, JSON snapshot/restore, and reset requiring a new session ID plus actor/reason/approval reference.
- Routes the multi-market backtest through the guard and marks equity at executable bar opens before authorizing new exposure, then at closes. A latched stop remains active for the rest of the replay; post-stop signals cannot create BUY fills.
- Adds tests for multi-market BUY blocking, partial exits, short prevention, concurrent stale proposals, restart recovery, audit-chain tampering, state-only halt-clearing tampering, audited reset, unresolved reservation reset refusal, and end-to-end backtest loss-stop behavior.
- Scope is isolated to six paths under `crypto_engine/`; no protected paths changed. No strategy-agent runtime, broker, order router, exchange connector, network request, credential, wallet or account functionality is introduced. The mandatory risk-interception boundary for future agent/simulator paths remains a required integration contract, not a proven existing agent-runtime control.
- **Verification pending:** no local execution result is claimed and no GitHub Actions workflow run/status is associated with the exact PR head. GitHub currently reports mergeable true; that is not a test result. The test suite, Python 3.11 compatibility and independent review remain unverified.
- PR #104 is not merged. No PAPER runner is activated; LIVE remains unavailable. Profitability is NOT VERIFIED. Overall completion remains UNRATED.
