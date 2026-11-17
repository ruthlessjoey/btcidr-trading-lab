# AI Trading & Automation Laboratory — project-wide completion tracker

**Status:** Provisional scope register; not yet a valid percentage score  
**Last checked:** 2026-11-18  
**Repository:** `ruthlessjoey/btcidr-trading-lab`

## Why the overall percentage is currently unrated

The authoritative whole-project master handoff and its complete acceptance criteria were not found in the accessible Project/Library material. The repository contains a Workstream B-specific handoff, but that is not the master project specification. The repository README describes Milestone 1 only; the development-stack roadmap describes tooling rollout, not the full trading-system requirements.

Therefore, assigning a numeric whole-project completion percentage now would require inventing the denominator or silently omitting protected work. This tracker records the currently evidenced components and blockers. It must be reconciled against the original master handoff before a weighted 80% score is published.

## Authority, baselines, and exclusions

### Evidence sources

- `main`: `3d478a37ce2963abbc9d89f6843d6f806d6d28f5` at the time of this tracker.
- M6 engineering baseline: `feature/m6-risk-engine` at `cd451972e3a641ad6fa78e64abf3968655a4b82a`.
- Q0.3–Q0.8 corrections plus provider sanitization are integrated as a candidate in draft PR #60, based on `feature/m6-risk-engine`; it is not merged.
- PR #56 is retained as a historical draft and is explicitly superseded by PR #60.
- Default-branch workflow isolation is in draft PR #57.
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

## Component register

| Component | Intended outcome / dependency | Implementation status | Test / verification status | Security status | Remaining work |
|---|---|---|---|---|---|
| Project architecture and ADRs | One provider-neutral architecture with explicit ownership, risk, portfolio, and execution boundaries | Partially documented across README, repository instructions, milestone history, and prior project decisions | Whole-project master specification not found; no complete acceptance matrix | Core invariants documented; full architecture reconciliation incomplete | Recover or reconstruct the authoritative master scope with owner confirmation; map every requirement and dependency |
| M1 public market-data transport | Read-only BTC/USDT public candle retrieval, parsing, and reporting | Implemented as a candidate; current approved Tokocrypto scope is only `www.tokocrypto.site` server-time/candles | Q0 offline suite historically passed 35/35 on commit `6678b3d06fc780bbeef21894c9650827a9e52904`; this is not evidence for later heads | Transport allowlist and fail-closed checks exist on the Q0 branch; live-check workflow is blocked where it imports protected modules | Re-run only the sparse, approved offline suite on the exact current Q0 head; independently review transport boundary |
| Provider-response sanitization | Prevent provider-controlled values and exceptions from reaching reports, logs, summaries, or output sinks | Integrated candidate is in draft PR #60 on top of the Q0 allowlist; PR #56 is superseded | A local isolated snapshot passed 50/50 tests across six approved offline modules; it is not a byte-for-byte checkout or exact-head GitHub Actions result. Historical 53/53 run on old PR #56 head remains historical only | Old PR #56 workflow checked out protected `validator.py` and `report.py`; its replacement now blocks before checkout. PR #60 keeps the Tokocrypto-only allowlist and excludes protected imports from the sanitizer test | Obtain exact-head manual workflow run and independent review; keep unapproved providers disabled; retain PR #56 as historical only |
| Market identity and historical dataset gate | Verify market identity before publishing a historical dataset | Step 1 deliberately fails closed; it writes no dataset and makes zero network requests | Static/offline tests exist on the Q0 branch; no successful dataset publication is evidenced | Fail-closed gate preserves the current public-route restriction | Owner-approved market-identity method or formal descope; only then implement and verify dataset creation |
| Research cross-check | Compare approved sources without allowing unapproved providers or provider-controlled data to bypass gates | Current cross-check authorization set is empty; cross-checks are blocked | No successful authorized cross-check run is evidenced | Empty provider set is intentionally fail-closed | Keep empty until a separate host/provider authorization and review |
| Dataset integrity and publication | Immutable dataset identity, manifests, hashes, atomic publication, rollback, path confinement | Candidate work exists across stacked PRs #17–#21, #25, and #27; not integrated into the authoritative baseline | Most PR descriptions report static review or tests not yet run; no single integrated exact-head result established here | Security work is present as separate draft changes; end-to-end assurance remains incomplete | Reconcile stack order and bases; run only approved offline tests; verify atomicity, rollback, symlink/path handling, and hash binding |
| Strategy and backtest research | Reproducible strategy selection and backtest evaluation with chronological splits, fees, slippage, and frozen test inputs | Candidate work exists in PR #2 and stacked PRs #16, #18, #20, #23–#24, #28–#36 | No complete integrated backtest verification is established; no profitability claim is permitted | Current backtest execution path reaches protected modules; the backtest workflow is blocked | Resolve protected import boundary without reading protected files; validate full lookback, split integrity, fee/slippage, holdout reservations, and independent out-of-sample evaluation |
| M6 risk engine | Fail-closed risk validation and separation of strategy proposals, risk decisions, and portfolio-owned accepted stops | Implemented on the M6 feature baseline; further security correction is in progress | Exact current-head test evidence and independent acceptance are not established by this tracker | Fail-closed architecture is retained; PAPER/LIVE remain gated | Finish security review, exact-head tests, and interface reconciliation with the portfolio/risk bridge |
| Portfolio ledger and accounting | FIFO accounting, partial closes, fees, slippage, and conservation of quantity/cost/P&L | Protected Workstream B; not inspected or modified here | Not independently verified in this workstream | Protected boundary preserved | Require a separate scope authorization or independent review evidence that does not expose protected implementation |
| Risk bridge and approval boundary | Bind accepted risk decisions to exactly authorized paper fills; reject duplicate, stale, mismatched, or unauthorized events | Protected Workstream B; not inspected or modified here | Not independently verified in this workstream | PAPER remains unavailable until this boundary is accepted | Separate authorization and independent review; preserve one-approval-per-fill and stop ownership |
| Paper-trading lifecycle and emergency stop | Controlled PAPER-only lifecycle with an independently enforced emergency stop and auditability | No accepted integrated paper-execution lifecycle is evidenced | No paper-execution verification is established | PAPER is not authorized merely because code exists; LIVE is unavailable | Complete safeguards, emergency-stop independence, audit trail, replay/recovery and operational acceptance before any paper operation |
| Operations, CI, and security automation | Safe offline testing, bounded specialist review, static workflow audit, least privilege, reproducible evidence | Several workflows and review tools exist; unsafe full-checkout/network workflows are being isolated in draft PR #57 | YAML syntax was parsed locally for the seven PR #57 workflow definitions; Actionlint/zizmor and GitHub workflow execution remain unrun | PR #57 blocks legacy live and Batch 1 workflows and adds sparse checkout to safe workflows/reviewers | Obtain independent review; run the workflow audit only after review; manually dispatch only approved safe tests when available |
| Development skills and quality tools | Reproducible, free-first Claude/ChatGPT development support | Tooling roadmap exists; skills, Ruff, Context7 configuration, and security-audit work remain in draft PRs #38–#48 | Claude skill ZIP upload/invocation and Actionlint/zizmor workflow execution remain unverified; Context7 is available in this ChatGPT environment | Skills are guidance, not a sandbox; no skill may bypass protected paths or approval | Review and adopt one skill/tool at a time; verify license, provenance, dependency hashes, free usage, and permissions |
| UI, monitoring, and operator experience | Clear operational visibility, stale-data warnings, auditability, and safe operator controls | Complete requirements and implementation evidence not established in the accessible master scope | UNVERIFIED | Must not expose credentials or provide an execution bypass | Confirm whether these are required components in the master specification before scoring |

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

At the time of this update, GitHub reports **50 open pull requests: 45 draft and 5 non-draft**. Many research and hardening changes are stacked on earlier branches rather than integrated into one accepted baseline. This is evidence of substantial candidate work, not evidence that the whole project is complete.

Important current review items:

- PR #56 — Batch 1 provider-response sanitization; draft and superseded by PR #60. The historical workflow checked out protected files; it now fails closed before checkout.
- PR #57 — default-branch workflow protected-path isolation; draft, head `55fde80570b3b7edefdc78f4b84d4ffbcf57a2a9`. Seven workflow files changed; no application source changed. Actionlint/zizmor execution remains pending.
- PR #58 — provisional project-wide completion tracker; draft, one documentation file.
- PR #59 — first repository-specific `security-review` skill; draft, one guidance-only file. Runtime discovery/invocation remains unverified.
- PR #60 — integrated Q0 transport allowlist and provider sanitization; draft, head `fb1537cad11c5c36a537ffca28969909b1ca025a`, 26 paths, 25 commits ahead of the M6 baseline. Local isolated snapshot: 50/50 tests; exact-head GitHub Actions run and independent review remain pending.
- PR #2 — Milestone 3 dataset/backtest; open against an older main base. Provider authorization and current integration status require reconciliation before use.
- PRs #16–#36 — stacked backtest, dataset integrity, and holdout-reservation changes; most remain draft and several descriptions explicitly say tests were not run.
- PRs #38–#48 — development tooling, skills, and review automation; remain separate draft stages.

No PR has been merged as part of this tracker work. No workflow was dispatched. No exchange request, account access, or trading action was performed.

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

**Whole-project completion percentage: UNRATED — denominator not yet authoritative.** This is not a zero-percent claim. It means the original master scope and weighting have not been recovered, and protected components cannot be independently scored under the current access boundary.

Before publishing a numeric percentage:

1. Recover the original whole-project master handoff or have the owner approve a reconstructed requirement inventory.
2. Establish one authoritative integration baseline and map every stacked PR to it.
3. Confirm which Workstream B components can be scored using independent evidence without opening protected implementation.
4. Assign explicit weights to every requirement; keep the weights stable and visible.
5. Score only implementation and verification evidence on exact commits.

The next engineering priorities are: finish the workflow isolation review; establish exact-head safe offline test evidence; reconcile the Q0 security branch with the M6 baseline; then proceed through dataset identity, research integrity, strategy/backtest, and risk/portfolio interfaces without crossing protected boundaries.
