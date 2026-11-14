# Automation Pilot

AUTOMATION PILOT: documentation-only

This file exists only to verify that a narrowly scoped GitHub Actions workflow can run on the isolated `automation/pilot` branch.

Scope:
- Documentation-only test.
- No trading logic, market data, datasets, research, backtests, credentials, exchange access, or execution.
- No access to protected `P1/` or `signal/data/` paths.
- No changes to `main`.

A passing check validates only this small CI trigger and file-presence check. It does not validate the trading system, strategy performance, or readiness for paper/live trading.
