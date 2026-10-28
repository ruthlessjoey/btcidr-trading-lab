# Dataset gate: BTC/USDT 1d (binance-vision)
Generated 2026-10-28 10:04:51 UTC · **READ-ONLY** · no keys, no orders

## GATE: ✅ PASS
The dataset passed every check. The backtest may use it.

## Market identity

- Provider: **binance-vision** (`https://data-api.binance.vision`), spot market
- Symbol **BTCUSDT** = base BTC / quote **USDT**
- This is **not** Tokocrypto and not USD. It is a PROXY for Tokocrypto BTC/USDT; Tokocrypto prices, spreads and fills are unverified.
- Exchange's own description: `{'symbol': 'BTCUSDT', 'status': 'TRADING', 'baseAsset': 'BTC', 'quoteAsset': 'USDT', 'isSpotTradingAllowed': True}`

## Coverage (actual, from the exchange)

| Item | Value |
|---|---|
| First candle (open, UTC) | 2017-08-17 |
| Last completed candle (open, UTC) | 2026-10-27 |
| Rows | 3359 |
| Rows expected for a gap-free range | 3359 |
| Missing days | 0 |
| Exact / conflicting duplicates | 0 / 0 |
| Still-forming candle excluded | 1 |
| HTTP requests | 6 |

## Pagination evidence

| Request | Asked from | Rows | First | Last |
|---|---|---|---|---|
| 1 | 2017-01-01 | 1000 | 2017-08-17 | 2020-05-12 |
| 2 | 2020-05-13 | 1000 | 2020-05-13 | 2023-02-06 |
| 3 | 2023-02-07 | 1000 | 2023-02-07 | 2025-11-02 |
| 4 | 2025-11-03 | 360 | 2025-11-03 | 2026-10-28 |

## Checks

| Check | Result | Detail |
|---|---|---|
| market_identity | ✅ PASS | exchange says symbol=BTCUSDT base=BTC quote=USDT status=TRADING spot=True; expected BTCUSDT BTC/USDT TRADING spot |
| clock | ✅ PASS | exchange time 2026-10-28 10:04:52 UTC; runner differs by 1s |
| pagination | ✅ PASS | 4 request(s); 3360 rows received; 0 page boundary problem(s); every page ascending and not earlier than its requested start |
| duplicates | ✅ PASS | 0 exact duplicate(s), 0 conflicting duplicate(s) among 3360 received rows (the pager asks for non-overlapping ranges, so none are expected) |
| closed_candles_only | ✅ PASS | 1 still-forming candle(s) excluded; 3359 completed candles kept |
| history_depth | ✅ PASS | actual first candle 2017-08-17, last 2026-10-27, 3359 rows; required: first on or before 2017-09-30 and at least 3000 rows |
| missing_days | ✅ PASS | 0 missing of 3359 expected |
| timestamp_grid | ✅ PASS | 0 candle(s) not on a UTC 1d boundary |
| validator_ohlc_sanity | ✅ PASS | high/low/open/close are consistent and positive |
| validator_volume_sanity | ✅ PASS | 0 invalid volume(s); 0 zero-volume candle(s) of 3359 |
| validator_price_spikes | ⚠️ WARN | 1 close-to-close move(s) larger than 25% |
| validator_freshness | ✅ PASS | newest closed candle ended 36292s before exchange time (limit 172800s) |
| previous_version | ✅ PASS | v20261027T102341Z_c11776a0 re-verified (hash ok). vs this fetch: 3358 common candles, 0 changed, 0 only in old, 1 new |
| csv_hash_roundtrip | ✅ PASS | re-read from disk: 3359 rows, sha256 3a39e8b75451e71d123e31e762416a801188126f7b00d6b88aa2ffc25ac3df59, identical to fetched: True |

HTTP evidence (first requests): `/api/v3/exchangeInfo` HTTP 200; `/api/v3/time` HTTP 200; `/api/v3/klines` HTTP 200; `/api/v3/klines` HTTP 200; `/api/v3/klines` HTTP 200; `/api/v3/klines` HTTP 200

## Largest daily moves (shown so outliers are visible, not hidden)

- 2020-03-12: -39.50%
- 2017-12-07: +22.50%
- 2021-02-08: +19.54%
- 2018-01-16: -19.50%
- 2017-09-14: -19.16%

## Dataset version (preserved, never overwritten)

- Version: `v20261028T100451Z_3a39e8b7`
- CSV: `v20261028T100451Z_3a39e8b7.csv`
- Manifest: `v20261028T100451Z_3a39e8b7.manifest.json`
- SHA-256: `3a39e8b75451e71d123e31e762416a801188126f7b00d6b88aa2ffc25ac3df59`
- Rows: 3359

## Earlier version

- v20261027T102341Z_c11776a0

## Limits

- Passing this gate means the data is complete, ordered, de-duplicated and correctly labelled. It says nothing about whether any strategy makes money.
- Candle time = open time in UTC; a daily candle is known only after 00:00 UTC the next day.
- Binance can revise or delist data in future; each fetch is stored as a new version so changes can be detected.
