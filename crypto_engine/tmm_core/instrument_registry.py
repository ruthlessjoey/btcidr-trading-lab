"""Versioned, point-in-time crypto spot instrument and lifecycle registry.

This module consumes caller-supplied metadata only. It does not discover
markets, fetch listings, inspect contracts or route orders.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Sequence

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
STATUSES = frozenset({"ACTIVE", "HALTED", "DELISTING_ANNOUNCED", "DELISTED",
                      "MIGRATION_PENDING", "UNKNOWN"})
MARKET_TYPES = frozenset({"CEX_SPOT", "DEX_POOL"})


class InstrumentRegistryError(ValueError):
    """Raised when instrument identity, versioning or lifecycle data is invalid."""


@dataclass(frozen=True)
class InstrumentVersion:
    market_id: str
    venue_id: str
    market_type: str
    base_asset_id: str
    quote_asset_id: str
    base_symbol: str
    quote_symbol: str
    effective_from: int
    effective_to: int | None
    source_id: str
    source_sha256: str
    source_timestamp: int
    observed_at: int
    status: str
    sell_side_available: bool | None
    reactivation_confirmed: bool | None = None


def _timestamp(value: object, field: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InstrumentRegistryError(f"{field} must be a nonnegative integer timestamp")
    return value


def validate_instrument_registry(*, records: Sequence[InstrumentVersion],
                                  decision_time: int,
                                  max_metadata_age_seconds: int = 86400) -> list[InstrumentVersion]:
    """Validate registry structure and return deterministic market/version order."""
    _timestamp(decision_time, "decision_time")
    if (isinstance(max_metadata_age_seconds, bool) or not isinstance(max_metadata_age_seconds, int)
            or max_metadata_age_seconds < 0):
        raise InstrumentRegistryError("max_metadata_age_seconds must be a nonnegative integer")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise InstrumentRegistryError("records must be a non-empty sequence")
    clean = []
    for record in records:
        if not isinstance(record, InstrumentVersion):
            raise InstrumentRegistryError("all registry records must be InstrumentVersion values")
        for field in ("market_id", "venue_id", "base_asset_id", "quote_asset_id",
                      "base_symbol", "quote_symbol", "source_id"):
            value = getattr(record, field)
            if not isinstance(value, str) or not value.strip():
                raise InstrumentRegistryError(f"{field} must be a non-empty string")
        if record.market_type not in MARKET_TYPES:
            raise InstrumentRegistryError("market_type must be CEX_SPOT or DEX_POOL")
        if record.status not in STATUSES:
            raise InstrumentRegistryError("market status is unsupported")
        if not isinstance(record.source_sha256, str) or not HASH_RE.fullmatch(record.source_sha256):
            raise InstrumentRegistryError("source_sha256 must be a lowercase 64-character SHA-256 digest")
        effective_from = _timestamp(record.effective_from, "effective_from")
        effective_to = _timestamp(record.effective_to, "effective_to", allow_none=True)
        source_timestamp = _timestamp(record.source_timestamp, "source_timestamp")
        observed_at = _timestamp(record.observed_at, "observed_at")
        if effective_to is not None and effective_to <= effective_from:
            raise InstrumentRegistryError("effective_to must be later than effective_from")
        if source_timestamp > observed_at:
            raise InstrumentRegistryError("source_timestamp cannot be later than observed_at")
        if source_timestamp > decision_time or observed_at > decision_time:
            raise InstrumentRegistryError("future instrument metadata is not allowed")
        if record.sell_side_available is not None and not isinstance(record.sell_side_available, bool):
            raise InstrumentRegistryError("sell_side_available must be boolean or None")
        if record.reactivation_confirmed is not None and not isinstance(record.reactivation_confirmed, bool):
            raise InstrumentRegistryError("reactivation_confirmed must be boolean or None")
        clean.append(record)

    clean.sort(key=lambda r: (r.market_id, r.effective_from, r.source_timestamp, r.source_sha256))
    previous_by_market: dict[str, InstrumentVersion] = {}
    for record in clean:
        previous = previous_by_market.get(record.market_id)
        if previous is not None:
            if previous.effective_to is None or record.effective_from < previous.effective_to:
                raise InstrumentRegistryError(f"overlapping effective versions for {record.market_id}")
        previous_by_market[record.market_id] = record
    return clean


def evaluate_market_lifecycle(*, records: Sequence[InstrumentVersion], market_id: str,
                              decision_time: int,
                              max_metadata_age_seconds: int = 86400) -> dict[str, object]:
    """Resolve one market as-of time and fail closed on halts, delists or migrations.

    A market is eligible for new entries only when ACTIVE, metadata is fresh,
    a sell-side path is explicitly available, and any reactivation after an
    inactive state is explicitly confirmed by newer source evidence.
    These flags are not order approval.
    """
    clean = validate_instrument_registry(records=records, decision_time=decision_time,
                                         max_metadata_age_seconds=max_metadata_age_seconds)
    if not isinstance(market_id, str) or not market_id.strip():
        raise InstrumentRegistryError("market_id is required")
    versions = [r for r in clean if r.market_id == market_id]
    current = [r for r in versions if r.effective_from <= decision_time
               and (r.effective_to is None or decision_time < r.effective_to)]
    if len(current) != 1:
        raise InstrumentRegistryError("market has no unique point-in-time registry version")
    record = current[0]
    reasons: list[str] = []
    metadata_fresh = decision_time - record.source_timestamp <= max_metadata_age_seconds
    if not metadata_fresh:
        reasons.append("STALE_MARKET_METADATA")

    prior = [r for r in versions if r.effective_from < record.effective_from]
    previous = prior[-1] if prior else None
    reactivation_required = previous is not None and previous.status != "ACTIVE" and record.status == "ACTIVE"
    if reactivation_required:
        if record.reactivation_confirmed is not True:
            reasons.append("REACTIVATION_NOT_CONFIRMED")
        if (previous is not None and
                (record.source_timestamp <= previous.source_timestamp
                 or record.observed_at <= previous.observed_at)):
            reasons.append("REACTIVATION_EVIDENCE_NOT_NEWER")

    sell_available = record.sell_side_available is True and metadata_fresh
    if record.status == "ACTIVE":
        if not sell_available:
            reasons.append("EXIT_PATH_NOT_CONFIRMED")
        entries = sell_available and not reasons
        exit_path = sell_available
    elif record.status in {"HALTED", "DELISTING_ANNOUNCED"}:
        entries = False
        exit_path = sell_available
        reasons.append(f"MARKET_{record.status}")
    else:
        entries = False
        exit_path = False
        reasons.append(f"MARKET_{record.status}")

    if reactivation_required and (record.reactivation_confirmed is not True
                                  or "REACTIVATION_EVIDENCE_NOT_NEWER" in reasons):
        entries = False
    return {
        "market_id": record.market_id,
        "venue_id": record.venue_id,
        "market_type": record.market_type,
        "base_asset_id": record.base_asset_id,
        "quote_asset_id": record.quote_asset_id,
        "status": record.status,
        "market_eligible_for_new_entries": entries,
        "sell_side_market_available": exit_path,
        "reactivation_required": reactivation_required,
        "reasons": sorted(set(reasons)),
        "source_id": record.source_id,
        "source_sha256": record.source_sha256,
        "source_timestamp": record.source_timestamp,
        "observed_at": record.observed_at,
        "decision_time": decision_time,
        "order_authorized": False,
        "delisted_position_resolution": "UNRESOLVED" if record.status == "DELISTED" else None,
    }
