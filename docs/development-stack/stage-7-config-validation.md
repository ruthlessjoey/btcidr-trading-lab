# Stage 7 — Claude configuration validation

The manual validation workflow checks only the shared Claude setup:

- JSON syntax for `.claude/settings.json` and `.mcp.json`;
- required Read/Edit denials for `P1/` and all of `signal/`;
- Context7 endpoint and environment-variable-only API key;
- GitHub MCP endpoint, allowed toolsets, and read-only mode;
- skill frontmatter presence and name-to-directory consistency;
- key safety markers in `CLAUDE.md`.

The workflow uses sparse checkout of Claude configuration only, pinned checkout, read-only permissions, and no persisted credentials. Its inline Python uses only the standard library. It does not import, build, test, or execute trading code and has no network calls beyond checkout.

Triggers are manual dispatch and pull requests to `main` that modify the Claude configuration paths. It has not been run in this session. Once merged to the default branch, dispatch it manually to verify the installed configuration.

This validates configuration structure only. It does not prove Claude Code has loaded the skills, that MCP OAuth/API key setup succeeded, or that the permission rules are a complete sandbox.
