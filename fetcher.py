"""READ-ONLY candle transport.

Tokocrypto is strictly limited to unauthenticated HTTPS GET requests to
https://www.tokocrypto.site/api/v3/klines. No Tokocrypto time, symbols,
exchange-info, account, order or .com endpoint is permitted.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

USER_AGENT = "tokocrypto-btcusdt-lab/0.1 (read-only market data)"

# Interval names -> seconds (Binance-style names).
TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800,
              "1h": 3600, "4h": 14400, "1d": 86400}

# Our own chunk size (kept well under the provider's documented maximum).
CANDLES_PER_REQUEST = 500
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TOKOCRYPTO_BASE_URL = "https://www.tokocrypto.site"
TOKOCRYPTO_KLINES_PATH = "/api/v3/klines"
TOKOCRYPTO_ALLOWED_QUERY = frozenset({"symbol", "interval", "startTime", "endTime", "limit"})

# Identity-only in-process capability used by the fixed-window research module.
# This deters accidental API misuse; it is not a security boundary against
# arbitrary code already executing inside this Python process.
_TOKOCRYPTO_FIXED_WINDOW_CAPABILITY = object()


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
        if not isinstance(self.name, str) or not isinstance(self.base_url, str):
            raise ValueError("source name and base URL must be strings")
        if "tokocrypto" in self.name.casefold() or "tokocrypto" in self.base_url.casefold():
            if self.style != "binance_style" or self.base_url != TOKOCRYPTO_BASE_URL:
                raise ValueError("Tokocrypto is restricted to the exact approved .site Binance-style host")

    @property
    def is_tokocrypto(self):
        return "tokocrypto" in self.name.casefold() or "tokocrypto" in self.base_url.casefold()

    def symbol(self, pair):
        return pair.replace("_", "") if self.style == "binance_style" else pair

    def time_url(self):
        if self.is_tokocrypto:
            raise ApiError("Tokocrypto server-time requests are not approved; use only the public klines endpoint")
        path = "/api/v3/time" if self.style == "binance_style" else "/open/v1/common/time"
        return self.base_url + path

    def klines_url(self):
        if self.is_tokocrypto:
            return TOKOCRYPTO_BASE_URL + TOKOCRYPTO_KLINES_PATH
        path = "/api/v3/klines" if self.style == "binance_style" else "/open/v1/market/klines"
        return self.base_url + path

    def symbols_url(self, pair):
        if self.is_tokocrypto:
            raise ApiError("Tokocrypto market-symbol discovery is not approved; use only the public klines endpoint")
        if self.style == "binance_style":
            return (self.base_url + "/api/v3/exchangeInfo?"
                    + urllib.parse.urlencode({"symbol": self.symbol(pair)}))
        return self.base_url + "/open/v1/common/symbols"


def _is_tokocrypto_host(url):
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except (TypeError, ValueError):
        return False
    return "tokocrypto" in urllib.parse.unquote(host).casefold()


def validate_request_url(url):
    """Fail closed on every Tokocrypto route except the exact public klines GET."""
    try:
        parsed = urllib.parse.urlsplit(url)
        if not _is_tokocrypto_host(url):
            return
        if (parsed.scheme != "https" or parsed.netloc != "www.tokocrypto.site"
                or parsed.path != TOKOCRYPTO_KLINES_PATH or parsed.fragment
                or parsed.username is not None or parsed.password is not None):
            raise ApiError("Tokocrypto request blocked: only exact HTTPS www.tokocrypto.site/api/v3/klines is approved")
        params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
        names = [name for name, _ in params]
        if len(params) != len(TOKOCRYPTO_ALLOWED_QUERY) or set(names) != TOKOCRYPTO_ALLOWED_QUERY:
            raise ApiError("Tokocrypto klines request has missing, duplicate or unapproved query parameters")
        values = dict(params)
        if (not re.fullmatch(r"[A-Z0-9]{5,20}", values["symbol"])
                or values["interval"] not in TF_SECONDS
                or not re.fullmatch(r"[0-9]{1,16}", values["startTime"])
                or not re.fullmatch(r"[0-9]{1,16}", values["endTime"])
                or not re.fullmatch(r"[0-9]{1,3}", values["limit"])):
            raise ApiError("Tokocrypto klines query values are invalid")
        start_ms, end_ms, limit = int(values["startTime"]), int(values["endTime"]), int(values["limit"])
        step_ms = TF_SECONDS[values["interval"]] * 1000
        if (start_ms < 0 or end_ms <= start_ms or not 1 <= limit <= CANDLES_PER_REQUEST
                or end_ms - start_ms > limit * step_ms):
            raise ApiError("Tokocrypto klines range or row limit is outside the approved bounds")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ApiError):
            raise
        raise ApiError("Tokocrypto request URL is malformed") from exc


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_TOKOCRYPTO_NO_REDIRECT = urllib.request.build_opener(_NoRedirectHandler)


def _open_json_response(url, timeout, *, tokocrypto_capability=None):
    """Shared bounded GET implementation with an identity-only historical scope."""
    validate_request_url(url)
    if (_is_tokocrypto_host(url)
            and tokocrypto_capability is not _TOKOCRYPTO_FIXED_WINDOW_CAPABILITY):
        raise ApiError(
            "Direct Tokocrypto transport is disabled; use the explicit fixed-window research interface"
        )
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    opener = _TOKOCRYPTO_NO_REDIRECT if _is_tokocrypto_host(url) else None
    if opener is None:
        response_context = urllib.request.urlopen(req, timeout=timeout)
    else:
        response_context = opener.open(req, timeout=timeout)
    with response_context as resp:
        body = resp.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ApiError("HTTP response exceeds the 4 MiB body limit")
        return resp.status, body


def default_opener(url, timeout):
    """Default GET opener. Tokocrypto requires the fixed-window capability."""
    return _open_json_response(url, timeout)


def _fixed_window_opener(url, timeout, *, tokocrypto_capability=None):
    """Private opener requiring the identity-only fixed-window capability."""
    return _open_json_response(
        url, timeout, tokocrypto_capability=tokocrypto_capability,
    )


def snippet(body, size=200):
    text = body.decode("utf-8", "replace") if body else ""
    return " ".join(text.split())[:size]


def http_get_json(url, timeout, retries, opener, sleep, *, _tokocrypto_capability=None):
    """GET a URL and decode JSON. Tokocrypto requires the fixed-window capability."""
    validate_request_url(url)
    if (_is_tokocrypto_host(url)
            and _tokocrypto_capability is not _TOKOCRYPTO_FIXED_WINDOW_CAPABILITY):
        raise ApiError(
            "Direct Tokocrypto JSON transport is disabled; use the explicit fixed-window research interface"
        )
    last = "no attempt was made"
    for attempt in range(1, retries + 1):
        status = None
        body = b""
        try:
            status, body = opener(url, timeout)
        except urllib.error.HTTPError as e:      # must come before URLError
            status = e.code
            try:
                body = e.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    body = body[:MAX_RESPONSE_BYTES]
            except Exception:
                body = b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"network error: {e}"
        if status is not None:
            if status == 200:
                if not isinstance(body, (bytes, bytearray)) or len(body) > MAX_RESPONSE_BYTES:
                    raise ApiError("HTTP response is not bytes or exceeds the 4 MiB body limit")
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
    if len(rows) > CANDLES_PER_REQUEST:
        raise ApiError(f"candle answer exceeds the {CANDLES_PER_REQUEST}-row request limit")
    out = []
    for i, row in enumerate(rows):
        try:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                raise ValueError("expected a list of at least 6 values")
            raw_timestamp = row[0]
            if (isinstance(raw_timestamp, bool)
                    or not isinstance(raw_timestamp, (str, int))
                    or (isinstance(raw_timestamp, str)
                        and not re.fullmatch(r"[0-9]{1,16}", raw_timestamp))):
                raise ValueError("candle timestamp must be an integer or decimal-digit string")
            if any(isinstance(value, bool) for value in row[1:6]):
                raise ValueError("boolean OHLCV values are forbidden")
            out.append(Candle(to_seconds(raw_timestamp), float(row[1]), float(row[2]),
                              float(row[3]), float(row[4]), float(row[5])))
        except (TypeError, ValueError) as e:
            raise ApiError(f"candle #{i} has an unexpected format ({e}): {str(row)[:200]}")
    return out


def fetch_server_time(src, timeout, retries, opener, sleep):
    return extract_server_time(
        http_get_json(src.time_url(), timeout, retries, opener, sleep))


def fetch_candles(src, pair, tf, start_s, end_s, timeout, retries, opener, sleep,
                 *, _tokocrypto_capability=None):
    """Fetch candles between bounds. Tokocrypto requires the fixed-window capability."""
    if tf not in TF_SECONDS:
        raise ValueError(f"unknown timeframe {tf!r}")
    if (src.is_tokocrypto
            and _tokocrypto_capability is not _TOKOCRYPTO_FIXED_WINDOW_CAPABILITY):
        raise ApiError(
            "Direct Tokocrypto candle retrieval is disabled; use fetch_tokocrypto_fixed_window"
        )
    if src.is_tokocrypto and opener is default_opener:
        opener = lambda url, timeout: _fixed_window_opener(
            url, timeout, tokocrypto_capability=_tokocrypto_capability,
        )
    window = CANDLES_PER_REQUEST * TF_SECONDS[tf]
    candles, requests_made = [], 0
    chunk_start = int(start_s)
    while chunk_start < end_s:
        chunk_end = int(min(chunk_start + window - 1, end_s))
        query = urllib.parse.urlencode(
            {"symbol": src.symbol(pair), "interval": tf,
             "startTime": chunk_start * 1000, "endTime": chunk_end * 1000,
             "limit": CANDLES_PER_REQUEST})
        raw = http_get_json(
            f"{src.klines_url()}?{query}", timeout, retries, opener, sleep,
            _tokocrypto_capability=_tokocrypto_capability,
        )
        candles.extend(parse_klines(raw))
        requests_made += 1
        chunk_start = chunk_end + 1
    return candles, requests_made
