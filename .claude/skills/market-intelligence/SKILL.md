---
name: market-intelligence
description: Use to structure public-market research, market context, data provenance, regime observations, and research questions for the AI Trading Lab.
---

# Market Intelligence

## Mission
Turn permitted public market information into traceable, timestamped research context. Market commentary is an input to research—not a trade instruction, price guarantee, or substitute for validated data.

## Scope and authorization
- Start with the exact research question, asset, venue, timeframe, observation window, and decision timestamp.
- Use only approved public sources and explicitly authorized endpoints. Do not infer permission to collect from a source because it is publicly reachable.
- The only approved Tokocrypto exception is unauthenticated public GET to `www.tokocrypto.site` for server time and candles. `www.tokocrypto.com`, symbol-info, `open/v1`, private endpoints, and account access are excluded.
- Do not initiate exchange/network requests, scheduled collection, workflows, or scripts unless that exact action is authorized.
- Do not access protected paths or protected Workstream B data. Never request credentials, account balances, wallet keys, OTPs, or private account access.

## Research method
1. Separate observed facts, source claims, interpretations, and hypotheses.
2. Record source identity, retrieval time, event time, timezone, instrument, venue, timeframe, units, and any known delay.
3. Distinguish candle-close data from intrabar observations; never use information that was unavailable at the simulated decision time.
4. Check source coverage, missing intervals, duplicate timestamps, outliers, stale observations, venue basis, and conflicting reports.
5. Treat social sentiment, headlines, influencer claims, and unverified narratives as noisy evidence; never convert them directly into signals.
6. Avoid look-ahead, survivorship, selection, and confirmation bias. Preserve the full observation set and document exclusions.
7. State alternative explanations and what evidence would falsify the interpretation.
8. Pass structured hypotheses to quant research and strategy validation; do not bypass risk approval or portfolio ownership.

## Market regime framework
When evidence permits, describe trend, volatility, liquidity/volume, range expansion/contraction, and unusual dislocations separately. State the measurement method and lookback. Do not label a regime from a single anecdotal observation.

## Output
Produce a dated intelligence note containing:
- question and scope;
- source/provenance ledger;
- observed facts versus interpretation;
- data quality and freshness limitations;
- regime observations and uncertainty;
- falsifiable hypotheses and follow-up research;
- explicit statement that no trade, execution, or profitability conclusion is authorized by the note.

Never invent current prices, events, source coverage, or market conditions.
