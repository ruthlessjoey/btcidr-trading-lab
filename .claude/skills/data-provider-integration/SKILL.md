---
name: data-provider-integration
description: Use when designing or reviewing an approved public, unauthenticated market-data provider adapter or its normalization and failure handling.
---
# Data Provider Integration

## Permission gate
Only work on explicitly authorized adapter paths. Never inspect `P1/`, `signal/data/`, any `signal/`, or Workstream B implementation/data. No credentials or private/authenticated endpoints.

## Requirements
- Public unauthenticated GET only.
- Explicit provider/endpoint allowlist, timeout, response-size bound, and rate-limit handling.
- Validate HTTP status, content type, payload shape, numeric finiteness, timestamp units, symbol, interval, ordering, duplicates, and candle completeness.
- Normalize to a provider-neutral schema without losing source timestamp or provenance.
- Distinguish missing, stale, malformed, partial, and unavailable data.
- Never silently fill gaps or convert invalid values into tradable values.
- No network in unit tests; use synthetic fixtures.
- Require a documented use case and ADR alignment before adding a provider.

## Tokocrypto boundary
Only unauthenticated server-time/candles requests to `www.tokocrypto.site` are within the approved exception. Do not use `www.tokocrypto.com`, private endpoints, account data, or authentication.

## Output
Document endpoints, request method, limits, normalized schema, failure modes, provenance, tests, and unverified assumptions. No adapter may place or manage orders.
