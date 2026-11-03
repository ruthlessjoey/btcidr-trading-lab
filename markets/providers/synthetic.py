"""markets/providers/synthetic.py - deterministic synthetic response bodies for offline tests.

SYNTHETIC VALUES. NOT MARKET DATA. Built from integer arithmetic so every run produces identical bytes.
The shapes follow each provider's documented layout, so the adapters are exercised on realistic structure.
"""
import json
from urllib.parse import parse_qs, urlparse


def series(first_open_s, count, timeframe_s):
    """Deterministic (open_time_s, open, high, low, close, volume) rows on the interval grid."""
    rows = []
    for i in range(count):
        p = 20000.0 + i * 15 + (i % 7) * 20
        rows.append((first_open_s + i * timeframe_s, p, p + 5.0, p - 5.0, p + 3.0, 100.5))
    return rows


def binance_body(rows, timeframe_s):
    """Binance klines layout: [open_ms, open, high, low, close, volume, close_ms, ...]. Prices are strings."""
    data = [[t * 1000, f"{o}", f"{h}", f"{lo}", f"{c}", f"{v}", (t + timeframe_s) * 1000 - 1,
             "0", "0", "0", "0", "0"] for (t, o, h, lo, c, v) in rows]
    return json.dumps(data).encode("utf-8")


def kraken_body(rows, pair_key="XXBTZUSD", last=0):
    """Kraken OHLC layout: {'error': [], 'result': {PAIR: [[time, o, h, l, c, vwap, vol, count], ...], 'last': n}}."""
    data = [[t, f"{o}", f"{h}", f"{lo}", f"{c}", f"{c}", f"{v}", 1] for (t, o, h, lo, c, v) in rows]
    return json.dumps({"error": [], "result": {pair_key: data, "last": last}}).encode("utf-8")


def kraken_error_body(messages):
    return json.dumps({"error": list(messages)}).encode("utf-8")


def query_value(url, key):
    values = parse_qs(urlparse(url).query).get(key)
    return values[0] if values else None


class ScriptedTransport:
    """A deterministic transport. Records every URL it is asked for. `responder(url)` returns bytes or raises."""

    def __init__(self, responder):
        self.responder = responder
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.responder(url)
