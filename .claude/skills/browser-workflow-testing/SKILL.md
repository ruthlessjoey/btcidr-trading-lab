---
name: browser-workflow-testing
description: Use Firecrawl Interact for bounded, multi-step, public, harmless website workflow tests with observable verification.
---

# Browser workflow testing

## Purpose and authority

This skill gives the Lab Commander a controlled way to execute real browser workflows on public websites using the existing Firecrawl Interact MCP tools.

It is for website workflows: navigate, inspect, click, fill a harmless test field, submit a demo-only action, inspect the resulting page state, and report what actually happened.

It is not a GitHub Actions runner, repository test runner, shell, or permission bypass.

Only the Lab Commander has Firecrawl Interact tools. Specialists may propose a browser test but must ask the Commander to execute it.

## Zero-budget rules

- Use only the already-connected Firecrawl account's included free allowance.
- Before a browser session, call `firecrawl_credit_usage({view: "current"})`.
- The published free plan has a monthly credit allowance; the published Interact rate is 2 credits per browser minute. The live account balance and current pricing take precedence over remembered figures.
- Keep smoke tests short: set a bounded timeout (normally 60–90 seconds) and stop the session immediately after evidence is collected.
- Never buy credits, enable pay-as-you-go, purchase proxies, upgrade, or use paid services.
- If the current balance cannot be established, is zero, or the account/tool reports a paid requirement, stop and report BLOCKED.
- A missing per-call credit field or unchanged balance is not proof that a call consumed zero credits.

## Allowed targets and actions

Allowed:
- Public documentation and public demo/test websites.
- One explicitly identified target domain per workflow.
- Navigation, page snapshots, screenshots, scrolling, opening tabs, clicking public navigation elements, and filling harmless demo/search/test fields.
- Submitting a form only when it is clearly a non-production demonstration/test form with no real-world side effect.
- Verifying the visible result through a fresh accessibility snapshot or screenshot.

Default safe smoke-test target:
- `https://demo.playwright.dev/todomvc`

Do not:
- Sign in, use saved profiles, use end-user cookies, or enter credentials.
- Access private account pages, social accounts, email, cloud dashboards, exchange accounts, wallets, or authenticated APIs.
- Submit orders, payments, withdrawals, deposits, contact forms, registrations, messages, or any consequential production form.
- Access private exchange APIs or unapproved Tokocrypto endpoints.
- Bypass CAPTCHAs, paywalls, bot protections, or site access controls.
- Use a browser session to inspect protected repository files or project data.
- Run shell, Python, or Node code for arbitrary filesystem/network operations. Prefer the natural-language browser prompt; when code is necessary, restrict it to browser-page interactions and DOM assertions only.

## Execution procedure

1. Define the objective, exact starting URL, allowed domain, and observable success conditions before starting.
2. Check the current Firecrawl free-credit balance.
3. Call `firecrawl_interact` with the target URL, a precise multi-step prompt, and a bounded timeout. Do not provide a browser profile or proxy.
4. Instruct the browser to take a fresh snapshot after each important state change.
5. Verify the result from returned browser state, not only from the agent's narrative. Look for exact visible text, checkbox/value state, item counts, confirmation headings, or other explicit success indicators.
6. If more than one call is needed, reuse the returned `scrapeId` and `conversationId`; do not start duplicate sessions.
7. Call `firecrawl_interact_stop` when finished.
8. Report PASS only when the final page state supports every required assertion. Otherwise report FAIL, PARTIAL, or BLOCKED.

## Evidence report

Every completed browser workflow report must include:
- Objective and exact starting URL.
- Date/time and target domain.
- Actions actually observed or returned by the browser.
- Each expected assertion and its supporting visible evidence.
- Final state and exit status, when returned.
- Firecrawl credit balance before/after when checked; identify any missing per-call cost evidence.
- Screenshots or session evidence links when available.
- Any failed, skipped, or unverified steps.
- A clear statement that the task was a browser workflow, not a GitHub Actions or repository test run.

Never convert a successful click into a successful workflow claim without checking the resulting state.

## Known limitations

- The browser runs in Firecrawl's hosted environment, not inside the user's iPhone Safari.
- The isolated browser does not automatically receive the user's browser cookies or credentials.
- Tool availability, run duration, browser features, and free-tier limits are controlled by the connected Firecrawl plan and team policy.
- Interact can execute multi-step website actions, but it does not dispatch GitHub Actions, execute repository test suites, or replace deterministic CI.
- For deterministic application UI tests, use a separately approved Playwright test harness once an actual UI target and a safe runtime are available.
