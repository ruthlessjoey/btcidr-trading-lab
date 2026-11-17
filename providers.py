"""providers.py - public market-data adapters.

Only build("tokocrypto") is currently authorized. Legacy adapter classes remain for
historical comparison code, but fetcher.validate_public_url refuses every host and
route except Tokocrypto's approved HTTPS time and candle endpoints. No adapter can
bypass that transport boundary.
"""
import math
import urllib.error
import urllib.parse
from datetime import datetime, timezone

import fetcher
from fetcher import ApiError, Candle, TF_SECONDS


def _safe_status_label(status):
    """Keep only exact built-in integer HTTP statuses in reportable provider logs."""
    if type(status) is not int or not 100 <= status <= 599:
        return "invalid HTTP status"
    return f"HTTP {status}"


def _safe_epoch_seconds(value):
    """Accept finite numeric seconds without accepting booleans or provider text."""
    if isinstance(value, bool):
        raise ValueError("boolean is not a timestamp")
    if type(value) is int:
        seconds = value
    elif type(value) is float and math.isfinite(value):
        seconds = int(value)
    elif type(value) is str and value.isascii() and value.isdecimal():
        seconds = int(value)
    else:
        raise ValueError("timestamp is not a supported numeric value")
    if seconds <= 0 or seconds > 10_000_000_000:
        raise ValueError("timestamp is outside the supported range")
    return seconds


class Http:
    """One GET helper per provider run; logs only a path and a safe status/category."""

    def __init__(self, timeout, retries, opener, sleep):
        self.timeout, self.retries, self.sleep = timeout, retries, sleep
        self._opener = opener
        self.requests = 0
        self.log = []

    def _record(self, url, what):
        self.log.append((urllib.parse.urlparse(url).path, what))

    def _opener_with_log(self, url, timeout):
        try:
            status, body = self._opener(url, timeout)
        except urllib.error.HTTPError as e:
            self._record(url, _safe_status_label(e.code))
            raise
        except Exception as e:
            self._record(url, f"network error ({type(e).__name__})")
            raise
        self._record(url, _safe_status_label(status))
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
    MAX_CANDLES = 720

    @staticmethod
    def _result(obj):
        if not isinstance(obj, dict) or "result" not in obj:
            raise ApiError("unexpected Kraken response format")
        if obj.get("error"):
            raise ApiError("Kraken returned an error response")
        return obj["result"]

    def server_time(self, http):
        res = self._result(http.get(self.base + "/0/public/Time"))
        try:
            value = res["unixtime"]
            if type(value) is not int or not 0 < value <= 10_000_000_000:
                raise ValueError("invalid timestamp")
            return value
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApiError("Kraken server-time response is invalid")

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
            raise ApiError("Kraken candle response must contain exactly one candle list")
        out = []
        for i, row in enumerate(res[keys[0]]):
            try:
                timestamp = row[0]
                if type(timestamp) is not int or not 0 < timestamp <= 10_000_000_000:
                    raise ValueError("invalid timestamp")
                out.append(Candle(timestamp, fetcher._finite_float(row[1]),
                                  fetcher._finite_float(row[2]), fetcher._finite_float(row[3]),
                                  fetcher._finite_float(row[4]), fetcher._finite_float(row[6])))
            except (KeyError, TypeError, ValueError, IndexError, OverflowError):
                raise ApiError(f"Kraken candle row {i} has an unexpected format")
        return _dedupe_sorted(out)


class Coinbase:
    name, label, quote = "coinbase", "BTC/USD", "USD"
    product, base = "BTC-USD", "https://api.exchange.coinbase.com"
    docs = "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles"
    GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
    MAX_PER_REQUEST = 300

    def server_time(self, http):
        obj = http.get(self.base + "/time")
        try:
            return _safe_epoch_seconds(obj["epoch"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ApiError("Coinbase server-time response is invalid")

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
                raise ApiError("Coinbase candle response is not a list")
            for i, row in enumerate(rows):
                try:
                    timestamp = row[0]
                    if type(timestamp) is not int or timestamp <= 0:
                        raise ValueError("invalid timestamp")
                    out.append(Candle(timestamp, fetcher._finite_float(row[3]),
                                      fetcher._finite_float(row[2]), fetcher._finite_float(row[1]),
                                      fetcher._finite_float(row[4]), fetcher._finite_float(row[5])))
                except (KeyError, TypeError, ValueError, IndexError, OverflowError):
                    raise ApiError(f"Coinbase candle row {i} has an unexpected format")
            cur = chunk_end
        return _dedupe_sorted(out)


class BinanceStyle:
    """Binance-layout klines; transport still enforces the exact Tokocrypto allowlist."""
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
    if name == "tokocrypto":
        return BinanceStyle("tokocrypto", "BTC/USDT", "USDT", "BTC_USDT",
                            "https://www.tokocrypto.site", "https://www.tokocrypto.com/apidocs/")
    raise ValueError(f"provider {name!r} is not currently authorized")
