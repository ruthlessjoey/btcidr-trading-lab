---
name: provider-integration
description: Use when adding, changing, or reviewing public exchange market-data adapters and provider normalization.
---

# Provider Integration

Provider adapters are read-only public market-data components. They do not authenticate, inspect user accounts, place orders, or own strategy/risk/portfolio decisions.

## Required workflow
1. Confirm exact provider, host, endpoint, method, data purpose, and authorization.
2. Use fixed allowlisted hosts and endpoint paths. Reject redirects or destination changes outside the approved host boundary.
3. Validate HTTP status, content type, response size, JSON shape, required keys, types, numeric finiteness, precision, timestamp units/ranges, symbol identity, and candle ordering.
4. Normalize provider-specific representations into provider-neutral internal models without discarding source timestamp or provenance metadata.
5. Reject malformed or contradictory payloads. Never coerce invalid values into plausible defaults.
6. Bound timeouts, retries, response bytes, list lengths, and numeric magnitudes. Avoid unbounded recursion or parsing.
7. Sanitize exceptions and logs; do not expose response bodies, secrets, or untrusted control characters.
8. Keep deterministic fixtures for success, empty, malformed, oversized, stale, and provider-error cases.
9. Test adapter behavior offline. Network diagnostics must be separate, read-only, and explicitly authorized.

## Tokocrypto boundary
Only unauthenticated public GET requests to `www.tokocrypto.site` for server time and candles are approved. `www.tokocrypto.com`, authenticated endpoints, private account endpoints, balance endpoints, and trading endpoints are outside scope unless separately authorized.
