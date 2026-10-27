"""net_lab.py - READ-ONLY reachability lab.

GETs a list of public market-data URLs from THIS machine and records exactly
what came back (HTTP status, size, start of the answer). It decides nothing.
Usage: python3 tools/net_lab.py      Writes: out/lab.md
"""
import os
import sys
import time
import urllib.error
import urllib.request

CANDIDATES = [
    ("crypto", "kraken time", "https://api.kraken.com/0/public/Time"),
    ("crypto", "kraken ohlc", "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"),
    ("crypto", "coinbase time", "https://api.exchange.coinbase.com/time"),
    ("crypto", "coinbase candles", "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600"),
    ("crypto", "bitstamp ohlc", "https://www.bitstamp.net/api/v2/ohlc/btcusd/?step=3600&limit=5"),
    ("crypto", "okx time", "https://www.okx.com/api/v5/public/time"),
    ("crypto", "okx candles", "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=5"),
    ("crypto", "bybit time", "https://api.bybit.com/v5/market/time"),
    ("crypto", "bybit kline", "https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=60&limit=5"),
    ("crypto", "binance time", "https://api.binance.com/api/v3/time"),
    ("crypto", "binance klines", "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5"),
    ("crypto", "binance vision klines", "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=5"),
    ("crypto", "gemini candles", "https://api.gemini.com/v2/candles/btcusd/1hr"),
    ("forex", "frankfurter latest", "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,JPY,IDR"),
    ("forex", "frankfurter series", "https://api.frankfurter.dev/v1/2026-09-20..2026-10-20?base=USD&symbols=EUR"),
    ("forex", "ecb sdmx", "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=5&format=jsondata"),
    ("stocks", "stooq spy daily", "https://stooq.com/q/d/l/?s=spy.us&i=d"),
    ("stocks", "yahoo chart spy (unofficial)", "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1mo&interval=1d"),
    ("shape", "kraken assetpairs", "https://api.kraken.com/0/public/AssetPairs"),
    ("shape", "kraken ticker all", "https://api.kraken.com/0/public/Ticker"),
    ("shape", "coinbase products", "https://api.exchange.coinbase.com/products"),
    ("shape", "binance vision exchangeInfo", "https://data-api.binance.vision/api/v3/exchangeInfo?symbol=BTCUSDT"),
    ("shape", "binance vision klines 1d", "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=3"),
    ("shape", "frankfurter v2 rates", "https://api.frankfurter.dev/v2/rates?base=USD&quotes=EUR,JPY,IDR"),
    ("shape", "frankfurter v2 series", "https://api.frankfurter.dev/v2/rates?from=2026-10-15&to=2026-10-20&base=USD&quotes=EUR"),
    ("shape", "frankfurter v2 currencies", "https://api.frankfurter.dev/v2/currencies"),
    ("shape", "frankfurter v1 series (old)", "https://api.frankfurter.dev/v1/2026-10-15..2026-10-20?base=USD&symbols=EUR"),
]


def get(url, timeout=15):
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "btcidr-trading-lab/0.2 (read-only reachability lab)",
                                               "Accept": "application/json,text/csv,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, body, err = r.status, r.read(), None
    except urllib.error.HTTPError as e:
        status, err = e.code, None
        try:
            body = e.read()
        except Exception:
            body = b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        status, body, err = None, b"", f"network error: {e}"
    return status, body, err, round(time.time() - t0, 2)


def main():
    os.makedirs("out", exist_ok=True)
    lines = ["# Reachability lab (read-only)", "",
             "| Class | Endpoint | Result | Bytes | Seconds | Start of answer |", "|---|---|---|---|---|---|"]
    for cls, name, url in CANDIDATES:
        status, body, err, secs = get(url)
        text = " ".join(body.decode("utf-8", "replace").split())[:110].replace("|", "/").replace("`", "'")
        result = err or f"HTTP {status}"
        lines.append(f"| {cls} | {name} | {result} | {len(body)} | {secs} | {text} |")
    samples = ["# Raw samples (first 1500 characters)", ""]
    for cls, name, url in CANDIDATES:
        if cls == "shape":
            status, body, err, secs = get(url)
            sample = body.decode("utf-8", "replace")[:1500].replace("```", "'''")
            samples += [f"## {name}", f"`{url}` -> {err or 'HTTP ' + str(status)}, {len(body)} bytes",
                        "```", sample, "```", ""]
    with open("out/lab_samples.md", "w", encoding="utf-8") as f:
        f.write("\n".join(samples))
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
