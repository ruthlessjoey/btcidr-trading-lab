# Cross-check of flagged candles

Dataset `v20261027T102241Z_c11776a0` (sha256 `c11776a0bbdcec4c...`). The Binance candles were **not changed**.

Sources: **Coinbase BTC/USD** daily candles (official docs read; USD is not USDT) and **Bitstamp BTC/USD** around flagged days (official docs NOT read this session, so unverified).
Pre-stated rule: open and close within 3.0%, and the day's return within 3.0 percentage points, on Coinbase BTC/USD (and Bitstamp if available).


## Whole-history comparison with Coinbase (3358 common days)

| Close difference |  |
|---|---|
| Median | 0.056% |
| 95th percentile | 0.926% |
| 99th percentile | 2.846% |
| Maximum | 11.780% |
| Days over 1% / 2% / 5% | 157 / 65 / 8 |

Largest disagreements: 2017-12-23 (11.78%), 2017-09-04 (8.851%), 2017-12-12 (7.784%), 2017-12-22 (6.22%), 2018-01-16 (5.791%), 2018-11-14 (5.654%), 2018-02-08 (5.282%), 2017-12-24 (5.076%)

## Flagged day 2020-03-12: **CONFIRMED (approximate: USD is not USDT)**

| Date | Source | Open | High | Low | Close |
|---|---|---|---|---|---|
| 2020-03-10 | binance | 7,929.87 | 8,149.00 | 7,728.01 | 7,894.56 |
| 2020-03-10 | coinbase | 7,934.56 | 8,158.25 | 7,733.56 | 7,894.68 |
| 2020-03-10 | bitstamp | 7,937.20 | 8,158.42 | 7,733.99 | 7,885.92 |
| 2020-03-11 | binance | 7,894.57 | 7,980.00 | 7,590.00 | 7,934.52 |
| 2020-03-11 | coinbase | 7,894.68 | 7,987.97 | 7,583.27 | 7,938.05 |
| 2020-03-11 | bitstamp | 7,893.63 | 7,988.78 | 7,591.99 | 7,934.57 |
| 2020-03-12 | binance | 7,934.58 | 7,966.17 | 4,410.00 | 4,800.00 |
| 2020-03-12 | coinbase | 7,938.05 | 7,969.45 | 4,644.00 | 4,857.10 |
| 2020-03-12 | bitstamp | 7,956.29 | 7,969.90 | 4,776.59 | 4,841.67 |
| 2020-03-13 | binance | 4,800.01 | 5,955.00 | 3,782.13 | 5,578.60 |
| 2020-03-13 | coinbase | 4,857.10 | 5,995.00 | 3,858.00 | 5,637.60 |
| 2020-03-13 | bitstamp | 4,841.67 | 5,990.35 | 3,850.00 | 5,622.74 |
| 2020-03-14 | binance | 5,576.05 | 5,640.52 | 5,055.13 | 5,172.06 |
| 2020-03-14 | coinbase | 5,630.93 | 5,669.00 | 5,050.00 | 5,165.25 |
| 2020-03-14 | bitstamp | 5,623.16 | 5,663.01 | 5,051.00 | 5,169.37 |
- vs coinbase: open -0.04%, close -1.18%, high -0.04%, low -5.04%; day return -39.50% (Binance) vs -38.81% (coinbase); gap -0.69 pp; rule met: True
- vs bitstamp: open -0.27%, close -0.86%, high -0.05%, low -7.67%; day return -39.50% (Binance) vs -38.98% (bitstamp); gap -0.52 pp; rule met: True
- High and low are shown but not used by the rule: they depend on when each venue traded the extreme, and this strategy uses only closes and next-day opens.

## Limits

- Two other venues agreeing supports that the move happened; it does not prove every price is exact.
- USD and USDT prices can differ, especially in a crash.
