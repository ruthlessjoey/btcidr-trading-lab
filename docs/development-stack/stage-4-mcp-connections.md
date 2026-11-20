# Stage 4 — Project MCP connections

## Context7

- Remote HTTP MCP endpoint: `https://mcp.context7.com/mcp`
- Free plan includes access to the MCP server and public-library documentation, subject to included usage limits.
- An API key is required by the current official Claude Code setup instructions.
- The project config references `CONTEXT7_API_KEY` through environment-variable expansion.
- Do not paste the key into chat, commit it, add it to a shared settings file, or expose it in logs.
- Do not enable paid overage. Stop using the service if the free quota is exhausted.
- Restrict queries to public library/API documentation. Do not send private source code, secrets, trading data, or user account information.

## GitHub MCP

- Uses GitHub's hosted remote MCP endpoint and its OAuth flow; no PAT is embedded.
- Enabled toolsets: `repos,pull_requests,actions`.
- Read-only mode is enforced by the remote endpoint header.
- Write tools, workflow dispatch, merge, and other mutations are intentionally unavailable in this configuration.
- Claude Code still requires the user to approve the project MCP server and complete GitHub OAuth.

## Firecrawl

- Official hosted remote MCP endpoint: `https://mcp.firecrawl.dev/v2/mcp-oauth` (OAuth sign-in; no API key or secret is stored in the repository).
- The project `.mcp.json` registers Firecrawl alongside Context7 and read-only GitHub MCP.
- OAuth exposes the full hosted tool surface subject to the account plan and team policy. The keyless endpoint `https://mcp.firecrawl.dev/v2/mcp` is a separate mode limited to Search, Scrape, and Parse; it is not used by this project configuration.
- Firecrawl is approved only within its included free allowance. Check `firecrawl_credit_usage` before substantial work, use bounded Agent `maxCredits`, disable unapproved provider execution, and stop at zero or uncertain balance. Never enable pay-as-you-go or paid overage.
- Relevant specialist roles should follow `.claude/skills/firecrawl-research/SKILL.md`. The dependent Firecrawl specialist PR restores 19 named project subagents and their domain skills, and adds explicit Firecrawl tool allowlists to the Commander and selected research/verification roles while retaining `permissionMode: plan` and read-only repository access. The live Claude Code OAuth and agent tool invocation remain unverified until the owner approves the project MCP server in a compatible runtime.
- The connected ChatGPT Firecrawl integration is verified in the Commander session. Claude Code project MCP requires user trust approval and browser OAuth; Claude.ai web uses its separate native connector flow.

## Runtime setup required

1. Open the repository in a supported Claude Code MCP client and accept the project trust prompt only after reviewing the project files.
2. Approve the Firecrawl server and complete the Firecrawl browser OAuth flow; confirm `firecrawl` appears in `/mcp` and its tools are available.
3. Approve the GitHub MCP server and complete the GitHub OAuth flow.
4. Create a free Context7 API key through the official Context7 account flow.
5. Set that key as the `CONTEXT7_API_KEY` environment variable in the Claude Code runtime. Never place the actual key in this repository or in chat.
6. Restart/reconnect Claude Code and confirm all three servers appear in `/mcp`.
7. Confirm GitHub tools are read-only, Context7 can resolve a public library documentation query, and Firecrawl credit usage reports the expected free balance.

## Limitations

- This repository change configures the servers; it cannot complete OAuth or set a private runtime environment variable on the user's behalf.
- Context7's free tier has included usage limits; requests beyond the included amount may be chargeable. No paid usage is authorized.
- No GitHub write tools are enabled. A separate explicit security review and approval are required before enabling them.
