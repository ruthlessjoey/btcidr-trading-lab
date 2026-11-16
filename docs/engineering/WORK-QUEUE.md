# AI Trading Lab — Prioritized Engineering Work Queue

**Status:** PROPOSED — planning only; no implementation authorization implied  
**Branch:** `chore/claude-engineering-tooling`  
**Source of truth:** Reconcile this queue against approved ADRs, the safety register, and owner decisions before each task.

## Operating rule

Work in dependency order. A task cannot advance because a later task is more exciting or appears more profitable. Each item requires an exact scope, explicit authorization for the relevant reads/writes/commands/external actions, and evidence-based acceptance. This queue does not authorize source changes, tests, workflows, network calls, deployments, or trading.

## Priority 0 — Keep unsafe paths contained

| ID | Work item | Finding / dependency | Exit evidence | Current state |
|---|---|---|---|---|
| Q0.1 | Keep PR #56 blocked; reconcile the v6 hardening spec and test plan into one internally consistent v7 contract | SAF-007, SAF-009; owner decisions D1–D8 and H1/H2 | Every requirement maps to exact implementation behavior, test cases, and acceptance criteria; all known contradictions resolved | BLOCKED — v7 reconciliation needed |
| Q0.2 | Remove the executable Tokocrypto `.com` fallback and fail closed on excluded provider configuration | SAF-001; approved host/endpoint boundary | Static review proves rejected configuration is refused before any network request; approved `.site` public GET scope is exact | PROPOSED — separate implementation authorization required |
| Q0.3 | Contain the diagnostic probe: no symbol-info, no unbounded body reads, no raw URL/body/exception leakage | SAF-002 | Static review proves excluded endpoints cannot be called and diagnostics are bounded/sanitized; do not run the old probe | BLOCKED — separate scope and safe replacement design required |
| Q0.4 | Redesign market-data workflow to remove autonomous triggers and unsafe publishing | SAF-003 | Reviewed workflow diff with no schedule/push-triggered external activity, least privilege, no destructive force-push; workflow remains unrun until separately authorized | PROPOSED — separate workflow authorization required |
| Q0.5 | Decide whether cross-check failure is a hard backtest gate | SAF-006 | Owner decision recorded; workflow behavior and docs agree; if mandatory, failure demonstrably blocks downstream backtest | BLOCKED — owner policy decision required |
| Q0.6 | Reconcile research provider paths with approved provider policy; remove disallowed Bitstamp and prevent Tokocrypto symbol-info access | SAF-004, SAF-005 | Static review of authorized files proves no disallowed host/path can be selected; no external request | BLOCKED — dependent on v7 provider contract and exact scope |

### Hardening contract already approved by owner

- Exact HTTPS host allowlist; reject redirects, wildcard hosts, unexpected ports, and URL userinfo.
- Remove Bitstamp from the cross-check scope; do not introduce new external hosts.
- Maximum response body 1 MiB; read at most 1 MiB + 1 byte and reject oversize before JSON parsing; close on every path.
- Reject the entire response unless OHLCV values are finite and satisfy positive OHLC, nonnegative volume, high/low consistency, and candle invariants.
- Reject duplicate open timestamps within a response; no silent deduplication. Cross-page duplicate policy remains a separate decision.
- Only HTTP 200 succeeds. Retry only HTTP 429 and 5xx; other statuses fail.
- Timestamps must be JSON integers; reject booleans, strings, floats (including integral floats), and truncation.
- Negative volume rejected; zero volume is valid unless provider contract says otherwise.

H1/H2 clarifications: numeric strings and booleans are not timestamps; fractional timestamps are not truncated; negative volume is invalid; zero volume is valid.

## Priority 1 — Establish reproducible research

Start only after Priority 0 containment is accepted.

| ID | Work item | Required output | Gate |
|---|---|---|---|
| Q1.1 | Define dataset provenance, schema/version, event-time versus receive-time, and freshness policy | Reproducible dataset manifest and quality report | Gate 2 |
| Q1.2 | Define deterministic replay and experiment metadata | Same inputs/configuration reproduce the same result | Gate 2 |
| Q1.3 | Define realistic cost model: fees, spread, slippage, latency, missed/rejected fills | Explicit cost assumptions and sensitivity report | Gate 2 |
| Q1.4 | Establish simple baseline strategies and anti-leakage controls | Chronological splits, no look-ahead, documented baselines | Gate 2 |
| Q1.5 | Establish experiment registry and parameter-trial accounting | Complete record of trials, including failed/negative results | Gate 2 |

No performance conclusion is valid if the data lineage, time alignment, or cost model is unknown.

## Priority 2 — Validate strategy hypotheses

Start only after reproducible research foundations are accepted.

| ID | Work item | Required output | Gate |
|---|---|---|---|
| Q2.1 | Write falsifiable strategy specifications | Exact entry/exit/invalidity rules and decision timestamps | Gate 3 |
| Q2.2 | Run chronological validation and walk-forward evaluation | Out-of-sample reports with untouched holdout discipline | Gate 3 |
| Q2.3 | Test parameter stability and market regimes | Sensitivity, drawdown, tail-loss, turnover, exposure reports | Gate 3 |
| Q2.4 | Independent quant challenge | Written acceptance or rejection with evidence | Gate 3 |

A profitable-looking backtest is not proof of a durable edge. Reject or revise strategies that fail out-of-sample, cost, or robustness checks.

## Priority 3 — Verify capital protection and accounting

Start only within separately authorized, readable scope. Protected Workstream B paths remain excluded unless the user authorizes exact paths independently.

| ID | Work item | Required output | Gate |
|---|---|---|---|
| Q3.1 | Review risk fail-closed invariants | Evidence for stale/invalid/missing/inconsistent input rejection | Gate 4 |
| Q3.2 | Verify stop ownership | Strategy proposes; risk validates; portfolio owns accepted stop | Gate 4 |
| Q3.3 | Verify exact-decimal accounting and partial closures | Conservation, idempotency, fee, and rounding evidence | Gate 4 |
| Q3.4 | Specify emergency stop and kill conditions | Unambiguous state transitions and recovery prerequisites | Gate 4 |

Do not infer safety from documentation alone. Do not access protected implementation to fill evidence gaps without separate explicit authorization.

## Priority 4 — Offline execution simulation only

Requires accepted prior gates and a new exact implementation authorization.

- Simulate order lifecycle without exchange connectivity.
- Cover partial fills, fees, rejects, timeouts, duplicate events, restart/recovery, and emergency stop.
- Keep PAPER disabled until independent acceptance, operational readiness, and separate explicit PAPER authorization.
- LIVE remains unavailable and out of scope.

## Priority 5 — Operational readiness and PAPER decision

Requires accepted prior gates, security review, operational runbooks, failure drills, rollback/recovery plan, and independent acceptance. A passing test suite does not itself authorize PAPER.

## Explicit unresolved decisions

1. Whether cross-check failure is a mandatory backtest blocker (SAF-006).
2. Whether duplicate timestamps across pagination boundaries should reject the whole dataset or follow a separately specified page-boundary rule (D5 only explicitly governs duplicates within a response).
3. Whether any retry behavior beyond HTTP 429 and 5xx is desired; current approved D6 says no network-exception retries.
4. Final v7 specification details still requiring reconciliation: exception-family behavior, proxy isolation, safe output directory, configuration refusal categories, report fields, non-GET behavior, and gap reporting. Do not invent these contracts.

## Global prohibitions

- No access to `P1/`, `signal/data/`, any copy of `signal/`, protected Workstream B data, or protected implementation.
- Do not inspect `markets/risk`, `validator.py`, or `report.py` without separate exact authorization.
- No credentials, private endpoints, account reads, balance sync, orders, withdrawals, or LIVE trading.
- Tokocrypto public exception remains unauthenticated GET only to `www.tokocrypto.site` for server time and candles. No `.com`, symbol-info, or `open/v1`.
- No tests, scripts, workflows, schedules, network calls, deployments, or CI dispatches without exact authorization.
- No source/test/workflow/config changes without exact scope-specific authorization.
- Spot long-only; no leverage, margin, shorts, or derivatives.

## Completion reporting

Report each item as NOT STARTED, IN REVIEW, BLOCKED, PROPOSED, IMPLEMENTED, TESTED, INDEPENDENTLY REVIEWED, or ACCEPTED. State the exact evidence and what was not done. Never substitute percentages for evidence. This queue is not a profitability or safety certification.
