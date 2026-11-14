# Stage 6 — Data validation and research-library decisions

## Pandera — defer until a dataframe schema is justified

Pandera is useful for validating pandas/polars dataframe schemas, but it brings a broader data-stack dependency footprint. The current staged rollout has not established a concrete need to introduce pandas solely to use Pandera.

Revisit when:
- an approved, non-protected dataframe boundary exists;
- a schema contract cannot be enforced adequately with the existing standard-library validation;
- Python compatibility, pandas/numpy versions, transitive dependencies, and hashes can be pinned;
- fixtures are synthetic or explicitly approved public samples.

Do not use it to inspect or validate protected datasets.

## QuantStats — defer until research metrics are defined

QuantStats can calculate and visualize portfolio performance statistics. It is not a market-data provider and must not be used to fetch data implicitly. Its dependency set and yfinance integration need review before installation.

Revisit only when the research workflow defines:
- a documented return series format and source;
- fees, slippage, missing data, and timestamp conventions;
- out-of-sample and walk-forward evaluation;
- benchmark selection and reporting expectations.

Never present a QuantStats report as proof of future profitability.

## PyPortfolioOpt — defer until an optimizer use case exists

PyPortfolioOpt provides portfolio optimization methods, but optimization is not a substitute for a validated trading edge. It can amplify unstable expected-return and covariance estimates.

Revisit only after:
- a stable, approved asset universe exists;
- estimates and constraints are defined and tested;
- transaction costs, turnover, liquidity, and concentration are accounted for;
- an out-of-sample comparison demonstrates value over a simpler baseline.

It must not add shorting, leverage, derivatives, or live execution.

## Riskfolio-Lib — defer due to overlap and dependency weight

Riskfolio-Lib provides advanced portfolio optimization and risk measures, but overlaps with PyPortfolioOpt for many candidate use cases and adds a heavier dependency surface.

Do not install both optimization frameworks by default. Select one only after a documented comparison shows a specific requirement that simpler risk controls cannot satisfy.

## Current decision

No Pandera, QuantStats, PyPortfolioOpt, or Riskfolio-Lib dependency is added in this stage. This is deliberate scope control, not a claim that the tools are unsuitable in all future research.

Before any future install, re-check the exact current release, license, Python support, dependency graph, wheel/source hashes, provenance, and isolated offline test plan. Keep all packages in a separate development/research environment, not the production runtime.
