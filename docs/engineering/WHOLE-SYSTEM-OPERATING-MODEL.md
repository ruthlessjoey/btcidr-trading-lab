# AI Trading Lab — Whole-System Operating Model

**Status:** PROPOSAL — planning and governance only  
**Applies to:** `ruthlessjoey/btcidr-trading-lab`  
**Current tooling branch:** `chore/claude-engineering-tooling`  
**Trading mode:** Research first; PAPER only after separate safeguards and authorization; LIVE unavailable.

## 1. Repository strategy

Keep the operating model, repository skills, architecture decisions, and implementation together in this repository. Do not create a second "army" repository: it would split the source of truth, duplicate safety rules, and create version drift.

Create a separate repository only if a genuinely independent deployable service is later approved (for example, a public-data collector or dashboard), with its own threat model, credentials policy, CI permissions, and release gates. It must not become a route around this repository's controls.

This document is a plan. It does not authorize source changes, external requests, workflows, deployment, or trading.

## 2. The whole-system team

The existing 16 repository skills cover coordination, security, architecture, market-data integration, quantitative research, strategy validation, risk, portfolio accounting, QA, debugging, execution boundaries, CI/release, supply chain, documentation, acceptance, and verification.

The orchestrator should coordinate the following workstreams. A role is a review/coding mandate, not a separately running agent unless the client actually dispatches an independent subagent.

| Workstream | Responsibilities | Required outputs |
|---|---|---|
| Product & system architecture | Requirements, interfaces, state machines, dependency direction | Approved architecture, ADRs, interface contracts |
| Engineering & implementation | Small scoped code changes, maintainability, error handling | Reviewed diffs, tests, migration notes |
| Market data & intelligence | Public market data, provider contracts, provenance, freshness, gaps, event/calendar context where approved | Validated datasets, lineage, staleness and quality reports |
| Quant research | Hypotheses, baselines, costs, walk-forward and out-of-sample evaluation | Reproducible experiment reports; no profit guarantees |
| Strategy engineering | Signal definitions, regime assumptions, entry/exit logic, parameter controls | Versioned strategy specs and falsifiable acceptance criteria |
| Risk & capital protection | Exposure, position sizing, stops, drawdown limits, kill conditions | Fail-closed risk policy and invariant evidence |
| Portfolio & accounting | Orders/fills only in authorized simulation, exact-decimal ledger, fees, partial closes, reconciliation | Conservation and idempotency evidence |
| Execution engineering | PAPER adapter, order lifecycle simulation, idempotency, duplicate prevention | Offline simulator first; LIVE remains disabled |
| Operations & observability | Health, stale data, failures, audit trail, alerting, recovery | Operational runbooks and failure drills |
| Security & supply chain | Threat model, dependencies, permissions, secrets, data minimization | Security review and dependency provenance |
| QA & verification | Unit/property/integration tests, deterministic fixtures, regression gates | Reproducible test evidence |
| Release & governance | Change control, CI, branch protection, approvals, rollback | Release checklist and signed-off evidence |
| Independent acceptance | Challenge evidence and verify requirements without implementing the change | PASS / PASS WITH FINDINGS / BLOCKED verdict |

## 3. System architecture and trust boundaries

Keep these responsibilities separate:

1. **Public data acquisition:** unauthenticated, explicitly allowlisted provider requests only. No exchange account access.
2. **Normalization and quality:** schema validation, timestamp units, candle invariants, duplicates, gaps, provenance, freshness.
3. **Research storage:** immutable/versioned datasets and experiment metadata; no protected data path access without explicit authorization.
4. **Research and backtesting:** deterministic replay, fees/slippage assumptions, survivorship/look-ahead controls, out-of-sample evaluation.
5. **Strategy:** proposes candidate signals and stop levels; cannot approve its own risk.
6. **Risk engine:** validates inputs and proposed exposure/stop; fails closed on stale, invalid, missing, or inconsistent state.
7. **Portfolio ledger:** owns accepted positions/stops and exact-decimal accounting; supports partial closures and idempotent events.
8. **Execution boundary:** initially simulator only. PAPER requires separate approval and all safeguards. LIVE code and credentials remain unavailable.
9. **Operations and audit:** health, provenance, logs, incident response, reproducibility, and controlled recovery.

No component may bypass the next component's validation. Public market data is not evidence of account balance, order acceptance, or actual fills.

## 4. Non-negotiable safety rules

- Spot, long-only. No shorts, leverage, margin, or derivatives.
- No exchange credentials, API keys, OTPs, wallet secrets, private endpoints, account reads, balance sync, reconciliation, orders, or withdrawals.
- Tokocrypto is a custody/funding venue, not a bot account. The only approved public exception remains unauthenticated GET server-time and candle access on `www.tokocrypto.site`; `www.tokocrypto.com`, symbol-info, and `open/v1` remain excluded.
- No network request, scheduled job, workflow run, deployment, or external diagnostic without exact authorization.
- No automatic failover to an unapproved provider.
- No silent data repair, deduplication, interpolation, or gap filling.
- Invalid, stale, incomplete, contradictory, or untrusted inputs must fail closed.
- Money and quantity accounting use exact decimal arithmetic.
- Strategy proposes stops; risk validates; portfolio owns accepted stops.
- Emergency stop must be independently demonstrated before PAPER execution.
- LIVE remains unavailable. No profit or safety guarantee may be claimed.

## 5. Research quality and the path toward an edge

The objective is to discover whether a strategy has a durable, net-of-costs edge—not to manufacture attractive backtest numbers.

Every strategy candidate must have:
- a written hypothesis and market rationale;
- a simple baseline and a reason to outperform it;
- point-in-time data and documented provenance;
- realistic fees, spread, slippage, latency, and rejected/missed trade assumptions;
- no look-ahead, leakage, survivorship, or accidental future-data access;
- chronological train/validation/test separation and walk-forward evaluation;
- sensitivity and parameter-stability analysis;
- regime and drawdown analysis;
- a predeclared acceptance threshold and experiment log;
- an untouched final holdout, used sparingly.

A positive backtest is not proof of future profitability. If evidence is weak, the correct outcome is reject, revise, or continue research—not deploy.

## 6. Delivery sequence and gates

### Gate 0 — Governance and scope
Confirm authoritative branch/commit, ADRs, project state, path exclusions, owners, and exact authorization. No implementation until scope is explicit.

### Gate 1 — Market-data containment
Resolve excluded provider fallbacks, symbol-info paths, diagnostic exposure, host/path/method/redirect/query allowlists, bounded reads, closure, retry semantics, timestamps, OHLCV validation, duplicates, and sanitization. Reconcile v7 spec and tests before code.

### Gate 2 — Reproducible research foundation
Establish dataset provenance, deterministic replay, fees/slippage, experiment tracking, baseline strategies, and anti-leakage checks.

### Gate 3 — Strategy validation
Require out-of-sample and walk-forward evidence, stability, drawdown limits, and independent quant review. No live claims.

### Gate 4 — Risk and portfolio integrity
Verify fail-closed risk behavior, exact-decimal accounting, partial closures, conservation, idempotency, accepted-stop ownership, and emergency-stop semantics within authorized readable scope.

### Gate 5 — Offline execution simulation
Build and verify only after separate authorization. Simulate order lifecycle, partial fills, fees, rejects, timeouts, duplicate events, restart/recovery, and kill switch. No exchange connectivity.

### Gate 6 — PAPER readiness
Requires accepted prior gates, independent security and acceptance reviews, operational runbooks, emergency-stop drills, explicit PAPER authorization, and narrowly scoped enablement. PAPER is not automatically enabled by passing tests.

### Gate 7 — LIVE
Out of scope and unavailable. Would require a new threat model, legal/compliance review, custody/execution architecture, security assessment, and separate explicit authorization. This plan does not propose or enable it.

## 7. Work-in-progress priorities

1. Keep PR #56 blocked until the approved v7 contract and test plan are internally consistent.
2. Contain the excluded Tokocrypto `.com` fallback and unapproved diagnostic paths through a separately authorized change.
3. Resolve workflow autonomy, permissions, and destructive publishing concerns before any workflow run.
4. Decide whether research cross-check failure is a mandatory backtest gate.
5. Reconcile stale handoff documentation from authoritative ADR/progress/sequencing records.
6. Only then proceed to the next milestone's implementation and verification.

## 8. Definition of done

A work item is complete only when:
- exact scope and authorization are recorded;
- code and tests match approved requirements;
- relevant deterministic tests are actually run and results inspected;
- security, data, architecture, and documentation reviews are complete;
- no protected path or unauthorized provider was accessed;
- CI/workflow/network actions are separately authorized and evidenced;
- independent acceptance records a verdict;
- rollback and operational implications are documented.

Never report a percentage as a substitute for evidence. Report completed artifacts, verified results, blockers, and the next required decision.

## 9. Current limitations

This operating model does not itself make the system safe, profitable, or operational. Repository skills are guidance, not sandboxing or permission enforcement. The current safety register remains open; PR #56 is not merge-ready; Step 6 is not accepted; Step 7 is blocked; Step 10 is design-only. No Tokocrypto login is needed for the approved public market-data work.
