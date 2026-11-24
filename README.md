# tokocrypto-btcusdt-lab

Milestone 1: a READ-ONLY checker for BTC/USDT candles from Tokocrypto's public endpoints.

- No orders. No API keys. No login. `config.json` must say `"mode": "read_only"`.
- Each run probes the endpoints, fetches real candles, validates them, and writes
  reports (see the run's Summary page on the Actions tab).
- Passing data checks say the data looks sane. They say nothing about profit.


Offline settlement follow-on PR #110 requires trusted batch IDs and rejects duplicate/previously attempted IDs before another gateway call. Replay protection is process-local only; durable replay tracking and atomic ledger/settlement transactions remain unimplemented. See [OFFLINE_SETTLEMENT.md](crypto_engine/OFFLINE_SETTLEMENT.md).


PR #111 adds durable SQLite batch idempotency with restart fail-closed behavior. It does not yet make the in-memory portfolio ledger and settlement callback atomic; see [OFFLINE_SETTLEMENT.md](crypto_engine/OFFLINE_SETTLEMENT.md).
