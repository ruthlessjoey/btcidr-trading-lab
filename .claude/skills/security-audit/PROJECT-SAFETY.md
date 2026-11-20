# Repository-specific security-audit policy

This file is a local safety overlay for `ruthlessjoey/btcidr-trading-lab`. It supplements the pinned Cloudflare skill; it does not claim to be authored or endorsed by Cloudflare.

## Current operating mode

- **Guidance mode only.** Use relevant methodology for read-only source review and security questions.
- **Full audit mode is not currently authorized or operational.** Do not launch the six-phase workflow, create audit run artifacts, or delegate agents unless the user separately authorizes a full audit and the environment's required capabilities have first been verified.
- This environment currently lacks a verified OS-enforced sandbox with all controls required by upstream `SKILL.md`, and lacks a verified parallel sub-agent execution facility. Do not assume ordinary GitHub Actions, a browser session, or a local shell is an adequate substitute.

## Execution restrictions

- Do not execute repository-controlled Python, JavaScript, shell, build, test, fixture, or workflow code as part of this skill.
- Do not run either upstream `validate-coverage-ledger.cjs` or `validate-findings.cjs`, and do not run their test files, until the user authorizes a suitable isolated validation environment.
- Static source inspection is allowed only within the scope explicitly authorized by the user.
- Do not install dependencies, make network calls from target code, probe deployed services, dispatch workflows, or spend paid API quota.
- Do not create, edit, delete, or promote target-repository source files or audit artifacts through this skill. Report proposed fixes; do not apply them.

## Protected scope and trading boundaries

- Never inspect, traverse, read, write, delete, rename, copy, archive, or otherwise access `P1/` or `signal/data/`. Exclude these paths before any traversal.
- Do not inspect or modify Workstream B.
- No exchange credentials, private/authenticated endpoints, balance synchronization, orders, withdrawals, wallets, or live execution.
- Tokocrypto public market-data exceptions remain limited to the separately approved scope; this skill does not authorize any Tokocrypto requests.
- Do not change the project's spot-only, long-only, PAPER/LIVE, emergency-stop, or custody boundaries.
- Never claim that an audit is comprehensive, that the system is secure, or that trading is profitable based on a guidance-mode review.

## Reporting

- Distinguish source-confirmed facts, hypotheses, and items requiring external validation.
- Treat this skill's presence as tooling only, not evidence that an audit has run.
- State the exact source ref and scope for any future review. A partial review must be labeled partial.
- If a requested action conflicts with these restrictions or cannot be safely validated, stop and explain the missing capability rather than improvising.
