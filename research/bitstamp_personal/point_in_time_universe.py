"""Offline verifier for the Bitstamp V2 point-in-time universe evidence.

No network access is performed here. The public-data runner remains blocked
until this manifest is complete, independently reviewed and hash-pinned.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

MAX_EVIDENCE_BYTES = 512 * 1024
EXPECTED_EVIDENCE_SHA256: str | None = None
EVIDENCE_FILENAME = "POINT_IN_TIME_UNIVERSE_EVIDENCE.json"

FROZEN_PREREGISTRATION_ID = "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2"
FROZEN_SYMBOLS = ("btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd")
FROZEN_START_TIMESTAMP = 1704067200
FROZEN_END_TIMESTAMP = 1793491200
FROZEN_INTERVAL_SECONDS = 3600
OFFICIAL_HOSTS = frozenset({"www.bitstamp.net", "blog.bitstamp.net"})
_HASH = re.compile(r"[0-9a-f]{64}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class PointInTimeUniverseError(ValueError):
    """Point-in-time market-universe evidence is incomplete or untrusted."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PointInTimeUniverseError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise PointInTimeUniverseError(f"non-standard JSON constant is not allowed: {value}")


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise PointInTimeUniverseError("evidence is not canonical JSON data") from exc


def evidence_payload_sha256(manifest: dict[str, Any]) -> str:
    """Hash accepted source facts while excluding reviewer attestations."""
    payload = {key: value for key, value in manifest.items() if key != "independent_review"}
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _timestamp(value: object, field: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PointInTimeUniverseError(f"{field} must be a nonnegative Unix timestamp")
    return value


def _string(value: object, field: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PointInTimeUniverseError(f"{field} must be a bounded non-empty string")
    return value


def _sha(value: object, field: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise PointInTimeUniverseError(f"{field} must be lowercase SHA-256")
    return value


def _source_index(sources: object) -> dict[str, dict[str, Any]]:
    if not isinstance(sources, list) or not sources:
        raise PointInTimeUniverseError("source_evidence must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    allowed_types = {
        "LISTING_NOTICE", "MARKET_STATUS_LEDGER",
        "API_SEMANTICS", "JURISDICTIONAL_STATUS_NOTICE", "DATA_RIGHTS",
    }
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {
            "source_id", "evidence_type", "url", "published_date",
            "claim", "snapshot_sha256",
        }:
            raise PointInTimeUniverseError(f"source_evidence[{index}] schema is invalid")
        source_id = _string(source["source_id"], f"source_evidence[{index}].source_id", maximum=128)
        if source_id in result:
            raise PointInTimeUniverseError("source_id values must be unique")
        if (not isinstance(source["evidence_type"], str)
                or source["evidence_type"] not in allowed_types):
            raise PointInTimeUniverseError(f"source_evidence[{index}].evidence_type is invalid")
        url = _string(source["url"], f"source_evidence[{index}].url", maximum=2048)
        if not url.startswith("https://"):
            raise PointInTimeUniverseError(f"source_evidence[{index}].url must use HTTPS")
        host = url[8:].split("/", 1)[0].split(":", 1)[0].lower()
        if host not in OFFICIAL_HOSTS:
            raise PointInTimeUniverseError(f"source_evidence[{index}] is not an official Bitstamp URL")
        published = source["published_date"]
        if published is not None and (
            not isinstance(published, str) or _DATE.fullmatch(published) is None
        ):
            raise PointInTimeUniverseError(
                f"source_evidence[{index}].published_date must be YYYY-MM-DD or null"
            )
        _string(source["claim"], f"source_evidence[{index}].claim", maximum=2048)
        if source["snapshot_sha256"] is not None:
            _sha(source["snapshot_sha256"], f"source_evidence[{index}].snapshot_sha256")
        result[source_id] = source
    return result


def _referenced_sources(
    ids: object, source_index: dict[str, dict[str, Any]], field: str,
    *, required_type: str | None = None,
) -> None:
    if not isinstance(ids, list) or not ids:
        raise PointInTimeUniverseError(f"{field} must reference at least one evidence source")
    if any(not isinstance(source_id, str) for source_id in ids):
        raise PointInTimeUniverseError(f"{field} source IDs must be strings")
    if len(set(ids)) != len(ids):
        raise PointInTimeUniverseError(f"{field} contains duplicate source IDs")
    for source_id in ids:
        if not isinstance(source_id, str) or source_id not in source_index:
            raise PointInTimeUniverseError(f"{field} references an unknown source")
        source = source_index[source_id]
        if source["snapshot_sha256"] is None:
            raise PointInTimeUniverseError(
                f"{field} source {source_id} has no captured, hash-pinned source snapshot"
            )
        if required_type is not None and source["evidence_type"] != required_type:
            raise PointInTimeUniverseError(
                f"{field} source {source_id} is not {required_type} evidence"
            )


def _ceil_hour(timestamp: int) -> int:
    return (
        (timestamp + FROZEN_INTERVAL_SECONDS - 1) // FROZEN_INTERVAL_SECONDS
    ) * FROZEN_INTERVAL_SECONDS


def _verify_review(review: object, evidence_sha256: str) -> None:
    if not isinstance(review, dict) or set(review) != {"status", "reviewers"}:
        raise PointInTimeUniverseError("independent_review schema is invalid")
    if review["status"] != "ACCEPTED":
        raise PointInTimeUniverseError("independent point-in-time evidence review is not accepted")
    reviewers = review["reviewers"]
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        raise PointInTimeUniverseError("at least two independent evidence reviewers are required")
    seen = set()
    for index, reviewer in enumerate(reviewers):
        if not isinstance(reviewer, dict) or set(reviewer) != {
            "reviewer_id", "status", "reviewed_evidence_sha256",
            "reviewed_market_status", "reviewed_data_rights",
        }:
            raise PointInTimeUniverseError(f"independent_review.reviewers[{index}] schema is invalid")
        reviewer_id = _string(
            reviewer["reviewer_id"], f"reviewer[{index}].reviewer_id", maximum=128
        )
        if reviewer_id in seen:
            raise PointInTimeUniverseError("independent reviewers must be distinct")
        seen.add(reviewer_id)
        if reviewer["status"] != "ACCEPTED":
            raise PointInTimeUniverseError(f"reviewer[{index}] has not accepted the evidence")
        if reviewer["reviewed_evidence_sha256"] != evidence_sha256:
            raise PointInTimeUniverseError(f"reviewer[{index}] reviewed a different evidence digest")
        if reviewer["reviewed_market_status"] is not True or reviewer["reviewed_data_rights"] is not True:
            raise PointInTimeUniverseError(
                f"reviewer[{index}] did not review both status and rights evidence"
            )


def _verify_market(
    market: object,
    index: int,
    source_index: dict[str, dict[str, Any]],
    date_policy: str,
) -> tuple[str, int]:
    required = {
        "market_symbol", "pair", "market_type", "global_scope",
        "listing_announcement_date", "first_listing_timestamp",
        "first_matching_enabled_timestamp", "first_market_orders_enabled_timestamp",
        "eligible_start_timestamp", "limit_only_matching_from_timestamp",
        "jurisdictional_notes", "source_ids", "status_intervals",
    }
    if not isinstance(market, dict) or set(market) != required:
        raise PointInTimeUniverseError(f"markets[{index}] schema is invalid")
    symbol = market["market_symbol"]
    if not isinstance(symbol, str) or symbol.casefold() not in FROZEN_SYMBOLS:
        raise PointInTimeUniverseError(
            f"markets[{index}].market_symbol is outside the frozen V2 universe"
        )
    symbol = symbol.casefold()
    pair = _string(market["pair"], f"markets[{index}].pair", maximum=64)
    if re.sub(r"[^a-z0-9]", "", pair.casefold()) != symbol:
        raise PointInTimeUniverseError(f"markets[{index}] pair does not match {symbol}")
    if market["market_type"] != "SPOT":
        raise PointInTimeUniverseError(f"{symbol} is not evidenced as SPOT")
    if market["global_scope"] != "GLOBAL_PUBLIC_MARKET":
        raise PointInTimeUniverseError(f"{symbol} must define global public-market scope")
    announcement = market["listing_announcement_date"]
    if announcement is not None and (
        not isinstance(announcement, str) or _DATE.fullmatch(announcement) is None
    ):
        raise PointInTimeUniverseError(
            f"{symbol}.listing_announcement_date must be YYYY-MM-DD or null"
        )

    first_listing = _timestamp(
        market["first_listing_timestamp"], f"{symbol}.first_listing_timestamp"
    )
    first_matching = _timestamp(
        market["first_matching_enabled_timestamp"],
        f"{symbol}.first_matching_enabled_timestamp",
    )
    first_market_orders = _timestamp(
        market["first_market_orders_enabled_timestamp"],
        f"{symbol}.first_market_orders_enabled_timestamp",
    )
    eligible_start = _timestamp(
        market["eligible_start_timestamp"], f"{symbol}.eligible_start_timestamp"
    )
    _timestamp(
        market["limit_only_matching_from_timestamp"],
        f"{symbol}.limit_only_matching_from_timestamp",
        optional=True,
    )
    notes = market["jurisdictional_notes"]
    if not isinstance(notes, list) or any(
        not isinstance(note, str) or len(note) > 512 for note in notes
    ):
        raise PointInTimeUniverseError(f"{symbol}.jurisdictional_notes must be bounded strings")
    _referenced_sources(market["source_ids"], source_index, f"{symbol}.source_ids")
    market_sources = [source_index[source_id] for source_id in market["source_ids"]]
    if not any(source["evidence_type"] == "LISTING_NOTICE" for source in market_sources):
        raise PointInTimeUniverseError(
            f"{symbol} listing timestamp lacks a source classified as LISTING_NOTICE"
        )
    if not any(source["evidence_type"] == "MARKET_STATUS_LEDGER" for source in market_sources):
        raise PointInTimeUniverseError(
            f"{symbol} matching/market-order timestamps lack a MARKET_STATUS_LEDGER source; interval evidence is not MARKET_STATUS_LEDGER"
        )
    if not (first_listing <= first_matching <= first_market_orders):
        raise PointInTimeUniverseError(
            f"{symbol} first listing/matching/market-order timestamps are inconsistent"
        )
    if eligible_start % FROZEN_INTERVAL_SECONDS:
        raise PointInTimeUniverseError(
            f"{symbol}.eligible_start_timestamp must align to a 1-hour candle"
        )
    if date_policy == "COMMON_START":
        if eligible_start != FROZEN_START_TIMESTAMP:
            raise PointInTimeUniverseError(f"{symbol} does not meet the common V2 start boundary")
        if max(first_listing, first_matching, first_market_orders) > FROZEN_START_TIMESTAMP:
            raise PointInTimeUniverseError(f"{symbol} was not fully eligible at the common V2 start")
    elif date_policy == "PER_MARKET_INCEPTION":
        expected_start = max(
            FROZEN_START_TIMESTAMP,
            _ceil_hour(max(first_listing, first_matching, first_market_orders)),
        )
        if eligible_start != expected_start:
            raise PointInTimeUniverseError(
                f"{symbol} per-market inception does not follow full-order eligibility"
            )
        if eligible_start < FROZEN_START_TIMESTAMP:
            raise PointInTimeUniverseError(f"{symbol} per-market inception precedes the V2 window")

    intervals = market["status_intervals"]
    if not isinstance(intervals, list) or not intervals:
        raise PointInTimeUniverseError(f"{symbol} has no historical trading/matching status ledger")
    cursor = eligible_start
    for interval_index, interval in enumerate(intervals):
        if not isinstance(interval, dict) or set(interval) != {
            "start_timestamp", "end_timestamp", "market_type", "trading",
            "matching", "instant_and_market_orders", "source_ids",
        }:
            raise PointInTimeUniverseError(
                f"{symbol}.status_intervals[{interval_index}] schema is invalid"
            )
        start = _timestamp(
            interval["start_timestamp"],
            f"{symbol}.status_intervals[{interval_index}].start_timestamp",
        )
        end = _timestamp(
            interval["end_timestamp"],
            f"{symbol}.status_intervals[{interval_index}].end_timestamp",
        )
        if start != cursor or end <= start:
            raise PointInTimeUniverseError(
                f"{symbol} status history has a gap, overlap or invalid interval"
            )
        if interval["market_type"] != "SPOT":
            raise PointInTimeUniverseError(f"{symbol} status interval is not SPOT")
        if any(
            interval[field] != "Enabled"
            for field in ("trading", "matching", "instant_and_market_orders")
        ):
            raise PointInTimeUniverseError(
                f"{symbol} contains a trading, matching or market-order-disabled interval"
            )
        _referenced_sources(
            interval["source_ids"], source_index,
            f"{symbol}.status_intervals[{interval_index}].source_ids",
            required_type="MARKET_STATUS_LEDGER",
        )
        cursor = end
    if cursor != FROZEN_END_TIMESTAMP:
        raise PointInTimeUniverseError(
            f"{symbol} historical status ledger does not reach the frozen end boundary"
        )
    return symbol, eligible_start


def verify_point_in_time_universe_evidence(
    raw: bytes,
    *,
    expected_sha256: str | None,
) -> dict[str, Any]:
    """Verify source facts, order-state intervals, rights and independent review."""
    if not isinstance(raw, bytes) or not raw:
        raise PointInTimeUniverseError("evidence manifest must be non-empty bytes")
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise PointInTimeUniverseError("evidence manifest exceeds the 512 KiB bound")
    if expected_sha256 is None:
        raise PointInTimeUniverseError("accepted point-in-time evidence digest is not pinned")
    expected = _sha(expected_sha256, "expected_sha256")
    try:
        manifest = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except PointInTimeUniverseError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PointInTimeUniverseError(
            "evidence manifest is not strict UTF-8 JSON"
        ) from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "preregistration_id", "candidate_symbols",
        "requested_window", "date_policy", "data_rights",
        "independent_review", "source_evidence", "markets",
    }:
        raise PointInTimeUniverseError("evidence manifest top-level schema is invalid")
    if isinstance(manifest["schema_version"], bool) or manifest["schema_version"] != 1:
        raise PointInTimeUniverseError("unsupported evidence manifest schema version")
    if manifest["preregistration_id"] != FROZEN_PREREGISTRATION_ID:
        raise PointInTimeUniverseError("evidence manifest preregistration ID does not match V2")
    if manifest["candidate_symbols"] != list(FROZEN_SYMBOLS):
        raise PointInTimeUniverseError("evidence manifest candidate universe differs from frozen V2")
    window = manifest["requested_window"]
    if not isinstance(window, dict) or set(window) != {
        "start_timestamp", "end_timestamp", "interval_seconds",
    }:
        raise PointInTimeUniverseError("requested_window schema is invalid")
    if window != {
        "start_timestamp": FROZEN_START_TIMESTAMP,
        "end_timestamp": FROZEN_END_TIMESTAMP,
        "interval_seconds": FROZEN_INTERVAL_SECONDS,
    }:
        raise PointInTimeUniverseError("requested window differs from frozen V2 boundaries")

    digest = evidence_payload_sha256(manifest)
    if digest != expected:
        raise PointInTimeUniverseError(
            "point-in-time evidence digest does not match the pinned SHA-256"
        )
    policy = manifest["date_policy"]
    if not isinstance(policy, dict) or set(policy) != {"status", "mode", "decision_note"}:
        raise PointInTimeUniverseError("date_policy schema is invalid")
    if (policy["status"] != "APPROVED"
            or not isinstance(policy["mode"], str)
            or policy["mode"] not in {"COMMON_START", "PER_MARKET_INCEPTION"}):
        raise PointInTimeUniverseError("V2 date policy decision is not approved")

    sources = _source_index(manifest["source_evidence"])
    rights = manifest["data_rights"]
    if not isinstance(rights, dict) or set(rights) != {"status", "scope", "source_ids"}:
        raise PointInTimeUniverseError("data_rights schema is invalid")
    if (
        rights["status"] != "APPROVED_PERSONAL_NONCOMMERCIAL"
        or rights["scope"] != "PERSONAL_NONCOMMERCIAL_SPOT_RESEARCH"
    ):
        raise PointInTimeUniverseError(
            "personal noncommercial data rights are not independently accepted"
        )
    _referenced_sources(
        rights["source_ids"], sources, "data_rights.source_ids",
        required_type="DATA_RIGHTS",
    )
    _verify_review(manifest["independent_review"], digest)

    markets = manifest["markets"]
    if not isinstance(markets, list) or len(markets) != len(FROZEN_SYMBOLS):
        raise PointInTimeUniverseError(
            "evidence manifest must include every frozen V2 market"
        )
    windows = {}
    for index, market in enumerate(markets):
        symbol, eligible_start = _verify_market(
            market, index, sources, policy["mode"],
        )
        if symbol in windows:
            raise PointInTimeUniverseError(f"duplicate market evidence for {symbol}")
        windows[symbol] = eligible_start
    if set(windows) != set(FROZEN_SYMBOLS):
        raise PointInTimeUniverseError(
            "market evidence does not cover the exact frozen V2 universe"
        )
    return {
        "evidence_sha256": digest,
        "preregistration_id": FROZEN_PREREGISTRATION_ID,
        "date_policy": policy["mode"],
        "eligible_start_by_symbol": windows,
        "market_count": len(windows),
        "rights_verified": True,
        "independent_review_accepted": True,
    }


def load_verified_point_in_time_universe_evidence() -> dict[str, Any]:
    """Load the committed evidence file; fail closed unless its digest is pinned."""
    path = Path(__file__).with_name(EVIDENCE_FILENAME)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PointInTimeUniverseError(
            "point-in-time evidence manifest is unavailable"
        ) from exc
    return verify_point_in_time_universe_evidence(
        raw, expected_sha256=EXPECTED_EVIDENCE_SHA256,
    )
