---
name: quant-research-review
description: Use when reviewing market-data research, backtests, signal evaluation, statistical claims, or strategy evidence.
---

# Quantitative Research Review

## Scope
Review research methodology, data suitability, statistical validity, and reproducibility. This skill does not authorize data collection, network access, backtests, or trading.

## Rules
- Treat source data, timestamps, missingness, duplicates, revisions, and survivorship as first-class research risks.
- Check for look-ahead bias, leakage, selection bias, survivorship bias, data snooping, multiple testing, and parameter overfitting.
- Separate in-sample, validation, and genuinely untouched out-of-sample periods chronologically.
- Model fees, spread, slippage, latency, partial fills, and realistic execution constraints before interpreting performance.
- Compare strategy results with appropriate simple baselines and buy/hold or cash benchmarks where relevant.
- Report sample size, uncertainty, drawdown, tail risk, turnover, exposure, and regime sensitivity; do not focus on win rate alone.
- Check that candle boundaries, timezone, bar-close timing, and signal availability match what a live decision could actually know.
- Never fill missing observations or interpolate prices silently. State the treatment of gaps and incomplete candles.
- Avoid treating correlated providers or instruments as independent confirmation.
- Use reproducible parameters, frozen datasets, and explicit data/version hashes when authorized.
- Do not claim profitability, predictive power, or robustness from a small or selected sample.

## Output
Provide: research question; dataset and provenance; leakage/bias checks; benchmark; metric interpretation; sensitivity/robustness gaps; conclusion confidence; next offline tests. Clearly label unknowns and unrun analysis.
