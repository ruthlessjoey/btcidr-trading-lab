"""fetcher.py - READ-ONLY client for Tokocrypto's public market-data endpoints.

Only public GET addresses are used. There is no login, no key and no code
that can place, cancel or change an order.

Only these exact public GET routes are permitted:
  {base}/api/v3/klines     (symbol BTCUSDT)
All other hosts, paths, endpoint styles and redirects are refused.
"""
import json
import math
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "tokocrypto-btcusdt-lab/0.1 (read-only market data)"
MAX_RESPONSE_BYTES = 1024 * 1024
APPROVED_HOST = "www.tokocrypto.site"
APPROVED_PATHS = {"/api/v3/klines"}
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
              "1h": 3600, "4h": 14400, "1d": 86400}
CANDLES_PER_REQUEST = 500


class ApiError(Exception):
    """Raised when the exchange gives no usable answer."""


class DisallowedRequestError(ApiError):
    """Raised before network access when a URL is outside the approved public API."""


class ResponseDeadlineError(TimeoutError):
    """Raised when the absolute HTTP response-body deadline expires."""


def validate_public_url(url):
    """Only the documented Tokocrypto HTTPS candle GET route is permitted."""
    try:
        p = urllib.parse.urlsplit(url)
        port = p.port
    except (TypeError, ValueError):
        raise DisallowedRequestError("request URL is malformed")
    if (p.scheme != "https" or p.hostname != APPROVED_HOST or
            p.username is not None or p.password is not None or
            port not in (None, 443) or p.fragment or p.path not in APPROVED_PATHS):
        raise DisallowedRequestError("request refused by the public market-data allowlist")
    if len(p.query) > 256:
        raise DisallowedRequestError("request query exceeds the approved length limit")
    try:
        pairs = (urllib.parse.parse_qsl(
            p.query, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
            if p.query else [])
    except ValueError:
        raise DisallowedRequestError("candle request query is malformed")
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise DisallowedRequestError("duplicate query parameters are not allowed")
    q = dict(pairs)
    required = {"symbol", "interval", "startTime", "endTime", "limit"}
    if set(q) != required:
        raise DisallowedRequestError("candle request must contain exactly the approved query parameters")
    if q.get("symbol") != "BTCUSDT" or q.get("interval") not in TF_SECONDS:
        raise DisallowedRequestError("candle request is outside the approved BTC/USDT market")
    numeric = ("startTime", "endTime", "limit")
    if any(not (q[k].isascii() and q[k].isdecimal()) for k in numeric):
        raise DisallowedRequestError("candle request contains an invalid numeric parameter")
    if len(q["startTime"]) > 14 or len(q["endTime"]) > 14 or len(q["limit"]) > 3:
        raise DisallowedRequestError("candle request numeric parameter exceeds the approved length")
    start_ms, end_ms, limit = (int(q[k]) for k in numeric)
    if (not 1 <= start_ms <= end_ms <= 10_000_000_000_000
            or not 1 <= limit <= CANDLES_PER_REQUEST):
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
        """Server-time access is not approved; no URL is constructed."""
        raise DisallowedRequestError(
            "Tokocrypto server-time route is unverified; no network request was made")

    def klines_url(self):
        return self.base_url + "/api/v3/klines"

    def symbols_url(self, pair):
        raise DisallowedRequestError("symbol metadata routes are not approved")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_bounded_body(response, max_bytes, timeout_seconds):
    """Read a bounded HTTP body with an absolute deadline across socket reads.

    The deadline begins after response headers. urllib's open timeout still applies
    per socket operation during connect/TLS/header parsing; it is not a total-request
    deadline. Content-Length is checked when present; transfer-encoded bodies are
    rejected rather than delegated to unbounded chunk-framing reads.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise ApiError("response size limit is invalid")
    if type(timeout_seconds) not in (int, float):
        raise ApiError("response deadline is invalid")
    try:
        timeout_value = float(timeout_seconds)
    except (TypeError, ValueError, OverflowError):
        raise ApiError("response deadline is invalid")
    if not math.isfinite(timeout_value) or timeout_value <= 0:
        raise ApiError("response deadline is invalid")

    # urllib returns addinfourl(HTTPResponse); direct HTTPResponse objects are
    # also supported for offline tests. Capture the underlying socket once.
    wrapped = getattr(response, "fp", None)
    if (wrapped is not None and hasattr(wrapped, "headers")
            and callable(getattr(wrapped, "read1", None))):
        http_response = wrapped
    else:
        http_response = response
    stream = getattr(http_response, "fp", None)
    if stream is None or not callable(getattr(stream, "read1", None)):
        raise ApiError("response does not support bounded single-read operation")
    try:
        sock = stream.raw._sock
    except (AttributeError, TypeError):
        raise ApiError("cannot enforce response body deadline") from None

    headers = getattr(http_response, "headers", None)
    declared_length = None
    if headers is not None:
        get_all = getattr(headers, "get_all", None)
        content_lengths = get_all("Content-Length") if callable(get_all) else None
        if content_lengths is None:
            value = headers.get("Content-Length")
            content_lengths = [] if value is None else [value]
        transfer_encodings = get_all("Transfer-Encoding") if callable(get_all) else None
        if transfer_encodings is None:
            value = headers.get("Transfer-Encoding")
            transfer_encodings = [] if value is None else [value]
        if transfer_encodings:
            raise ApiError("response transfer encoding is not approved")
        if isinstance(content_lengths, str):
            content_lengths = [content_lengths]
        if len(content_lengths) > 1:
            raise ApiError("response Content-Length is duplicated")
        if content_lengths:
            value = str(content_lengths[0])
            if (not value or not value.isascii() or not value.isdecimal()
                    or len(value) > 20):
                raise ApiError("response Content-Length is invalid")
            try:
                declared_length = int(value, 10)
            except (ValueError, OverflowError):
                raise ApiError("response Content-Length is invalid") from None
            if declared_length > max_bytes:
                raise ApiError("response exceeded the 1 MiB public-data limit")

    deadline = time.monotonic() + timeout_value
    chunks = []
    total = 0
    isclosed = getattr(http_response, "isclosed", None)
    while True:
        if callable(isclosed) and isclosed():
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResponseDeadlineError("response body deadline exceeded")
        try:
            sock.settimeout(remaining)
        except (AttributeError, OSError, TypeError, ValueError):
            raise ApiError("cannot enforce response body deadline") from None
        read_size = min(64 * 1024, max_bytes + 1 - total)
        try:
            chunk = stream.read1(read_size)
        except (TimeoutError, socket.timeout) as exc:
            raise ResponseDeadlineError("response body deadline exceeded") from exc
        if time.monotonic() > deadline:
            raise ResponseDeadlineError("response body deadline exceeded")
        if not isinstance(chunk, (bytes, bytearray)):
            raise ApiError("response body is invalid")
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ApiError("response exceeded the 1 MiB public-data limit")
        chunks.append(bytes(chunk))
    if declared_length is not None and total != declared_length:
        raise ApiError("response body length does not match Content-Length")
    return b"".join(chunks)


def default_opener(url, timeout):
    """Do one bounded HTTPS GET without proxies or redirects."""
    validate_public_url(url)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    resp = opener.open(req, timeout=timeout)
    try:
        body = read_bounded_body(resp, MAX_RESPONSE_BYTES, timeout)
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
        if status == 429:
            # Tokocrypto documents Retry-After for rate limits. This transport
            # interface does not preserve response headers, so fail closed rather
            # than retrying before the server's requested wait has elapsed.
            raise ApiError("HTTP 429 rate limit; automatic retry disabled")
        if status < 500:
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
    """Fail closed until Tokocrypto documents and the owner approves a server-time route."""
    raise DisallowedRequestError(
        "Tokocrypto server-time route is unverified; no network request was made")


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
