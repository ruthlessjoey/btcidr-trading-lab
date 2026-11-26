# Bitstamp V2 point-in-time market-universe research

Research date: 27 November 2026
Status: **INCOMPLETE — public-data runner must remain blocked.**

This note records public official Bitstamp announcements found during desk research. It is not an independent acceptance report and does not prove continuous market-order availability or source rights.

## Frozen V2 universe

The current V2 preregistration covers 1-hour USD spot markets from 2024-01-01 00:00 UTC through 2026-11-01 00:00 UTC:
`btcusd`, `ethusd`, `xrpusd`, `dogeusd`, `shibusd`, `pepeusd`, `solusd`.

## Official evidence located

| Market | Official Bitstamp evidence | What it establishes | What remains unknown |
|---|---|---|---|
| BTC/USD | [Changes to tick sizes, 2 Aug 2022](https://blog.bitstamp.net/post/changes-to-tick-sizes/) | BTC/USD existed as a spot pair by Aug 2022. The notice also records a no-matching maintenance halt of up to one hour on 10 Aug 2022. | Initial listing date and complete matching/market-order halt history over the frozen 2024–2026 interval. |
| ETH/USD | [Changes to tick sizes, 2 Aug 2022](https://blog.bitstamp.net/post/changes-to-tick-sizes/) | ETH/USD existed as a spot pair by Aug 2022. The notice records the same tick-size maintenance and up-to-one-hour no-matching halt. | Initial listing date and complete matching/market-order halt history over the frozen interval. |
| XRP/USD | [Bitstamp introduces XRP trading, 10 Jan 2017](https://blog.bitstamp.net/post/bitstamp-introduces-xrp-trading/) says full trading from 17 Jan 2017. [US halt notice, 25 Dec 2020](https://blog.bitstamp.net/post/xrp-trading-and-deposits-be-halted-us-customers/) says US trading halted 8 Jan 2021 21:00 UTC while other countries were unaffected. [US resumption, 13 Jul 2023](https://blog.bitstamp.net/post/xrp-is-back-in-the-us-start-trading-today/). | Global listing predates V2 start; the US-specific interruption ended before 2024. | Complete market-wide maintenance and matching history during 2024–2026; residency-specific scope must not be conflated with global public OHLC. |
| DOGE/USD | [We're listing Dogecoin, 22 Dec 2022](https://blog.bitstamp.net/post/were-listing-dogecoin-doge/) says DOGE was launched and available to buy/trade that day, with DOGE/USD and DOGE/EUR. | DOGE trading existed before the V2 start. | Exact first matching/market-order timestamp and complete later halt/maintenance history. |
| SHIB/USD | [We're listing SHIB, 6 Jun 2022](https://blog.bitstamp.net/post/shib-listing/) says transfers 6 Jun, post-only 7 Jun 07:00 UTC, limit-only matching 7 Jun 11:00 UTC, and full trading only after sufficient liquidity. The earlier [8 Dec 2021 notice](https://blog.bitstamp.net/post/lots-of-fresh-faces-around-bitstamp-these-days-4-new-cryptocurrencies/) had postponed the SHIB post-only/limit-only stages. | SHIB/USD existed before V2 start and matching began in limit-only mode on 7 Jun 2022 11:00 UTC. | Exact time when full trading/market orders became enabled. The current simulator assumes next-open market fills, so limit-only matching is not sufficient evidence for its execution model. |
| SOL/USD | [SOL and DOT now available, 24 Aug 2022](https://blog.bitstamp.net/post/sol-and-dot-are-now-available/) says SOL was listed globally except Singapore; transfer-only 22 Aug, post-only 23 Aug 07:00 UTC, limit-only matching 23 Aug 11:00 UTC, full trading after sufficient liquidity. [US relisting notice, 29 Nov 2024](https://blog.bitstamp.net/post/were-listing-pepe-and-relisting-sol-in-the-usa/). | Global SOL/USD existed before V2 start; US availability was jurisdiction-specific and later restored. | Exact full-trading/market-order enable time and complete market-wide halt history. |
| PEPE/USD | [Bitstamp new listings, 13 Feb 2024](https://blog.bitstamp.net/post/bitstamps-new-listings-lmwr-pepe-blur-and-vext/) lists PEPE/USD and PEPE/EUR globally, except Singapore and the US. The schedule may be subject to change. [US listing, 29 Nov 2024](https://blog.bitstamp.net/post/were-listing-pepe-and-relisting-sol-in-the-usa/). | PEPE was not listed at the frozen V2 start of 1 Jan 2024; the official global listing announcement is 13 Feb 2024. | Exact first matching/market-order timestamp and jurisdiction-specific history. The current single-start V2 manifest cannot truthfully claim PEPE coverage from 1 Jan 2024. |

## Material findings

1. **PEPE conflicts with the frozen common start date.** The current V2 dataset manifest requires 24,840 contiguous hourly candles from 1 Jan 2024, but Bitstamp's official global listing notice for PEPE is dated 13 Feb 2024. A complete PEPE dataset cannot include genuine pre-listing candles. The V2 common start must be amended, PEPE must use a separate later inception date with a new per-market preregistration, or PEPE must be deferred from this V2 cohort.
2. **SHIB and SOL have documented limit-only phases, but not exact full-trading timestamps in the located notices.** The current simulator assumes market fills at the next candle open. It cannot treat limit-only matching as proof that market-order fills were available.
3. **BTC/ETH maintenance notices prove that matching interruptions occur.** The adapter's missing-candle checks help detect gaps, but do not independently establish all short interruptions or order-type restrictions.
4. **XRP restrictions were jurisdiction-specific.** The US halt must not be incorrectly applied to global public OHLC, but the market's jurisdictional status still needs a clear scope definition.
5. These announcements do not provide a complete 2024–2026 trading/matching status ledger, delisting history, source-rights grant or evidence that every market was continuously eligible.

## Required decision and next evidence

- Preserve `POINT_IN_TIME_UNIVERSE_EVIDENCE_STATUS = NOT_VERIFIED`.
- Do not dispatch public research or request Bitstamp data.
- Independently verify exact first market-order/matching times, later halts and delistings for every candidate market.
- Resolve PEPE's pre-listing interval by either changing the common start date before any data run, creating a market-specific inception-date design, or deferring PEPE from V2.
- Confirm the data licence/terms permit the intended personal, noncommercial research and storage/hash workflow.
- Independently review this evidence and hash-pin an accepted universe manifest before changing the runner gate to VERIFIED.

No provider API was called and no market data was downloaded for this research note.


## Current order-entry and matching status semantics

Bitstamp's official [API changelog](https://www.bitstamp.net/api/) dated 9 November 2026 distinguishes order entry from matching:
- Operational: `trading=Enabled`, `matching=Enabled`.
- No-matching halt: `trading=Enabled`, `matching=Disabled`; limit orders can be entered/cancelled, but market and instant orders are rejected.
- Full halt: both fields are `Disabled`.

The current Bitstamp adapter requires both fields to be `Enabled`, and its offline tests explicitly reject a market with matching disabled. This is the correct current-state fail-closed check. The public endpoint reports current status only; it does not provide the historical 2024–2026 status ledger needed to prove continuous market-order availability.
