# Stage 3 — Python quality tooling

## Installed in repository configuration

Ruff is introduced as a CI-only development tool, not a runtime dependency.

- Version: 0.17.5
- License: MIT
- PyPI requires Python >=3.7; the project baseline uses Python 3.11.
- Distribution: Linux x86-64 manylinux wheel for the Ubuntu 24.04 runner.
- SHA-256: `40ca8afaac309b41a5b2e09e4e7beb1f824826b93c25697c4d74f573324fba4e`
- Install mode: binary-only, no dependencies, hash-required.
- Workflow: manual dispatch only; read-only permissions; checkout credentials are not persisted.
- Scope: sparse checkout and lint only the listed root-level Python modules. No automatic formatting or fixes.

## Not installed yet

Hypothesis 6.170.15 is the current release identified during this review (MPL-2.0; Python >=3.11). It is deferred because PyPI reports no provenance for the release and the complete wheel hash/dependency lock has not yet been independently captured. Its runtime dependency must also be pinned. No unverified package install is added merely to complete the checklist.

Pandera, QuantStats, PyPortfolioOpt, and Riskfolio-Lib remain deferred pending a concrete use case, dependency review, and compatible test plan.

## Verification limits

- Ruff wheel hash is taken from the PyPI release file page.
- The workflow is manual-only and has not been dispatched.
- No Python source or tests were changed.
- No protected paths or Workstream B implementation/data were inspected.
- No package was installed in this session; GitHub Actions will install Ruff only when the user dispatches the workflow after the PR chain is merged.
