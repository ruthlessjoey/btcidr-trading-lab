"""Noncommercial Bitstamp public spot OHLC research adapter.

Only unauthenticated GETs to the documented public markets and OHLC endpoints
are allowed. Raw data stays in process memory; callers must not publish it.
"""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
from collections.abc import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, Request, build_opener,
)

HOST = "www.bitstamp.net"
BASE = f"https://{HOST}/api/v2"
MARKETS_PATH = "/api/v2/markets/"
OHLC_RE = re.compile(r"^/api/v2/ohlc/([a-z0-9-]+)/$")
SYMBOL_RE = re.compile(r"^[a-z0-9-]{3,40}$")
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_PAGE_ROWS = 1000
MAX_PAGES = 100
STEP_SECONDS = 3600


class BitstampDataError(ValueError):
    """Public data response or request failed strict validation."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BitstampDataError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise BitstampDataError(f"non-standard JSON constant is forbidden: {value}")


def _validate_url(url: str) -> dict[str, str]:
    if not isinstance(url, str) or not url:
        raise BitstampDataError("URL is required")
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise BitstampDataError("malformed URL") from exc
    if (parsed.scheme != "https" or parsed.netloc != HOST
            or parsed.hostname != HOST or parsed.username is not None
            or parsed.password is not None or parsed.port is not None
            or parsed.fragment):
        raise BitstampDataError("only the exact Bitstamp HTTPS public host is allowed")
    params = {}
    for key, value in pairs:
        if key in params:
            raise BitstampDataError(f"duplicate query parameter: {key}")
        params[key] = value
    if parsed.path == MARKETS_PATH:
        if params:
            raise BitstampDataError("markets endpoint does not accept query parameters here")
        return {"kind": "markets"}
    match = OHLC_RE.fullmatch(parsed.path)
    if not match or not SYMBOL_RE.fullmatch(match.group(1)):
        raise BitstampDataError("only documented public markets and OHLC paths are allowed")
    if set(params) != {"step", "limit", "end", "exclude_current_candle"}:
        raise BitstampDataError("OHLC request parameters are incomplete or unexpected")
    if params["step"] != str(STEP_SECONDS):
        raise BitstampDataError("only 1-hour spot candles are enabled in this research run")
    if not params["limit"].isdecimal() or not 1 <= int(params["limit"]) <= MAX_PAGE_ROWS:
        raise BitstampDataError("OHLC limit must be between 1 and 1000")
    if not params["end"].isdecimal():
        raise BitstampDataError("OHLC end must be an integer Unix timestamp")
    if params["exclude_current_candle"] != "true":
        raise BitstampDataError("the open/current candle must be excluded")
    return {"kind": "ohlc", "market_symbol": match.group(1)}


def _default_opener():
    return build_opener(
        _NoRedirect(),
        HTTPSHandler(context=ssl.create_default_context()),
    )


def fetch_json(url: str, *, opener=None, timeout: int = 20) -> tuple[object, str]:
    """Fetch bounded JSON from an exact public endpoint; no credentials or redirects."""
    _validate_url(url)
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": "TwinMoneyMaker-PersonalResearch/0.1",
        },
    )
    client = opener if opener is not None else _default_opener()
    try:
        with client.open(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise BitstampDataError(f"unexpected HTTP status: {status}")
            content_type = response.headers.get("Content-Type", "")
            if content_type and "application/json" not in content_type.lower():
                raise BitstampDataError("response content type is not JSON")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise BitstampDataError(f"Bitstamp HTTP error: {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise BitstampDataError(f"Bitstamp public request failed: {type(exc).__name__}") from exc
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise BitstampDataError("empty or oversized Bitstamp response")
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise BitstampDataError("response is not strict UTF-8 JSON") from exc
    return payload, hashlib.sha256(raw).hexdigest()


def fetch_spot_markets(*, opener=None) -> tuple[dict[str, dict[str, object]], str]:
    payload, raw_hash = fetch_json(f"https://{HOST}{MARKETS_PATH}", opener=opener)
    if not isinstance(payload, list):
        raise BitstampDataError("markets response must be a JSON list")
    markets = {}
    for index, row in enumerate(payload):
        if not isinstance(row, Mapping):
            raise BitstampDataError(f"market row {index} is not an object")
        symbol = row.get("market_symbol")
        if not isinstance(symbol, str) or not SYMBOL_RE.fullmatch(symbol):
            continue
        if row.get("market_type") != "SPOT":
            continue
        # Bitstamp documents separate order-entry and matching states. A market
        # with matching disabled is not currently executable even if trading
        # remains Enabled during a no-matching halt.
        if row.get("trading") != "Enabled" or row.get("matching") != "Enabled":
            continue
        name = row.get("name")
        base_currency = row.get("base_currency")
        counter_currency = row.get("counter_currency")
        if not all(isinstance(value, str) and value.strip()
                   for value in (name, base_currency, counter_currency)):
            raise BitstampDataError("SPOT market identity metadata is incomplete")
        base_code = base_currency.strip().lower()
        quote_code = counter_currency.strip().lower()
        if (not re.fullmatch(r"[a-z0-9]{2,15}", base_code)
                or not re.fullmatch(r"[a-z0-9]{2,15}", quote_code)):
            raise BitstampDataError("SPOT base/quote currency code is invalid")
        named_symbol = re.sub(r"[^a-z0-9]", "", name.lower())
        if symbol != base_code + quote_code or named_symbol != symbol:
            raise BitstampDataError("SPOT market symbol, name, base and quote identity do not agree")
        if symbol in markets:
            raise BitstampDataError("duplicate SPOT market symbol in markets response")
        markets[symbol] = {
            "market_symbol": symbol,
            "name": name.strip(),
            "base_currency": base_currency.strip().upper(),
            "counter_currency": counter_currency.strip().upper(),
            "trading": "Enabled",
            "matching": "Enabled",
            "market_type": "SPOT",
        }
    if not markets:
        raise BitstampDataError("Bitstamp markets response contained no valid SPOT markets")
    return markets, raw_hash


def _normalize_candle(row: object, *, step: int) -> dict[str, object]:
    from decimal import Decimal, InvalidOperation

    if not isinstance(row, Mapping):
        raise BitstampDataError("OHLC row must be an object")
    try:
        raw_timestamp = row["timestamp"]
    except KeyError as exc:
        raise BitstampDataError("OHLC timestamp must be an integer Unix timestamp") from exc
    if (
        isinstance(raw_timestamp, bool)
        or not isinstance(raw_timestamp, (str, int))
        or (isinstance(raw_timestamp, str) and not raw_timestamp.isdecimal())
    ):
        raise BitstampDataError("OHLC timestamp must be an integer Unix timestamp")
    open_ts = int(raw_timestamp)
    if open_ts < 0 or open_ts % step:
        raise BitstampDataError("OHLC timestamp is negative or not aligned to the requested step")
    values = {}
    for key in ("open", "high", "low", "close", "volume"):
        try:
            raw_value = row[key]
        except KeyError as exc:
            raise BitstampDataError(f"invalid OHLC {key}") from exc
        if isinstance(raw_value, bool) or not isinstance(raw_value, (str, int)):
            raise BitstampDataError(f"invalid OHLC {key}")
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise BitstampDataError(f"invalid OHLC {key}") from exc
        if not value.is_finite():
            raise BitstampDataError(f"non-finite OHLC {key}")
        values[key] = value
    if min(values[k] for k in ("open", "high", "low", "close")) <= 0:
        raise BitstampDataError("OHLC prices must be positive")
    if values["volume"] < 0:
        raise BitstampDataError("OHLC volume cannot be negative")
    if values["high"] < max(values["open"], values["close"], values["low"]):
        raise BitstampDataError("OHLC high violates price bounds")
    if values["low"] > min(values["open"], values["close"], values["high"]):
        raise BitstampDataError("OHLC low violates price bounds")
    return {
        "open_timestamp": open_ts,
        "timestamp": open_ts + step,
        **{key: str(value) for key, value in values.items()},
    }


def fetch_spot_history(
    market_symbol: str,
    *,
    start_timestamp: int,
    end_timestamp: int,
    opener=None,
    sleep: Callable[[float], None] = time.sleep,
    max_pages: int = MAX_PAGES,
) -> dict[str, object]:
    """Fetch closed 1h spot candles backwards using the documented end cursor.

    Data is held in memory only. The function returns hashes and normalized
    rows; it never writes raw provider data to disk.
    """
    if not isinstance(market_symbol, str) or not SYMBOL_RE.fullmatch(market_symbol):
        raise BitstampDataError("market_symbol is invalid")
    for name, value in (("start_timestamp", start_timestamp), ("end_timestamp", end_timestamp)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise BitstampDataError(f"{name} must be a nonnegative integer")
    if end_timestamp <= start_timestamp:
        raise BitstampDataError("end_timestamp must be after start_timestamp")
    if start_timestamp % STEP_SECONDS or end_timestamp % STEP_SECONDS:
        raise BitstampDataError("requested range must align to exact 1-hour candle boundaries")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= MAX_PAGES:
        raise BitstampDataError("max_pages must be between 1 and 100")

    cursor = end_timestamp
    by_open = {}
    page_hashes = []
    pages = 0
    observed_pair = None
    while cursor > start_timestamp:
        if pages >= max_pages:
            raise BitstampDataError("OHLC pagination exceeded the hard page limit")
        query = urlencode({
            "step": str(STEP_SECONDS),
            "limit": str(MAX_PAGE_ROWS),
            "end": str(cursor),
            "exclude_current_candle": "true",
        })
        url = f"{BASE}/ohlc/{market_symbol}/?{query}"
        payload, raw_hash = fetch_json(url, opener=opener)
        page_hashes.append(raw_hash)
        pages += 1
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), Mapping):
            raise BitstampDataError("OHLC response is missing the data object")
        data = payload["data"]
        pair = data.get("pair") or data.get("market")
        if not isinstance(pair, str) or not pair.strip():
            raise BitstampDataError("OHLC response is missing its market identity")
        pair = pair.strip()
        if observed_pair is None:
            observed_pair = pair
        elif pair.casefold() != observed_pair.casefold():
            raise BitstampDataError("OHLC market identity changed between pages")
        rows = data.get("ohlc")
        if not isinstance(rows, list):
            raise BitstampDataError("OHLC response data.ohlc must be a list")
        if not rows:
            break
        normalized = [_normalize_candle(row, step=STEP_SECONDS) for row in rows]
        normalized.sort(key=lambda row: row["open_timestamp"])
        eligible = [
            row for row in normalized
            if start_timestamp <= row["open_timestamp"]
            and row["timestamp"] <= end_timestamp
            and row["open_timestamp"] < cursor
        ]
        if not eligible:
            raise BitstampDataError("OHLC pagination returned no rows before the requested cursor")
        oldest = eligible[0]["open_timestamp"]
        for row in eligible:
            ts = row["open_timestamp"]
            if ts in by_open:
                raise BitstampDataError("duplicate candle returned across OHLC pages")
            by_open[ts] = row
        if oldest >= cursor:
            raise BitstampDataError("OHLC pagination made no backwards progress")
        cursor = oldest - 1
        if oldest <= start_timestamp:
            break
        sleep(0.15)

    candles = [by_open[key] for key in sorted(by_open)]
    if not candles:
        raise BitstampDataError("no closed OHLC candles returned for requested range")
    gaps = []
    if candles[0]["open_timestamp"] > start_timestamp:
        gaps.append({
            "gap_type": "LEADING",
            "after_open_timestamp": None,
            "before_open_timestamp": candles[0]["open_timestamp"],
            "missing_hours": (candles[0]["open_timestamp"] - start_timestamp) // STEP_SECONDS,
        })
    for index in range(1, len(candles)):
        delta = candles[index]["open_timestamp"] - candles[index - 1]["open_timestamp"]
        if delta != STEP_SECONDS:
            gaps.append({
                "gap_type": "INTERNAL",
                "after_open_timestamp": candles[index - 1]["open_timestamp"],
                "before_open_timestamp": candles[index]["open_timestamp"],
                "missing_hours": max(0, delta // STEP_SECONDS - 1),
            })
    if candles[-1]["timestamp"] < end_timestamp:
        gaps.append({
            "gap_type": "TRAILING",
            "after_open_timestamp": candles[-1]["open_timestamp"],
            "before_open_timestamp": None,
            "missing_hours": (end_timestamp - candles[-1]["timestamp"]) // STEP_SECONDS,
        })
    canonical = json.dumps(
        candles, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return {
        "market_symbol": market_symbol,
        "pair": pair,
        "step_seconds": STEP_SECONDS,
        "row_count": len(candles),
        "first_open_timestamp": candles[0]["open_timestamp"],
        "last_close_timestamp": candles[-1]["timestamp"],
        "gap_count": len(gaps),
        "gaps": gaps[:20],
        "coverage_status": "CONTIGUOUS" if not gaps else "GAPS_DETECTED_BACKTEST_BLOCKED",
        "dataset_sha256": hashlib.sha256(canonical).hexdigest(),
        "raw_page_sha256": hashlib.sha256("".join(page_hashes).encode("ascii")).hexdigest(),
        "page_count": pages,
        "candles": candles,
    }
