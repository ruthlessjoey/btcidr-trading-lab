# Crypto and meme-coin market-data source approval matrix

**Research date:** 23 November 2026  
**Purpose:** Identify technically suitable and rights-compatible data sources for crypto spot and meme-coin research.  
**Important:** Preliminary documentation review, not legal advice. Terms can change; obtain written provider confirmation where indicated. No provider APIs were called, no market data was downloaded, no accounts were created, and no subscriptions or payments were made.

## Current authorization boundary

The only currently approved market-data request remains unauthenticated HTTPS GET BTCIDR candles from:

`https://www.tokocrypto.site/api/v3/klines`

No other provider, symbol, network, path, API, WebSocket, archive download or dataset is authorized for retrieval. This document does not expand that permission.

The approved BTCIDR feed was previously observed to end on 29 November 2025. It is stale for current signals and recent out-of-sample validation. Do not forward-fill or extrapolate it.

## Candidate comparison

| Source | Best fit | Documented coverage / limits | Rights and restrictions | Decision |
|---|---|---|---|---|
| Kraken historical OHLCVT archive | CEX historical baseline | Full history per Kraken pair through 30 Sep 2026; 1m, 5m, 15m, 1h, 4h, 12h and 1d. Full archive split into roughly 2 GB parts with SHA-256 checksums. Missing intervals mean no trades. REST OHLC endpoint is limited to 720 recent candles. | Kraken's API and global terms need a written interpretation for this project's automated personal research use. | Strong CEX candidate; request written permission before retrieval. |
| Binance Public Data / Vision | Broad CEX historical research | Public spot archives by symbol and interval, with daily/monthly files and checksums. | Published data terms use CC BY-NC-SA 4.0 and restrict live proprietary trading execution and automated commercial order generation. | Research-only candidate if strictly non-commercial and separately approved; not a permanent live-data source. |
| CryptoDataDownload free CSV | Broad CEX research baseline | Free historical OHLCV from major exchanges; advertised coverage extends back to 2017. Some granularities or markets may require a free account. | Free downloads are CC BY-NC-SA 4.0. This is not a commercial license. | Possible non-commercial research dataset only; not approved for retrieval. |
| CryptoDataDownload paid API | CEX history and prepared ML features | Advertises 1,500+ instruments, 112+ endpoints, Binance spot/futures, Deribit, Bitstamp, Gemini, Coinbase, Kraken and Bitfinex data. Token-authenticated quota: 10,000/day; 1m endpoints: 100/hour. No DEX pool or Pump.fun coverage was established in the reviewed catalog. | Advertises a personal commercial license at US$79.99/month. AI-training, retention and underlying-source rights still need written confirmation. Requires account/token. | Strong paid CEX candidate if individual-use and AI/ML rights are confirmed; no DEX/meme-pool coverage established. |
| GeckoTerminal Public API | DEX pool OHLCV for meme coins | Pool-address OHLCV; day/hour/minute timeframes; max 1,000 candles; `before_timestamp` pagination. Swagger says 1-minute caching, 2–3 seconds after confirmed transactions, and approximately 10 calls/minute. A newer support article says 30 calls/minute, so published limits conflict. API is beta. | CoinGecko/GeckoTerminal terms impose data-use, caching and AI-training restrictions. Do not use for model training, holdout validation or retained historical datasets without written permission. | Technically relevant for DEX discovery/research, but unsuitable as a default AI-training dataset under currently visible terms. |
| DEX Screener API | New-pair and token discovery | Official API documents token profiles, pair/token lookups and market metadata with endpoint-specific rate limits. No historical OHLCV candle endpoint appears in the official reference reviewed. | API terms restrict directly competing products, resale and third-party distribution. | Possible discovery-only candidate; not a backtest data source. |
| pumpdata.fun sample dataset | Solana meme-coin execution/microstructure research | One UTC day (15 Oct 2026), approximately 42.2 million rows and 4.16 GB; includes Pump.fun bonding-curve and PumpSwap trades, failed transactions, launches and graduations. | Sample declares CC BY 4.0 with attribution. Full history is licensed for internal research only; aggregate findings may be published, but not raw rows or substitutable datasets. Full-history access is sold through x402/USDC. | Excellent schema/stress-test candidate, but one day is not profitability evidence. Full-history purchase is not authorized and conflicts with the no-payment boundary. |
| PumpArchive GitHub | Potential Solana token-history archive | Repository currently contains only a README describing an architecture and roadmap; no implementation files were present in the inspected repository tree. | No repository license file was present. | Not installable or reusable as code at this time. |
| CoinAPI | Broad CEX/DEX market-data platform | Advertises 400+ exchanges, DEXs and prediction markets, OHLCV, trades and order books. Exact Pump.fun/Solana DEX coverage needs a symbol/venue confirmation. | Its usage policy says internal trading systems, quantitative research and internal AI/ML are generally allowed. However, its binding customer agreement grants use for **internal business purposes only**, requires account registration and a paid subscription, and leaves third-party data-source licensing to the customer. | Potential only if CoinAPI confirms in writing that an individual personal project is eligible and confirms the exact DEX coverage. Not free or currently authorized. |
| Coinbase market data | CEX spot candles | Public candle API has per-request history limits and requires pagination for deeper history. | Market Data Terms (updated 7 Aug 2026) permit personal/research use but expressly prohibit using Market Data or derived works to develop, train, fine-tune, validate, benchmark or improve AI/ML models or automated systems. | Exclude from Twin Money Maker model training, validation and profitability research. |
| Massive / Polygon crypto flat files | CEX trades and aggregates | Daily flat files with trades, minute aggregates and daily aggregates across Coinbase, Bitfinex, Bitstamp and Kraken. | Individual market-data terms restrict use to personal, non-business and non-commercial purposes and prohibit AI/ML training unless expressly permitted. | Exclude from AI training unless a separate written license is obtained. |

## Recommended path

1. **Do not add another provider to runtime yet.** Keep the existing NextMe BTCIDR request-policy validator offline-only.
2. **For CEX historical research:** ask Kraken to confirm automated personal research/backtesting rights for its public OHLCVT archive. If not granted, ask CryptoDataDownload whether its paid personal commercial license expressly covers private AI training, model validation and retention.
3. **For meme-coin history:** the pumpdata.fun sample is a technically rich one-day fixture, not a backtest corpus. Full history requires a separate license and payment, neither authorized. Ask the provider whether a no-payment research sample or academic tranche is available.
4. **For DEX discovery:** DEX Screener may be useful for candidate-pair discovery only, subject to its API terms. Do not treat boosts, promotions or displayed volume as proof of organic demand.
5. **Do not rely on GeckoTerminal/CoinGecko data for AI training or holdout validation** unless the provider grants written rights that cover those uses.
6. **CoinAPI is not approved as an individual-use source yet.** Its usage policy is more permissive for internal AI/ML than several alternatives, but its customer agreement's "internal business purposes only" grant must be clarified for a personal project.
7. Keep all provider data source IDs, terms versions, retrieval timestamps, payload hashes, listing dates, delistings and symbol mappings in the provenance record. Never combine datasets with incompatible rights into one training corpus.

## Approval required before any retrieval

A future data-access request must name the exact provider, endpoint or archive, symbols/markets, data fields, intended use (discovery, backtest, model training, validation or paper monitoring), retention period, and license basis. Approval for one source does not authorize other endpoints or providers.

No profitability claim can be made from synthetic data or from a one-day meme-coin sample. Authentic multi-period history, realistic execution costs and untouched out-of-sample periods remain mandatory.

## Official documentation and terms reviewed

- [Kraken downloadable historical OHLCVT archive](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data)
- [Kraken public OHLC API](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data)
- [Binance Public Data repository](https://github.com/binance/binance-public-data)
- [Binance Public Data terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- [CryptoDataDownload free historical files](https://www.cryptodatadownload.com/data/)
- [CryptoDataDownload API and pricing](https://www.cryptodatadownload.com/api/)
- [CryptoDataDownload API reference and quotas](https://api.cryptodatadownload.com/)
- [GeckoTerminal API specification](https://api.geckoterminal.com/docs/v2/swagger.json)
- [GeckoTerminal terms](https://www.geckoterminal.com/terms)
- [CoinGecko API terms](https://www.coingecko.com/en/api_terms)
- [DEX Screener API reference](https://docs.dexscreener.com/api/reference)
- [DEX Screener API terms](https://docs.dexscreener.com/api/api-terms-and-conditions)
- [pumpdata.fun one-day sample dataset card](https://huggingface.co/datasets/pumpdatafun/pump-fun-trades-sample)
- [PumpArchive repository](https://github.com/PumpArchive/PumpArchive)
- [CoinAPI usage policy](https://www.coinapi.io/usage-policy)
- [CoinAPI customer agreement and legal terms](https://www.coinapi.io/legal)
- [Coinbase Market Data Terms of Use](https://www.coinbase.com/legal/market_data)
- [Massive market data terms](https://massive.com/terms)
