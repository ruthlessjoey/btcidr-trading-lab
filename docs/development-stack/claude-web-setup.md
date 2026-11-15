# Using the trading skills with regular Claude (claude.ai)

## Target environment

This guide targets Claude on the web or mobile app (claude.ai), not Claude Code. Repository files under `.claude/skills/` are not automatically loaded by Claude.ai just because they exist in GitHub.

Claude.ai supports custom Skills when **Code execution and file creation** is enabled. Custom Skills are uploaded by the individual user and are not automatically shared from this GitHub repository.

Official setup reference: https://support.claude.com/en/articles/12512180-use-skills-in-claude

## Recommended setup

1. Open Claude and go to **Settings → Capabilities**.
2. Enable **Code execution and file creation** (the label may appear as **Create and edit files** in the updated settings).
3. Open **Customize → Skills**.
4. Use **Create skill → Upload a skill** to upload a ZIP containing one skill folder. Each uploaded skill must have its own `SKILL.md` at the root of that skill folder.
5. Enable the uploaded skill in the Skills list.
6. In a chat, ask Claude to apply the relevant skill and state the exact task and authorized files.

If the Skills controls are unavailable, use the fallback below. Do not assume the skill is active merely because its files are in GitHub.

## Which repository skills to adapt/upload first

Start with these repository-specific, guidance-only skills:

- `trading-architecture-review`
- `security-review`
- `offline-testing`
- `data-provider-integration`
- `risk-engine-invariants`
- `documentation-consistency`

Upload and enable only the skills needed for the current task. These are review guides, not security enforcement or repository access controls.

The imported upstream Superpowers material is retained as source/reference material. Do **not** assume every upstream workflow is usable in regular Claude: instructions that depend on Claude Code filesystem discovery, terminal commands, Git worktrees, plugin namespaces, or subagents need a Claude.ai-specific adaptation before use. In particular, do not expect `superpowers:...` references to resolve automatically.

## Project instructions fallback

If custom Skills are unavailable, create or open a Claude Project and add concise project instructions. Add the relevant Markdown guides to Project knowledge using the project's upload control. Project knowledge provides context; it does not grant repository access or execute workflows.

Suggested project instruction:

> You are assisting with the AI Trading Lab as a read-only architecture and safety reviewer unless I explicitly authorize a narrowly scoped change. Before reviewing, confirm the exact authorized files and baseline. Never inspect, search, enumerate, read, write, or process `P1/`, any `signal/` path (including `signal/data/`), or protected Workstream B source/data. Preserve all approved ADRs and custody boundaries. No exchange credentials, private endpoints, account access, balances, wallets, orders, withdrawals, leverage, derivatives, shorting, or live execution. Crypto is spot and long-only. Tokocrypto public-data exception is limited to unauthenticated server-time/candles on `www.tokocrypto.site`; `www.tokocrypto.com` remains excluded. Distinguish evidence from assumptions, proposals from approvals, and unrun checks from passed checks. Never claim profitability, full-system validation, or completion without evidence. Stop if a task requires access to a protected path.

## Mobile upload notes

On iPhone, use Safari to open the repository and download only the intended skill folder or prepared skill ZIP. Do not upload the whole repository ZIP as a skill: it may contain unrelated or protected material and is not a valid single-skill package. If no ready-made ZIP is provided, ask for one rather than trying to upload the raw `SKILL.md` alone.

## Limitations and safety

- A custom Skill gives Claude instructions; it is not a sandbox, permission boundary, or guarantee of compliance.
- Claude.ai does not gain automatic access to this private repository from a skill upload. Provide only the specific authorized files or use an explicitly connected GitHub integration with least privilege.
- Do not paste tokens, API keys, exchange credentials, or private account information into chats or skill files.
- Code execution availability and network access depend on account and organization settings. Do not treat it as permission to run repository code or access external services.
- No trading, paper execution, live execution, or workflow dispatch is authorized by this guide.
