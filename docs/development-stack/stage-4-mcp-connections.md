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

## Runtime setup required

1. Open the repository in Claude Code and accept the project trust prompt only after reviewing the project files.
2. Approve the GitHub MCP server and complete the GitHub OAuth flow.
3. Create a free Context7 API key through the official Context7 account flow.
4. Set that key as the `CONTEXT7_API_KEY` environment variable in the Claude Code runtime. Never place the actual key in this repository or in chat.
5. Restart/reconnect Claude Code and confirm both servers appear in `/mcp`.
6. Confirm GitHub tools are read-only and Context7 can resolve a public library documentation query.

## Limitations

- This repository change configures the servers; it cannot complete OAuth or set a private runtime environment variable on the user's behalf.
- Context7's free tier has included usage limits; requests beyond the included amount may be chargeable. No paid usage is authorized.
- No GitHub write tools are enabled. A separate explicit security review and approval are required before enabling them.
