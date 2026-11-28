# Bitstamp public API data-rights terms research

**Research date:** 2026-11-29  
**Scope:** static reading of official Bitstamp API documentation and the Bitstamp Ltd Terms of Use. No provider requests, market-data downloads, credentials, account access, or legal advice.

## 1. Official API documentation

Bitstamp's Public API documentation contains a section titled **Commercial Use of Bitstamp's Exchange Data**. It directs companies using Bitstamp exchange data for their own commercial purposes to contact `partners@bitstamp.net` and sign a commercial-use Data License Agreement. It also describes incorporation and redistribution for commercial purposes under that framework.

The API page does not expressly state whether an individual may retain raw public API candles, derived features, research outputs, or backups for private noncommercial research. The commercial-use section is not treated as an affirmative personal-use data licence.

Source: https://www.bitstamp.net/api/

## 2. Official Bitstamp Ltd Terms of Use

The official Terms of Use page for Bitstamp Ltd was reviewed. It was last updated 2025-05-30.

Relevant provisions, paraphrased:
- The Terms grant a personal, non-exclusive, non-transferable, non-sublicensable and limited right to enter and use the Site and Services.
- The Limited Right of Use section describes Materials as Site content such as text, graphics, logos, icons and images, permits a personal/informational/noncommercial copy of those Materials, and separately restricts copying, scraping, collecting or distributing Materials manually or automatically.
- The page discusses API keys and third-party applications as a way to access Services, but it does not expressly define public API market-data retention rights.

The reviewed Terms do not explicitly resolve whether public API market data is within the defined Site Materials, whether local storage of raw OHLC candles is permitted, or whether derived statistical research artifacts may be retained. This is a genuine ambiguity, not an affirmative permission and not proof of a prohibition.

Source: https://www.bitstamp.net/legal/terms-of-use/ltd/

## 3. Applicable-entity limitation

The reviewed Terms are specifically for Bitstamp Ltd. The applicable Bitstamp contracting entity for any individual account or API relationship is not established by this public research. No account was accessed to identify it, and no account information is required for this research.

## 4. Required written clarification

Before admitting Bitstamp data for durable research storage, obtain written clarification from Bitstamp covering:
1. Unauthenticated public API market data used by an individual for private, noncommercial research.
2. Local retention of raw OHLC candles and source-response hashes.
3. Retention and use of derived features, aggregate statistics, and private research reports.
4. Private backup and reproducibility copies.
5. Any restrictions on later use of those results for the individual's own trading decisions.
6. Whether a separate agreement is required for any future commercial use or redistribution.

If any commercial use or redistribution is contemplated, follow the API documentation's Data License Agreement route before that use.

## 5. Evidence-gate disposition

Keep unchanged:
- `data_rights.status = NOT_VERIFIED`.
- Source snapshot hashes null until immutable official snapshots are captured and hashed.
- Accepted evidence digest unpinned.
- Public research blocked before the first provider request.

This note is a terms-research record only. It is not legal advice, does not grant permission, and does not authorize any API request or data download.
