# Optional browser automation tools

## Jev Ultrafast

This is an optional, pinned Git submodule at `tools/jev-ultrafast`, sourced from:

- Upstream: https://github.com/browser-use/jev-ultrafast
- Pinned upstream commit: `cf3c406f0fc4becff8986ed4d4d37b7b9f102e45`
- Licence: MIT (see the upstream `LICENSE` file)

### Important status

This adds the upstream source reference only. It does **not** install Python packages, launch Chrome, configure API keys, or enable any automation. It is not imported by the trading application and is not part of any trading workflow.

The upstream project README now says its core idea is incorporated into Browser Use's `ultrafast` mode. The standalone repository is retained as the original Browser Use × TypeSafe experiment.

### Runtime and service requirements

- Python 3.12 or newer (the upstream `pyproject.toml` requirement).
- A local Chrome/Chromium environment connected through Browser Harness / Chrome DevTools Protocol.
- A TypeSafe API key for agent decisions.
- A separate OpenAI-compatible text-model API key for `TYPE_TEXT` actions (the upstream example uses OpenRouter).

Those hosted APIs may incur charges. No API keys or credentials have been added to this repository. Do not commit secrets.

### Trading-lab isolation

Jev is a general-purpose browser automation experiment, not a trading component. Do not connect it to exchange accounts, credentials, private exchange endpoints, wallets, order placement, withdrawals, trading decisions, or CI workflows. Do not use it to bypass the lab's manual approval gates.

This submodule is pinned for review only. Runtime setup, live browser use, dependency installation, and any integration require a separate explicit approval after security review.
