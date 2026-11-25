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


## 25 November — receiver hardening and legacy SELL closure (PRs #149–#150)

Live-refreshed state:
- PR #149 head: `8db0cd10649e169bb19e934d40f0e760c5b8b0be`, stacked on PR #148 head `ee6387fbb5f721a509a38b971dc3db35452b0c73`.
- PR #150 head: `8551e596fab6d3c649b00281a784d76cef546ae4`, stacked on PR #149 head `8db0cd10649e169bb19e934d40f0e760c5b8b0be`.
- Both PRs remain draft/open/unmerged. The ancestry comparison for #150 is 15 commits ahead / 0 behind #149.

### PR #149 — inbox and receipt hardening

- Reject TEMP triggers attached to `main.reservation_inbox` by inspecting `temp.sqlite_master`.
- On idempotent replay, verify the stored receipt against the deterministic receipt recomputed from canonical payload; changed stored receipts fail closed.
- Include `account_id` in pending sender outbox rows so the trusted delivery worker can construct the canonical receiver payload.
- Fix test coverage for receiver-database receipt tampering and exercise ambiguous response retry, durable receiver connection restart and two concurrent workers.

Exact-head CI run [45550760669](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45550760669):
- Python 3.11.18 / SQLite 3.46.1: 13/13 receiver tests passed.
- Python 3.13.18 / SQLite 3.46.1: 13/13 receiver tests passed.
- Reviewer job was skipped, not passed. No authenticated remote receiver or external network transport is implemented.

### PR #150 — eliminate the legacy SELL bypass

- Fail closed on every SELL when reservation schema v2 is missing or does not match the exact current schema.
- Keep BUY-only batches available on legacy v1 settlement databases.
- Require exact per-fill allocations when reservation v2 is enabled.
- Keep batch status pending until both legacy settlement and reservation outboxes are acknowledged.
- Correct regression fixtures so duplicate-ID, multi-reservation, BUY-allocation and expiry tests exercise their intended conditions.

Exact tested tree: `7b067d48540eb860535b34c5f361301827b89ccc`. It is the tree of current PR #150 head `8551e596fab6d3c649b00281a784d76cef546ae4`; the isolated workflow run used its first-parent commit `cbced35c542eeae67fd74074b0deb720abd14c50` before the ancestry-sync merge commit, with identical tree contents.

GitHub Actions run [45551184494](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45551184494):
- Python 3.11.18 / SQLite 3.46.1: schema 25 + lifecycle 21 + allocation preflight 16 + atomic allocation 13 + settlement store 22 + receiver 13 = **110/110 passed**.
- Python 3.13.18 / SQLite 3.46.1: **110/110 passed**.
- The workflow used sparse checkout of only the named unprotected settlement source and test files. It did not test the whole repository.
- Reviewer job remains skipped. Multiprocess crash/restore drills, independent adversarial acceptance, migration tests and remote receiver implementation remain pending.

### PR #153 — migration acceptance plan

- Documentation-only draft PR from main at `0426e1ecd5bd01913a568272792c355c4b7059c7`.
- Defines exact v1, earlier-v2 and current-v2 source classifications, read-only preflight, historical row preservation, expiry evidence, v1 inventory bootstrap, backup/restore, reconciliation and independent acceptance.
- No migration code or execution is included or authorized.

### Current readiness disposition

- Legacy v1 and earlier-v2 database SELLs remain intentionally blocked until migration/bootstrap is separately implemented, reviewed and approved.
- No database was migrated or touched.
- Install readiness: **NOT READY**.
- Trading readiness: **NOT READY**.
- PAPER activation: **ON HOLD**.
- LIVE trading: **DISABLED / ABSENT**.
- Profitability / high win-rate evidence: **NOT ESTABLISHED**.
- Overall whole-project completion: **UNRATED** pending approved scope and evidence criteria.

The six-suite result is meaningful evidence for the tested reservation/settlement modules only; it is not a whole-project acceptance result, profitability result or production trading authorization.


## Current latest candidate head — acknowledgment hardening and 222-test pass (25 November 2026)

The previous 220-test result at #150 head 8551e596... has been superseded by later sender/receiver acknowledgement hardening. The current live #150 branch is:

- PR #150 current head: 8b2cf3a7065c5603d0409d5ac6e42a40754d010b.
- Base: current PR #149 head 8db0cd10649e169bb19e934d40f0e760c5b8b0be.
- Exact pull-request run [#45551918569](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45551918569): **success**.
- Python 3.11.18 / SQLite 3.46.1: schema 25/25, lifecycle 21/21, allocations 16/16, atomic allocations 13/13, settlement 22/22, receiver 14/14 = **111/111**.
- Python 3.13.18 / SQLite 3.46.1: the same suite counts = **111/111**.
- Total **222 successful test executions**. Both matrix jobs and all 12 test steps passed.

### New current-head hardening
Three new commits added:
- revalidate the persisted reservation outbox row at acknowledgment time against the canonical recomputed payload and the hash observed before the receiver callback;
- bind the acknowledgment update to the exact expected SHA-256 hash, rejecting sender state mutation during delivery;
- reject malformed stored reservation payloads closed.

The receiver test module now has 14 tests, including:
- mutate the sender outbox market_id from BTC/USDT to ETH/USDT during the trusted receiver callback; receiver stores the original payload, but sender acknowledgment fails because persisted payload no longer matches the original hash; sender row stays PENDING for reconciliation/retry;
- a tampered stored payload hash prevents the receiver callback from being invoked;
- reject a receiver receipt not bound to the canonical payload.

The immediately preceding head cf73a354... failed four settlement-store tests because they called the hardened acknowledgment API without its required expected_payload_sha256. Subsequent test commits corrected those calls and added tamper coverage. Preserve that failure as history; only the current exact head is passing.

The pass remains focused on six settlement/reservation modules. It does not certify the entire repository, an independent security review, production external effect, real database migration, crash/power-loss/restore, installation/trading readiness or profitability.

## Q0.8 specialist review — separate outstanding blocker

PR #60 latest head remains e8674dbfe3efd2339ddb028484362f9466f7b058 (open/draft; base historical M6 cd451972e3a641ad6fa78e64abf3968655a4b82a). Offline Q0.8 security regression workflow run [#45055081357](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45055081357) passed at that head.

The latest immutable 19-role review run [#45056820308](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45056820308) failed before any role review started:
- syntax compilation passed;
- synthetic policy smoke test passed;
- immutable PR head validation and snapshot completed;
- review stopped with `Scoped review diff exceeded limit: chars=230101 limit=224000`;
- no checkpoint file existed; the artifact upload reported no files, and there is no valid checkpoint to resume;
- the OpenRouter 429 quota/resume path was **not** reached; this is a diff-size blocker, not a rate-limit failure;
- do not resume the old run 44337003905 or assume this failed run can resume.

Next safe task: inspect the unprotected immutable reviewer and workflow to design an exact-SHA scoped/chunked diff review under a fixed resource ceiling. Do not inspect protected paths. Do not dispatch another workflow or change model/provider secrets without the user's separate operational approval. The offline regression pass and the 19-role review are separate gates.

## Current state in brief

- main: 0426e1ecd5bd01913a568272792c355c4b7059c7; no merge.
- PR #149: 8db0cd10649e169bb19e934d40f0e760c5b8b0be, draft/open; receiver CI passed 13/13 per Python version.
- PR #150: 8b2cf3a7065c5603d0409d5ac6e42a40754d010b, draft/open; latest full six-suite CI passed 111/111 per Python version.
- PR #147: documentation tracker, draft/open; addendum updated to record this current state.
- PR #151/#152: closed as duplicates/superseded; branches retained.
- Independent reservation-stack security acceptance: **PENDING**.
- Q0.8 19-role specialist review: **INCONCLUSIVE / BLOCKED BEFORE REVIEW**.
- Install readiness: **NOT READY**; PAPER **ON HOLD**; LIVE **DISABLED / ABSENT**.
- BTC/IDR profitability/high win rate: **NOT ESTABLISHED**.
- Overall project completion: **UNRATED**.


## 25 November — final sender acknowledgement binding and exact-head CI refresh

This supersedes the earlier PR149/150 verification counts above; those earlier counts are retained as historical test runs.

### PR #149 — final receiver/sender acknowledgement hardening

- Current branch head: `6a3c91ea9164e5cfcac39390aab2f54e4a5ac185`.
- Stacked on PR #148 head `ee6387fbb5f721a509a38b971dc3db35452b0c73`: 16 commits ahead / 0 behind.
- Receiver inbox rejects TEMP triggers attached to the main inbox; idempotent replay validates the deterministic receipt.
- Sender pending-row query includes the account identity required to reconstruct the canonical receiver payload.
- The sender ACK boundary now reloads the full outbox record inside `BEGIN IMMEDIATE`, recomputes the canonical payload hash and deterministic receipt, checks both against the delivered payload evidence, and conditionally acknowledges only the unchanged pending row.
- A callback-time sender-row mutation regression proves a changed sender payload stays pending instead of being acknowledged.

Exact-head Actions run [45552657350](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45552657350):
- Python 3.11.18 / SQLite 3.46.1: 21/21 settlement-store and 14/14 receiver tests passed.
- Python 3.13.18 / SQLite 3.46.1: 21/21 settlement-store and 14/14 receiver tests passed.
- The workflow uses sparse checkout of only the named unprotected settlement/receiver source and test files.
- Reviewer job is skipped, not passed.

### PR #150 — legacy SELL bypass and integrated settlement closure

- Current branch head: `3bffd6bc32ff72072c24ec94ef2c642e5f7104e4`.
- Current PR #149 base: `6a3c91ea9164e5cfcac39390aab2f54e4a5ac185`.
- Ancestry comparison: 24 commits ahead / 0 behind.
- Legacy v1 databases remain BUY-only; every SELL requires the full verified current reservation schema v2 and exact per-fill allocation.
- Earlier-v2 schemas without the current expiry/lifecycle DDL fail closed.
- Dual-outbox completion requires both settlement and reservation acknowledgements.
- The sender ACK payload binding from PR149 is included in the current candidate tree.
- The workflow now runs one settlement-store suite (no duplicate invocation) plus schema, lifecycle, allocation, atomic-allocation and receiver suites.

Exact-head Actions run [45552712044](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45552712044):
- Python 3.11.18 / SQLite 3.46.1: schema 25 + lifecycle 21 + allocation preflight 16 + atomic allocations 13 + settlement store 22 + receiver 14 = **111/111 passed**.
- Python 3.13.18 / SQLite 3.46.1: the same six suites = **111/111 passed**.
- Sparse checkout contains only named unprotected reservation/settlement source and test files; workflow permissions are contents:read and checkout credentials are not persisted.
- Reviewer job is skipped, not passed. These tests are not full-repository acceptance, migration verification, remote receiver verification, or crash/restore acceptance.

### Next release blockers and readiness

1. Obtain an independent adversarial review of PRs #139–#150 against exact current heads and retain a signed/reproducible evidence packet.
2. Design and test a read-only preflight for v1 / earlier-v2 / current-v2 databases on disposable copies.
3. Implement a separately reviewed, non-destructive migration and explicit v1 inventory bootstrap. Do not invent expiry timestamps or auto-authorize holdings.
4. Run process-level concurrency, crash injection, backup/restore, corrupted DB, outbox replay and resource-exhaustion drills.
5. Implement a separately reviewed authenticated remote receiver only after defining its real business effect and trust boundary.
6. Keep strategy agents proposal-only and the settlement DB/receiver callback private to the trusted composition root.
7. Begin preregistered profitability research only after point-in-time data rights/coverage, realistic fees/spread/slippage/impact/liquidity, holdouts and multiple-testing controls are independently accepted.

### Team roles for handoff

- **Commander / coordinator:** workstream sequencing, evidence register, safety guardrails, release gates and handoff accuracy.
- **Architecture specialist:** multi-market boundaries, interfaces, state transitions, transaction sequencing and system integration.
- **SQLite persistence specialist:** exact DDL, transactions, indexes, locking, schema migration, audit and outbox durability.
- **Security reviewer:** adversarial schema/data review, TEMP/main shadowing, TOCTOU, malformed payloads, replay, identity and privilege boundaries.
- **Reliability specialist:** Python-version CI, multiprocess concurrency, crash/restart, backup/restore, resource bounds and recovery drills.
- **Ledger/accounting specialist:** fill/reservation/inventory reconciliation, long-only constraints, fees, balances, settlement and historical preservation.
- **Quant research specialist:** preregistered strategies, realistic cost modeling, out-of-sample net profitability and high-win-rate measurement.
- **Independent acceptance reviewer:** separate pass/fail/inconclusive decision on immutable heads and evidence, not author-provided assertion.
- **Project owner:** approves protected access, data/provider scope, historical inventory bootstrap, migration manifest, PR merges, PAPER activation and any later LIVE decision.

### Current disposition

- PRs #149 and #150 remain open/draft/unmerged. PR #153 remains documentation-only/open/draft.
- No existing database was inspected, migrated or modified.
- Install readiness: **NOT READY**.
- Trading readiness: **NOT READY**.
- PAPER activation: **ON HOLD**.
- LIVE trading: **DISABLED / ABSENT**.
- Profitability / high-win-rate evidence: **NOT ESTABLISHED**.
- Overall full-project completion: **UNRATED** pending owner-approved scope, weights and evidence criteria.

The 111-test result is scoped to the isolated candidate settlement/reservation modules. It is not evidence of a profitable strategy, complete product, production deployment or trading authorization.

## 25 November — owner-approved Tokocrypto boundary correction (PR #154)

This update supersedes the previous provider-policy count and earlier PR149/150 verification heads wherever the counts below supersede them.

### Security findings

Static inspection of the candidate repository found two mismatches with the current owner-approved market-data boundary:

1. The crypto_engine provider-policy allowlist, test fixture, README, data-source approval matrix and root CLAUDE.md treated https://cloudme-toko.2meta.app/api/v1/klines as approved while denying https://www.tokocrypto.site/api/v3/klines.
2. The legacy root providers.build('tokocrypto') constructed a generic Binance-style source that used BTCUSDT and could request server-time; the legacy probe.py diagnostic also requests symbol metadata. Both are outside the current approved unauthenticated BTCIDR candles-only scope.

### PR #154 correction

- PR #154: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/154.
- Branch head: 78724489bc679e4b3ad5e6e613e4b2987fd516fc.
- Base: PR #150 head df6bcc41d97b5e5640ce1c20f10d88e4c0434e19.
- Comparison: 15 commits ahead / 0 behind; 10 changed paths.
- The offline crypto_engine policy now permits only the exact https://www.tokocrypto.site/api/v3/klines host/path, unauthenticated GET, BTCIDR symbol and approved request fields. The older 2meta host/path, Tokocrypto .com, wrong paths, server-time, metadata, unapproved symbols and authentication are rejected.
- The legacy root Tokocrypto adapter is disabled at both entry points: providers.build('tokocrypto') refuses construction, and fetcher.Source rejects Tokocrypto identities and Tokocrypto hosts regardless of caller-supplied source name. This closes the simple renaming bypass.
- Root market-data-check.yml remains blocked. No root runner, protected import closure, network request, DNS lookup, Tokocrypto endpoint or live market data was used.

### Exact-head verification

- Full unprotected crypto_engine/tests matrix: https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45555163021.
  - Python 3.11.18 / SQLite 3.46.1: 218/218 passed.
  - Python 3.13.18 / SQLite 3.46.1: 218/218 passed.
  - Sparse checkout: 22 crypto_engine/tmm_core source files plus 18 crypto_engine/tests files. The suite is synthetic/offline; the Tokocrypto policy tests validate request structure only and do not submit a request.
- Legacy root adapter containment: https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45555162962.
  - Python 3.11.18: 4/4 passed.
  - Python 3.13.18: 4/4 passed.
  - Sparse checkout: fetcher.py, providers.py and one isolated root adapter guard test.
- Both runs are exact-head evidence at 78724489bc679e4b3ad5e6e613e4b2987fd516fc. The advisory immutable-review workflow is skipped, not passed.

### Latest reservation / settlement evidence remains

- PR #149 head: 104756a8f4978f9e81bf40928902f419ab61b528; run 45553924899: Python 3.11.18 and 3.13.18 each passed 23 settlement-store + 16 receiver tests. Includes deterministic receipt, TEMP-trigger, sender ACK payload binding and v2 restart recovery.
- PR #150 head: df6bcc41d97b5e5640ce1c20f10d88e4c0434e19, 28 ahead / 0 behind PR #149; run 45554067988: Python 3.11.18 and 3.13.18 each passed all six suites, 115/115.
- PR #154 is stacked after PR #150 and remains open/draft/unmerged.

### Current disposition

- Tokocrypto public retrieval remains unperformed. The current allowed representation is the exact .site/api/v3/klines BTCIDR candle-only request; no server-time, symbol metadata, .com, 2meta or other host/path is authorized.
- Legacy root Tokocrypto runner remains disabled; a dedicated candles-only live integration is not implemented or activated.
- Install readiness: NOT READY; trading readiness: NOT READY; PAPER activation: ON HOLD; LIVE: DISABLED / ABSENT.
- Profitability / high-win-rate evidence: NOT ESTABLISHED.
- Whole-project completion: UNRATED pending owner-approved scope, weights and evidence criteria.

The 218 + 4 results are isolated offline engineering evidence. They do not establish endpoint response compatibility, full repository acceptance, profitable strategies, production deployment or trading authorization.
## 25 November — final Tokocrypto URL hardening and legacy adapter containment

This supersedes the earlier PR154 218-test count and records the final URL parser hardening.

- PR #154 head: 81be796269bd473ee767335b16cf3bcab4974f4e; base PR #150 head df6bcc41d97b5e5640ce1c20f10d88e4c0434e19; comparison 17 commits ahead / 0 behind.
- The offline crypto_engine policy now permits only unauthenticated GET to the exact owner-approved https://www.tokocrypto.site/api/v3/klines BTCIDR candle endpoint; it rejects the 2meta host/path, Tokocrypto .com, wrong paths, authentication/custom headers, other symbols and malformed query requests.
- URL validation now also rejects whitespace/control normalization, fragments (including empty fragments), non-ASCII URLs, URLs over 2,048 characters, too many query fields, duplicate keys, Unicode decimal digits and oversized timestamp/limit integers.
- Legacy root Tokocrypto access is blocked at both entry points: providers.build('tokocrypto') raises; fetcher.Source rejects Tokocrypto identity or Tokocrypto hosts, including when renamed by callers. Root market-data-check workflow remains blocked.
- Full unprotected crypto_engine suite exact-head run [45555538730](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45555538730): 219/219 on Python 3.11.18 and 219/219 on Python 3.13.18; SQLite 3.46.1.
- Isolated legacy root adapter guard run [45555538736](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45555538736): 4/4 on Python 3.11.18 and 4/4 on Python 3.13.18.
- Reviewer run 45555536008 was skipped, not passed. No Tokocrypto API request, DNS lookup, server-time, symbol-metadata request or live candle retrieval was performed.

Current PR chain remains candidate-only: PR149 head 104756a8f4978f9e81bf40928902f419ab61b528; PR150 head df6bcc41d97b5e5640ce1c20f10d88e4c0434e19; PR154 head 81be796269bd473ee767335b16cf3bcab4974f4e. All remain open/draft/unmerged.

Readiness remains unchanged: install/trading NOT READY; PAPER ON HOLD; LIVE DISABLED / ABSENT; profitability/high-win-rate NOT ESTABLISHED; overall completion UNRATED. The 219 + 4 runs are isolated offline evidence, not production acceptance or proof of endpoint compatibility.


## 26 November — account audit baseline and outbox delivery integrity follow-up

This section supersedes the previous PR #172 test count and adds the current exact-head state. All items below remain draft candidates; no PR was merged and protected `main` remains `0426e1ecd5bd01913a568272792c355c4b7059c7`.

### PR #173 — require the initial account audit event

- PR: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/173
- Exact head: `e6eaccc917695c48fb70d02e5a5ce764b9d11498`; base PR #172 head `eefb9305f3749fa1214e7040776c300771399bff`.
- Finding: PR #172 created an `ACCOUNT_INITIALIZED` audit event, but a database with its sole initial audit row deleted still had an empty hash chain that verified successfully. The opening-cash baseline could therefore disappear before the first fill.
- Change: new databases persist an `account_initialization_audit=required-v1` metadata policy marker; the verifier rejects a missing initialization event or an altered marker value.
- Exact-head Actions run [45669896171](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45669896171): Python 3.11.18 / SQLite 3.46.1 passed settlement-store 48/48 and receiver 16/16; Python 3.13.18 / SQLite 3.46.1 passed 48/48 and 16/16. Total 64 tests per Python version.
- The workflow skipped the separate reservation schema/lifecycle/allocation suites because the changed paths were the settlement store and its tests; do not describe this as the complete crypto_engine suite.
- PR remains open/draft/unmerged; independent adversarial review pending.

### PR #175 — modified policy-marker regression

- PR: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/175
- Exact head: `706cff1fb013406517de541138872f72fee361be`; base PR #173 head `e6eaccc917695c48fb70d02e5a5ce764b9d11498`.
- Test-only change: mutate the `account_initialization_audit` marker to an unknown value and assert that snapshot validation fails closed.
- Exact-head Actions run [45670551948](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45670551948): Python 3.11.18 / SQLite 3.46.1 passed settlement-store 49/49 and receiver 16/16; Python 3.13.18 / SQLite 3.46.1 passed 49/49 and 16/16. Total 65 tests per Python version.
- PR remains open/draft/unmerged; independent review pending.

### PR #174 — verify account and reservation integrity before outbox operations

- PR: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/174
- Current head: `d8033a68a8bcaa1896eabaf5978bd266fd45e6b1`; base PR #173 head `e6eaccc917695c48fb70d02e5a5ce764b9d11498`.
- Finding: `pending_outbox()` exposed pending settlement rows and `acknowledge_outbox()` accepted receipts without first reconciling the fill/account audit state. Snapshot and batch-creation checks did not cover these outbox paths.
- Proposed correction: share one account/reservation verifier; run it in a consistent read transaction before returning pending settlement outbox rows; run it under `BEGIN IMMEDIATE` before accepting a settlement-outbox acknowledgement; reuse it in snapshot.
- Added regressions for tampered account cash during pending-outbox read, tampered account cash during acknowledgement, and a tampered reservation expiry before either settlement-outbox operation.
- **Verification status: NOT VERIFIED.** No Actions run or check-run was present for exact head `d8033a68a8bcaa1896eabaf5978bd266fd45e6b1` at the time of this tracker update. Do not infer a pass from adjacent PR runs.
- PR remains open/draft/unmerged; exact-head CI and independent review pending.

### Current security interpretation and limitations

- The initialization policy marker detects deletion of the initial event while the marker remains present. It is not an external cryptographic anchor and does not protect against a party that deliberately rewrites both the audit table and its metadata marker. Do not describe SQLite's internal hash chain as tamper-proof against arbitrary database-file rewriting.
- Existing databases predating the marker are not retrofitted with fabricated opening-cash evidence. Their historical initial cash baseline remains unavailable and must be reconciled using separate evidence.
- No PR was merged, no protected path was accessed, no user database was inspected or migrated, and no network/provider/account/wallet/PAPER/LIVE activity occurred.
- Tokocrypto BTCIDR on the approved `.site/api/v3/klines` host remains UNVERIFIED / BLOCKED because official support material maps that MBX host family to non-IDR examples and maps BTCIDR to the currently prohibited NextMe/2meta host. No endpoint or DNS request was made. Do not switch host or symbol automatically.
- MEME_INTEL remains separate; integration still requires independent readiness and separate owner approval.

### Next priority queue

1. Obtain exact-head Python 3.11/3.13 CI for PR #174 and inspect all logs, test counts, warnings and failures. Keep the PR draft until verified.
2. Independently adversarially review PRs #149–#175 at immutable SHAs, including SQLite schema/trigger trust, audit truncation, opening-cash baselines, all read/write/replay/outbox surfaces, sender/receiver receipt binding and transaction rollback. Record PASS / FAIL / INCONCLUSIVE; skipped jobs are not reviews.
3. Continue synthetic-only crash/restart, lock-contention, backup/restore, corruption, truncation and resource-exhaustion tests. Do not touch existing user databases.
4. Preserve the Tokocrypto host/symbol block until the owner resolves the compatibility conflict and approves a precise lawful source contract.
5. Begin preregistered multi-market profitability research only with verified point-in-time rights/coverage, realistic fees/spread/slippage/impact/liquidity, untouched chronological holdouts, multiple-testing controls and independent reproduction.
6. Keep strategy agents proposal-only, PAPER activation ON HOLD and LIVE disabled/absent.
7. Refresh this tracker and the handoff ZIP after each major verified milestone.




## 26 November — reservation outbox, market registry and warning-clean verification

Protected `main` remains `0426e1ecd5bd01913a568272792c355c4b7059c7`. The following are candidate branches only; no PR is merged.

### PR #176 — verify account integrity before reservation outbox delivery

- Exact head: `7430b466a119c3b5c934cd9a33cce860b72f4378`; base PR #174 head `d8033a68a8bcaa1896eabaf5978bd266fd45e6b1`.
- Finding: reservation-specific outbox read/ack paths checked reservation state but did not first reconcile account cash/holdings to the fill audit.
- Adds shared account-state validation before reservation-outbox reads and acknowledgements.
- Exact-head run [45671378473](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45671378473): Python 3.11.18 and 3.13.18 each passed 53 settlement-store + 16 receiver tests (69 per version).
- PR remains open/draft/unmerged; independent review pending.

### PR #177 — close SQLite test connections and enforce ResourceWarning checks

- Exact head: `69555d54f97c703b8f8f6a3a2ad77e60fdddc2ab`; based on PR #174.
- Replaces sqlite3 transaction context usage in the settlement-store and receiver test modules with managed contexts that preserve commit/rollback and explicitly close each connection.
- Adds `-W error::ResourceWarning` to both isolated test commands.
- Exact-head run [45672004202](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45672004202): Python 3.11.18 and 3.13.18 each passed 51 settlement-store + 16 receiver tests. No actual `ResourceWarning:` or `Exception ignored` output remained in the final logs.
- PR remains open/draft/unmerged.

### PR #178 — duplicate SQLite connection cleanup

- Exact head: `e27bb6ba286a32f083467a87e92b38faba95b980`; based on PR #177.
- Its only diff repeats the final audit-count connection cleanup already present in PR #177 head `69555d54f97c703b8f8f6a3a2ad77e60fdddc2ab`.
- No unique implementation delta or separate exact-head verification is established. Treat as redundant/superseded; do not count it as additional progress.

### PR #179 — independent external audit checkpoint design proposal

- Exact head: `9be33784ecfb9ac0da5e50d4c0153d7f10f287ff`; documentation-only, based directly on protected main.
- Defines a signed, canonical external checkpoint record, independent signer/storage trust boundaries, durable local outbox/read-back protocol, rollback/fork handling, fail-closed behavior, backup/restore and required crash/adversarial tests.
- Correctly states that a hash chain stored only in a writable SQLite database is not an external trust anchor.
- This is a design proposal only. No signer, key storage, independent storage, network/cloud service or implementation is selected or added. Requires independent architecture/security review and owner decisions on storage, signing platform, checkpoint frequency and recovery authority.
- No code-test evidence is claimed.

### PR #180 — audit market registry identity

- Corrected exact head: `a1f8da5fec61df06c2dcecfea49d9c7439c47cc0`; based on PR #176 head `7430b466a119c3b5c934cd9a33cce860b72f4378`.
- Finding: fills were reconciled to registered market IDs, but the base/quote mapping behind a market ID was not independently reconciled. The public registration method rejected changes, but a direct SQLite row mutation could alter the mapping.
- New databases now record a market-registration audit policy marker. New market registrations append an account/market/base/quote-bound `MARKET_REGISTERED` event. The verifier compares the full market registry to its audit events and rejects changed/missing/duplicate/unexpected mappings.
- Existing pre-marker databases remain compatible and are not retroactively treated as if they had market-registration audit history.
- First run [45672520898](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45672520898) failed on the earlier head because the synthetic tampering test closed without committing its update. The test fixture was corrected.
- Corrected exact-head run [45672710073](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45672710073): Python 3.11.18 and 3.13.18 each passed 55 settlement-store + 16 receiver tests (71 per version).
- PR remains open/draft/unmerged; independent review pending.

### PR #181 — warning-clean tests on the market-audit/reservation-outbox stack

- Exact head: `8a63d7c3d831344d9444abe4f188fc84fa7e587c`; based on corrected PR #180 head `a1f8da5fec61df06c2dcecfea49d9c7439c47cc0`.
- Includes PR #176 reservation-outbox account checks and PR #180 market-registry audit.
- Applies managed connection closure to all 58 settlement-store test contexts and 16 receiver test contexts, including the final audit-count connection.
- Both isolated suites run with ResourceWarning promoted to an error.
- Exact-head run [45672928121](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45672928121): Python 3.11.18 and 3.13.18 each passed 55 settlement-store + 16 receiver tests (71 per version). The logs contain no actual ResourceWarning or ignored-connection output.
- PR remains open/draft/unmerged; independent review pending.

### Current interpretation and next priorities

- PR #173–#181 strengthen internal SQLite accounting, market identity, outbox and test resource handling. They are still candidate branches and have not been accepted into main.
- PR #177 is the warning-clean branch based on #174; PR #181 is the warning-clean branch that also includes #176 and #180. Prefer reviewing the complete #181 ancestry rather than treating sibling branches as one integrated result.
- PR #178 duplicates the final cleanup already in #177 and has no unique value.
- PR #179 is a design proposal; an external checkpoint cannot be implemented safely until the independent storage medium, signer/key-store, maximum unanchored window and recovery authority are decided and reviewed.
- The new market audit marker detects isolated market-row/event tampering while the marker or event history remains. It is not an external anchor against a coordinated rewrite of the entire SQLite database.
- Continue independent adversarial review of PR #149/#150/#154/#155/#157/#164/#165/#167–#181. Verify exact SHAs and distinguish code CI from independent acceptance.
- Continue crash/restore, concurrency, truncation, corruption and resource-exhaustion testing on synthetic disposable DBs only.
- No existing user DB was inspected or migrated. No provider endpoint, DNS, account, wallet, PAPER or LIVE activity occurred.
- Install/trading readiness: **NOT READY**. PAPER: **ON HOLD**. LIVE: **DISABLED / ABSENT**. Profitability/high win rate: **NOT ESTABLISHED**. Overall completion: **UNRATED**.




## 26 November — anchored market policy and registration fail-closed correction

### PR #182 — bind market policy to immutable initialization evidence

- Exact head: `2ac4984000106193681a8e7cf13c7a335830b68a`; base PR #181 head `8a63d7c3d831344d9444abe4f188fc84fa7e587c`.
- Finding: PR #180's market-registration metadata marker could be deleted, after which an unlogged market row could be inserted and the verifier could misclassify the new database as legacy.
- Fix: include `market_registration_audit=required-v1` in the initial ACCOUNT_INITIALIZED audit event; verify the initial-event policy and metadata marker agree; preserve compatibility for legacy initialization events that predate this policy.
- Adds regression deleting the marker and inserting an unlogged market.
- Exact-head run [45673574959](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45673574959): Python 3.11.18 and 3.13.18 each passed 56 settlement-store + 16 receiver tests (72 per version).
- PR remains open/draft/unmerged; independent review pending.

### PR #183 — registration-boundary verification (superseded)

- Exact head: `3f0f906a292a97d43daeab50c3c96507ace9d7e4`; base PR #181.
- Added shared account/market/reservation verification before register_market reads/writes.
- Exact-head run [45673775102](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45673775102): Python 3.11.18 and 3.13.18 each passed 56 settlement-store + 16 receiver tests.
- This branch did not include PR #182's stronger binding of the market policy to the initialization audit event. Its registration-verification changes and tests are included in PR #184. Treat #183 as superseded and do not count it as a separate integration candidate.

### PR #184 — combine policy anchoring and registration verification

- Current exact head: `bd16e0ffecb85acf825673aa92fafb251827fa2e`; base PR #182 head `2ac4984000106193681a8e7cf13c7a335830b68a`.
- Runs the shared account/market/reservation verifier inside `BEGIN IMMEDIATE` before register_market reads or writes.
- Adds tests proving registration rejects a tampered market mapping and a removed required market-policy marker.
- Also adds regressions for invalid account-initialization and market-registration policy marker values.
- Exact-head run [45674267447](https://github.com/ruthlessjoey/btcidr-trading-lab/actions/runs/45674267447): Python 3.11.18 and 3.13.18 each passed 60 settlement-store + 16 receiver tests (76 per version). No actual ResourceWarning or ignored-connection output.
- PR #184 includes the PR #181 warning-clean test setup, PR #180 market registry audit, PR #176 reservation outbox account verification, and the prior account/fill reconciliation chain.
- PR remains open/draft/unmerged; independent adversarial review pending.

### Duplicate and design-only PR disposition

- PR #178 repeats the final audit-count connection cleanup already present in PR #177 and #181. It has no unique implementation delta and is marked superseded in its body.
- PR #179 remains a separate documentation-only proposal for signed external audit checkpoints. It is not implemented. Signer/key-store, independent storage medium, checkpoint frequency and recovery authority remain undecided and require independent review and owner approval.

### Updated readiness and next priorities

- The #184 exact-head tests validate selected settlement-store and receiver modules only; they are not full repository acceptance.
- The market-policy marker is bound to the initial account audit event, which detects isolated marker deletion. It remains an in-database control, not an external trust anchor against coordinated rewriting of the entire SQLite database.
- Independent adversarial acceptance across PRs #149/#150/#154/#155/#157/#164/#165/#167–#184 remains pending.
- Continue synthetic-only crash/restart, concurrency, backup/restore, corruption, truncation, rollback/fork and resource-exhaustion tests.
- Review PR #179's external checkpoint design before any signer/storage implementation.
- No existing user database was inspected or migrated; no provider/DNS/account/wallet/PAPER/LIVE activity occurred.
- Install/trading readiness: **NOT READY**. PAPER: **ON HOLD**. LIVE: **DISABLED / ABSENT**. Profitability/high win rate: **NOT ESTABLISHED**. Overall completion: **UNRATED**.

