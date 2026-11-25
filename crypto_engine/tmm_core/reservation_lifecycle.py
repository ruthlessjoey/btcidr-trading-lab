"""Transactional lifecycle for trusted offline synthetic SELL reservations.

Every mutating call requires a caller-owned BEGIN IMMEDIATE transaction. The
caller owns commit/rollback and must include any settlement work in the same
transaction. These functions provide no exchange, wallet, PAPER activation, or
LIVE trading capability. Never expose the SQLite connection to strategy agents.
"""
from __future__ import annotations

import json
import sqlite3
from decimal import Decimal, InvalidOperation

from .sqlite_settlement_store import _event_hash
from .reservation_schema_v2 import ensure_reservation_schema_v2


_MAX_SQLITE_INTEGER = 2**63 - 1


class ReservationLifecycleError(RuntimeError):
    """Invalid reservation lifecycle transition or stale state."""


def _validate_audit_schema(db: sqlite3.Connection) -> None:
    audit_ddl = db.execute(
        "SELECT sql FROM main.sqlite_master WHERE type='table' AND name='audit'"
    ).fetchone()
    expected = (
        "CREATE TABLE audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL, "
        "previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)"
    )
    if audit_ddl is None or "".join(audit_ddl[0].split()).casefold() != "".join(
        expected.split()
    ).casefold():
        raise ReservationLifecycleError("canonical settlement audit schema is required")


def _require_transaction(db: sqlite3.Connection) -> None:
    if not isinstance(db, sqlite3.Connection):
        raise ReservationLifecycleError("a trusted SQLite connection is required")
    if not db.in_transaction:
        raise ReservationLifecycleError("caller-owned BEGIN IMMEDIATE transaction is required")
    ensure_reservation_schema_v2(db)
    _validate_audit_schema(db)


def _text(value: object, field: str, limit: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReservationLifecycleError(f"{field} is required and must be at most {limit} characters")
    return value


def _integer(value: object, field: str) -> int:
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < 0 or value > _MAX_SQLITE_INTEGER):
        raise ReservationLifecycleError(
            f"{field} must be a nonnegative SQLite integer"
        )
    return value


def _version(value: object) -> int:
    if (isinstance(value, bool) or not isinstance(value, int)
            or value < 1 or value >= _MAX_SQLITE_INTEGER - 1):
        raise ReservationLifecycleError(
            "expected_version leaves room for a safe monotonic version increment"
        )
    return value


def _quantity(value: object) -> str:
    if isinstance(value, bool):
        raise ReservationLifecycleError("authorized_quantity must be a finite positive decimal")
    raw = str(value)
    if len(raw) > 128:
        raise ReservationLifecycleError("authorized_quantity exceeds supported decimal text length")
    try:
        number = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReservationLifecycleError(
            "authorized_quantity must be a finite positive decimal"
        ) from exc
    if not number.is_finite() or number <= 0:
        raise ReservationLifecycleError("authorized_quantity must be a finite positive decimal")
    parts = number.as_tuple()
    if (len(parts.digits) > 38 or parts.exponent < -18 or parts.exponent > 128
            or number.adjusted() > 38):
        raise ReservationLifecycleError("authorized_quantity exceeds supported decimal precision")
    return format(number, "f")


def _audit(db: sqlite3.Connection, event: dict[str, object]) -> None:
    _validate_audit_schema(db)
    row = db.execute(
        "SELECT event_hash FROM main.audit ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    previous = row[0] if row else "0" * 64
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
    digest = _event_hash(previous, event)
    db.execute(
        "INSERT INTO main.audit(event_json,previous_hash,event_hash) VALUES(?,?,?)",
        (encoded, previous, digest),
    )


def _reservation(db: sqlite3.Connection, reservation_id: str):
    return db.execute(
        "SELECT reservation_id,account_id,market_id,base_asset,quote_asset,"
        "authorized_quantity,consumed_quantity,created_at,expires_at,version,status "
        "FROM main.reservations WHERE reservation_id=?",
        (reservation_id,),
    ).fetchone()


def create_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    market_id: str, base_asset: str, quote_asset: str,
    authorized_quantity: object, created_at: int, expires_at: int,
) -> dict[str, object]:
    """Create a PENDING reservation; authorization is a separate explicit transition."""
    _require_transaction(db)
    reservation_id = _text(reservation_id, "reservation_id", 256)
    account_id = _text(account_id, "account_id")
    market_id = _text(market_id, "market_id", 128)
    base_asset = _text(base_asset, "base_asset", 32)
    quote_asset = _text(quote_asset, "quote_asset", 32)
    quantity = _quantity(authorized_quantity)
    created_at = _integer(created_at, "created_at")
    expires_at = _integer(expires_at, "expires_at")
    if expires_at <= created_at:
        raise ReservationLifecycleError("expires_at must be later than created_at")

    account = db.execute(
        "SELECT account_id,currency FROM main.account WHERE singleton=1"
    ).fetchone()
    if account != (account_id, quote_asset):
        raise ReservationLifecycleError("reservation account or quote asset does not match settlement account")
    market = db.execute(
        "SELECT base_asset,quote_asset FROM main.markets WHERE market_id=?",
        (market_id,),
    ).fetchone()
    if market != (base_asset, quote_asset):
        raise ReservationLifecycleError("reservation market asset identity mismatch")

    try:
        db.execute(
            "INSERT INTO main.reservations("
            "reservation_id,account_id,market_id,base_asset,quote_asset,"
            "authorized_quantity,consumed_quantity,created_at,expires_at,version,status"
            ") VALUES(?,?,?,?,?,?, '0',?,?,1,'PENDING')",
            (reservation_id, account_id, market_id, base_asset, quote_asset,
             quantity, created_at, expires_at),
        )
    except sqlite3.IntegrityError as exc:
        raise ReservationLifecycleError("reservation identity or schema constraint rejected creation") from exc

    _audit(db, {
        "kind": "RESERVATION_CREATED", "reservation_id": reservation_id,
        "account_id": account_id, "market_id": market_id,
        "base_asset": base_asset, "quote_asset": quote_asset,
        "authorized_quantity": quantity, "created_at": created_at,
        "expires_at": expires_at, "version": 1, "status": "PENDING",
    })
    return dict(zip(
        ("reservation_id","account_id","market_id","base_asset","quote_asset",
         "authorized_quantity","consumed_quantity","created_at","expires_at","version","status"),
        _reservation(db, reservation_id),
    ))


def authorize_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    expected_version: int, now: int,
) -> dict[str, object]:
    """CAS transition PENDING -> ACTIVE, only before its persisted expiry."""
    _require_transaction(db)
    reservation_id = _text(reservation_id, "reservation_id", 256)
    account_id = _text(account_id, "account_id")
    expected_version = _version(expected_version)
    now = _integer(now, "now")
    row = _reservation(db, reservation_id)
    if row is None or row[1] != account_id:
        raise ReservationLifecycleError("reservation not found for account")
    if row[10] != "PENDING":
        raise ReservationLifecycleError("only PENDING reservations can be authorized")
    if now < row[7]:
        raise ReservationLifecycleError("authorization timestamp predates reservation creation")
    if now >= row[8]:
        raise ReservationLifecycleError("expired reservation cannot be authorized")
    if row[9] != expected_version:
        raise ReservationLifecycleError("stale reservation version")
    changed = db.execute(
        "UPDATE main.reservations SET status='ACTIVE',version=version+1 "
        "WHERE reservation_id=? AND account_id=? AND status='PENDING' "
        "AND version=? AND expires_at>?",
        (reservation_id, account_id, expected_version, now),
    ).rowcount
    if changed != 1:
        raise ReservationLifecycleError("reservation authorization compare-and-set failed")
    _audit(db, {
        "kind": "RESERVATION_AUTHORIZED", "reservation_id": reservation_id,
        "account_id": account_id, "market_id": row[2],
        "previous_version": expected_version, "version": expected_version + 1,
        "timestamp": now, "status": "ACTIVE",
    })
    return dict(zip(
        ("reservation_id","account_id","market_id","base_asset","quote_asset",
         "authorized_quantity","consumed_quantity","created_at","expires_at","version","status"),
        _reservation(db, reservation_id),
    ))


def _transition(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    expected_version: int, now: int, target: str, allowed: tuple[str, ...],
    require_expired: bool = False,
) -> dict[str, object]:
    _require_transaction(db)
    reservation_id = _text(reservation_id, "reservation_id", 256)
    account_id = _text(account_id, "account_id")
    expected_version = _version(expected_version)
    now = _integer(now, "now")
    row = _reservation(db, reservation_id)
    if row is None or row[1] != account_id:
        raise ReservationLifecycleError("reservation not found for account")
    if row[10] not in allowed:
        raise ReservationLifecycleError(f"reservation status {row[10]} cannot transition to {target}")
    if row[9] != expected_version:
        raise ReservationLifecycleError("stale reservation version")
    if now < row[7]:
        raise ReservationLifecycleError("transition timestamp predates reservation creation")
    if require_expired and now < row[8]:
        raise ReservationLifecycleError("reservation has not reached expiry")
    if not require_expired and now >= row[8]:
        raise ReservationLifecycleError("expired reservation must use expiry transition")
    changed = db.execute(
        "UPDATE main.reservations SET status=?,version=version+1 "
        "WHERE reservation_id=? AND account_id=? AND status=? AND version=?",
        (target, reservation_id, account_id, row[10], expected_version),
    ).rowcount
    if changed != 1:
        raise ReservationLifecycleError("reservation transition compare-and-set failed")
    _audit(db, {
        "kind": "RESERVATION_" + target, "reservation_id": reservation_id,
        "account_id": account_id, "market_id": row[2],
        "previous_status": row[10], "status": target,
        "previous_version": expected_version, "version": expected_version + 1,
        "timestamp": now,
    })
    return dict(zip(
        ("reservation_id","account_id","market_id","base_asset","quote_asset",
         "authorized_quantity","consumed_quantity","created_at","expires_at","version","status"),
        _reservation(db, reservation_id),
    ))


def release_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    expected_version: int, now: int,
) -> dict[str, object]:
    """Release remaining quantity from an active reservation using CAS."""
    return _transition(
        db, reservation_id=reservation_id, account_id=account_id,
        expected_version=expected_version, now=now, target="RELEASED",
        allowed=("ACTIVE",),
    )


def cancel_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    expected_version: int, now: int,
) -> dict[str, object]:
    """Cancel a pending or active reservation using CAS."""
    return _transition(
        db, reservation_id=reservation_id, account_id=account_id,
        expected_version=expected_version, now=now, target="CANCELLED",
        allowed=("PENDING", "ACTIVE"),
    )


def expire_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
    expected_version: int, now: int,
) -> dict[str, object]:
    """Expire a pending or active reservation at/after its persisted expiry."""
    return _transition(
        db, reservation_id=reservation_id, account_id=account_id,
        expected_version=expected_version, now=now, target="EXPIRED",
        allowed=("PENDING", "ACTIVE"), require_expired=True,
    )


def get_reservation(
    db: sqlite3.Connection, *, reservation_id: str, account_id: str,
) -> dict[str, object] | None:
    """Read a reservation scoped to its owning account."""
    if not isinstance(db, sqlite3.Connection):
        raise ReservationLifecycleError("a trusted SQLite connection is required")
    reservation_id = _text(reservation_id, "reservation_id", 256)
    account_id = _text(account_id, "account_id")
    row = _reservation(db, reservation_id)
    if row is None or row[1] != account_id:
        return None
    return dict(zip(
        ("reservation_id","account_id","market_id","base_asset","quote_asset",
         "authorized_quantity","consumed_quantity","created_at","expires_at","version","status"),
        row,
    ))
