"""Preflight and transactional persistence for synthetic SELL allocations.

The pure validator is not an authorization boundary. The transactional helper
reloads fills/reservations from the trusted SQLite database, validates versions
and remaining quantities, updates consumption, persists allocation/outbox rows,
and appends audit events without committing. Never accept reservation state
supplied by a strategy agent.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from decimal import Decimal, InvalidOperation, localcontext
from typing import Mapping, Sequence

from .reservation_lifecycle import (
    ReservationLifecycleError,
    _audit,
    _require_transaction,
)


class ReservationAllocationError(ValueError):
    """Invalid or inconsistent SELL reservation allocation input."""


def _quantity(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ReservationAllocationError(f"{field} must be a finite decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReservationAllocationError(
            f"{field} must be a finite decimal"
        ) from exc
    if not number.is_finite():
        raise ReservationAllocationError(f"{field} must be finite")
    parts = number.as_tuple()
    if len(parts.digits) > 38 or parts.exponent < -18 or number.adjusted() > 38:
        raise ReservationAllocationError(f"{field} exceeds supported decimal precision")
    return number


def _required_text(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReservationAllocationError(f"{key} is required")
    return value


def validate_sell_allocations(
    *,
    account_id: str,
    fills: Sequence[Mapping[str, object]],
    reservations: Sequence[Mapping[str, object]],
    allocations: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Validate exact per-fill allocations against a trusted reservation snapshot.

    The caller must invoke this while holding the authoritative settlement
    transaction and must persist the returned rows in that same transaction.
    A result from this function alone does not reserve or consume inventory.
    """
    if not isinstance(account_id, str) or not account_id.strip():
        raise ReservationAllocationError("account_id is required")
    for name, values in (("fills", fills), ("reservations", reservations),
                         ("allocations", allocations)):
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ReservationAllocationError(f"{name} must be a sequence")

    fill_by_id: dict[str, dict[str, object]] = {}
    for raw in fills:
        if not isinstance(raw, Mapping):
            raise ReservationAllocationError("each fill must be a mapping")
        fill_id = _required_text(raw, "fill_id")
        if fill_id in fill_by_id:
            raise ReservationAllocationError("fill IDs must be unique")
        side = raw.get("side")
        if side not in ("BUY", "SELL"):
            raise ReservationAllocationError("fill side must be BUY or SELL")
        market_id = _required_text(raw, "market_id")
        quantity = _quantity(raw.get("quantity"), "fill quantity")
        if quantity <= 0:
            raise ReservationAllocationError("fill quantity must be positive")
        fill_by_id[fill_id] = {
            "side": side, "market_id": market_id, "quantity": quantity
        }

    reservation_by_id: dict[str, dict[str, object]] = {}
    for raw in reservations:
        if not isinstance(raw, Mapping):
            raise ReservationAllocationError("each reservation must be a mapping")
        reservation_id = _required_text(raw, "reservation_id")
        if reservation_id in reservation_by_id:
            raise ReservationAllocationError("reservation IDs must be unique")
        owner = _required_text(raw, "account_id")
        market_id = _required_text(raw, "market_id")
        version = raw.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ReservationAllocationError("reservation version must be a positive integer")
        authorized = _quantity(raw.get("authorized_quantity"), "authorized_quantity")
        consumed = _quantity(raw.get("consumed_quantity", "0"), "consumed_quantity")
        if authorized <= 0 or consumed < 0 or consumed > authorized:
            raise ReservationAllocationError("invalid reservation quantity state")
        with localcontext() as decimal_context:
            decimal_context.prec = 80
            remaining = authorized - consumed
        reservation_by_id[reservation_id] = {
            "account_id": owner, "market_id": market_id, "version": version,
            "remaining": remaining,
        }

    normalized: list[dict[str, object]] = []
    allocation_ids: set[str] = set()
    allocated_by_fill: dict[str, Decimal] = {}
    allocated_by_reservation: dict[str, Decimal] = {}
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        for raw in allocations:
            if not isinstance(raw, Mapping):
                raise ReservationAllocationError("each allocation must be a mapping")
            allocation_id = _required_text(raw, "allocation_id")
            if allocation_id in allocation_ids:
                raise ReservationAllocationError("allocation IDs must be unique")
            allocation_ids.add(allocation_id)
            fill_id = _required_text(raw, "fill_id")
            reservation_id = _required_text(raw, "reservation_id")
            if fill_id not in fill_by_id:
                raise ReservationAllocationError("allocation references unknown fill")
            if reservation_id not in reservation_by_id:
                raise ReservationAllocationError("allocation references unknown reservation")
            fill = fill_by_id[fill_id]
            reservation = reservation_by_id[reservation_id]
            if fill["side"] != "SELL":
                raise ReservationAllocationError("BUY fills cannot consume SELL reservations")
            if reservation["account_id"] != account_id:
                raise ReservationAllocationError("cross-account reservation allocation rejected")
            if reservation["market_id"] != fill["market_id"]:
                raise ReservationAllocationError("cross-market reservation allocation rejected")
            version = raw.get("reservation_version")
            if isinstance(version, bool) or not isinstance(version, int):
                raise ReservationAllocationError("reservation_version must be an integer")
            if version != reservation["version"]:
                raise ReservationAllocationError("stale reservation version")
            quantity = _quantity(raw.get("allocated_quantity"), "allocated_quantity")
            if quantity <= 0:
                raise ReservationAllocationError("allocated_quantity must be positive")
            allocated_by_fill[fill_id] = allocated_by_fill.get(fill_id, Decimal("0")) + quantity
            allocated_by_reservation[reservation_id] = (
                allocated_by_reservation.get(reservation_id, Decimal("0")) + quantity
            )
            normalized.append({
                "allocation_id": allocation_id,
                "fill_id": fill_id,
                "reservation_id": reservation_id,
                "account_id": account_id,
                "market_id": str(fill["market_id"]),
                "allocated_quantity": format(quantity, "f"),
                "reservation_version": version,
            })

        for fill_id, fill in fill_by_id.items():
            allocated = allocated_by_fill.get(fill_id, Decimal("0"))
            if fill["side"] == "SELL" and allocated != fill["quantity"]:
                raise ReservationAllocationError(
                    "SELL allocations must equal each fill quantity exactly"
                )
            if fill["side"] == "BUY" and allocated != 0:
                raise ReservationAllocationError("BUY fills cannot have allocations")

        for reservation_id, allocated in allocated_by_reservation.items():
            if allocated > reservation_by_id[reservation_id]["remaining"]:
                raise ReservationAllocationError("reservation over-consumption rejected")

    return sorted(normalized, key=lambda row: str(row["allocation_id"]))


def consume_sell_allocations(
    db: sqlite3.Connection, *, account_id: str, batch_id: str,
    allocations: Sequence[Mapping[str, object]], timestamp: int,
) -> list[dict[str, object]]:
    """Consume ACTIVE reservations for every SELL fill in a PROCESSING batch.

    Call only after the batch and its fills have been inserted, inside the same
    caller-owned BEGIN IMMEDIATE transaction that will commit balances/fills.
    This function never commits. Any exception requires the caller to roll back
    the complete settlement transaction.
    """
    try:
        _require_transaction(db)
    except ReservationLifecycleError as exc:
        raise ReservationAllocationError(str(exc)) from exc

    if not isinstance(account_id, str) or not account_id.strip():
        raise ReservationAllocationError("account_id is required")
    if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 256:
        raise ReservationAllocationError("batch_id is required")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or not 0 <= timestamp <= 2**63 - 1:
        raise ReservationAllocationError("timestamp must be a nonnegative SQLite integer")
    if not isinstance(allocations, Sequence) or isinstance(allocations, (str, bytes)):
        raise ReservationAllocationError("allocations must be a sequence")
    if len(allocations) > 1000:
        raise ReservationAllocationError("allocation count exceeds the 1000-row limit")

    batch = db.execute(
        "SELECT status,created_at FROM main.batches WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if batch is None or batch[0] != "PROCESSING":
        raise ReservationAllocationError("allocations require an existing PROCESSING batch")
    if batch[1] != timestamp:
        raise ReservationAllocationError("allocation timestamp must match the batch timestamp")

    raw_fills = db.execute(
        "SELECT fill_id,market_id,side,quantity,timestamp FROM main.fills "
        "WHERE batch_id=? ORDER BY fill_id LIMIT 10001",
        (batch_id,),
    ).fetchall()
    if any(row[4] != timestamp for row in raw_fills):
        raise ReservationAllocationError("allocation timestamp must match every fill timestamp")
    if len(raw_fills) > 10000:
        raise ReservationAllocationError("batch fill count exceeds the 10000-row reservation limit")
    fills = [
        {"fill_id": row[0], "market_id": row[1], "side": row[2], "quantity": row[3]}
        for row in raw_fills
    ]
    sell_fills = [fill for fill in fills if fill["side"] == "SELL"]
    if not sell_fills and not allocations:
        return []

    reservation_ids: set[str] = set()
    for raw in allocations:
        if not isinstance(raw, Mapping):
            raise ReservationAllocationError("each allocation must be a mapping")
        allocation_id = _required_text(raw, "allocation_id")
        fill_id = _required_text(raw, "fill_id")
        reservation_id = _required_text(raw, "reservation_id")
        if len(allocation_id) > 256 or len(fill_id) > 256 or len(reservation_id) > 256:
            raise ReservationAllocationError("allocation identifiers exceed the 256-character limit")
        if len(str(raw.get("allocated_quantity"))) > 128:
            raise ReservationAllocationError("allocated_quantity text exceeds the 128-character limit")
        reservation_ids.add(reservation_id)
    if len(reservation_ids) > 1000:
        raise ReservationAllocationError("reservation count exceeds the 1000-row limit")

    reservations = []
    reservation_rows: dict[str, tuple] = {}
    for reservation_id in sorted(reservation_ids):
        row = db.execute(
            "SELECT reservation_id,account_id,market_id,authorized_quantity,"
            "consumed_quantity,version,status,created_at,expires_at "
            "FROM main.reservations WHERE reservation_id=?",
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise ReservationAllocationError("allocation references unknown reservation")
        if row[1] != account_id:
            raise ReservationAllocationError("cross-account reservation allocation rejected")
        if row[6] != "ACTIVE":
            raise ReservationAllocationError("reservation must be ACTIVE before allocation")
        if timestamp < row[7]:
            raise ReservationAllocationError("allocation timestamp predates reservation creation")
        if timestamp >= row[8]:
            raise ReservationAllocationError("expired reservation cannot fund a SELL fill")
        reservation_rows[reservation_id] = row
        reservations.append({
            "reservation_id": row[0], "account_id": row[1], "market_id": row[2],
            "authorized_quantity": row[3], "consumed_quantity": row[4],
            "version": row[5],
        })

    normalized = validate_sell_allocations(
        account_id=account_id, fills=fills,
        reservations=reservations, allocations=allocations,
    )
    allocated_by_reservation: dict[str, Decimal] = {}
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        for item in normalized:
            reservation_id = str(item["reservation_id"])
            amount = Decimal(str(item["allocated_quantity"]))
            allocated_by_reservation[reservation_id] = (
                allocated_by_reservation.get(reservation_id, Decimal("0")) + amount
            )

        for reservation_id, amount in sorted(allocated_by_reservation.items()):
            row = reservation_rows[reservation_id]
            if row[5] >= 2**63 - 2:
                raise ReservationAllocationError("reservation version cannot be incremented safely")
            old_consumed = Decimal(str(row[4]))
            new_consumed = old_consumed + amount
            if new_consumed > Decimal(str(row[3])):
                raise ReservationAllocationError("reservation over-consumption rejected")
            changed = db.execute(
                "UPDATE main.reservations SET consumed_quantity=?,version=version+1 "
                "WHERE reservation_id=? AND account_id=? AND market_id=? "
                "AND status='ACTIVE' AND version=? AND consumed_quantity=? AND expires_at>?",
                (format(new_consumed, "f"), reservation_id, account_id,
                 row[2], row[5], row[4], timestamp),
            ).rowcount
            if changed != 1:
                raise ReservationAllocationError("reservation compare-and-set failed")
            _audit(db, {
                "kind": "RESERVATION_QUANTITY_CONSUMED",
                "reservation_id": reservation_id, "account_id": account_id,
                "market_id": row[2], "previous_consumed_quantity": format(old_consumed, "f"),
                "consumed_quantity": format(new_consumed, "f"),
                "allocated_quantity": format(amount, "f"),
                "previous_version": row[5], "version": row[5] + 1,
                "batch_id": batch_id, "timestamp": timestamp,
            })

        for item in normalized:
            allocation_id = str(item["allocation_id"])
            idempotency_key = "reservation-allocation:" + allocation_id
            payload = {
                "schema": 1, "idempotency_key": idempotency_key,
                "allocation_id": allocation_id, "batch_id": batch_id,
                "fill_id": item["fill_id"], "reservation_id": item["reservation_id"],
                "account_id": account_id, "market_id": item["market_id"],
                "reservation_version": item["reservation_version"],
                "allocated_quantity": item["allocated_quantity"],
            }
            payload_json = json.dumps(
                payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
            payload_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            db.execute(
                "INSERT INTO main.reservation_allocations("
                "allocation_id,batch_id,fill_id,reservation_id,account_id,market_id,"
                "allocated_quantity,reservation_version) VALUES(?,?,?,?,?,?,?,?)",
                (allocation_id, batch_id, item["fill_id"], item["reservation_id"],
                 account_id, item["market_id"], item["allocated_quantity"],
                 item["reservation_version"]),
            )
            db.execute(
                "INSERT INTO main.reservation_outbox("
                "idempotency_key,allocation_id,batch_id,reservation_id,fill_id,"
                "account_id,market_id,reservation_version,allocated_quantity,"
                "payload_sha256,status,receiver_receipt) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,'PENDING',NULL)",
                (idempotency_key, allocation_id, batch_id, item["reservation_id"],
                 item["fill_id"], account_id, item["market_id"],
                 item["reservation_version"], item["allocated_quantity"], payload_sha256),
            )

    return [
        {**item, "idempotency_key": "reservation-allocation:" + str(item["allocation_id"])}
        for item in normalized
    ]
