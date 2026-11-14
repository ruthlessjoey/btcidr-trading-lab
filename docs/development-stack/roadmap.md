# Free-first development stack: staged rollout

## Purpose

Create a reliable, reviewable development environment for the BTC/IDR Trading Lab that improves Claude-assisted work across shared repository tasks and supports both workstreams without crossing their access boundaries.

This roadmap is an implementation sequence, not permission to access protected source, install paid services, merge pull requests, or enable trading execution.

## Existing work to keep separate

- PR #38 contains a pinned Cloudflare security-audit skill and a local safety overlay. It remains a separate draft PR; its full audit mode is not approved or operational.
- PR #39 hardens the manual security-lint workflow. CodeQL checks completed successfully, but Actionlint/zizmor workflow execution remains outstanding.
- The repository's existing trading architecture and data protections remain authoritative.

## Staged rollout

### Stage 1 — Shared Claude project foundation

- Add root `CLAUDE.md` instructions for repository purpose, workstream separation, protected paths, trading invariants, free-only policy, least privilege, and review requirements.
- Add project-level Claude permission denials for direct Read/Edit access to `P1/` and `signal/data/`.
- Treat permission settings as defense-in-depth, not a complete sandbox: shell commands and external tools may have different access paths.
- Keep Workstream B implementation and data unopened. Shared root instructions may still guide Claude when working within separately approved Workstream B scope.

### Stage 2 — Claude skills and development workflow

Add and validate one skill at a time:
1. `security-review`
2. `trading-architecture-review`
3. `offline-testing`
4. `data-provider-integration`
5. `risk-engine-invariants`
6. `documentation-consistency`

Evaluate the upstream Superpowers skills for Claude Code and integrate only the useful, compatible, license-verified parts. Keep upstream attribution and pin the source revision. Do not treat the ChatGPT-installed Superpowers plugin as automatically installed in Claude Code.

Use Context7 documentation support only after confirming the official MCP configuration, privacy behavior, and free usage path. Never place API keys or other secrets in the repository.

### Stage 3 — Python development quality

- Evaluate Ruff as a lint-only tool first; do not apply mass formatting.
- Evaluate Hypothesis for property-based tests of unprotected, approved code.
- Pin exact versions and verify package metadata, wheel hashes, transitive dependencies, and Python compatibility before installation.
- Keep development dependencies separate from runtime dependencies.
- No package installation or repository-controlled test execution until the dependency and isolation review is complete.

### Stage 4 — Market-data validation

- Evaluate Pandera only for approved normalized market-data schemas.
- Do not read or modify frozen/protected data.
- Tests must use synthetic fixtures or separately approved public samples, never protected datasets.
- Network access remains disabled by default.

### Stage 5 — Research analytics

Evaluate QuantStats, PyPortfolioOpt, and Riskfolio-Lib separately. Add none merely for completeness. Require a concrete research use case, compatible Python/dependency tree, and a documented isolation plan. Do not use analytics outputs as evidence of profitability without independent validation.

### Stage 6 — Browser and agent automation

- Prefer Playwright for free, local, deterministic browser tests where a suitable runtime exists.
- Evaluate Browser Use and Stagehand only if a genuinely free, local model/runtime path is available; exclude paid APIs and hosted usage.
- Defer OpenHands until its runtime, sandbox, compute requirements, and no-cost operation are demonstrated.
- Browser automation must not access exchange accounts, credentials, protected workstream data, or perform consequential GitHub actions without explicit approval.

### Stage 7 — End-to-end verification

For every stage:
- review exact changed files and upstream source pins;
- verify licenses and dependency provenance;
- run only approved checks in an isolated environment;
- inspect the actual outputs and Git diff;
- open a separate draft PR;
- document untested behavior and remaining risks;
- do not merge until the user reviews and separately approves.

## Non-goals

- No live trading, exchange account integration, wallet or order access.
- No paid API, hosted agent, subscription, or cloud runtime.
- No access to `P1/`, `signal/data/`, or protected Workstream B implementation.
- No autonomous code changes, workflow dispatch, secrets, or merge authority.
- No claim that development tooling makes a strategy profitable.
