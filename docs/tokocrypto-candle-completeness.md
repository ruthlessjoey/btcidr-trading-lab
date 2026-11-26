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


## Clock trust gate

The current caller-clock helper accepts a positive integer epoch and labels its source, but it cannot authenticate that value. A syntactically valid integer, a call to the process wall clock, and an elapsed-time check against a monotonic clock do not establish absolute UTC accuracy. A monotonic clock can detect elapsed-time discontinuities after a trusted anchor; it cannot prove that the initial anchor is correct.

Until a reviewed host-clock attestor exists:
- current-window collection, freshness claims and unattended scheduling remain blocked;
- caller-supplied timestamps must remain explicitly `NOT_VERIFIED`;
- the provider's candle timestamps must not be treated as a substitute for a trusted current-time source;
- do not restore Tokocrypto `/api/v3/time`, use `.com`, query another unapproved endpoint, or introduce an external time service without separate approval.

A future attestor must provide a bounded evidence record containing the UTC epoch, clock source and synchronization state, last successful synchronization time, uncertainty bound, and paired monotonic reading. The consumer must reject missing/stale evidence, unsynchronized status, uncertainty above the preregistered threshold, or wall-clock/monotonic discontinuity. The implementation must prove which host service produced the evidence rather than trusting caller-supplied booleans or labels.

On iPhone, the user-facing “Set Automatically” setting is an operator configuration, not an attestation readable by this Python helper; it cannot alone certify unattended automation. A runtime platform and its supported clock-status interface must be selected and independently tested before implementing the attestor. This project does not yet have an approved platform attestor.

Historical research can avoid dependence on current wall-clock time by preregistering fixed UTC start/end boundaries that are wholly in the past, then applying the complete-grid and point-in-time gates. That is a separate research-window interface; it must not silently reuse the current-window helper with an arbitrary timestamp.


## Fixed UTC-boundary research windows

A separate fixed-boundary helper can retrieve a pre-registered interval without reading a current wall clock or requesting provider server time. The caller supplies exact integer UTC start and end-exclusive epochs; both must align to the timeframe, increase, and remain within the 14-day request bound. The helper reuses the same complete-grid and OHLCV checks.

It deliberately does **not** assert that the selected interval is in the past, authenticate the preregistration record, verify the provider clock, or establish market identity. Its output labels the temporal past assertion `NOT_PERFORMED` and provider clock skew `NOT_VERIFIED`. Only use fixed windows whose boundaries have been preregistered and independently verified as historical. Do not use this interface for unattended current-market collection.

The interface makes no request during validation or testing; all regressions use synthetic responses. The only network path available when a caller explicitly invokes retrieval remains the exact approved public `/api/v3/klines` GET.


## Static pair allowlist

The Tokocrypto helper currently accepts only `BTC_USDT`, matching the one static Tokocrypto mapping present in the reviewed repository config/provider adapter. This is an implementation scope boundary, **not** proof that the pair is currently listed, that the provider's symbol identity is verified, or that the venue data are suitable for research. The identity status remains `NOT_VERIFIED`.

Any additional Tokocrypto pair requires a separate evidence-backed identity review and explicit allowlist update before the adapter will issue a request. The wider Twin Money Maker project remains multi-market; this restriction applies only to this single Tokocrypto adapter until its market registry is independently reviewed.


## Runtime enforcement of the current-window clock gate

The legacy `fetch_tokocrypto_candles` compatibility entry point is intentionally blocked and raises before invoking the opener. The earlier implementation merely labelled caller time `NOT_VERIFIED` while still allowing a network request; that contradicted the release rule above. Only a separately reviewed host-clock attestor may reopen current-window retrieval.

The fixed UTC-boundary research interface remains separate. It still does not prove the boundaries are historical or authenticate their preregistration record; the operator must independently freeze and verify those boundaries before a request. Market identity and provider rights remain separate hard gates.


## Canonical Tokocrypto candle request path

The general fetcher, low-level JSON transport, and legacy provider adapter are not authorized entry points for Tokocrypto candles. They reject Tokocrypto requests before invoking an opener. The only supported helper that opts into the Tokocrypto transport scope is `fetch_tokocrypto_fixed_window`, which requires explicit frozen UTC boundaries and passes the private fixed-window scope through the bounded fetcher.

This narrows ordinary call paths; it does not make caller-supplied boundaries authentic. The fixed-window helper still labels provider clock skew `NOT_VERIFIED` and temporal past assertion `NOT_PERFORMED`. A request must only be made after the preregistration is independently verified as historical and market identity/data rights are accepted. No current-window or unattended collection is enabled.
