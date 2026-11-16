# AI Trading Lab — Whole-System Operating Model

**Status:** PROPOSAL — planning and governance only  
**Applies to:** `ruthlessjoey/btcidr-trading-lab`  
**Current tooling branch:** `chore/claude-engineering-tooling`  
**Trading mode:** Research first; PAPER only after separate safeguards and authorization; LIVE unavailable.

## 1. Repository strategy

Keep the operating model, repository skills, architecture decisions, and implementation together in this repository. Do not create a second "army" repository: it would split the source of truth, duplicate safety rules, and create version drift.

Create a separate repository only if a genuinely independent deployable service is later approved, with its own threat model, credentials policy, CI permissions, and release gates. It must not become a route around this repository's controls.

This document is a plan. It does not authorize source changes, external requests, workflows, deployment, or trading.

## 2. Whole-system team

The repository has 19 specialist skill instructions covering coordination, architecture, implementation, market data, market intelligence, quant research, strategy, risk, portfolio accounting, execution, operations, security, supply chain, QA, debugging, CI/release, documentation, independent acceptance, and verification.

A role is a review or implementation mandate, not a separately running agent unless the active client actually dispatches an independent subagent. See [REVIEW-ARMY.md](REVIEW-ARMY.md) for the complete roster.

| Workstream | Responsibilities | Required outputs |
|---|---|---|
| Product & system architecture | Requirements, interfaces, state machines, dependency direction | Approved architecture, ADRs, interface contracts |
| Engineering & implementation | Small scoped code changes, maintainability, error handling | Reviewed diffs, tests, migration notes |
| Market data & intelligence | Approved public market data, provider contracts, provenance, freshness, gaps, approved event context | Validated datasets, lineage, staleness and quality reports |
| Quant research | Hypotheses, baselines, costs, walk-forward and out-of-sample evaluation | Reproducible experiment reports; no profit guarantees |
| Strategy engineering | Signal definitions, regime assumptions, entry/exit logic, parameter controls | Versioned strategy specs and falsifiable acceptance criteria |
| Risk & capital protection | Exposure, position sizing, stops, drawdown limits, kill conditions | Fail-closed risk policy and invariant evidence |
| Portfolio & accounting | Simulation-only fills, exact-decimal ledger, fees, partial closes, reconciliation | Conservation and idempotency evidence |
| Execution engineering | PAPER adapter, order lifecycle simulation, idempotency, duplicate prevention | Offline simulator first; LIVE remains disabled |
| Operations & observability | Health, stale data, failures, audit trail, alerting, recovery | Operational runbooks and failure drills |
| Security & supply chain | Threat model, dependencies, permissions, secrets, data minimization | Security review and dependency provenance |
| QA & verification | Unit/property/integration tests, deterministic fixtures, regression gates | Reproducible test evidence |
| Release & governance | Change control, CI, branch protection, approvals, rollback | Release checklist and signed-off evidence |
| Independent acceptance | Challenge evidence and verify requirements without implementing the change | PASS / PASS WITH FINDINGS / BLOCKED verdict |

## 3. System architecture and trust boundaries

1. **Public data acquisition:** unauthenticated, explicitly allowlisted provider requests only. No exchange account access.
2. **Normalization and quality:** schema validation, timestamp units, candle invariants, duplicates, gaps, provenance, freshness.
3. **Research storage:** immutable/versioned datasets and experiment metadata; protected paths remain inaccessible unless separately authorized.
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

Every strategy candidate must have a written hypothesis, simple baseline, point-in-time data and provenance, realistic fees/spread/slippage/latency assumptions, no look-ahead or leakage, chronological train/validation/test separation, walk-forward evaluation, parameter stability, regime and drawdown analysis, predeclared acceptance thresholds, and an untouched final holdout used sparingly.

A positive backtest is not proof of future profitability. If evidence is weak, the correct outcome is reject, revise, or continue research—not deploy.

## 6. Delivery gates

- **Gate 0 — Governance and scope:** authoritative branch/commit, ADRs, project state, exclusions, owners, exact authorization.
- **Gate 1 — Market-data containment:** resolve excluded fallbacks, diagnostic paths, host/path/method/redirect/query allowlists, bounded reads, closure, retry semantics, timestamps, OHLCV validation, duplicates, sanitization. Reconcile v7 spec/tests before code.
- **Gate 2 — Reproducible research:** provenance, deterministic replay, costs, experiment tracking, baselines, anti-leakage.
- **Gate 3 — Strategy validation:** out-of-sample/walk-forward evidence, stability, drawdown limits, independent quant review.
- **Gate 4 — Risk and portfolio integrity:** fail-closed risk, exact-decimal accounting, partial closures, conservation, idempotency, stop ownership, emergency-stop semantics within authorized readable scope.
- **Gate 5 — Offline execution simulation:** only after separate authorization; simulate lifecycle, partial fills, fees, rejects, timeouts, duplicate events, recovery, kill switch. No exchange connectivity.
- **Gate 6 — PAPER readiness:** accepted prior gates, independent security/acceptance reviews, runbooks, emergency-stop drills, explicit PAPER authorization, narrowly scoped enablement.
- **Gate 7 — LIVE:** out of scope and unavailable; would require a new threat model, legal/compliance review, custody/execution architecture, security assessment, and separate explicit authorization.

## 7. Immediate work priorities

See [WORK-QUEUE.md](WORK-QUEUE.md) for the ordered, dependency-aware backlog. Priority 0 keeps PR #56 blocked pending v7 reconciliation and addresses excluded provider fallbacks, diagnostic endpoints, workflow autonomy, and unresolved cross-check policy before new research or execution work.

## 8. Definition of done

A work item is complete only when exact scope and authorization are recorded; code and tests match approved requirements; relevant deterministic tests are actually run and results inspected; security, data, architecture, and documentation reviews are complete; no protected path or unauthorized provider was accessed; external/CI actions were separately authorized; independent acceptance records a verdict; and rollback/operational implications are documented.

Never report a percentage as a substitute for evidence. Report completed artifacts, verified results, blockers, and the next required decision.

## 9. Current limitations

This operating model does not itself make the system safe, profitable, or operational. Repository skills are guidance, not sandboxing or permission enforcement. The safety register remains open; PR #56 is not merge-ready; Step 6 is not accepted; Step 7 is blocked; Step 10 is design-only. No Tokocrypto login is needed for the approved public market-data work.
