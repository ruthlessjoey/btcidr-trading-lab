# Tokocrypto closed-window candle completeness

Status: isolated child candidate of PR #215; not merged into protected `main`.

## Contract

A requested `lookback_days` window is accepted only when the response contains the complete interval-aligned candle grid from the first requested open time through the last fully closed candle. Every open time must equal the previous expected open time plus exactly one interval.

The helper rejects:
- a missing first, middle or trailing candle;
- duplicate or out-of-order timestamps;
- a candle outside the requested closed UTC window;
- timestamps that are not aligned to the selected timeframe;
- malformed, non-finite or internally inconsistent OHLCV values.

It does not interpolate, forward-fill, synthesize zero-volume rows or otherwise repair missing provider data. A gap is a hard data-integrity failure. This is deliberately conservative: whether a provider omits no-trade intervals must be established from provider semantics and separately approved before any normalization policy is considered.

## Evidence boundary

The regression tests use only synthetic response rows and the existing approved endpoint construction. They make no DNS lookup, HTTP request or exchange call. The sparse workflow checks out only unprotected fetcher/provider/test files and does not import protected validator/report modules or protected directories.

A complete contiguous grid is necessary but not sufficient for research eligibility. It does not authenticate the caller clock, establish market/symbol identity, prove provider coverage outside the requested window, establish commercial data rights, or validate execution costs. In particular, caller clock synchronization remains `NOT_VERIFIED`; this change does not enable routine unattended collection, strategy evaluation, PAPER or LIVE execution.

## Acceptance

- Exact requested start and end boundaries are present.
- Every adjacent candle open time differs by exactly one timeframe interval.
- Actual candle count equals the number of intervals in the requested window.
- Any missing interval causes a fail-closed error before downstream research can consume the series.
