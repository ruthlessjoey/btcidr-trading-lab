# Bitstamp historical market-status evidence research

**Research date:** 2026-11-29  
**Scope:** static inspection of official Bitstamp public documentation and listing announcements only. No API requests, data downloads, credentials, or account access.

## 1. Current API status semantics — official documentation

Bitstamp's API changelog dated 2026-11-09 states that `GET /api/v2/markets/` now exposes a separate `matching` field and that `trading` reports order entry:

- Operational: `trading=Enabled`, `matching=Enabled`.
- No-matching halt: `trading=Enabled`, `matching=Disabled`; limit orders can be placed/cancelled, but instant and market orders are rejected.
- Full halt: `trading=Disabled`, `matching=Disabled`.

This resolves current field semantics, but it is a current-state API description. It does not supply historical status intervals for 2024–2026. A current endpoint response cannot be projected backwards into historical market eligibility.

Source: https://www.bitstamp.net/api/

## 2. Historical public order-event endpoint is not a market-status ledger

The same official API changelog records a 2026-02-16 `POST /api/v2/order_data/` endpoint for historical public order-event gap recovery. The documentation lists X-Auth authentication headers and `since_id` / `until_id` event-ID bounds; if `since_id` is omitted, the default is only 24 hours before `until_id`.

This endpoint:
- requires authentication;
- is a public order-event gap-recovery interface, not a historical market-status endpoint;
- does not establish listing, matching-enable, or instant/market-order-enable timestamps;
- is not used by this project.

No credentials were requested or used, and no request was made.

Source: https://www.bitstamp.net/api/

## 3. SHIB/USD — partial timestamps established

Bitstamp's official listing schedule gives:
- Post-only order entry: 2022-06-07 07:00 UTC (Unix 1654585200).
- Limit-only matching: 2022-06-07 11:00 UTC (Unix 1654599600).
- Full trading / all order types: only after sufficient liquidity; no exact activation timestamp is provided.

The evidence manifest now records the first two timestamps. The first market-order-enable timestamp, eligible start, continuous status intervals, source snapshot hash, and independent review remain missing.

Source: https://blog.bitstamp.net/post/shib-listing/

## 4. SOL/USD — partial timestamps established

Bitstamp's official listing schedule gives:
- Post-only order entry: 2022-08-23 07:00 UTC (Unix 1661238000).
- Limit-only matching: 2022-08-23 11:00 UTC (Unix 1661252400).
- Full trading / all order types: only after sufficient liquidity; no exact activation timestamp is provided.

The evidence manifest now records the first two timestamps. The first market-order-enable timestamp, eligible start, continuous status intervals, source snapshot hash, and independent review remain missing.

A separate 2023 notice suspended SOL trading for US customers only. That is jurisdiction-specific and must not be misrepresented as a global market halt.

Sources:
- https://blog.bitstamp.net/post/sol-and-dot-are-now-available/
- https://blog.bitstamp.net/post/important-update-halt-of-axs-chz-ex-ny-mana-matic-near-sand-and-sol/
- https://blog.bitstamp.net/post/were-listing-pepe-and-relisting-sol-in-the-usa/

## 5. PEPE/USD — listing date only

Bitstamp's official 2024-02-13 announcement lists PEPE/USD and PEPE/EUR globally, excluding the US and Singapore. A separate US availability announcement was published 2024-11-29.

Neither source gives the exact first full market-order-enable timestamp or a continuous historical matching/status ledger. The manifest therefore retains the announcement date but does not invent an eligible-start timestamp.

Sources:
- https://blog.bitstamp.net/post/bitstamps-new-listings-lmwr-pepe-blur-and-vext/
- https://blog.bitstamp.net/post/were-listing-pepe-and-relisting-sol-in-the-usa/

## 6. Gate disposition

The following remain unchanged:
- Data rights: `NOT_VERIFIED`.
- Independent review: `NOT_VERIFIED`.
- Source snapshot SHA-256 values: null until immutable official snapshots are captured.
- Historical market-order-enable timestamps: incomplete.
- Continuous status intervals: empty.
- Accepted evidence digest: unpinned.
- Public research: blocked before the first provider request.

The partial SHIB and SOL timestamps are source-derived facts, not a complete eligibility attestation. No status interval or market-order eligibility has been inferred from a listing notice.
