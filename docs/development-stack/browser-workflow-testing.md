# Browser workflow testing with Firecrawl

**Purpose:** Execute and verify multi-step workflows on public websites without introducing another paid browser service.

## Chosen architecture

- **ChatGPT Commander:** the connected Firecrawl app exposes `firecrawl_interact` and `firecrawl_interact_stop` for hosted browser navigation and interaction.
- **Repository Commander:** the project-scoped Firecrawl MCP server in `.mcp.json` exposes the same browser-interaction tools after the user approves the project server and completes OAuth in a compatible MCP client.
- **Research:** use the existing `firecrawl-research` skill for Search, Scrape, Map, Crawl, and bounded Agent research.
- **Browser workflow policy:** use `.claude/skills/browser-workflow-testing/SKILL.md` for multi-step actions, assertions, budget limits, and evidence reporting.

This is one Firecrawl service used through two distinct connections. The ChatGPT connection does not automatically authenticate Claude Code or another MCP client.

## Why Firecrawl was retained

The connected Firecrawl Interact tool accepts a target URL and a natural-language task (or browser code), then returns browser actions, accessibility snapshots, execution output, exit status, and a session identifier. This is materially different from Search/Scrape alone: it can interact with visible page controls and inspect the resulting state.

A local alternative such as Playwright MCP or Browser Use would require an MCP client with a local Node/Python runtime and a browser installation. A local browser MCP cannot be attached as a custom tool to this user's ChatGPT Free iPhone app. No local model/runtime or supported desktop MCP client was verified for the user's current environment. Do not add a second browser runtime until those prerequisites exist and a concrete project UI test target is approved.

## Verified public workflow smoke test

**Date:** 2026-11-21  
**Target:** https://demo.playwright.dev/todomvc  
**Operation:** Add a demo todo, verify it appears, mark it complete, and verify the completed state.  
**Tool result:** Firecrawl Interact returned `success=true`, `exitCode=0`, and a browser session identifier.

Observed sequence:
1. Opened the public TodoMVC demonstration page.
2. Filled the visible `What needs to be done?` field with `Twin Money Maker browser smoke test` and pressed Enter.
3. A new accessibility snapshot showed the exact item text in the list and the footer showed one item remaining.
4. Clicked the item's `Toggle Todo` checkbox.
5. The final accessibility snapshot showed the checkbox as checked, the item text still present, a completed-item Delete control, and the footer showing zero items remaining with a Clear completed control.

**Result:** PASS for this bounded public UI workflow. This proves the connected Firecrawl Interact tool can execute a multi-step browser task and inspect post-action state. It does not prove all websites, login flows, anti-bot scenarios, or long-running tasks will work.

**Credit accounting caveat:** the immediate post-test account check returned `remainingCredits=1001` against `planCredits=1000`, unchanged from the pre-test check. The Interact response did not return a per-call credit cost, so do not claim this specific browser test consumed zero credits. No cash payment, upgrade, purchase, or automatic reload was performed.

## What this does and does not replace

| Capability | Status |
|---|---|
| Public multi-step browser navigation | VERIFIED |
| Click and fill harmless demo controls | VERIFIED |
| Inspect post-action page state | VERIFIED |
| Return execution output and exit status | VERIFIED |
| Public web research and extraction | VERIFIED separately in the Firecrawl integration tests |
| Private account login using user cookies | NOT AUTHORIZED / NOT TESTED |
| CAPTCHA or anti-bot bypass | NOT AUTHORIZED |
| GitHub Actions dispatch or CI execution | NOT A FIRECRAWL CAPABILITY |
| Local deterministic application UI test suite | NOT INSTALLED / NO APPROVED UI TARGET |

## Budget and security

- Use only the connected free allowance.
- Check the current credit balance before substantial browser work.
- Use short timeouts and stop sessions promptly.
- No paid APIs, paid proxies, paid browser hosting, upgrades, top-ups, or automatic reloads.
- No credentials, private account data, protected repository content, or exchange information may enter the browser session.
- Use only public, harmless test/demo interactions. Consequential actions require separate explicit authorization.
- Keep all existing PAPER-only, LIVE-disabled, exchange, protected-path, and Workstream B boundaries intact.

## Runtime activation for repository agents

1. Open the repository in a supported Claude Code MCP client.
2. Review and approve the project Firecrawl server in `.mcp.json`.
3. Complete Firecrawl OAuth in the browser.
4. Confirm the Commander has the exact Firecrawl Interact and credit-usage tools in its allowlist.
5. Load the `browser-workflow-testing` skill and run a harmless smoke test only after checking the free balance.
6. Report actual tool discovery and execution separately; the existence of an agent definition is not proof that the client loaded it.

## Important distinction

Firecrawl Interact is a hosted browser workflow executor. It does not execute Python unit tests, run repository scripts, or dispatch GitHub Actions workflows. Those remain separate engineering/CI operations and require their own authorized runner and approval.
