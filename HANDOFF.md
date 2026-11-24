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

1. PR #106 policy primitive is NOT wired into `RiskGateway`. Trusted exposure marks and owner-approved exposure policy must become mandatory gateway inputs, inaccessible to strategy agents.
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
- Current source head at handoff update: `31946a535af24d0013bbff84b8b941d253e95772`
- Draft/open/unmerged; stacked on PR #106. Do not merge without separate approval.

Added `crypto_engine/tmm_core/policy_gateway.py` with `PolicyEnforcedRiskGateway`. It requires exact-True owner authorization of the exposure policy at create and restore, reads the complete authoritative holdings/equity, requests marks for the full holdings market set, rejects incomplete mark coverage, applies the exposure/liquidity policy, then passes only permitted proposal deltas to the existing session-loss gateway. The existing gateway still independently re-reads holdings/equity and persists/anchors its session-risk journal.

Added `crypto_engine/tests/test_policy_gateway.py` covering per-market cap enforcement, stale and missing marks, agent override attempts, unknown markets, owner-policy approval, and agent-inaccessible policy parameters. Added `crypto_engine/POLICY_GATEWAY.md` documenting interfaces, flow and limitations.

**Verification is pending.** No exact-head tests have been run, no GitHub Actions runs/checks exist for this head, and no independent review is claimed. Do not treat the wrapper as production-ready.

Important security limitation: Python private attributes are not an isolation boundary. The raw gateway and trusted dependencies must remain inside a trusted composition root; strategy agents require separate process/container isolation and capability-limited IPC. Production ledger, marks/liquidity, owner policy/reset and independent external audit-anchor services remain unimplemented. The wrapper does not create a broker or paper runner. PAPER remains on hold and LIVE remains disabled.
