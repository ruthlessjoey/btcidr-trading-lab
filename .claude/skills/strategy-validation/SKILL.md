---
name: strategy-validation
description: Use when reviewing strategy rules, signal timing, parameter choices, market regimes, or evidence used to justify a trading strategy.
---

# Strategy Validation

## Scope
Review strategy logic and its evidence without accessing protected data or running network collection, backtests, or trading. Strategy research does not establish profitability.

## Review checklist
- State the hypothesis, market, timeframe, entry/exit rules, and invalidation conditions precisely.
- Ensure signals use only information available at the decision timestamp; avoid look-ahead and future-bar leakage.
- Distinguish intrabar observations from confirmed candle-close signals.
- Separate strategy proposal from risk approval and portfolio-owned accepted stops.
- Test chronological train/validation/out-of-sample separation; never randomly shuffle time series.
- Track every parameter trial and avoid selecting only the best-performing result.
- Include fees, spread, slippage, latency, partial fills, rejected orders, and realistic execution assumptions in any future paper analysis.
- Evaluate performance by regime and report drawdown, tail loss, exposure, turnover, and sample size, not win rate alone.
- Compare with simple baselines; report uncertainty and sensitivity to parameters.
- Define stale-data, missing-data, and market-dislocation behavior as no-signal or fail-closed, not a guessed price.
- Keep long-only spot constraints explicit. No leverage, shorts, margin, or derivatives.

## Output
Return a strategy specification, leakage/bias checklist, falsifiable tests, robustness gaps, and an evidence-based conclusion. Label all unrun analyses.
