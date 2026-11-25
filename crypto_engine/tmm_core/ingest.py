"""End-to-end offline validation of an approved public kline response payload."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .provider_policy import ProviderPolicyError, build_kline_provenance
from .tokocrypto_klines import KlinePayloadError, normalize_tokocrypto_klines


MAX_KLINE_RESPONSE_BYTES = 4 * 1024 * 1024


class IngestionError(ValueError):
    """Raised when a response cannot pass source-policy and data validation."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IngestionError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise IngestionError(f"non-standard JSON constant is not allowed: {value}")


def decode_kline_response(raw_response: bytes) -> Any:
    """Validate bounded UTF-8 JSON response bytes without asserting source identity."""
    try:
        text = raw_response.decode("utf-8", errors="strict")
        return json.loads(text, object_pairs_hook=_unique_object,
                          parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IngestionError("response is not valid strict UTF-8 JSON") from exc


def validate_approved_kline_payload(*, method: str, url: str, raw_response: bytes,
                                    retrieved_at_ms: int, decision_time_ms: int,
                                    expected_symbol: str, expected_interval: str,
                                    headers: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Validate URL policy, raw response integrity, schema and as-of time.

    The function accepts bytes already obtained by an external caller. It does
    not make a request and cannot prove which network peer supplied those bytes.
    """
    if not isinstance(raw_response, bytes) or not raw_response:
        raise IngestionError("raw response must be non-empty bytes")
    if len(raw_response) > MAX_KLINE_RESPONSE_BYTES:
        raise IngestionError("raw response exceeds the 4 MiB safety limit")
    try:
        provenance = build_kline_provenance(method=method, url=url,
                                             raw_payload=raw_response,
                                             retrieved_at_ms=retrieved_at_ms,
                                             headers=headers)
        request_parameters = provenance["request"]["parameters"]
        if request_parameters.get("symbol") != expected_symbol:
            raise IngestionError("requested symbol does not match expected symbol")
        if request_parameters.get("interval") != expected_interval:
            raise IngestionError("requested interval does not match expected interval")
        response = decode_kline_response(raw_response)
        candles = normalize_tokocrypto_klines(response, decision_time_ms=decision_time_ms)
    except (ProviderPolicyError, KlinePayloadError, IngestionError) as exc:
        raise IngestionError(str(exc)) from exc
    except IngestionError:
        raise
    except (TypeError, ValueError) as exc:
        raise IngestionError("response payload could not be validated") from exc

    gaps = [
        {"row_index": index, "gap_before_ms": row["gap_before_ms"],
         "source_open_time_ms": row["source_open_time_ms"],
         "previous_close_time_ms": candles[index - 1]["source_close_time_ms"]}
        for index, row in enumerate(candles) if index > 0 and row["gap_before_ms"] > 0
    ]
    return {
        "symbol": expected_symbol,
        "interval": expected_interval,
        "row_count": len(candles),
        "gap_count": len(gaps),
        "gaps": gaps,
        "coverage_status": "CONTIGUOUS" if not gaps else "GAPS_DETECTED_BACKTEST_BLOCKED_BY_DEFAULT",
        "first_close_time_ms": candles[0]["source_close_time_ms"],
        "last_close_time_ms": candles[-1]["source_close_time_ms"],
        "candles": candles,
        "provenance": provenance,
        "validation_status": "URL_POLICY_AND_PAYLOAD_SCHEMA_VALIDATED_SOURCE_PEER_AND_SYMBOL_LISTING_NOT_INDEPENDENTLY_VERIFIED",
    }
