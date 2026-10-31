# Live market-data check (1h candles, last 14 days)
Generated 2026-10-31 04:02:31 UTC · **READ-ONLY** · no keys, no orders

## Overall: ✅ PASS
3 of 4 providers VERIFIED (need 1). Enough providers passed every validation check.

| Provider | Pair | Verdict | Last close | Last closed candle | Candles | Requests |
|---|---|---|---|---|---|---|
| kraken | BTC/USD | ✅ VERIFIED | 77,018.20 USD | 2026-10-31 03:00 UTC | 335 | 2 |
| coinbase | BTC/USD | ✅ VERIFIED | 77,011.23 USD | 2026-10-31 03:00 UTC | 335 | 3 |
| binance-vision | BTC/USDT | ✅ VERIFIED | 77,170.74 USDT | 2026-10-31 03:00 UTC | 335 | 2 |
| tokocrypto | BTC/USDT | 🚫 BLOCKED FROM RUNNER | - | - | - | 1 |

## kraken - ✅ VERIFIED
- Pair: **BTC/USD** (quote asset USD; USD and USDT are different assets)
- Docs: https://docs.kraken.com/api-reference/market-data/get-ohlc-data
- 1 Reachability: OK (exchange time 2026-10-31 04:02 UTC)
- 2 Parsing: OK (336 candles parsed)
- 3 Validation: PASS
- HTTP evidence: `/0/public/Time` HTTP 200; `/0/public/OHLC` HTTP 200

| Check | Result | Detail |
|---|---|---|
| has_data | ✅ PASS | 336 candles received |
| order_and_duplicates | ✅ PASS | sorted_as_received=True, exact_duplicates_removed=0, conflicting_duplicates=0 |
| closed_candles | ✅ PASS | 335 closed candles; 1 still-forming candle(s) excluded |
| timestamp_grid | ✅ PASS | all timestamps are exact multiples of 3600s |
| missing_candles | ✅ PASS | 0 missing (0.00%) |
| ohlc_sanity | ✅ PASS | high/low/open/close are consistent and positive |
| volume_sanity | ✅ PASS | 0 invalid volume(s); 0 zero-volume candle(s) of 335 |
| price_spikes | ✅ PASS | 0 close-to-close move(s) larger than 10% |
| freshness | ✅ PASS | newest closed candle ended 151s before exchange time (limit 7200s) |
| history_coverage | ✅ PASS | first candle 2026-10-17 05:00 UTC vs requested start 2026-10-17 04:02 UTC |
| clock_skew | ✅ PASS | runner clock differs from exchange clock by 0s |

## coinbase - ✅ VERIFIED
- Pair: **BTC/USD** (quote asset USD; USD and USDT are different assets)
- Docs: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
- 1 Reachability: OK (exchange time 2026-10-31 04:02 UTC)
- 2 Parsing: OK (336 candles parsed)
- 3 Validation: PASS
- HTTP evidence: `/time` HTTP 200; `/products/BTC-USD/candles` HTTP 200; `/products/BTC-USD/candles` HTTP 200

| Check | Result | Detail |
|---|---|---|
| has_data | ✅ PASS | 336 candles received |
| order_and_duplicates | ✅ PASS | sorted_as_received=True, exact_duplicates_removed=0, conflicting_duplicates=0 |
| closed_candles | ✅ PASS | 335 closed candles; 1 still-forming candle(s) excluded |
| timestamp_grid | ✅ PASS | all timestamps are exact multiples of 3600s |
| missing_candles | ✅ PASS | 0 missing (0.00%) |
| ohlc_sanity | ✅ PASS | high/low/open/close are consistent and positive |
| volume_sanity | ✅ PASS | 0 invalid volume(s); 0 zero-volume candle(s) of 335 |
| price_spikes | ✅ PASS | 0 close-to-close move(s) larger than 10% |
| freshness | ✅ PASS | newest closed candle ended 151s before exchange time (limit 7200s) |
| history_coverage | ✅ PASS | first candle 2026-10-17 05:00 UTC vs requested start 2026-10-17 04:02 UTC |
| clock_skew | ✅ PASS | runner clock differs from exchange clock by 0s |

## binance-vision - ✅ VERIFIED
- Pair: **BTC/USDT** (quote asset USDT; USD and USDT are different assets)
- Docs: https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only
- 1 Reachability: OK (exchange time 2026-10-31 04:02 UTC)
- 2 Parsing: OK (336 candles parsed)
- 3 Validation: PASS
- HTTP evidence: `/api/v3/time` HTTP 200; `/api/v3/klines` HTTP 200

| Check | Result | Detail |
|---|---|---|
| has_data | ✅ PASS | 336 candles received |
| order_and_duplicates | ✅ PASS | sorted_as_received=True, exact_duplicates_removed=0, conflicting_duplicates=0 |
| closed_candles | ✅ PASS | 335 closed candles; 1 still-forming candle(s) excluded |
| timestamp_grid | ✅ PASS | all timestamps are exact multiples of 3600s |
| missing_candles | ✅ PASS | 0 missing (0.00%) |
| ohlc_sanity | ✅ PASS | high/low/open/close are consistent and positive |
| volume_sanity | ✅ PASS | 0 invalid volume(s); 0 zero-volume candle(s) of 335 |
| price_spikes | ✅ PASS | 0 close-to-close move(s) larger than 10% |
| freshness | ✅ PASS | newest closed candle ended 152s before exchange time (limit 7200s) |
| history_coverage | ✅ PASS | first candle 2026-10-17 05:00 UTC vs requested start 2026-10-17 04:02 UTC |
| clock_skew | ✅ PASS | runner clock differs from exchange clock by 1s |

## tokocrypto - 🚫 BLOCKED FROM RUNNER
- Pair: **BTC/USDT** (quote asset USDT; USD and USDT are different assets)
- Docs: https://www.tokocrypto.com/apidocs/
- 1 Reachability: FAIL
- 2 Parsing: not run
- 3 Validation: not run
- Failure detail: https://www.tokocrypto.site/api/v3/time -> HTTP 451: <body><embed src='/not-support' type='text/html' style='width:100%;height:100vh;'/></body> (not retried)
- HTTP evidence: `/api/v3/time` HTTP 451

## Cross-check (information only) at candle 2026-10-31 03:00 UTC

| Provider | Quote | Close |
|---|---|---|
| kraken | USD | 77,018.20 |
| coinbase | USD | 77,011.23 |
| binance-vision | USDT | 77,170.74 |

Spread between highest and lowest close: 0.207%. Different venues and quote assets (USD vs USDT) are expected to differ a little.

## Limits of this report

- A VERIFIED provider means: the endpoint answered from this runner, the candles parsed, and they passed every check above at this moment. It says nothing about profit.
- Only one run is shown; availability from GitHub can change. Re-run to re-verify.
- BLOCKED FROM RUNNER means the exchange refused this runner (HTTP 403/451). No attempt is made to bypass it.
