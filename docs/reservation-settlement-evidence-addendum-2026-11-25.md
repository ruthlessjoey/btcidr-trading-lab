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
