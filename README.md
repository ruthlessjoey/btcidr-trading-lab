# tokocrypto-btcusdt-lab

Milestone 1: a READ-ONLY checker for BTC/USDT candles from Tokocrypto's public endpoints.

- No orders. No API keys. No login. `config.json` must say `"mode": "read_only"`.
- Each run probes the endpoints, fetches real candles, validates them, and writes
  reports (see the run's Summary page on the Actions tab).
- Passing data checks say the data looks sane. They say nothing about profit.
