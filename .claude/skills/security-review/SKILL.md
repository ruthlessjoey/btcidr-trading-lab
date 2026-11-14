---
name: security-review
description: Use when assessing code, workflows, dependencies, permissions, secrets handling, data access, or automation security in explicitly authorized repository paths.
---
# Security Review

## Mandatory exclusions
Never access `P1/`, `signal/data/`, any `signal/` path, or protected Workstream B source/data. Exclude before traversal. If a tool cannot guarantee exclusion, do not run it.

## Checklist
- Trust boundaries: user input, repository content, external data, tools, workflows, model output.
- Permissions: least privilege, read-only by default, no unnecessary write tokens.
- Actions: immutable SHAs, pinned tool versions, credential persistence disabled, explicit permissions, bounded timeouts.
- Dependencies: license, provenance, pinning, hashes, transitive dependencies, install scripts, binary artifacts.
- Secrets: no credentials in source, logs, artifacts, prompts, or MCP configuration.
- Network: deny by default; allow only documented public unauthenticated endpoints within approved scope.
- Automation: no hidden dispatch, merge, release, deployment, account access, or destructive action.
- Supply chain: distinguish signed provenance from unsigned tags and unverified assets.
- Fail closed on stale, malformed, partial, unauthenticated, or unexpected inputs.

## Trading prohibitions
No exchange credentials, private endpoints, account login, balances, wallets, orders, withdrawals, leverage, derivatives, shorting, or live execution. Tokocrypto public-data exception is limited to unauthenticated server-time/candles on `www.tokocrypto.site`; `www.tokocrypto.com` remains excluded.

## Output
State scope, evidence, severity, exploit preconditions, impact, and smallest safe remediation. Mark unexecuted or unverified work as such. Do not call a guidance review a penetration test or comprehensive audit.
