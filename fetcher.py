"""fetcher.py - READ-ONLY client for Tokocrypto's public market-data endpoints.

Only public GET addresses are used. There is no login, no key and no code
that can place, cancel or change an order.

Two "styles" of public endpoint are supported, because Tokocrypto publishes both:
  binance_style  {base}/api/v3/time and {base}/api/v3/klines     (symbol BTCUSDT)
  open_v1        {base}/open/v1/common/time and .../market/klines (symbol BTC_USDT)
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "tokocrypto-btcusdt-lab/0.1 (read-only market data)"

# Interval names -> seconds (Binance-style names).
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
              "1h": 3600, "4h": 14400, "1d": 86400}

# Our own chunk size (kept well under the usual 1000-candle cap).
CANDLES_PER_REQUEST = 500


class ApiError(Exception):
    """Raised when the exchange gives no usable answer."""


@dataclass(frozen=True)
class Candle:
    time: int       # candle open time, unix seconds (UTC)
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Source:
    name: str
    style: str       # "binance_style" or "open_v1"
    base_url: str

    def __post_init__(self):
        if self.style not in ("binance_style", "open_v1"):
            raise ValueError(f"unknown source style {self.style!r}")

    def symbol(self, pair):
        return pair.replace("_", "") if self.style == "binance_style" else pair

    def time_url(self):
        path = "/api/v3/time" if self.style == "binance_style" else "/open/v1/common/time"
        return self.base_url + path

    def klines_url(self):
        path = "/api/v3/klines" if self.style == "binance_style" else "/open/v1/market/klines"
        return self.base_url + path

    def symbols_url(self, pair):
        if self.style == "binance_style":
            return (self.base_url + "/api/v3/exchangeInfo?"
                    + urllib.parse.urlencode({"symbol": self.symbol(pair)}))
        return self.base_url + "/open/v1/common/symbols"


def default_opener(url, timeout):
    """Do one real HTTPS GET. Returns (status_code, body_bytes)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def snippet(body, size=200):
    text = body.decode("utf-8", "replace") if body else ""
    return " ".join(text.split())[:size]


def http_get_json(url, timeout, retries, opener, sleep):
    """GET a URL and decode JSON. Retries network errors, 429 and 5xx."""
    last = "no attempt was made"
    for attempt in range(1, retries + 1):
        status = None
        body = b""
        try:
            status, body = opener(url, timeout)
        except urllib.error.HTTPError as e:      # must come before URLError
            status = e.code
            try:
                body = e.read()
            except Exception:
                body = b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"network error: {e}"
        if status is not None:
            if status == 200:
                try:
                    return json.loads(body.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as e:
                    raise ApiError(f"HTTP 200 but the body is not valid JSON ({e}): "
                                   f"{snippet(body)}")
            last = f"HTTP {status}" + (f": {snippet(body)}" if body else "")
            if status != 429 and status < 500:
                raise ApiError(f"{url} -> {last} (not retried)")
        if attempt < retries:
            sleep(2 ** attempt)
    raise ApiError(f"{url} failed after {retries} attempts: {last}")


def to_seconds(t):
    """Exchange timestamps are milliseconds; accept seconds too. Returns seconds."""
    t = int(t)
    return t // 1000 if t > 100_000_000_000 else t


def unwrap(obj):
    """open/v1 answers may be {"code": 0, "msg": "...", "data": ...}. Peel that off
    and turn any non-zero error code into an ApiError."""
    for _ in range(3):
        if not isinstance(obj, dict):
            break
        code = obj.get("code")
        if code not in (None, 0, "0", 200, "200"):
            raise ApiError(f"exchange error code {code}: {str(obj.get('msg', obj))[:200]}")
        for key in ("data", "list", "klines", "result"):
            if key in obj:
                obj = obj[key]
                break
        else:
            break
    return obj


def extract_server_time(obj):
    obj = unwrap(obj)
    if isinstance(obj, dict):
        for key in ("serverTime", "server_time", "timestamp", "time"):
            if key in obj:
                obj = obj[key]
                break
    try:
        return to_seconds(obj)
    except (TypeError, ValueError):
        raise ApiError(f"unexpected server-time answer: {str(obj)[:200]}")


def parse_klines(raw):
    """Rows must look like [openTime, open, high, low, close, volume, ...]."""
    rows = unwrap(raw)
    if not isinstance(rows, list):
        raise ApiError(f"candle answer is not a list: {str(rows)[:200]}")
    out = []
    for i, row in enumerate(rows):
        try:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                raise ValueError("expected a list of at least 6 values")
            out.append(Candle(to_seconds(row[0]), float(row[1]), float(row[2]),
                              float(row[3]), float(row[4]), float(row[5])))
        except (TypeError, ValueError) as e:
            raise ApiError(f"candle #{i} has an unexpected format ({e}): {str(row)[:200]}")
    return out


def fetch_server_time(src, timeout, retries, opener, sleep):
    return extract_server_time(
        http_get_json(src.time_url(), timeout, retries, opener, sleep))


def fetch_candles(src, pair, tf, start_s, end_s, timeout, retries, opener, sleep):
    """Fetch candles between start_s and end_s. Returns (candles, requests_made)."""
    if tf not in TF_SECONDS:
        raise ValueError(f"unknown timeframe {tf!r}")
    window = CANDLES_PER_REQUEST * TF_SECONDS[tf]
    candles, requests_made = [], 0
    chunk_start = int(start_s)
    while chunk_start < end_s:
        chunk_end = int(min(chunk_start + window - 1, end_s))
        query = urllib.parse.urlencode(
            {"symbol": src.symbol(pair), "interval": tf,
             "startTime": chunk_start * 1000, "endTime": chunk_end * 1000,
             "limit": CANDLES_PER_REQUEST})
        raw = http_get_json(f"{src.klines_url()}?{query}", timeout, retries, opener, sleep)
        candles.extend(parse_klines(raw))
        requests_made += 1
        chunk_start = chunk_end + 1
    return candles, requests_made
