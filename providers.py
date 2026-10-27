"""providers.py - READ-ONLY adapters, one per exchange, for PUBLIC candle endpoints.

Every adapter has its own URL, symbol format, response layout and time rules.
Nothing here logs in, uses keys, or can place an order.

Doc facts below were read from each exchange's official docs on 2026-10-27
(Kraken, Coinbase, Binance "market data only" page) and are re-checked by the
live run itself: a provider counts as verified only if real candles pass validation.
"""
import urllib.error
import urllib.parse
from datetime import datetime, timezone

import fetcher
from fetcher import ApiError, Candle, TF_SECONDS


class Http:
    """One GET helper per provider run. Counts requests and records the real HTTP status
    (or network error) of each one, so reports can show evidence."""

    def __init__(self, timeout, retries, opener, sleep):
        self.timeout, self.retries, self.sleep = timeout, retries, sleep
        self._opener = opener
        self.requests = 0
        self.log = []                 # [(url path, "HTTP 200" | "HTTP 403" | "network error: ...")]

    def _record(self, url, what):
        self.log.append((urllib.parse.urlparse(url).path, what))

    def _opener_with_log(self, url, timeout):
        try:
            status, body = self._opener(url, timeout)
        except urllib.error.HTTPError as e:
            self._record(url, f"HTTP {e.code}")
            raise
        except Exception as e:
            self._record(url, f"network error: {type(e).__name__}")
            raise
        self._record(url, f"HTTP {status}")
        return status, body

    def get(self, url):
        self.requests += 1
        return fetcher.http_get_json(url, self.timeout, self.retries,
                                     self._opener_with_log, self.sleep)


def _dedupe_sorted(candles):
    """Join pages: one candle per open time (the later copy wins), oldest first."""
    return [c for _, c in sorted({c.time: c for c in candles}.items())]


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Kraken:
    name, label, quote = "kraken", "BTC/USD", "USD"
    symbol, base = "XBTUSD", "https://api.kraken.com"
    docs = "https://docs.kraken.com/api-reference/market-data/get-ohlc-data"
    INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}
    MAX_CANDLES = 720          # docs: only the most recent 720 entries are available

    @staticmethod
    def _result(obj):
        if not isinstance(obj, dict) or "result" not in obj:
            raise ApiError(f"unexpected Kraken answer: {str(obj)[:200]}")
        if obj.get("error"):
            raise ApiError(f"Kraken error: {obj['error']}")
        return obj["result"]

    def server_time(self, http):
        res = self._result(http.get(self.base + "/0/public/Time"))
        try:
            return int(res["unixtime"])
        except (KeyError, TypeError, ValueError):
            raise ApiError(f"no unixtime in Kraken answer: {str(res)[:200]}")

    def candles(self, tf, start_s, end_s, http):
        if tf not in self.INTERVALS:
            raise ValueError(f"Kraken does not offer timeframe {tf!r}")
        if (end_s - start_s) / TF_SECONDS[tf] > self.MAX_CANDLES:
            raise ValueError("requested range is longer than Kraken's 720-candle window")
        q = urllib.parse.urlencode({"pair": self.symbol, "interval": self.INTERVALS[tf],
                                    "since": int(start_s)})
        res = self._result(http.get(f"{self.base}/0/public/OHLC?{q}"))
        keys = [k for k in res if k != "last"]
        if len(keys) != 1 or not isinstance(res[keys[0]], list):
            raise ApiError(f"expected exactly one candle list, got keys {list(res)[:5]}")
        out = []
        for i, row in enumerate(res[keys[0]]):
            # [time, open, high, low, close, vwap, volume, count]
            try:
                out.append(Candle(int(row[0]), float(row[1]), float(row[2]), float(row[3]),
                                  float(row[4]), float(row[6])))
            except (TypeError, ValueError, IndexError) as e:
                raise ApiError(f"Kraken candle #{i} has an unexpected format ({e}): {str(row)[:200]}")
        return _dedupe_sorted(out)


class Coinbase:
    name, label, quote = "coinbase", "BTC/USD", "USD"
    product, base = "BTC-USD", "https://api.exchange.coinbase.com"
    docs = "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles"
    GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
    MAX_PER_REQUEST = 300      # docs: at most 300 candles per request

    def server_time(self, http):
        obj = http.get(self.base + "/time")
        try:
            return int(float(obj["epoch"]))
        except (KeyError, TypeError, ValueError):
            raise ApiError(f"no epoch in Coinbase answer: {str(obj)[:200]}")

    def candles(self, tf, start_s, end_s, http):
        if tf not in self.GRANULARITY:
            raise ValueError(f"Coinbase does not offer timeframe {tf!r}")
        g = self.GRANULARITY[tf]
        window = (self.MAX_PER_REQUEST - 1) * g
        out, cur = [], int(start_s)
        while cur < end_s:
            chunk_end = min(cur + window, int(end_s))
            q = urllib.parse.urlencode({"granularity": g, "start": _iso(cur), "end": _iso(chunk_end)})
            rows = http.get(f"{self.base}/products/{self.product}/candles?{q}")
            if not isinstance(rows, list):
                raise ApiError(f"expected a list of candles, got: {str(rows)[:200]}")
            for i, row in enumerate(rows):
                # [time, low, high, open, close, volume]
                try:
                    out.append(Candle(int(row[0]), float(row[3]), float(row[2]), float(row[1]),
                                      float(row[4]), float(row[5])))
                except (TypeError, ValueError, IndexError) as e:
                    raise ApiError(f"Coinbase candle #{i} has an unexpected format ({e}): "
                                   f"{str(row)[:200]}")
            cur = chunk_end
        return _dedupe_sorted(out)


class BinanceStyle:
    """Binance-layout klines. Used for Binance's market-data-only host and for Tokocrypto."""
    MAX_PER_REQUEST = 500

    def __init__(self, name, label, quote, pair, base_url, docs, style="binance_style"):
        self.name, self.label, self.quote, self.docs = name, label, quote, docs
        self.pair, self.src = pair, fetcher.Source(name, style, base_url)

    def server_time(self, http):
        return fetcher.extract_server_time(http.get(self.src.time_url()))

    def candles(self, tf, start_s, end_s, http):
        if tf not in TF_SECONDS:
            raise ValueError(f"unknown timeframe {tf!r}")
        window = self.MAX_PER_REQUEST * TF_SECONDS[tf]
        out, cur = [], int(start_s)
        while cur < end_s:
            chunk_end = int(min(cur + window - 1, end_s))
            q = urllib.parse.urlencode({"symbol": self.src.symbol(self.pair), "interval": tf,
                                        "startTime": cur * 1000, "endTime": chunk_end * 1000,
                                        "limit": self.MAX_PER_REQUEST})
            out.extend(fetcher.parse_klines(http.get(f"{self.src.klines_url()}?{q}")))
            cur = chunk_end + 1
        return _dedupe_sorted(out)


def build(name):
    if name == "kraken":
        return Kraken()
    if name == "coinbase":
        return Coinbase()
    if name == "binance-vision":
        return BinanceStyle("binance-vision", "BTC/USDT", "USDT", "BTC_USDT",
                            "https://data-api.binance.vision",
                            "https://developers.binance.com/docs/binance-spot-api-docs/faqs/market_data_only")
    if name == "tokocrypto":
        return BinanceStyle("tokocrypto", "BTC/USDT", "USDT", "BTC_USDT",
                            "https://www.tokocrypto.site", "https://www.tokocrypto.com/apidocs/")
    raise ValueError(f"unknown provider {name!r}")
