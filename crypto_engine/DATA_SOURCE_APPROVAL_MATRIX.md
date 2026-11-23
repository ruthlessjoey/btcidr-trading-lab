# Crypto and meme-coin market-data source approval matrix

**Research date:** 23 November 2026  
**Purpose:** Identify lawful, technically suitable data sources for crypto spot and meme-coin research.  
**Important:** This is a documentation review only. No provider APIs were called, no market data was downloaded, no accounts were created, and no subscriptions or payments were made.

## Current authorization boundary

The only currently approved market-data request remains unauthenticated HTTPS GET BTCIDR candles from:

`https://cloudme-toko.2meta.app/api/v1/klines`

No other provider, symbol, network, path, API, WebSocket, archive download or dataset is authorized for retrieval. This document does not expand that permission.

The approved BTCIDR feed was previously observed to end on 29 November 2025. It is stale for current signals and recent out-of-sample validation. Do not forward-fill or extrapolate it.

## Candidate comparison

| Source | Best fit | Documented coverage / limits | Rights and restrictions | Decision |
|---|---|---|---|---|
| Kraken historical OHLCVT archive | CEX historical baseline | Full history per Kraken pair through 30 Sep 2026; 1m, 5m, 15m, 1h, 4h, 12h and 1d. Full archive split into roughly 2 GB parts with SHA-256 checksums. Missing intervals mean no trades. REST OHLC endpoint is limited to 720 recent candles. | Kraken's API and global terms need a written interpretation for this project's automated personal research use. | Strong CEX candidate; request written permission before retrieval. |
| Binance Public Data / Vision | Broad CEX historical research | Public spot archives by symbol and interval, with daily/monthly files and checksums. | Published data terms use CC BY-NC-SA 4.0 and restrict live proprietary trading execution and automated commercial order generation. | Research-only candidate if strictly non-commercial and separately approved; not a permanent live-data source. |
| CryptoDataDownload free CSV | Broad CEX research baseline | Free daily, hourly and 1-minute OHLCV from major exchanges, advertised since 2017; daily refresh. Some granularities may require a free account. | Free downloads are CC BY-NC-SA 4.0. This is not a commercial license. | Possible non-commercial research dataset only; not approved for retrieval. |
| CryptoDataDownload paid API | CEX history and prepared ML features | API catalog advertises multi-exchange OHLCV, tick data, risk metrics and precomputed ML features; token-authenticated limits include 10,000 requests/day and 100 requests/hour for 1m endpoints. | Advertises a personal commercial license at US$79.99/month. Exact AI-training, retention and source-specific rights still need written confirmation. Requires account/token. | Potential paid CEX option; do not subscribe or create credentials without approval. |
| GeckoTerminal Public API | DEX pool OHLCV for meme coins | Pool-address OHLCV; day/hour/minute timeframes; max 1,000 candles; `before_timestamp` pagination. Swagger says 1-minute caching, 2–3 seconds after confirmed transactions, and approximately 10 calls/minute. A newer support article says 30 calls/minute, so the published limits conflict. API is beta. | CoinGecko/GeckoTerminal terms impose data-use, caching and AI-training restrictions. Do not use for model training, holdout validation or retained historical datasets without written permission. | Technically relevant for DEX discovery/research, but unsuitable as a default AI-training dataset under currently visible terms. |
| DEX Screener API | New-pair and token discovery | Official API documents token profiles, pair/token lookups and market metadata with endpoint-specific rate limits. No historical OHLCV candle endpoint appears in the official reference reviewed. | Commercial and non-commercial use is described, but direct competing products, resale and third-party distribution are restricted. | Possible discovery-only candidate; not a backtest data source. |
| pumpdata.fun sample dataset | Solana meme-coin execution/microstructure research | One UTC day (15 Oct 2026), approximately 42.2 million rows and 4.16 GB; includes Pump.fun bonding-curve and PumpSwap trades, failed transactions, launches and graduations. | Sample declares CC BY 4.0 with attribution. Full history is licensed for internal research only; aggregate findings may be published, but not raw rows or substitutable datasets. Full-history access is sold through x402/USDC. | Excellent schema/stress-test candidate, but one day is not profitability evidence. Full-history purchase is not authorized and conflicts with the no-payment boundary. |
| PumpArchive GitHub | Potential Solana token-history archive | Repository currently contains only a README describing an architecture and roadmap; no implementation files were present in the inspected repository tree. | No repository license file was present. | Not installable or reusable as code at this time. |
| CoinAPI | Broad CEX/DEX market-data platform | Advertises 400+ exchanges, DEXs and prediction markets, OHLCV, trades and order books. Exact Pump.fun/Solana DEX coverage needs a symbol/venue confirmation. | Usage guidance says internal trading systems, quantitative research and internal AI/ML are allowed; the customer agreement grants use for internal business purposes and requires an account, API key and paid subscription. | Best apparent licensing fit for internal AI research if a paid plan and exact DEX coverage are approved; not free and not currently authorized. |
| Coinbase market data | CEX spot candles | Public candle API has per-request history limits and requires pagination for deeper history. | Market-data terms reviewed prohibit AI/ML training, fine-tuning, validation or benchmarking. | Exclude from model training and profitability validation. |
| Massive / Polygon crypto flat files | CEX trades and aggregates | Daily flat files with trades, minute aggregates and daily aggregates across Coinbase, Bitfinex, Bitstamp and Kraken. | Individual market-data terms restrict use to personal, non-business and non-commercial purposes and prohibit AI/ML training unless expressly permitted. | Exclude from AI training unless a separate written license is obtained. |

## Recommended path

1. **Do not add another provider to runtime yet.** Keep the existing NextMe BTCIDR request-policy validator offline-only.
2. **For CEX historical research:** ask Kraken to confirm automated personal research/backtesting rights for its public OHLCVT archive. If not granted, ask CryptoDataDownload whether its paid personal commercial license expressly covers private AI training and model validation.
3. **For meme-coin history:** the pumpdata.fun sample is a technically rich one-day fixture, not a backtest corpus. Full history requires a separate license and payment, neither authorized. Ask the provider whether a no-payment research sample or academic tranche is available.
4. **For DEX discovery:** DEX Screener may be useful for candidate-pair discovery only, subject to its API terms. Do not treat boosts, promotions or displayed volume as proof of organic demand.
5. **Do not rely on GeckoTerminal/CoinGecko data for AI training or holdout validation** unless the provider grants written rights that cover those uses.
6. Keep all provider data source IDs, terms versions, retrieval timestamps, payload hashes, listing dates, delistings and symbol mappings in the provenance record. Never combine datasets with incompatible rights into one training corpus.

## Approval required before any retrieval

A future data-access request must name the exact provider, endpoint or archive, symbols/markets, data fields, intended use (discovery, backtest, model training, validation or paper monitoring), retention period, and license basis. Approval for one source does not authorize other endpoints or providers.

No profitability claim can be made from synthetic data or from a one-day meme-coin sample. Authentic multi-period history, realistic execution costs and untouched out-of-sample periods remain mandatory.
