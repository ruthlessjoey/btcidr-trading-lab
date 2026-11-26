# Bitstamp data-rights research addendum

Research date: 2026-11-27
Scope: public Bitstamp API documentation only; no account access, API credentials, provider API requests, market-data retrieval, or redistribution.

## Primary official source

Bitstamp Public API documentation: https://www.bitstamp.net/api/

The page's section **Commercial Use of Bitstamp's Exchange Data** states that companies seeking to use Bitstamp exchange data for their own commercial purposes are directed to contact partners@bitstamp.net and sign a commercial-use Data License Agreement. It also states that Bitstamp allows incorporation and redistribution of exchange data for commercial purposes under that framework.

The same page documents public market metadata and OHLC endpoints, and distinguishes current market fields including `trading`, `matching`, and `instant_and_market_orders`.

## What this source does and does not establish

Established by the current official API page:
- A commercial-use Data License Agreement is required for companies using Bitstamp exchange data for their own commercial purposes, as described by Bitstamp.
- The public API documentation exposes market metadata and OHLC endpoints.
- Current market status semantics include separate trading, matching, and instant/market-order fields.

Not established by the located official page:
- An affirmative grant or permission for this project's personal, noncommercial research use.
- Whether local retention of raw OHLC data, derived research datasets, hashes, or private GitHub storage is permitted under the applicable terms.
- Whether a later product, signal, paid service, or other commercial use is permitted without a separate license.
- Historical market-status intervals for 2024–2026.

The commercial-use statement must not be interpreted as an affirmative personal-use license. Equally, the absence of an explicit personal-use statement on this API page is not proof that personal use is prohibited. The governing terms and the user's intended storage/use case require confirmation from Bitstamp or a qualified reviewer.

## Evidence-gate disposition

Keep all of the following unchanged:
- `data_rights.status = NOT_VERIFIED`
- source `snapshot_sha256 = null` until an exact official source snapshot is captured and hashed
- `EXPECTED_EVIDENCE_SHA256 = None` until the complete manifest is accepted
- public-data collection blocked before the first market-metadata or OHLC request

Do not create a reviewer attestation from this desk research. Independent reviewers must assess the governing terms and the exact proposed use, storage, and retention scope, then attest to the same final evidence digest.

## Required next step

Obtain an authoritative written clarification from Bitstamp (or a documented applicable terms clause) covering personal, noncommercial API research and local storage of raw data and derived artifacts. If commercial use is later contemplated, obtain the commercial Data License Agreement before any such use. Record the exact source, retrieval date, immutable snapshot hash, and reviewer assessment without changing the gate to accepted prematurely.

## Source register

1. Bitstamp Public API (official; current API documentation): https://www.bitstamp.net/api/
2. Bitstamp fee schedule (official; fee information only, not a data-rights grant): https://www.bitstamp.net/fee-schedule/

This addendum is research documentation, not legal advice or a permission grant.
