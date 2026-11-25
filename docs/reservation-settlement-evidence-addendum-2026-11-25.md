# Twin Money Maker — Reservation / Settlement Engineering Addendum
**Date:** 25 November 2026 (Asia/Makassar)  
**Repository:** `ruthlessjoey/btcidr-trading-lab`  
**Base main at addendum creation:** `0426e1ecd5bd01913a568272792c355c4b7059c7`

This is a dated addendum to the project completion tracker. It records candidate engineering changes in stacked draft PRs; it does not replace the full project tracker or grant mainline/integration credit.

## Owner objective and product scope

Twin Money Maker is a multi-market AI Trading & Automation Laboratory, not a BTC-only bot:
- Crypto spot across assets, pairs and venues, including meme coins.
- Equities, ETFs, FX, commodities and cash-market research.
- Later limited signal-only markets where appropriate.
- BTC/IDR is the initial engineering foundation.
- MEME_INTEL remains a separate project until independently ready and explicit integration approval is given.
- Top objectives are security, system reliability, and demonstrated cost-adjusted profitability / high win rate. Performance must be supported by reproducible out-of-sample evidence.

Overall project completion remains **UNRATED** pending the authoritative whole-project scope/evidence reconciliation. Profitability remains **NOT ESTABLISHED** by this engineering work.

## Safety boundaries

- Spot-only, long-only; no shorts, leverage, margin or derivatives.
- PAPER-only; PAPER activation remains on hold. LIVE trading disabled/absent.
- No real-money orders, deposits, withdrawals, payments, funding, credentials, private account data or wallet/account access.
- Tokocrypto public market data only. Historical approved endpoint references conflict between `www.tokocrypto.site/api/v3/klines` and `cloudme-toko.2meta.app/api/v1/klines`; do not call until exact host/path/symbol/interval approval is verified. Never use Tokocrypto `.com`.
- Protected paths requiring separate approval: `P1/`, `signal/data/`, copies of `signal/`, `markets/risk/`, `validator.py`, `report.py`, and protected Workstream B artifacts. Do not inspect, modify, expose, import or execute them. Do not run tests whose import closure reaches them.
- No force pushes, resets, destructive actions, branch deletion, PR merges, deployments or workflow dispatch without separate explicit approval.
- Do not weaken security controls.

## Candidate PR chain

All PRs below were live-refreshed on 25 November 2026. They remain **open / draft / unmerged**. Their ancestry is stacked; none is integrated into `main`.

| PR | Focus | Current head | State |
|---|---|---|---|
| [#139](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/139) | Reject persistent/TEMP triggers on reservation parent tables | `7019bb13689f0767616a491dbcfc566c05ec3388` | Draft |
| [#140](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/140) | Validate parent table column/PK contract (superseded by #141 exact DDL) | `27764ed0a8041bf98a38ddae09e38c4b1292548b` | Draft |
| [#141](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/141) | Exact normalized DDL for `markets`, `batches`, `fills` | `95306e45c283648f8adc051f3c2a410fe085b724` | Draft |
| [#142](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/142) | Reject custom indexes on parent settlement tables | `a26411b21f5b7a8c734b70c00a0d5592cda1c178` | Draft |
| [#143](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/143) | Fail closed on existing SQLite FK violations | `4589a2f6548085ffbb8d88e814a7df2983c4b1f7` | Draft |
| [#144](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/144) | Reservation lifecycle, expiry, version CAS and audit | `8b8543c2fe9bf90d1b525a8cf14446debfcb7079` | Draft |
| [#145](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/145) | Atomic per-fill SELL allocation persistence and reservation consumption | `e6ae9c62499703290b3bd658c67d1f5556b636ea` | Draft |
| [#146](https://github.com/ruthlessjoey/btcidr-trading-lab/pull/146) | Integrate allocations into `SQLiteSettlementStore.apply_batch` and coordinate both outboxes | `be59ab5529981b87538a7d3bc9b3c146d48f9343` | Draft |

### PR #139–#143: schema trust-boundary hardening

- Reject triggers attached to `markets`, `batches`, `fills`, and all reservation tables, including TEMP triggers.
- Verify exact parent settlement DDL, including CHECK constraints and generated-column/collation integrity.
- Reject custom persistent indexes on parent and reservation tables.
- Run `PRAGMA main.foreign_key_check` and fail closed on existing orphan rows or pragma database errors.
- A static review correction to #141 restored canonical batch-status and fill-side CHECK constraints and removed an obsolete loop. This was a static correction, not an exact-head test pass.

### PR #144: lifecycle state machine

- Reservation schema v2 adds explicit `PENDING`, persisted `expires_at`, a CHECK requiring expiry after creation, and positive monotonic version constraints.
- Lifecycle functions: create PENDING, authorize PENDING→ACTIVE, release ACTIVE, cancel PENDING/ACTIVE, expire PENDING/ACTIVE, and account-scoped read.
- Mutations require a caller-owned transaction and use version-checked compare-and-set; the caller owns commit/rollback.
- Each transition appends to the existing settlement audit hash chain.
- Account and registered market/base/quote identities are checked.
- Existing databases with the earlier reservation-v2 DDL fail closed; no migration is included or authorized.

### PR #145: per-fill allocation persistence

- Reload fills and reservation state from the trusted database, not strategy-supplied snapshots.
- Require exact allocation of every SELL fill; reject BUY allocation, cross-account/market use, stale versions, expired/inactive reservations, over-consumption, duplicate IDs and duplicate fill/reservation pairs.
- Aggregate consumption per reservation; perform compare-and-set updates and increment reservation version once per batch.
- Persist allocation rows and deterministic idempotency-keyed reservation outbox records in the same caller-owned transaction.
- Append reservation consumption to the audit hash chain.
- Bounds: 10,000 fills scanned; 1,000 allocations/reservations; bounded identifiers, quantity text and SQLite integer versions.

### PR #146: settlement-store integration

- `SQLiteSettlementStore.apply_batch` accepts bounded `sell_allocations`.
- When reservation schema v2 is enabled, a SELL batch without exact per-fill allocations fails closed.
- Allocation data participates in the batch request hash for replay integrity.
- Fill rows, reservation consumption, allocation rows, reservation outbox, balances, audit and batch result are committed in the same SQLite transaction.
- A failed allocation or outbox write aborts the entire batch.
- Adds reservation outbox listing and receipt-idempotent acknowledgement.
- Batch remains `COMMITTED_PENDING_OUTBOX` until both the legacy settlement outbox and reservation outbox are acknowledged; then it becomes `COMPLETE`.

**Known rollout limitation:** PR #146 preserves legacy v1 behavior when reservation schema v2 has not been enabled. Legacy SELL fills in such databases are not reservation-protected. A separately reviewed, evidence-backed migration/rollout is required before claiming reservation enforcement across all SELL paths.

## Verification and evidence status

- PR #139–#146 exact-head CI: **PENDING**.
- Python 3.11 exact-head tests: **PENDING**.
- PR #144 lifecycle regression suite: 21 test methods authored; execution unverified.
- PR #144 reservation-schema suite: 24 test methods authored; execution unverified.
- PR #145 atomic-allocation suite: 12 test methods authored; execution unverified.
- PR #146 settlement-store suite: 21 test methods authored; execution unverified.
- PR #146 compare against PR #145 head: 19 commits ahead / 0 behind; 7 changed paths.
- GitHub combined status lookups and workflow-run lookups returned empty arrays for latest candidate heads. Empty output is not a pass and does not prove no workflow exists.
- PR #146 has no submitted independent review or review threads at last check.
- Narrow earlier evidence remains: PR #136 isolated module 13 passed, #137 14 passed, #138 15 passed, and PR #139 local trigger-catalog reproductions passed. These do not verify #141–#146.
- No exact-head tests were run in this session. No workflow was dispatched.
- No protected paths, provider endpoints, account data, migration, exchange calls, PAPER activation, LIVE execution, or trading operations were accessed/performed.

## Readiness

- Reservation schema trust-boundary candidate: implemented in draft PRs; **not yet independently accepted**.
- Reservation lifecycle: candidate implementation only; exact tests pending.
- Atomic per-fill reservation allocation: candidate implementation only; exact tests pending.
- Settlement-store integration: candidate implementation only; exact tests pending.
- Remote idempotent outbox receiver / ambiguous-delivery recovery: **NOT IMPLEMENTED**.
- v1→v2 migration and legacy SELL-path closure: **NOT IMPLEMENTED**.
- Crash/concurrency/restore drills: **PENDING**.
- Independent adversarial acceptance: **PENDING**.
- Profitability/high-win-rate evidence: **NOT ESTABLISHED**.
- Install readiness: **NOT READY**.
- Trading readiness: **NOT READY**.
- PAPER activation: **ON HOLD**.
- LIVE: **DISABLED / ABSENT**.

## Next required work

1. Run exact-head focused tests for #139–#146 in a safe isolated checkout and capture SHA, command, Python/SQLite versions and results.
2. Obtain Python 3.11 CI and independent adversarial review for the entire dependency chain.
3. Resolve any test failures and repeat exact-head verification after every correction.
4. Complete reservation outbox receiver semantics, idempotency, duplicate receipt handling and ambiguous-delivery recovery.
5. Design v1→v2 migration only on a disposable verified database copy; preserve historical SELL and legacy outbox blockers absent evidence-backed reconciliation.
6. Close legacy SELL bypass before reservation enforcement can be called universal.
7. Run multiprocess concurrency, crash injection, backup/restore, malformed DB and resource-exhaustion drills.
8. Keep strategy agents proposal-only until persistence, risk and trust boundaries are accepted.
9. Conduct preregistered profitability research using point-in-time data, realistic fees/spread/slippage/market impact/liquidity, untouched chronological holdouts, multiple-testing controls, net returns and independent reproduction.

## Team roles

- **Commander/coordinator:** sequencing, evidence register, safety, tracker and handoffs.
- **Architecture specialist:** state contracts, lifecycle, transaction boundaries and multi-market integration.
- **SQLite persistence specialist:** DDL, pragmas, transaction semantics, locking, migration, backup/restore and outbox.
- **Security reviewer:** adversarial schema/data review, TEMP/main/attached shadowing, malformed schema and resource exhaustion.
- **Test/reliability specialist:** exact-SHA tests, Python 3.11 CI, resource benchmarks, crash/concurrency/restore.
- **Quant research specialist:** preregistered strategies, realistic costs and out-of-sample profitability research.
- **Independent acceptance reviewer:** evidence-based pass/fail/inconclusive decisions.
- **User/project owner:** approvals for protected paths, merges, providers, migration, deployment and trading activation.

This addendum is candidate engineering evidence only. It is not a full repository archive, installable product, trading authorization, or profitability claim.


## 25 November — idempotent reservation inbox candidate (PR #148)

- PR #148 is open/draft/unmerged, stacked on PR #146. Current head: `ee6387fbb5f721a509a38b971dc3db35452b0c73`.
- Adds an offline SQLite inbox with exact DDL checks, canonical payload hashes, unique idempotency keys and deterministic payload-bound receipts.
- Adds a bounded delivery coordinator that verifies the sender's stored payload hash, invokes an injected trusted receiver, verifies the exact deterministic receipt and then acknowledges the sender outbox.
- Models ambiguous delivery: the receiver commits its inbox row but the response is lost; retrying the same key/payload returns the original receipt without duplicating the inbox row.
- Nine focused receiver tests are authored; exact-head execution and Python 3.11 CI remain pending.
- This is a local inbox/receipt contract, not a remote production receiver. It does not implement a real external business effect, authenticated network transport or remote service. Those remain separate work.
- No exact-head tests or workflow dispatch are claimed. Empty status/workflow lookups are not passes. No network/provider/account/trading activity occurred.



## Superseding progress — PRs #149 and #150 (25 November 2026)

The following two security corrections are stacked on PR #148 and supersede the corresponding open gaps above. They remain draft candidates and are not mainline integration or independent acceptance.

### PR #149 — inbox TEMP-trigger and receipt-integrity correction

- Branch head: `55afaf28a89a04566ad1c07d2bbe9ad75580e634`.
- Adds verification of `temp.sqlite_master` for TEMP triggers attached to `main.reservation_inbox`. The prior verifier checked only `main.sqlite_master`; SQLite permits a TEMP trigger to attach to a main-database table.
- Replayed inbox records must now match the deterministic receipt recomputed from the canonical payload. A modified stored receipt is rejected instead of returned as valid.
- Adds four focused regressions/reliability tests: TEMP-trigger rejection, corrupted receipt rejection, retry after receiver connection restart, and two concurrent delivery workers sharing one durable receipt.
- Targeted Python 3.13.5 / SQLite 3.46.1 execution against the updated receiver implementation passed those cases plus valid deterministic replay. The full repository test module, Python 3.11 CI, multiprocess crash/restore drills and independent review remain pending.
- PR #149 is open/draft/unmerged and is based on PR #148 head `ee6387fbb5f721a509a38b971dc3db35452b0c73`.

### PR #150 — close legacy unreserved SELL bypass

- Branch head: `8550fd6f222e16a698b6bdeaacde98fbc350f8fe`.
- `SQLiteSettlementStore.apply_batch` now rejects SELL fills if reservation schema v2 is absent, not merely if schema v2 is present but allocations are missing.
- BUY-only batches remain available on v1 databases.
- The regression suite now covers legacy v1 SELL rejection and verifies the batch remains pending until both the legacy and reservation outboxes are acknowledged.
- This intentionally means legacy databases cannot SELL until a separately reviewed rollout/migration establishes valid schema-v2 reservation state. No existing database is migrated, rewritten, or automatically seeded.
- Static inspection confirms the gate occurs before batch writes inside the caller-owned transaction. Exact-head Python execution, the full `crypto_engine/tests` suite, Python 3.11 CI and independent review remain pending.
- PR #150 is open/draft/unmerged and is based on PR #149 head `55afaf28a89a04566ad1c07d2bbe9ad75580e634`.

### Updated dependency and readiness disposition

The candidate dependency chain is now #139 → #140 → #141 → #142 → #143 → #144 → #145 → #146 → #148 → #149 → #150. PR #147 is the separate documentation tracker. All implementation PRs in this chain remain draft/open/unmerged; no change has been accepted into `main`.

The #150 fail-closed gate closes the code-level legacy SELL bypass in its branch, but does **not** migrate existing databases, seed reservations, validate historical balances, or make old databases SELL-capable. The receiver is still a local SQLite contract, not a production remote service or authenticated transport adapter.

Fresh exact-head status/workflow lookups for #149 and #150 returned empty arrays; this does not prove that CI passed or that workflows do not exist. Neither PR has independent acceptance. No install/trading readiness is claimed.

### Revised next priorities

1. Obtain an isolated checkout and run exact-SHA tests for the complete #139–#150 stack, recording the tested SHA, Python/SQLite versions, exact commands, logs and all results. Repeat on Python 3.11 CI. No tests may import protected paths.
2. Fix every failure on a new immutable head and rerun the complete required suite; do not promote any earlier test result to a later commit.
3. Commission adversarial review of the complete stack, especially SQLite schema trust, attached/TEMP objects, transaction boundaries, outbox receipt authenticity, idempotent replay, cross-account/market use and rollback semantics.
4. Design v1→v2 enablement only on disposable verified copies. Preserve existing holdings, legacy SELL history, outbox state and audit-chain continuity; no live database migration or seeding without separate approval.
5. Add deterministic crash/power-loss, multiprocess race, receiver restart, backup/restore, malformed DB, resource-exhaustion and partial-write tests.
6. Keep any remote receiver, network transport, broker integration, strategy authority, PAPER activation and LIVE functionality disabled until their own security design, tests, approval and evidence gates pass.
7. Continue preregistered, cost-adjusted multi-market profitability research. The 181/181 result belongs only to the separate research prototype; no BTC/IDR OOS profitability or high-win-rate evidence exists yet.


## Independent research prototype revalidation — 25 November 2026

The separately uploaded `TwinMoneyMaker_ExternalResearch_2026-11-23_REVALIDATED.zip` was freshly extracted to a disposable temporary directory and verified in this session.

- Archive SHA-256 manifest: all listed files verified.
- Environment: Python 3.13.5; the SQLite runtime used by the current environment is 3.46.1.
- Command: `PYTHONNOUSERSITE=1 sh install.sh` from the archive's `prototype/` directory.
- Result: **181/181 unit tests passed**.
- Additional installer checks passed: `pip check`, the static boundary check across 18 modules, and `compileall`.
- No third-party dependency was installed and no network/provider call, account access, exchange action or order was performed.

This independently revalidates only the separate standard-library prototype and its synthetic fixtures. It does not test any upstream trading platform, the GitHub repository's PR #139–#150 code, live market data, a strategy on BTC/IDR, or trading profitability. The prototype is not approved for exchange connection or installation into the main repository.


### PR #151 — restore the sender/receiver payload projection

- Branch head: `f52f391cde7298ceff2b50dfdb0c34f7b4098157`.
- Static integration review found that `deliver_pending_reservation_outbox()` reads `account_id`, but `SQLiteSettlementStore.pending_reservation_outbox()` omitted it from the selected columns and returned dictionary. The initial delivery therefore raised `KeyError("account_id")` before invoking the receiver.
- The sender query and field mapping now include the persisted `account_id`; the return type also reflects the integer reservation version.
- Adds an explicit projection regression and strengthens the delivery test to assert that the trusted receiver callback gets the account ID from the persisted sender row.
- PR #151 is open/draft/unmerged and is based on PR #150 head `8550fd6f222e16a698b6bdeaacde98fbc350f8fe`.
- Exact-head Python execution, the full repository suite, Python 3.11 CI and independent review remain pending.

This correction makes the sender's projected record structurally match the receiver's required payload; it does not add remote transport or authenticate an external receiver.

### Latest stacked implementation chain

The active implementation chain is now #139 → #140 → #141 → #142 → #143 → #144 → #145 → #146 → #148 → #149 → #150 → #151. PR #147 is the separate documentation tracker branch, updated to record these follow-ups. All implementation PRs remain open/draft/unmerged and none is in `main`.


## Exact-head CI milestone — PR #150 (25 November 2026)

The other project build session advanced the #150 branch with the isolated CI workflow and then fixed both receiver-module test defects. The live branch and pull request were refreshed:

- PR #150 remains **open / draft / unmerged**.
- Exact passing head: `0bf6f044bd49a05226bdde33cb9641af11cbc68f`.
- Exact-head GitHub Actions push run: [45550416851](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45550416851) — overall **success**.
- Workflow job for Python 3.11.18 / SQLite 3.46.1: `test_sqlite_settlement_store.py` 22/22 passed; `test_reservation_outbox_receiver.py` 13/13 passed.
- Workflow job for Python 3.13.18 / SQLite 3.46.1: settlement-store 22/22 passed; receiver 13/13 passed.
- Both matrix jobs passed. This is 70 successful test executions across two Python interpreters.
- The workflow used `contents: read`, pinned action SHAs, sparse checkout of the explicitly listed settlement files, no protected-path checkout, and did not dispatch the specialist review workflow.

The passing receiver run includes two corrections made after earlier failures:
1. The pending sender outbox query now selects and maps `account_id`, matching the delivery worker's canonical payload contract.
2. The stored-receipt tampering test now modifies `reservation_inbox` in the receiver DB (not the sender settlement DB).

Earlier runs on older exact commits failed; those runs remain in GitHub history. Only the final exact head above is a passing result. No broad test suite or independent acceptance was implied.

## PR #151 disposition

PR #151 (account identity in reservation outbox records) was closed as a duplicate after its two intended fixes were incorporated into the later #150 branch commits `db53e772e5cd36de74adbb37cee93fd4b3a08a38` and `0bf6f044bd49a05226bdde33cb9641af11cbc68f`. Its branch is retained; no branch was deleted and no PR was merged.

## Revised readiness

- Exact-head focused settlement/receiver CI on #150: **PASS** on Python 3.11.18 and 3.13.18 (70 test executions).
- Full PR #139–#150 dependency suite: **PENDING**.
- Python CI for earlier schema/lifecycle/allocation PRs #139–#146: **PENDING** except insofar as their source is exercised by the two #150 focused suites.
- Independent adversarial acceptance: **PENDING**; the Workstream A immutable AI review trigger was skipped, not passed.
- Crash/power-loss/multiprocess/backup-restore drills: **PENDING** beyond the focused receiver concurrency/restart unit tests.
- Existing database v1→v2 migration/enablement: **NOT IMPLEMENTED**; legacy SELL is blocked by #150.
- Remote receiver, authenticated network transport and production integration: **NOT IMPLEMENTED**.
- Install readiness: **NOT READY**.
- PAPER activation: **ON HOLD**; LIVE **DISABLED / ABSENT**.
- Profitability/high win-rate: **NOT ESTABLISHED**. The separately revalidated 181/181 research prototype is synthetic harness evidence only.

### Next engineering priorities

1. Verify the #150 passing head and complete dependency graph in an isolated checkout. Extend the pinned sparse CI or add a separate approved matrix for #139–#146 only if their import closure is proven to exclude protected modules.
2. Execute exact-SHA regression suites for schema DDL, parent triggers/indexes/foreign-key checks, lifecycle, atomic allocations and settlement-store integration on Python 3.11 and 3.13. Capture failures and logs; rerun after every code change.
3. Commission independent security acceptance over main/TEMP/attached SQLite objects, schema tampering, transaction rollback, receipt binding, duplicate/replay races, resource exhaustion and malformed database state.
4. Design—but do not run—v1→v2 data migration on disposable synthetic copies. Any real or existing local database migration requires separate explicit approval and an evidence-backed inventory/balance/audit reconciliation plan.
5. Complete remote receiver threat model and transport design separately; no broker/network adapter may be connected to this offline prototype without new approval.
6. Continue preregistered profitability research only after the approved BTC/IDR historical data blocker is resolved. Do not claim strategy profitability from synthetic 181/181 unit tests.


## Superseding full-stack verification — 25 November 2026

PR #150 has now expanded from the earlier 2-module matrix to the complete six-module reservation/settlement regression matrix. The previous 2-module result remains historical; the following is the stronger latest result:

- PR #150 current exact head: `83f9a789eb0e7fc869de3a45041c2336c6b3595c`.
- Exact-head GitHub Actions push run: [45551031050](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45551031050), completed **success**.
- Python 3.11.18 + SQLite 3.46.1: reservation schema v2 25/25; lifecycle 21/21; allocation validator 16/16; atomic allocations 13/13; settlement store 22/22; receiver 13/13. Total **110/110**.
- Python 3.13.18 + SQLite 3.46.1: the same six suites **110/110**.
- Total: **220 successful test executions**. Both matrix jobs and all 12 test steps passed.

The expanded run follows CI-discovered test fixture corrections: the foreign-key regression now supplies all 11 reservation fields using an explicit column list, and the multi-reservation allocation fixture sums exactly to the SELL fill quantity. Failed earlier runs apply only to earlier SHAs.

### PR branch updates and disposition

- PR #149 current head: `8db0cd10649e169bb19e934d40f0e760c5b8b0be`; open/draft/unmerged. Its exact-head PR and push runs #45550760669 and #45550753144 passed the receiver suite 13/13 on Python 3.11.18 and 3.13.18. The other suites are gated to the child integration branch and were skipped on #149.
- PR #150 current head: `83f9a789eb0e7fc869de3a45041c2336c6b3595c`; open/draft/unmerged. Full six-suite exact-head CI passed on run #45551031050.
- PR #151 and PR #152 were closed as superseded/duplicate; their branches were retained and not deleted. PR #151's account_id projection correction and receiver test database-target correction were incorporated into the later #150 branch commits. PR #152's duplicate FK fixture correction was overtaken by the same change on #150 before its branch could be integrated.
- `main` remains `0426e1ecd5bd01913a568272792c355c4b7059c7`; no merge has occurred.

### Current evidence boundary

This is now an exact-head pass for all six targeted reservation/settlement regression modules on the #150 candidate branch. It still does **not** establish:
- the complete repository test suite or all upstream PR #139–#148 exact heads individually;
- independent adversarial acceptance (the Workstream A immutable AI review trigger was skipped, not passed);
- production receiver authentication/transport or an external business effect;
- crash/power-loss, process-kill, restore, malformed-file, or resource-exhaustion certification;
- v1→v2 migration safety for any existing database;
- PAPER activation, LIVE capability, profitability or high win rate.

Overall project completion remains **UNRATED**; install/trading readiness remains **NOT READY**; PAPER is **ON HOLD** and LIVE is **DISABLED / ABSENT**.


## Latest rebased full-stack CI — exact PR head PASS (25 November 2026)

The child integration branch has been synchronized with the latest PR #149 head. This is the current authoritative focused CI result; the earlier #150 heads `83f9a789...` and `0bf6f044...` remain historical results only.

- PR #149 current head: `8db0cd10649e169bb19e934d40f0e760c5b8b0be` (open/draft/unmerged).
- PR #150 current base: `8db0cd10649e169bb19e934d40f0e760c5b8b0be`.
- PR #150 current exact head: `8551e596fab6d3c649b00281a784d76cef546ae4` (open/draft/unmerged).
- Exact-head pull-request run [#45551202442](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45551202442) — **success**.
- Python 3.11.18 / SQLite 3.46.1: schema v2 25/25; lifecycle 21/21; allocation validation 16/16; atomic allocation 13/13; settlement store 22/22; receiver 13/13 = **110/110**.
- Python 3.13.18 / SQLite 3.46.1: the same six suites = **110/110**.
- Combined: **220/220 successful test executions** across the two interpreters. Both jobs and all 12 test steps passed on the exact current PR head.

The earlier expanded run at #150 head `83f9a789eb0e7fc869de3a45041c2336c6b3595c` also passed, then the PR branch synchronized with the newest #149 base and inherited its sparse test workflow. The current result is stronger because it ran on the rebased PR head as a `pull_request` event, rather than relying solely on a push event.

### Independent-review gate disposition

The main-branch `Workstream A immutable AI review` workflow is not a valid reviewer for this reservation chain. Its trusted-base workflow is restricted to a fixed 25-file Workstream A allowlist and runs only when a non-draft PR targets `main` and carries the `workstream-a-review` label. PRs #149 and #150 are draft child-branch PRs, and reservation files are outside that allowlist. The skipped `pull_request_target` job is therefore **not** evidence of review; neither should it be forced to review these files.

No approved independent reservation-stack reviewer has completed acceptance. The next acceptance gate must be a separately scoped, immutable review of exact head `8551e596...`, with an explicit allowlist of the reservation/settlement modules and their tests, no protected paths, no code execution, no secrets disclosure, and a review result anchored to the exact SHA. Until that is done, security acceptance remains PENDING.

### Current branch disposition

- PR #147 — tracker addendum, open/draft/unmerged, base `main`.
- PR #149 — inbox TEMP-trigger/receipt-integrity hardening, open/draft/unmerged.
- PR #150 — legacy SELL fail-closed gate plus integrated reservation settlement and full six-suite workflow, open/draft/unmerged; exact-head focused CI PASS.
- PR #151 and #152 — closed as superseded duplicates; their branches remain, no deletion.
- `main` remains `0426e1ecd5bd01913a568272792c355c4b7059c7`. No PR merge or deployment occurred.

### Readiness remains constrained

The six-suite CI pass does not certify the full repository or production use. Still pending: exact-head independent adversarial review, crash/power-loss/restore and malformed database drills, v1→v2 migration design and synthetic-copy validation, remote receiver authentication/transport, external idempotent effect semantics, broader risk controls, PAPER activation approval, and cost-adjusted multi-market profitability evidence. Install readiness remains **NOT READY**; trading readiness remains **NOT READY**; PAPER **ON HOLD**; LIVE **DISABLED / ABSENT**; profitability **NOT ESTABLISHED**; overall project completion **UNRATED**.
