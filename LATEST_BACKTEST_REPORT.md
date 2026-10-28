# BTC/USDT trend-filter backtest (research only)
Run `40669227958` · **READ-ONLY** · no keys, no orders, no live trading

> **This is a historical simulation on a proxy market. It does not show that the strategy is profitable and it is not a signal.** Costs are unverified assumptions, past data is one sample, and the market is Binance BTC/USDT, **not** Tokocrypto execution prices.

## Data (preserved version, pinned)

- `v20261027T102241Z_c11776a0` · sha256 `c11776a0bbdcec4c1dbc0d0c556e2d8f9ec691968b31d61e2e2376d950dbad54`
- binance-vision BTC/USDT 1d spot · 3358 candles · 2017-08-17 to 2026-10-26 (UTC open times)
- Re-verified at load: hash, market identity, order, no duplicates, no gaps, only completed candles.

## Flagged candle (2020-03-12, -39.5% in one day)

- **2020-03-12: CONFIRMED (approximate: USD is not USDT)** (rule: open and close within 3.0%, and the day's return within 3.0 percentage points, on Coinbase BTC/USD (and Bitstamp if available)).
  - coinbase: day return -38.81% vs Binance -39.50%, close diff -1.18%, low diff -5.04%
  - bitstamp: day return -38.98% vs Binance -39.50%, close diff -0.86%, low diff -7.67%
- Whole history vs Coinbase: median close difference 0.06%, 99th percentile 2.85%, max 11.78%.

Sensitivity: the same selection with the candle **removed** (2020-03-12); the original candle is kept in the data.
- Selected period with the candle: **150**; without it: **150** (unchanged).
- Test-window signals for the chosen period identical with and without the candle: **True**.

| MA | Train return (with / without) | Validation return (with / without) |
|---|---|---|
| 50 | +405.6% / +366.4% | +159.9% / +159.9% |
| 100 | +623.4% / +623.4% | +98.6% / +98.6% |
| 150 | +603.9% / +603.9% | +171.4% / +171.4% |
| 200 | +146.0% / +146.0% | +173.2% / +173.2% |

## Assumptions (ALL UNVERIFIED for Tokocrypto)

| Item | Value | Status |
|---|---|---|
| BASE | fee 0.40% per side, slippage 0.05% per fill | assumption; the 0.40% estimate came from a Tokocrypto support page read through a summarizer, not confirmed for any account |
| STRESS | fee 0.40% per side, slippage 0.20% per fill | assumption; the 0.40% estimate came from a Tokocrypto support page read through a summarizer, not confirmed for any account |
| LOW FEE | fee 0.10% per side, slippage 0.05% per fill | assumption; the 0.40% estimate came from a Tokocrypto support page read through a summarizer, not confirmed for any account |
| LOW FEE + STRESS SLIPPAGE | fee 0.10% per side, slippage 0.20% per fill | assumption; the 0.40% estimate came from a Tokocrypto support page read through a summarizer, not confirmed for any account |
| Starting capital | 1000 USDT per segment (hypothetical) | assumption |
| Position size | 100% of cash, long only, no leverage | design choice |
| Minimum order | 10 USDT | assumption, unverified |
| Quantity step | 1e-05 BTC (rounded down) | assumption, unverified |
| Fills | next candle's open, worsened by slippage | design rule against look-ahead |
| Not modelled | interest on cash, taxes beyond the fee estimate, partial fills, order-book depth, downtime | - |

## Chronological split (60% / 20% / 20% by row count)

| Segment | From | To | Bars |
|---|---|---|---|
| Train | 2018-03-05 | 2023-02-20 | 1814 |
| Validation | 2023-02-21 | 2024-12-22 | 671 |
| Test | 2024-12-23 | 2026-10-26 | 673 |
Train scoring starts after a 200-bar warm-up so every candidate is scored on the same bars. Each segment starts flat with fresh capital; earlier candles only warm up the averages.

## Selection (train + validation only)

_Pre-registered before any test result was computed. Candidates: 50, 100, 150, 200 days. Costs for selection: the BASE scenario. Step 1 (training, bars from index 200 to the end of the training window, identical for all candidates): a candidate is eligible only if its training total return is above zero. Step 2 (validation): among eligible candidates choose the highest validation score = total return / max(max drawdown, 5%). Ties: fewer validation trades, then the larger period. If no candidate is eligible, nothing is selected and the test period is not evaluated. The test period is never used to choose anything._

| MA days | Train return | Train max DD | Eligible | Validation return | Validation max DD | Val. trades | Score | Chosen |
|---|---|---|---|---|---|---|---|---|
| 50 | +405.6% | 61.4% | yes | +159.9% | 29.0% | 16 | 5.51 |  |
| 100 | +623.4% | 40.8% | yes | +98.6% | 39.8% | 15 | 2.48 |  |
| 150 | +603.9% | 46.3% | yes | +171.4% | 26.6% | 8 | 6.45 | **yes** |
| 200 | +146.0% | 66.3% | yes | +173.2% | 28.0% | 7 | 6.19 |  |

**Frozen choice: 150-day moving average.** Frozen record hash `00431d956bd4387b...` was written before the test window was evaluated.

## Results for the frozen choice

Train and validation were used to choose, so they are NOT independent evidence. Only the test block is out-of-sample, and it is a single period.

### TRAIN (in-sample): 2018-03-05 to 2023-02-20

| Costs | Row | Return | Max drawdown | Closed trades | Win rate | Profit factor | Exposure |
|---|---|---|---|---|---|---|---|
| BASE | Strategy | +603.9% | 46.3% | 15 (+1 open) | 20.0% | 2.37 | 43.3% |
| BASE | Buy and hold | +114.8% | 76.6% | 0 (+1 open) | n/a | n/a | 100.0% |
| BASE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| STRESS | Strategy | +571.9% | 47.0% | 15 (+1 open) | 20.0% | 2.28 | 43.3% |
| STRESS | Buy and hold | +114.4% | 76.6% | 0 (+1 open) | n/a | n/a | 100.0% |
| STRESS | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| LOW FEE | Strategy | +672.5% | 45.0% | 15 (+1 open) | 20.0% | 2.60 | 43.3% |
| LOW FEE | Buy and hold | +115.4% | 76.6% | 0 (+1 open) | n/a | n/a | 100.0% |
| LOW FEE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| LOW FEE + STRESS SLIPPAGE | Strategy | +637.4% | 45.7% | 15 (+1 open) | 20.0% | 2.48 | 43.3% |
| LOW FEE + STRESS SLIPPAGE | Buy and hold | +115.1% | 76.6% | 0 (+1 open) | n/a | n/a | 100.0% |
| LOW FEE + STRESS SLIPPAGE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |

### VALIDATION (used for selection): 2023-02-21 to 2024-12-22

| Costs | Row | Return | Max drawdown | Closed trades | Win rate | Profit factor | Exposure |
|---|---|---|---|---|---|---|---|
| BASE | Strategy | +171.4% | 26.6% | 8 (+1 open) | 37.5% | 4.34 | 78.8% |
| BASE | Buy and hold | +281.4% | 26.2% | 0 (+1 open) | n/a | n/a | 100.0% |
| BASE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| STRESS | Strategy | +164.5% | 27.5% | 8 (+1 open) | 12.5% | 3.92 | 78.8% |
| STRESS | Buy and hold | +280.8% | 26.2% | 0 (+1 open) | n/a | n/a | 100.0% |
| STRESS | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| LOW FEE | Strategy | +185.6% | 24.8% | 8 (+1 open) | 37.5% | 5.42 | 78.8% |
| LOW FEE | Buy and hold | +282.6% | 26.2% | 0 (+1 open) | n/a | n/a | 100.0% |
| LOW FEE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |
| LOW FEE + STRESS SLIPPAGE | Strategy | +178.4% | 25.7% | 8 (+1 open) | 37.5% | 4.82 | 78.8% |
| LOW FEE + STRESS SLIPPAGE | Buy and hold | +282.0% | 26.2% | 0 (+1 open) | n/a | n/a | 100.0% |
| LOW FEE + STRESS SLIPPAGE | Cash | +0.0% | 0.0% | 0 | n/a | n/a | 0.0% |

### TEST (final, evaluated once): 2024-12-23 to 2026-10-26

Not evaluated: dry run: the config says evaluate_test is false, so the test window was not computed or looked at.
**DRY RUN: no test-window result exists yet.** The choice above is frozen; the final run will evaluate the test window once.

## How to read this

- A positive number here is not evidence of profit; a negative one is not proof of failure.
- Only one asset, one rule and one test period were examined; the four candidates were compared on the same history.
- Compare every strategy row with buy-and-hold in the same block and with the drawdown it took.
- Before trusting anything: more trades, other periods or assets, real fees, and paper trading with live prices.

## Metric limitations

- **Total return** - one number for one start and end date; moving either by a few weeks can change it a lot. Open positions are valued at the last close without exit costs, for the strategy and buy-and-hold alike.
- **Maximum drawdown** - measured on daily closing equity, so it hides intraday drops; real drawdowns are at least this large. It describes the past worst case, not a limit.
- **Trade count** - closed round trips. A trend filter makes few trades, so every other statistic rests on a small sample. Under 30 closed trades is flagged as too few to conclude anything.
- **Win rate** - share of closed trades with a profit after costs. It ignores size: a strategy can win often and still lose money, or win rarely and make money.
- **Profit factor** - gross profit divided by gross loss. Shown as n/a with no losing trade; it swings wildly with a handful of trades.
- **Exposure** - share of days a position was held. Lower exposure explains lower risk and lower return; compare return per unit of exposure, not return alone.
- **Benchmarks** - buy-and-hold pays the same entry costs once. Cash returns exactly 0%: no interest is modelled.

## Unresolved concerns

- The market is Binance BTC/USDT; Tokocrypto prices, spreads, fees and order rules are unverified.
- Cost and trading-rule numbers above are assumptions.
- Only closes and opens are used; intraday stops and intraday drawdowns are not simulated.
- One cross-check of the flagged day uses USD venues, not USDT.

Logs for the frozen choice under base costs: `trades.csv`, `orders.csv`, `equity.csv`; the frozen record is `frozen_choice.json`.
