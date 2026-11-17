"""fetcher.py - READ-ONLY client for Tokocrypto's public market-data endpoints.

Only public GET addresses are used. There is no login, no key and no code
that can place, cancel or change an order.

Only these exact public GET routes are permitted:
  {base}/api/v3/time
  {base}/api/v3/klines     (symbol BTCUSDT)
All other hosts, paths, endpoint styles and redirects are refused.
"""
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "tokocrypto-btcusdt-lab/0.1 (read-only market data)"
MAX_RESPONSE_BYTES = 1024 * 1024
APPROVED_HOST = "www.tokocrypto.site"
APPROVED_PATHS = {"/api/v3/time", "/api/v3/klines"}
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
              "1h": 3600, "4h": 14400, "1d": 86400}
CANDLES_PER_REQUEST = 500


class ApiError(Exception):
    """Raised when the exchange gives no usable answer."""


class DisallowedRequestError(ApiError):
    """Raised before network access when a URL is outside the approved public API."""


def validate_public_url(url):
    """Only the approved Tokocrypto HTTPS time and candle GET routes are permitted."""
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except (TypeError, ValueError):
        raise DisallowedRequestError("request URL is malformed")
    if (p.scheme != "https" or p.hostname != APPROVED_HOST or
            p.username is not None or p.password is not None or
            port not in (None, 443) or p.fragment or p.path not in APPROVED_PATHS):
        raise DisallowedRequestError("request refused by the public market-data allowlist")
    try:
        pairs = urllib.parse.parse_qsl(p.query, keep_blank_values=True, strict_parsing=True) if p.query else []
    except ValueError:
        raise DisallowedRequestError("candle request query is malformed")
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise DisallowedRequestError("duplicate query parameters are not allowed")
    if p.path == "/api/v3/time":
        if pairs:
            raise DisallowedRequestError("server-time route does not accept query parameters")
    else:
        q = dict(pairs)
        required = {"symbol", "interval", "startTime", "endTime", "limit"}
        if set(q) != required:
            raise DisallowedRequestError("candle request must contain exactly the approved query parameters")
        if q.get("symbol") != "BTCUSDT" or q.get("interval") not in TF_SECONDS:
            raise DisallowedRequestError("candle request is outside the approved BTC/USDT market")
        numeric = ("startTime", "endTime", "limit")
        if any(not (q[k].isascii() and q[k].isdecimal()) for k in numeric):
            raise DisallowedRequestError("candle request contains an invalid numeric parameter")
        start_ms, end_ms, limit = (int(q[k]) for k in numeric)
        if start_ms > end_ms or not 1 <= limit <= CANDLES_PER_REQUEST:
            raise DisallowedRequestError("candle request range or limit is outside the approved bounds")
    return url


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Source:
    name: str
    style: str
    base_url: str

    def __post_init__(self):
        if self.style != "binance_style":
            raise DisallowedRequestError("only the approved Tokocrypto Binance-style API is permitted")

    def symbol(self, pair):
        return pair.replace("_", "")

    def time_url(self):
        return self.base_url + "/api/v3/time"

    def klines_url(self):
        return self.base_url + "/api/v3/klines"

    def symbols_url(self, pair):
        raise DisallowedRequestError("symbol metadata routes are not approved")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def default_opener(url, timeout):
    """Do one bounded HTTPS GET without following redirects."""
    validate_public_url(url)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    opener = urllib.request.build_opener(_NoRedirect())
    resp = opener.open(req, timeout=timeout)
    try:
        body = resp.read(MAX_RESPONSE_BYTES + 1)
        return resp.status, body
    finally:
        resp.close()


def _reject_json_constant(value):
    raise ValueError("non-standard JSON numeric constant")


def _finite_float(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric candle value")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("candle value must be finite")
    return number


def http_get_json(url, timeout, retries, opener, sleep):
    """GET only approved URLs; bound responses and never expose provider text."""
    validate_public_url(url)
    last = "no attempt was made"
    for attempt in range(1, retries + 1):
        status = None
        body = b""
        network_error = False
        try:
            status, body = opener(url, timeout)
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                e.close()
            except Exception:
                pass
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            network_error = True
            last = f"network error ({type(e).__name__})"
        except Exception as e:
            raise ApiError(f"unexpected transport failure ({type(e).__name__})") from None

        if type(body) is not bytes:
            raise ApiError("transport returned an invalid response body")
        if len(body) > MAX_RESPONSE_BYTES:
            raise ApiError("response exceeded the 1 MiB public-data limit")
        if network_error:
            if attempt < retries:
                sleep(2 ** attempt)
            continue
        if status is None:
            raise ApiError("transport returned no HTTP status")
        if type(status) is not int or not 100 <= status <= 599:
            raise ApiError("transport returned an invalid HTTP status")
        if status == 200:
            try:
                return json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant)
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise ApiError("HTTP 200 response was not valid JSON")
        last = f"HTTP {status}"
        if status != 429 and status < 500:
            raise ApiError(f"HTTP {status} (not retried)")
        if attempt < retries:
            sleep(2 ** attempt)
    raise ApiError(f"request failed after {retries} attempts: {last}")


def to_seconds(t):
    """Accept integer Unix seconds/milliseconds or an ASCII decimal string."""
    if type(t) is int:
        value = t
    elif type(t) is str and t.isascii() and t.isdecimal():
        value = int(t)
    else:
        raise TypeError("timestamp must be an integer or decimal string")
    if value <= 0 or value > 10_000_000_000_000:
        raise ValueError("timestamp is outside the supported range")
    return value // 1000 if value > 100_000_000_000 else value


def unwrap(obj):
    """Peel known response wrappers without exposing provider-controlled values."""
    for _ in range(3):
        if not isinstance(obj, dict):
            break
        code = obj.get("code")
        if code is not None:
            valid_code = ((type(code) is int and code in (0, 200)) or
                          (type(code) is str and code in ("0", "200")))
            if not valid_code:
                raise ApiError("exchange returned an error response")
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
    except (TypeError, ValueError, OverflowError):
        raise ApiError("unexpected server-time response format")


def parse_klines(raw):
    """Rows must look like [openTime, open, high, low, close, volume, ...]."""
    rows = unwrap(raw)
    if not isinstance(rows, list):
        raise ApiError("candle response is not a list")
    out = []
    for i, row in enumerate(rows):
        try:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                raise ValueError("expected a list of at least 6 values")
            out.append(Candle(
                to_seconds(row[0]), _finite_float(row[1]), _finite_float(row[2]),
                _finite_float(row[3]), _finite_float(row[4]), _finite_float(row[5])))
        except (TypeError, ValueError, OverflowError):
            raise ApiError(f"candle row {i} has an unexpected format")
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
