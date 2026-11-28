# Versioned calendar amendment: per-market inception with common UTC OOS

**Version:** PER_MARKET_INCEPTION_GLOBAL_UTC_OOS_V1  
**Approval date:** 2026-11-29  
**Scope:** BTC/USD, ETH/USD, XRP/USD, DOGE/USD, SHIB/USD, PEPE/USD and SOL/USD Bitstamp SPOT research only.

## Approved date policy

Each candidate market begins at the first hourly candle boundary at or after the latest of its independently evidenced first listing, first matching-enabled and first instant/market-order-enabled timestamps, clamped to the preregistered research start. No pre-listing or pre-market-order candle may be requested or used.

The common OOS calendar begins at the latest eligible inception among the selected markets. Every selected market must contain the exact same contiguous hourly UTC timestamps from that common start through the frozen end boundary. The common window must satisfy the existing minimum-history, training, embargo, five-fold OOS and final-holdout constraints.

## Training and evaluation

- Each market retains its full verified inception history for expanding training and causal indicator warmup.
- Training cutoffs are mapped from the shared calendar into each market's own candle indices.
- All markets use identical UTC OOS start, end-exclusive and next-open terminal-liquidation timestamps for every fold.
- All markets use the same UTC final 10% holdout interval. It remains untouched, unevaluated and unavailable for tuning.
- A missing candle, gap, duplicate, differing end boundary, insufficient common history or inexact timestamp mapping blocks the entire global DSR universe.
- No synthetic, forward-filled or backfilled observations are permitted.
- Market-level results may be diagnostic only; global promotion remains blocked unless every preregistered market and strategy is present and the complete evidence gate is accepted.

## Evidence and approval boundaries

The user's approval selects the date-policy design only. It does not approve market eligibility facts, data rights, historical status intervals, source snapshots, reviewer attestations or the accepted evidence digest. Those controls remain independently required. The public-data runner must remain blocked before the first provider request until all point-in-time evidence requirements are complete and the exact manifest digest is accepted.

## Statistical and execution boundaries

The existing five-fold expanding-training design, 50-bar embargoes, next-open terminal liquidation, global registered-trial universe, frozen strategy family, cost assumptions and append-only trial history remain in force. The calendar amendment does not authorize parameter tuning, final-holdout access, PAPER activation, LIVE trading, leverage, shorting or derivatives.

This amendment is a research protocol, not a profitability claim. Positive net profitability and high win rate remain unestablished until rights-cleared real data, realistic venue-specific execution evidence, independent statistical review and reproducible net-of-cost results exist.
