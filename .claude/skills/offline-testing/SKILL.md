---
name: offline-testing
description: Use when designing or reviewing tests that must run without exchange credentials, private endpoints, external network access, or protected datasets.
---
# Offline Testing

## Scope
Tests may cover only explicitly authorized, unprotected source. Never inspect or use `P1/`, `signal/data/`, any `signal/`, or protected Workstream B files/data.

## Rules
- Default to deterministic offline tests with synthetic fixtures.
- Do not fetch live market data or contact an exchange during unit tests.
- Do not read secrets, account data, or local credential stores.
- Test missing, stale, malformed, duplicated, out-of-order, partial, and boundary inputs.
- Assert fail-closed behavior and explicit error states.
- Use property-based tests only where invariants are clear and generated data is synthetic.
- Separate unit, integration, contract, and manual diagnostic tests.
- Never label a mocked test as a live-provider test.
- Review imports, fixtures, hooks, subprocesses, and network behavior before running repository-controlled tests in an isolated environment.

## Reporting
Record exact command, environment, test count, pass/fail/skip status, and whether network access was disabled. A test not run is not passed.
