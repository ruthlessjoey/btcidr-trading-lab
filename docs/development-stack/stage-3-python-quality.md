# Stage 3 — Python static quality

## Selected tool

Ruff is an open-source MIT-licensed Python linter and formatter. This stage installs only its standalone linter binary; it does not add a runtime dependency or modify application code.

- Version: `0.17.5` (published 2026-11-12).
- Official source: [Astral Ruff 0.17.5 release](https://github.com/astral-sh/ruff/releases/tag/0.17.5).
- Release tag commit: `c91de8a012cb87efe279b762020a0d28dd75ddb5`; GitHub reports its commit signature as valid.
- Linux x86-64 GNU archive: `ruff-x86_64-unknown-linux-gnu.tar.gz`.
- SHA-256: `7d261fc981a784668e19e9fa6ad437bfd95b67f2dc263fc1eab87d54d72fcc90` (GitHub release asset digest).
- PyPI currently reports no provenance for the 0.17.5 release files; the workflow therefore uses the official GitHub release asset and verifies its published digest rather than installing an unprovenanced wheel.
- No third-party Python dependencies are installed.

## Workflow boundary

`.github/workflows/python-static-quality.yml` is manual-only and read-only.

- Uses immutable `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` with `persist-credentials: false`.
- Sparse-checks out only `fetcher.py`, `providers.py`, `live_check.py`, `probe.py`, and `run.py`.
- Explicitly excludes protected `validator.py`, `report.py`, `P1/`, `signal/`, and Workstream B files/data.
- Ruff reads source statically; it does not import or execute the target modules.
- Runs `ruff check` only. It never formats files, applies fixes, writes source, or accesses exchange endpoints.

## Verification limits

- The Ruff release tag signature and asset digest were checked through GitHub release metadata.
- Workflow YAML syntax was parsed locally before the workflow was offered for dispatch.
- Ruff has not been executed against this repository snapshot yet. The workflow is manual-only and must be dispatched by the owner after review.
- Any findings must be triaged; do not run auto-fix or alter trading behavior merely to satisfy lint rules.
