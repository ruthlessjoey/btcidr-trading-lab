# Twin Money Maker — Complete engineering handoff

Repository: `ruthlessjoey/btcidr-trading-lab`

## Current source stack

- PR #104 — shared multi-market session-loss guard; head `5eb9384021364e3218fb536c9086972a5657d4a1`.
- PR #105 — fail-closed account-risk gateway stacked on #104; head `97711de52431763aa868794bfef71cf8581adcbc`.
- PR #106 — exposure and liquidity policy primitive stacked on #105; exact source head before this handoff document: `9dbf39c57ec7d92198a97ae4c236c27f2e580d22`.
- Branch: `security/multi-market-exposure-policy-2026-11-24`.
- All three PRs are draft/open/unmerged. Do not merge without explicit owner approval.

## Architecture

- PR #104 provides a thread-safe session loss latch, blocks new BUY exposure after the threshold, caps SELL exits to inventory, reserves concurrent exits, hash-chains the journal, restores state from the journal, and requires an audited reset. The multi-market backtest routes proposals through this guard.
- PR #105 provides the account proposal/reset facade. It obtains equity and holdings from an injected ledger, requires owner-approved session policy and reset verification, persists snapshots transactionally in SQLite, requires an external audit anchor at startup, and locks after persistence/anchor failures.
- PR #106 adds an offline Decimal-based policy primitive for shared gross, per-market, aggregate base-asset, aggregate quote-asset, and per-market executable-liquidity caps. It requires fresh marks and caps sells to actual holdings.

## Roles and authority

- Owner / Commander: owns scope, risk-policy approval and reset approval; coordinates specialists. The Commander does not self-certify evidence.
- Architecture / Integration: owns stable interfaces, shared-account semantics, market identity and integration design.
- Risk / Security: challenges risk limits, loss-stop semantics, inventory invariants, persistence, audit anchoring and bypass resistance.
- Data / Market: validates point-in-time marks, FX, market lifecycle, liquidity, provenance and venue-specific constraints.
- Strategy / Research: generates research proposals only. No direct ledger, risk-state, broker, order or reset access.
- Test / QA: exact-head tests, adversarial cases, regression tests and reproducibility evidence.
- Independent Reviewer: attempts bypasses and reviews evidence independently; cannot approve its own implementation.
- Release / Documentation: tracker accuracy, reproducible installation, evidence manifests and ZIP integrity.

The Commander coordinates; specialists challenge each other; evidence decides. Agents must never be able to approve their own risk policy, reset a halt, modify authoritative inventory, or access execution interfaces.

## Non-negotiable safety

- Spot-only, long-only. No shorts, leverage, margin or derivatives.
- Multi-market PAPER account remains ON HOLD. Do not activate it. LIVE remains disabled/absent.
- No real-money orders, deposits, withdrawals, payments, funding, credentials, private exchange APIs, wallets or private account data.
- No provider request unless the exact host, path, method, symbols and interval are currently approved. No Tokocrypto `.com` endpoints.
- Protected paths require separate approval: `P1/`, `signal/data/`, copies of `signal/`, `markets/risk/`, `validator.py`, `report.py`, and protected Workstream B artifacts.
- Do not merge PRs #104, #105, #106 or their base PRs without explicit approval.
- MEME_INTEL remains separate; integration requires independent readiness and separate approval.

## Verification

The PR #106 source head `9dbf39c57ec7d92198a97ae4c236c27f2e580d22` was downloaded from GitHub and tested with Python 3.11.2:
- Full `crypto_engine` unittest discovery: 70 passed, 0 failed.
- `python -m compileall -q tmm_core tests`: passed.
- GitHub source archive integrity: passed.
- No network, market-provider, exchange, account, wallet or order requests were made.
- GitHub Actions runs for that exact SHA: none returned by the connected GitHub workflow-run lookup.

This test evidence applies to the exact SHA above. After this handoff document commit, rerun tests against the new branch head before citing exact-head verification for the updated branch.

## Critical remaining blockers

1. PR #107 adds a proposal-only `PolicyEnforcedRiskGateway` wrapper around `RiskGateway`; production composition must expose only this facade to strategy agents. The raw gateway still exists as a lower-level class and the isolated agent runtime/composition root is not yet implemented.
2. Production authoritative multi-market ledger/equity/holdings implementation is absent; PR #105 currently uses injected protocols and test doubles.
3. Production owner-policy and reset authorization services are absent.
4. Production external audit-anchor service is absent; the interface is injected.
5. Agent runtime/process isolation and end-to-end proof that agents cannot bypass the gateway are absent.
6. Broker-free multi-market PAPER simulation and realistic market-specific execution/liquidity modeling remain incomplete.
7. Independent red-team/security review and exact-head GitHub CI are outstanding.
8. Profitability is not established. Any profitability work must use preregistration, realistic costs/impact, point-in-time data, untouched holdouts, multiple-testing control and independent reproduction. No win-rate or profit claim without this evidence.

This branch is an engineering source handoff, NOT an install-ready trading system, NOT permission to advance PAPER, and NOT evidence of profitability. Overall project completion remains UNRATED.


## PR #107 — trusted exposure enforcement integration (24 Nov 2026)

- PR: https://github.com/ruthlessjoey/btcidr-trading-lab/pull/107
- Branch: `security/exposure-gateway-enforcement-2026-11-24`
- Current source head before this handoff refresh: `e505aef3eab93cda213092a23fce40ed829ad97f`
- Draft/open/unmerged; stacked on PR #106. Do not merge without separate approval.

Added `crypto_engine/tmm_core/policy_gateway.py` with `PolicyEnforcedRiskGateway`. It requires exact-True owner authorization of the exposure policy at create and restore, reads the complete authoritative holdings/equity, requests marks for the full holdings market set, rejects incomplete mark coverage, applies the exposure/liquidity policy, then passes only permitted proposal deltas to the existing session-loss gateway. The existing gateway still independently re-reads holdings/equity and persists/anchors its session-risk journal.

Added `crypto_engine/tests/test_policy_gateway.py` covering per-market cap enforcement, stale and missing marks, agent override attempts, unknown markets, owner-policy approval, agent-inaccessible policy parameters, and the absence of public settlement/reset methods on the strategy facade. The facade exposes only `propose` and `is_halted`; settlement and reset remain reserved for trusted future services. Added `crypto_engine/POLICY_GATEWAY.md` documenting interfaces, flow and limitations.

**Offline verification on the current code snapshot (Python 3.11 runtime):** 82/82 `crypto_engine` unit tests passed; `security_check.py` passed after narrowing its static rule to permit only the explicit local `sqlite3.connect` persistence call; `compileall` passed. The test run used the uploaded PR #107 branch archive plus the latest changed source/test/checker edits fetched from GitHub and applied locally; it is not a GitHub Actions run. Added SQLite storage checks for private parent-directory permissions, symlinked parent components, symlinked DB files and hard-linked DB files. No Actions acceptance or independent security review is claimed. Do not treat the wrapper as production-ready.

Important security limitation: Python private attributes are not an isolation boundary. The raw gateway and trusted dependencies must remain inside a trusted composition root; strategy agents require separate process/container isolation and capability-limited IPC. Production ledger, marks/liquidity, owner policy/reset and independent external audit-anchor services remain unimplemented. The wrapper does not create a broker or paper runner. PAPER remains on hold and LIVE remains disabled.


Verification note: The 82-test/static/compile results above are a local replay against the uploaded PR #107 branch archive with latest branch file edits applied. They do not establish GitHub CI status for the final branch SHA. The workflow run observed for the earlier PR #107 head was skipped, not passed.


## PR #107 follow-on storage hardening

The lower-level SQLite risk-state store now requires a private, current-user-owned parent directory on POSIX; rejects symlinked parent path components, symlinked/non-regular database files and hard links; creates/enforces a mode-0600 database; enables SQLite FULL synchronous commits, foreign keys, trusted-schema disablement and DELETE journaling. Four tests cover shared directory, symlink, symlinked-parent and hard-link rejection. The policy-enforced strategy facade exposes only `propose` and `is_halted`; it does not expose sell settlement or reset. Latest local replay: 82 tests passed, static check passed, compile passed. This is defense-in-depth, not a substitute for OS isolation, production trusted services or independent audit anchoring.


## Follow-on milestone — offline synthetic portfolio ledger (24 Nov 2026)

PR #108 adds `tmm_core.offline_portfolio.SyntheticPortfolioLedger` and focused tests. It provides thread-safe Decimal cash/inventory accounting for a registered multi-market universe, idempotent synthetic fills, strict BUY cash and SELL inventory checks, exact quote-currency matching, complete fresh mark requirements for equity, account scoping and a hash-chained in-memory audit log. This is a synthetic test/research ledger only. It has no network, exchange, broker, account, wallet, order, PAPER or LIVE capability. It is not yet composed into `PolicyEnforcedRiskGateway`; the next step is a trusted offline settlement/simulation controller, with agent access remaining proposal-only.


## Follow-on milestone — broker-free settlement controller (24 Nov 2026)

PR #109 adds `tmm_core.offline_settlement.OfflineSettlementController`, a trusted offline composition-root component. It requests authorization from an injected proposal-only risk client, requires exact market coverage, validates timestamp-matched synthetic OHLCV bars, applies explicit per-market quantity steps, price ticks, fees, adverse half-spread/slippage and bar-volume participation limits, applies synthetic fills to the in-memory portfolio ledger, then settles SELL reservations using authorized versus actually filled quantities, including partial and zero fills. This is a deterministic bar-level approximation, not a production broker or order-book model. It has no network, provider, exchange, account, wallet, order, PAPER or LIVE capability. The controller must remain outside strategy-agent processes. Exact-head full-suite tests and independent review remain required.


## Follow-on hardening — settlement batch replay guard (24 Nov 2026)

PR #110 adds a trusted `batch_id` to the offline settlement controller. Duplicate or previously attempted batch IDs are rejected before a second proposal-gateway call; fill IDs are derived from the batch ID. Bars and execution rules are prevalidated before the stateful risk call. Aggregate BUY cash and SELL inventory are preflighted before ledger mutation. A concrete undefined Decimal alias was corrected by importing the ledger's `D` alias.

Replay protection is in-memory only and does not survive restart. Failed attempts burn their batch IDs; they require trusted reconciliation before a new batch. Ledger mutation and the SELL settlement callback are not one durable transaction: callback/process failure can leave partial state. This PR does not claim atomic batch execution or production-grade durable idempotency. Focused tests and exact-head full-suite/CI/independent review remain pending.


## Follow-on milestone — durable offline batch journal (24 Nov 2026)

PR #111 adds `SQLiteBatchJournal` and makes it mandatory for `OfflineSettlementController`. Batch claims and completed results are stored in SQLite using immediate transactions and FULL synchronous commits. Each batch ID is bound to a canonical hash of proposals, bars, timestamp and execution rules. Identical completed replays return the stored result without calling the proposal gateway again; ID reuse with different payload is rejected.

The journal is bound to a runtime identity. A new process/runtime cannot automatically resume it: it fails closed and requires trusted reconciliation. An interrupted `PROCESSING` record also blocks replay. This is deliberate because the portfolio ledger remains in-memory; replaying a completed result into a fresh ledger would create inconsistent accounting. The journal and ledger/SELL callback are not one atomic transaction. Durable portfolio state, recovery tooling and atomic cross-component settlement remain outstanding.

Local verification of the uploaded source snapshot after these changes: 103 crypto_engine tests passed; static boundary check passed for 17 modules; compileall passed. Runtime was Python 3.13.5. These results are local on the uploaded PR #110 archive with the PR #111 changes applied, not GitHub CI or exact branch checkout. Python 3.11 and independent review remain pending.
