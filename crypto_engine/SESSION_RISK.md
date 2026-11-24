# Shared multi-market session-loss guard

## Control semantics
- One guard instance represents one shared account session across all market IDs.
- Session loss is measured from opening equity. The backtest marks the portfolio at each executable bar open **before** accepting target deltas, and again at each close.
- At or beyond the configured threshold, the guard latches SESSION_LOSS_LIMIT; no later BUY proposal is authorized.
- SELL proposals are always bounded by current holdings. Outstanding concurrent sell reservations are subtracted from available inventory so stale parallel proposals cannot reserve the same units twice.
- Each sell reservation must be settled after a definitive fill or rejection. Unresolved reservations block reset.
- The stop survives snapshot/restore and cannot be cleared by a strategy proposal. Reset requires a different session ID, positive opening equity, actor, reason and approval reference; the reset is appended to the audit chain.
- Portfolio drawdown may latch the same guard with reason MAX_PORTFOLIO_DRAWDOWN.

## API sketch
```python
guard = SessionLossGuard(session_id="paper-session-001", opening_equity="10000",
                         max_session_loss="0.05", started_at=1_800_000_000)
guard.observe_equity(equity="9499", timestamp=1_800_000_060)
permitted = guard.authorize_proposals(
    proposals={"BTC/USDT": "0.2", "ETH/USDT": "-1.5"},
    holdings={"BTC/USDT": "0.1", "ETH/USDT": "1.0"},
    timestamp=1_800_000_061)
guard.settle_sell(market_id="ETH/USDT", authorized_quantity="1.0",
                  filled_quantity="0.8", timestamp=1_800_000_061)
snapshot = guard.snapshot()
restored = SessionLossGuard.restore(snapshot)
```

## Persistence and security boundary
The snapshot is JSON-serializable and includes the complete event chain, current latch and pending sell reservations. The caller must persist it atomically in a trusted durable store and restore it before accepting new proposals. A local SHA-256 chain detects accidental changes and unanchored edits but is not cryptographic proof against an attacker who can rewrite the entire snapshot and chain; production deployment must anchor the chain head outside the local writable trust boundary.

The current repository package has no strategy-agent runtime, broker, exchange connector or order router. The backtest demonstrates the intended mandatory interception point for strategy target weights. Before any future paper simulator or agent execution interface is added, it must route every proposal through this guard and deterministic risk service; agents must not receive write access to risk state or any direct order capability.

## Limitations
- This is a deterministic research/simulation control, not a live trading component.
- The session threshold is relative to session opening equity, not a trailing high-water mark.
- The backtest stop is latched for the remainder of that replay. The explicit reset API is tested separately.
- No real exchange, wallet, network or account activity is performed.
