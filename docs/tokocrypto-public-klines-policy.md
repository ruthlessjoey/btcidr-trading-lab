# Tokocrypto public-candle allowlist

Status: isolated security candidate; not merged into protected `main`.

## Sole permitted network operation

The only permitted Tokocrypto request is an unauthenticated HTTPS GET to this exact endpoint:

`https://www.tokocrypto.site/api/v3/klines`

The implementation enforces an exact host, scheme, path and query-parameter allowlist. The query must contain exactly one each of `symbol`, `interval`, `startTime`, `endTime` and `limit`; the response is capped at 4 MiB and 500 candle rows per request. Redirects are disabled for Tokocrypto requests. Duplicate, missing, malformed or unapproved query parameters fail closed.

## Explicitly blocked

- `/api/v3/time`
- `/api/v3/exchangeInfo` or other symbol/market discovery endpoints
- `/open/v1/**`
- The `www.tokocrypto.com` host and all other Tokocrypto host aliases
- Account, wallet, order, withdrawal, private, authenticated or WebSocket routes
- Redirects to any other route or host

The repository config now has one Tokocrypto source only: `tokocrypto-mbx`, `binance_style`, `https://www.tokocrypto.site`. The unapproved `.com` fallback was removed.

## Operational consequence

The legacy read-only orchestrators currently request exchange server time before candles. Tokocrypto server-time access is intentionally rejected, so these legacy orchestration paths fail closed for Tokocrypto rather than silently making an unapproved request. The fetcher and adapter can retrieve candles when an authorized caller supplies its own bounded time range; a separate safe orchestration path must be validated before enabling routine Tokocrypto collection. Do not restore the time endpoint or `.com` fallback to make the legacy runner pass.

## Test boundary

`tests/test_tokocrypto_endpoint_policy.py` imports only `fetcher.py` and `providers.py`; the dedicated workflow sparsely checks out those files, `config.json` and safe tests. It does not import `run.py`, `live_check.py`, `validator.py` or `report.py`, and it performs no network request. The regular Tokocrypto market diagnostic workflow remains blocked.

## Trading and data limitations

This control does not enable PAPER or LIVE execution, place orders, connect an account, or prove data quality or profitability. It authorizes no commercial redistribution of provider data. Only public spot candles are in scope; the source must still pass a separate data coverage, integrity, market-identity and cost-aware research gate before any strategy evaluation.
