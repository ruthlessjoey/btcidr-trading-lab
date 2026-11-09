"""net_lab.py - bounded, policy-enforced public market-data reachability diagnostics.

Only exact approved GET routes are listed. No provider body snippets are logged.
This utility is manual-only; the scheduled workflow does not invoke it.
"""
import os
import sys
import time
import urllib.error
import urllib.parse

import fetcher


CANDIDATES = [
    ("crypto", "kraken time", "https://api.kraken.com/0/public/Time"),
    ("crypto", "kraken ohlc", "https://api.kraken.com/0/public/OHLC?" +
     urllib.parse.urlencode({"pair": "XBTUSD", "interval": 60})),
    ("crypto", "binance vision time", "https://data-api.binance.vision/api/v3/time"),
    ("crypto", "binance vision klines", "https://data-api.binance.vision/api/v3/klines?" +
     urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})),
    ("crypto", "tokocrypto time", "https://www.tokocrypto.site/api/v3/time"),
    ("crypto", "tokocrypto klines", "https://www.tokocrypto.site/api/v3/klines?" +
     urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "1h", "limit": 5})),
    ("research", "coinbase time", "https://api.exchange.coinbase.com/time"),
    ("research", "coinbase candles", "https://api.exchange.coinbase.com/products/BTC-USD/candles?" +
     urllib.parse.urlencode({"granularity": 3600})),
]


def get(url, timeout=15):
    """One GET through the shared policy-enforced, bounded transport."""
    t0 = time.monotonic()
    try:
        status, body = fetcher.default_opener(url, timeout)
        return status, len(body), "ok", round(time.monotonic() - t0, 2)
    except urllib.error.HTTPError as exc:
        status = exc.code if type(exc.code) is int and 100 <= exc.code <= 599 else None
        try:
            exc.close()
        except Exception:
            pass
        return status, 0, "HTTP error", round(time.monotonic() - t0, 2)
    except Exception:
        return None, 0, "request rejected or unavailable", round(time.monotonic() - t0, 2)


def main():
    os.makedirs("out", exist_ok=True)
    lines = ["# Approved market-data reachability lab", "",
             "| Class | Endpoint | Result | Bytes | Seconds |",
             "|---|---|---|---:|---:|"]
    for cls, name, url in CANDIDATES:
        status, size, result, secs = get(url)
        if status is not None:
            result = f"HTTP {status}"
        lines.append(f"| {cls} | {name} | {result} | {size} | {secs} |")
    text = "\n".join(lines) + "\n"
    with open("out/lab.md", "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
