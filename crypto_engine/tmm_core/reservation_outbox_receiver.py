"""Offline idempotent receiver contract for reservation outbox delivery.

This module provides a local SQLite inbox and retry-safe delivery coordinator.
It performs no network access. A future remote adapter must preserve the same
idempotency and receipt contract and be separately reviewed before use.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping


class ReservationInboxError(RuntimeError):
    """Invalid reservation outbox payload, inbox state, or receipt."""


_INBOX_DDL = (
    "CREATE TABLE reservation_inbox("
    "idempotency_key TEXT PRIMARY KEY,"
    "payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),"
    "payload_json TEXT NOT NULL,"
    "receipt TEXT NOT NULL UNIQUE)"
)
_PAYLOAD_FIELDS = {
    "schema", "idempotency_key", "allocation_id", "batch_id", "fill_id",
    "reservation_id", "account_id", "market_id", "reservation_version",
    "allocated_quantity",
}


def _canonical_payload(payload: Mapping[str, object]) -> tuple[str, str, str]:
    if not isinstance(payload, Mapping) or set(payload) != _PAYLOAD_FIELDS:
        raise ReservationInboxError("reservation outbox payload fields do not match schema v1")
    if payload.get("schema") != 1 or isinstance(payload.get("schema"), bool):
        raise ReservationInboxError("unsupported reservation outbox payload schema")
    text_fields = (
        "idempotency_key", "allocation_id", "batch_id", "fill_id",
        "reservation_id", "account_id", "market_id",
    )
    for field in text_fields:
        value = payload.get(field)
        limit = 280 if field == "idempotency_key" else 256
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ReservationInboxError(f"{field} must be nonempty and bounded")
    if payload["idempotency_key"] != "reservation-allocation:" + payload["allocation_id"]:
        raise ReservationInboxError("reservation outbox idempotency key does not match allocation ID")
    version = payload.get("reservation_version")
    if isinstance(version, bool) or not isinstance(version, int) or not 1 <= version < 2**63 - 2:
        raise ReservationInboxError("reservation_version is outside the safe SQLite integer range")
    quantity_text = payload.get("allocated_quantity")
    if not isinstance(quantity_text, str) or not quantity_text or len(quantity_text) > 128:
        raise ReservationInboxError("allocated_quantity must be a bounded decimal string")
    try:
        quantity = Decimal(quantity_text)
    except (InvalidOperation, ValueError) as exc:
        raise ReservationInboxError("allocated_quantity must be a finite positive decimal") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise ReservationInboxError("allocated_quantity must be a canonical finite positive decimal")
    parts = quantity.as_tuple()
    if len(parts.digits) > 38 or parts.exponent < -18 or parts.exponent > 128 or quantity.adjusted() > 38:
        raise ReservationInboxError("allocated_quantity exceeds supported decimal precision")
    if format(quantity, "f") != quantity_text:
        raise ReservationInboxError("allocated_quantity must be a canonical finite positive decimal")

    canonical = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    key = str(payload["idempotency_key"])
    receipt = hashlib.sha256(
        b"tmm-reservation-inbox-v1\0" + key.encode("utf-8")
        + b"\0" + digest.encode("ascii")
    ).hexdigest()
    return canonical, digest, receipt


def ensure_reservation_inbox_schema(db: sqlite3.Connection) -> None:
    """Create or verify the receiver inbox inside a caller-owned transaction."""
    if not isinstance(db, sqlite3.Connection) or not db.in_transaction:
        raise ReservationInboxError("caller-owned SQLite transaction is required")
    db.execute(
        "CREATE TABLE IF NOT EXISTS reservation_inbox("
        "idempotency_key TEXT PRIMARY KEY,"
        "payload_sha256 TEXT NOT NULL CHECK(length(payload_sha256)=64),"
        "payload_json TEXT NOT NULL,"
        "receipt TEXT NOT NULL UNIQUE)"
    )
    row = db.execute(
        "SELECT sql FROM main.sqlite_master WHERE type='table' AND name='reservation_inbox'"
    ).fetchone()
    if row is None or "".join(row[0].split()).casefold() != "".join(_INBOX_DDL.split()).casefold():
        raise ReservationInboxError("reservation inbox schema definition mismatch")
    unexpected = db.execute(
        "SELECT type,name FROM main.sqlite_master WHERE "
        "((type='index' AND name NOT LIKE 'sqlite_autoindex_%') OR type='trigger') "
        "AND lower(tbl_name)='reservation_inbox' ORDER BY type,name"
    ).fetchall()
    if unexpected:
        raise ReservationInboxError(f"unapproved reservation inbox schema objects: {unexpected}")

    unexpected_temp_triggers = db.execute(
        "SELECT type,name,tbl_name FROM temp.sqlite_master "
        "WHERE type='trigger' AND lower(tbl_name)='reservation_inbox' "
        "ORDER BY name"
    ).fetchall()
    if unexpected_temp_triggers:
        raise ReservationInboxError(
            f"unapproved TEMP reservation inbox triggers: {unexpected_temp_triggers}"
        )


def accept_reservation_outbox(
    db: sqlite3.Connection, payload: Mapping[str, object],
) -> str:
    """Record or replay an outbox payload; caller owns BEGIN IMMEDIATE and commit."""
    if not isinstance(db, sqlite3.Connection) or not db.in_transaction:
        raise ReservationInboxError("caller-owned BEGIN IMMEDIATE transaction is required")
    ensure_reservation_inbox_schema(db)
    canonical, digest, receipt = _canonical_payload(payload)
    key = str(payload["idempotency_key"])
    existing = db.execute(
        "SELECT payload_sha256,payload_json,receipt FROM main.reservation_inbox "
        "WHERE idempotency_key=?", (key,)
    ).fetchone()
    if existing is not None:
        old_digest, old_payload, old_receipt = existing
        if old_digest != digest or old_payload != canonical:
            raise ReservationInboxError("idempotency key reused with different reservation payload")
        if old_receipt != receipt:
            raise ReservationInboxError("stored reservation inbox receipt mismatch")
        return receipt
    try:
        db.execute(
            "INSERT INTO main.reservation_inbox("
            "idempotency_key,payload_sha256,payload_json,receipt) VALUES(?,?,?,?)",
            (key, digest, canonical, receipt),
        )
    except sqlite3.IntegrityError as exc:
        raise ReservationInboxError("reservation inbox uniqueness constraint rejected payload") from exc
    return receipt


def deliver_pending_reservation_outbox(
    store: object, receiver: Callable[[Mapping[str, object]], str], *, limit: int = 100,
) -> list[str]:
    """Deliver pending rows to an injected trusted receiver and acknowledge receipts.

    If receiver acceptance commits but the response is lost, the row stays pending.
    Retrying the same idempotency key returns the receiver's original receipt.
    No network transport is implemented here.
    """
    if not callable(receiver):
        raise ReservationInboxError("a trusted receiver callback is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ReservationInboxError("limit must be in [1, 1000]")
    pending = store.pending_reservation_outbox(limit=limit)
    acknowledged = []
    for row in pending:
        payload = {
            "schema": 1,
            "idempotency_key": row["idempotency_key"],
            "allocation_id": row["allocation_id"],
            "batch_id": row["batch_id"],
            "fill_id": row["fill_id"],
            "reservation_id": row["reservation_id"],
            "account_id": row["account_id"],
            "market_id": row["market_id"],
            "reservation_version": row["reservation_version"],
            "allocated_quantity": row["allocated_quantity"],
        }
        _, digest, expected_receipt = _canonical_payload(payload)
        if digest != row["payload_sha256"]:
            raise ReservationInboxError("stored reservation outbox payload hash mismatch")
        receipt = receiver(payload)
        if not isinstance(receipt, str) or receipt != expected_receipt:
            raise ReservationInboxError("receiver returned a receipt not bound to this payload")
        store.acknowledge_reservation_outbox(
            row["idempotency_key"], receiver_receipt=receipt,
            expected_payload_sha256=row["payload_sha256"],
        )
        acknowledged.append(row["idempotency_key"])
    return acknowledged
