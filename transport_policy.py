"""Exact public market-data transport policy. Pure stdlib; no network side effects."""
from __future__ import annotations

import ipaddress
import socket
import time
from urllib.parse import parse_qsl, urlsplit


class PolicyError(ValueError):
    """A request is outside the explicitly approved public read-only route matrix."""


# Provider IDs resolve to fixed origins; configuration must never add an origin.
PROVIDER_BASE_URLS = {
    "kraken": "https://api.kraken.com",
    "binance-vision": "https://data-api.binance.vision",
    "tokocrypto": "https://www.tokocrypto.site",
    "coinbase-research": "https://api.exchange.coinbase.com",
}

# (host, method, exact path): (allowed query keys, maximum response bytes)
ROUTES = {
    ("api.kraken.com", "GET", "/0/public/Time"): (set(), 32 * 1024),
    ("api.kraken.com", "GET", "/0/public/OHLC"): ({"pair", "interval", "since"}, 2 * 1024 * 1024),
    ("data-api.binance.vision", "GET", "/api/v3/time"): (set(), 32 * 1024),
    ("data-api.binance.vision", "GET", "/api/v3/klines"): (
        {"symbol", "interval", "startTime", "endTime", "limit"}, 2 * 1024 * 1024),
    ("data-api.binance.vision", "GET", "/api/v3/exchangeInfo"): ({"symbol"}, 512 * 1024),
    ("www.tokocrypto.site", "GET", "/api/v3/time"): (set(), 32 * 1024),
    ("www.tokocrypto.site", "GET", "/api/v3/klines"): (
        {"symbol", "interval", "startTime", "endTime", "limit"}, 2 * 1024 * 1024),
    ("api.exchange.coinbase.com", "GET", "/time"): (set(), 32 * 1024),
    ("api.exchange.coinbase.com", "GET", "/products/BTC-USD/candles"): (
        {"granularity", "start", "end"}, 1024 * 1024),
}

REQUIRED_QUERY_KEYS = {
    ("api.kraken.com", "GET", "/0/public/OHLC"): {"pair", "interval"},
    ("data-api.binance.vision", "GET", "/api/v3/klines"): {"symbol", "interval", "limit"},
    ("data-api.binance.vision", "GET", "/api/v3/exchangeInfo"): {"symbol"},
    ("www.tokocrypto.site", "GET", "/api/v3/klines"): {"symbol", "interval", "limit"},
    ("api.exchange.coinbase.com", "GET", "/products/BTC-USD/candles"): {"granularity"},
}

MAX_URL_LENGTH = 8192
READ_CHUNK_BYTES = 64 * 1024


def provider_base_url(provider_id: str) -> str:
    try:
        return PROVIDER_BASE_URLS[provider_id]
    except (KeyError, TypeError):
        raise PolicyError("provider is not approved")


def validate_request(url: str, method: str = "GET") -> int:
    """Validate the raw URL before any opener (including an injected opener) is called."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise PolicyError("request URL is invalid")
    if method != "GET":
        raise PolicyError("HTTP method is not approved")
    if not url.isascii() or any(ord(ch) < 0x21 or ord(ch) == 0x7f for ch in url):
        raise PolicyError("request URL contains invalid characters")
    if "\\" in url or "#" in url:
        raise PolicyError("request URL contains a forbidden delimiter")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise PolicyError("request URL authority is invalid")
    if parts.scheme != "https" or not host:
        raise PolicyError("only approved HTTPS URLs are allowed")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise PolicyError("userinfo is not allowed")
    if parts.fragment:
        raise PolicyError("URL fragments are not allowed")
    if port not in (None, 443):
        raise PolicyError("non-default HTTPS ports are not allowed")
    if parts.netloc not in (host, host + ":443") or host.endswith(".") or "%" in parts.netloc:
        raise PolicyError("URL authority is not canonical")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PolicyError("IP-literal hosts are not allowed")
    if host == "localhost" or host.endswith(".localhost") or "xn--" in host:
        raise PolicyError("host is not approved")
    route = ROUTES.get((host, method, parts.path))
    if route is None:
        raise PolicyError("host, method, or path is not approved")
    if "%" in parts.path or any(seg in (".", "..") for seg in parts.path.split("/")):
        raise PolicyError("URL path is not canonical")
    allowed_keys, max_bytes = route
    if len(parts.query) > 4096:
        raise PolicyError("request query is too long")
    try:
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True) if parts.query else []
    except ValueError:
        raise PolicyError("request query is malformed")
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)) or not set(keys).issubset(allowed_keys):
        raise PolicyError("request query is not approved")
    required = REQUIRED_QUERY_KEYS.get((host, method, parts.path), set())
    if not required.issubset(set(keys)):
        raise PolicyError("request query is incomplete")
    if any(not k.isascii() or not v.isascii()
           or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in k + v)
           for k, v in pairs):
        raise PolicyError("request query contains invalid characters")
    return max_bytes


def _set_socket_timeout(response, remaining: float) -> None:
    """Require a real socket so a slow-drip peer cannot defeat the total deadline."""
    try:
        sock = response.fp.raw._sock
        sock.settimeout(max(0.001, remaining))
    except (AttributeError, OSError, TypeError):
        raise PolicyError("cannot enforce response deadline")


def read_bounded(response, max_bytes: int, timeout_seconds: float) -> bytes:
    """Read at most max_bytes, enforce a wall-clock deadline, and reject overflow."""
    headers = getattr(response, "headers", None)
    if headers is not None:
        declared = headers.get("Content-Length")
        if declared is not None:
            if not str(declared).isdigit():
                raise PolicyError("response length header is invalid")
            if int(declared) > max_bytes:
                raise PolicyError("response exceeds the approved size limit")
    deadline = time.monotonic() + timeout_seconds
    chunks = []
    total = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PolicyError("response deadline exceeded")
        _set_socket_timeout(response, remaining)
        chunk = response.read(min(READ_CHUNK_BYTES, max_bytes + 1 - total))
        if time.monotonic() > deadline:
            raise PolicyError("response deadline exceeded")
        if not isinstance(chunk, (bytes, bytearray)):
            raise PolicyError("response body is invalid")
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PolicyError("response exceeds the approved size limit")
        chunks.append(bytes(chunk))
    return b"".join(chunks)
