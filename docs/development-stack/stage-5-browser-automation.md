# Stage 5 — Browser automation decision

## Candidate evaluation

### Playwright — keep as the future UI-testing choice

- License: Apache-2.0.
- It is a deterministic browser automation and testing framework, not an autonomous coding agent.
- It can run in GitHub Actions, but this repository currently has no approved browser-facing application or UI test target identified for it.
- It does not solve AI-driven GitHub repository editing or approvals; the read-only GitHub MCP connection is the safer API-level foundation.
- Decision: do not add Playwright as a dependency or create a browser workflow until a concrete, authorized UI test target exists.

### Browser Use — defer

- License: MIT.
- AI-driven browser automation requires a model/runtime. A free source license does not make hosted model inference or hosted browser infrastructure free.
- The user's current environment has no local desktop/Ollama runtime. Do not substitute paid API calls or hosted browser credits.
- Decision: do not install until a genuinely free, local model/runtime and isolated browser environment are available.

### Stagehand — defer

- License: MIT.
- Its typical workflows depend on a browser runtime and LLM provider; hosted Browserbase or paid model/API usage is not authorized.
- Decision: do not install or configure a paid provider.

### OpenHands — defer

- OpenHands requires an agent execution environment and sandbox/runtime. A repository alone or an iPhone browser cannot provide the required persistent isolated computer.
- No zero-cost, secure, persistent deployment has been verified for this project.
- Decision: do not deploy to a paid hosted environment or weaken sandbox requirements.

## Current approved automation boundary

- GitHub MCP is configured in read-only mode for repository, pull-request, and Actions information.
- No browser session may access exchange accounts, personal account data, secrets, protected source/data, or Workstream B implementation.
- No automated GitHub writes, workflow dispatch, merge, release, or deployment are enabled.
- Use explicit user approval for each consequential repository action.

## Revisit criteria

Reconsider Playwright when a real UI test target exists. Reconsider Browser Use/Stagehand/OpenHands only after demonstrating:
1. no paid API, hosted browser, subscription, or recurring cost;
2. a persistent isolated runtime with enforceable filesystem/network boundaries;
3. explicit allowlists for repositories, URLs, and actions;
4. audit logs and human approval before consequential writes;
5. tests proving protected paths and exchange endpoints cannot be accessed.
