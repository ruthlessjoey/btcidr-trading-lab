# Repository instructions for Claude

These instructions apply across the repository, including shared tooling used by Workstream A and Workstream B. They do not grant permission to inspect or change protected workstreams or data.

## Mission and working style

- Preserve the repository's documented architecture and approved decisions. Read the relevant, unprotected ADRs and handoff documents before proposing changes.
- Prefer small, reviewable, independently verifiable changes. Work on a dedicated branch and submit a pull request; never commit directly to `main`.
- Explain the purpose, scope, risks, and verification evidence for each change. Separate facts, assumptions, and recommendations.
- Do not claim a test, audit, build, or security check passed unless its fresh output was observed.
- Do not claim a strategy is profitable without reproducible, out-of-sample evidence that includes fees, slippage, and realistic execution assumptions.

## Protected paths and workstreams

The following restrictions are mandatory:

1. Never enumerate, traverse, search, read, write, edit, delete, rename, copy, archive, upload, or otherwise process anything under `P1/`.
2. Never enumerate, traverse, search, read, write, edit, delete, rename, copy, archive, upload, or otherwise process anything under any `signal/` path, including copies nested elsewhere in the repository.
3. Never enumerate, traverse, search, read, write, edit, delete, rename, copy, archive, upload, or otherwise process anything under `markets/risk/`.
4. Never read, write, edit, execute, import, or otherwise process any file named `validator.py` or `report.py`, including copies nested elsewhere in the repository.
5. Workstream B source, data, artifacts, and implementation remain protected. Do not inspect, traverse, search, read, execute, or modify Workstream B content unless the owner gives separate, explicit authorization that identifies the specific scope. Shared root-level instructions and tooling may support Workstream B without opening or changing its protected implementation.
6. Before any repository-wide search, recursive listing, archive, test discovery, or broad checkout, explicitly exclude every protected path and file above. If a tool cannot guarantee exclusion, do not run it.
7. Do not infer that permission to improve shared tooling authorizes access to protected source or data.

If protected content appears in output accidentally, stop. Do not quote, summarize, copy, or continue processing it.

Project `Read`/`Edit` permission denials are defense-in-depth, not an OS sandbox. They do not constrain arbitrary subprocesses or every indirect file access. Never treat them as authorization to run scripts or tests whose execution/import closure may reach protected content; use only a verified OS-enforced boundary or keep the work static and read-only.

## Trading and exchange safety boundaries

- Spot crypto only; long-only. No shorting, leverage, margin, or derivatives.
- No exchange credentials, secrets, private/authenticated endpoints, account login, balance synchronization, wallet access, order placement, cancellation, funding, payments, withdrawals, or real-money activity.
- Tokocrypto is a user funding/custody venue, not a bot account. The only approved Tokocrypto market-data access is unauthenticated HTTPS GET candles from `https://www.tokocrypto.site/api/v3/klines`. Do not call server-time endpoints, use `www.tokocrypto.com`, or access private/authenticated endpoints. This Tokocrypto-specific rule does not itself authorize or revoke other providers; use other market-data hosts only where a separate current ADR or provider allowlist explicitly permits them.
- PAPER-only. LIVE trading remains disabled and unavailable.
- An emergency stop is required before any paper execution. Partial closures must remain supported in paper accounting.
- Strategy may propose a stop; risk validates it; portfolio owns the accepted stop.
- Do not change custody, execution, risk, or exchange boundaries as part of a tooling task.

## Safe development and automation

- Free/open-source-first: do not introduce paid APIs, paid hosted agents, subscriptions, or usage-based services. Verify licenses and the full dependency tree before adding packages.
- Pin dependencies and third-party GitHub Actions to reviewed versions or immutable commit SHAs. Verify package/artifact hashes where available.
- Use least-privilege workflow permissions. Do not add secrets, tokens, write permissions, automatic deployments, scheduled execution, or workflow dispatch triggers unless separately authorized.
- Do not run repository-controlled scripts, tests, build steps, hooks, or workflows merely because they exist. Review what they execute first and use an appropriately isolated environment.
- Never use an agent, browser automation tool, or MCP server to bypass repository restrictions or user approval.
- Do not install a tool that requires a paid model/API or hosted service for its intended operation. A free source license does not make hosted usage free.
- Keep external network access disabled for tests unless a specific public endpoint is approved for that test.

## Change control

- Keep each installation milestone on its own branch and pull request.
- Draft PRs are for review; do not merge them. Do not dispatch workflows, change repository settings, alter branch protection, or modify secrets without explicit authorization for that exact action.
- Do not force-push or delete branches.
- Do not combine unrelated package upgrades, source changes, and workflow permission changes in one PR.
- Report any unverified behavior as unverified and list what remains to be tested.

## Workstream separation

- Shared documentation, development guidance, and approved quality tools may be designed to help both workstreams.
- Do not import Workstream B source or data into Workstream A tests, fixtures, reports, or commits.
- Do not change Workstream B implementation under the authority to improve shared tooling. Obtain a separate scope approval before any such change.
- Keep the workstream-specific review and validation evidence separate.

## Mobile-first collaboration

The repository owner works from an iPhone. Prefer changes that can be reviewed and managed through GitHub's mobile website. Provide exact, short GitHub UI steps when a manual action is required; do not assume desktop terminal access.
