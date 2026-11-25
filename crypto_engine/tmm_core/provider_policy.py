"""Strict allowlist and provenance helpers for approved public candle requests.

This module validates a proposed request; it never sends it. It permits only
unauthenticated GET to the exact owner-approved Tokocrypto BTCIDR kline endpoint.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit


APPROVED_HOST = "www.tokocrypto.site"
APPROVED_PATH = "/api/v3/klines"
APPROVED_SYMBOL = "BTCIDR"
APPROVED_INTERVALS = frozenset({"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"})
ALLOWED_QUERY_KEYS = frozenset({"symbol", "interval", "startTime", "endTime", "limit"})


class ProviderPolicyError(ValueError):
    """Raised when a data request violates the approved-source policy."""


def validate_approved_kline_request(*, method: str, url: str,
                                    headers: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Validate and return a safe request descriptor; does not perform I/O."""
    if not isinstance(method, str) or method.upper() != "GET":
        raise ProviderPolicyError("only unauthenticated GET is approved")
    if headers is not None and (not isinstance(headers, Mapping) or len(headers) != 0):
        raise ProviderPolicyError("request headers are not approved; send no authentication or custom headers")
    if not isinstance(url, str) or not url:
        raise ProviderPolicyError("request URL is required")
    try:
        parsed = urlsplit(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise ProviderPolicyError("request URL is malformed") from exc
    if (parsed.scheme != "https" or parsed.netloc != APPROVED_HOST
            or parsed.hostname != APPROVED_HOST or parsed.username is not None
            or parsed.password is not None or parsed.port is not None
            or parsed.path != APPROVED_PATH or parsed.fragment):
        raise ProviderPolicyError("request must use the exact approved HTTPS host and kline path")
    if not pairs:
        raise ProviderPolicyError("symbol and interval query parameters are required")
    params: dict[str, str] = {}
    for key, value in pairs:
        if key not in ALLOWED_QUERY_KEYS:
            raise ProviderPolicyError(f"query parameter is not allowed: {key}")
        if key in params:
            raise ProviderPolicyError(f"duplicate query parameter: {key}")
        if not value:
            raise ProviderPolicyError(f"query parameter cannot be empty: {key}")
        params[key] = value
    if "symbol" not in params or "interval" not in params:
        raise ProviderPolicyError("symbol and interval query parameters are required")
    if params["symbol"] != APPROVED_SYMBOL:
        raise ProviderPolicyError("only the approved BTCIDR symbol is permitted")
    if params["interval"] not in APPROVED_INTERVALS:
        raise ProviderPolicyError("interval is not in Tokocrypto's documented kline interval set")
    if "startTime" in params and not params["startTime"].isdecimal():
        raise ProviderPolicyError("startTime must be integer milliseconds")
    if "endTime" in params and not params["endTime"].isdecimal():
        raise ProviderPolicyError("endTime must be integer milliseconds")
    if "startTime" in params and "endTime" in params:
        if int(params["endTime"]) < int(params["startTime"]):
            raise ProviderPolicyError("endTime cannot be before startTime")
    if "limit" in params:
        if not params["limit"].isdecimal() or not 1 <= int(params["limit"]) <= 1000:
            raise ProviderPolicyError("limit must be between 1 and 1000")
    return {
        "method": "GET",
        "scheme": "https",
        "host": APPROVED_HOST,
        "path": APPROVED_PATH,
        "parameters": dict(sorted(params.items())),
        "authentication": "NONE",
        "request_headers": "NONE",
        "source_scope": "APPROVED_PUBLIC_KLINE_ONLY",
        "network_action_performed": False,
    }


def build_kline_provenance(*, method: str, url: str, raw_payload: bytes,
                           retrieved_at_ms: int,
                           headers: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Bind raw response bytes to the approved request descriptor with SHA-256."""
    descriptor = validate_approved_kline_request(method=method, url=url, headers=headers)
    if not isinstance(raw_payload, bytes) or not raw_payload:
        raise ProviderPolicyError("raw_payload must be non-empty response bytes")
    if (isinstance(retrieved_at_ms, bool) or not isinstance(retrieved_at_ms, int)
            or retrieved_at_ms <= 0):
        raise ProviderPolicyError("retrieved_at_ms must be a positive integer")
    return {
        "request": descriptor,
        "retrieved_at_ms": retrieved_at_ms,
        "payload_bytes": len(raw_payload),
        "payload_sha256": hashlib.sha256(raw_payload).hexdigest(),
        "provenance_status": "REQUEST_POLICY_VALIDATED_PAYLOAD_HASHED_SOURCE_TRUTH_NOT_INDEPENDENTLY_VERIFIED",
    }
