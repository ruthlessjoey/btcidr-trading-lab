---
name: offline-testing
description: Use when adding or changing tests, test fixtures, CI checks, or validation for this repository.
---

# Offline Testing

Make tests deterministic, repeatable, safe to run from a developer device, and independent of exchange availability.

## Rules
1. Ordinary unit and regression tests must not contact exchanges, trading platforms, wallets, or external services.
2. Use fixed fixtures and fake transports for provider responses. Keep network diagnostics separate, manually invoked, read-only, and separately authorized.
3. Freeze or inject time. Do not depend on wall-clock time, timezone, random values, or external mutable state unless the behavior specifically requires it.
4. Use exact decimal literals for monetary expectations. Derive expected results independently; do not compute them using the production helper under test.
5. Test valid, invalid, missing, malformed, stale, non-finite, out-of-range, duplicate, and contradictory inputs where relevant.
6. Test intended paths and bypass paths: direct constructors, deserialization, mutated objects, alternate entry points, replay, and state restoration.
7. For refusals, assert stable error categories and prove state is unchanged.
8. For accounting, assert quantity, cash, open cost, realized P&L, fee treatment, and partial-close conservation with hand-checked examples.
9. Run the narrow test first, then the complete relevant suite. Record interpreter version, exact command, exit status, and full test count.
10. Do not report a Python version as verified unless that exact interpreter ran the tests.

## Test-first cycle
- RED: write one focused test and run it; confirm it fails for the intended reason.
- GREEN: make the smallest production change and rerun the test.
- REFACTOR: simplify only while keeping tests green.
- Run the full relevant suite and inspect all output before reporting.

Use mutations to test whether assertions detect meaningful behavioral regressions. Classify survivors as equivalent/redundant, uncovered, or unresolved; never hide survivors in an aggregate score.
