"""SQLite schema-v2 reservation objects for trusted offline settlement.

The caller owns the transaction and must already have the v1 settlement tables.
This helper does not migrate v1 data, authorize reservations, or integrate the
objects into SQLiteSettlementStore.apply_batch. Never expose its connection to
strategy agents.
"""
from __future__ import annotations

import json
import sqlite3
from decimal import Decimal, InvalidOperation


class ReservationSchemaError(RuntimeError):
    """Unsafe or inconsistent reservation schema state."""


_SCHEMA = {
    "reservations": (
        "CREATE TABLE reservations("
        "reservation_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,"
        "market_id TEXT NOT NULL REFERENCES markets(market_id),"
        "base_asset TEXT NOT NULL,quote_asset TEXT NOT NULL,"
        "authorized_quantity TEXT NOT NULL,consumed_quantity TEXT NOT NULL,"
        "created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL "
        "CHECK(expires_at > created_at),version INTEGER NOT NULL "
        "CHECK(version >= 1 AND version < 9223372036854775807),"
        "status TEXT NOT NULL CHECK(status IN "
        "('PENDING','ACTIVE','RELEASED','CANCELLED','EXPIRED')))"
    ),
    "reservation_allocations": (
        "CREATE TABLE reservation_allocations("
        "allocation_id TEXT PRIMARY KEY,"
        "batch_id TEXT NOT NULL REFERENCES batches(batch_id),"
        "fill_id TEXT NOT NULL REFERENCES fills(fill_id),"
        "reservation_id TEXT NOT NULL REFERENCES reservations(reservation_id),"
        "account_id TEXT NOT NULL,market_id TEXT NOT NULL,"
        "allocated_quantity TEXT NOT NULL,reservation_version INTEGER NOT NULL,"
        "UNIQUE(fill_id,reservation_id))"
    ),
    "reservation_outbox": (
        "CREATE TABLE reservation_outbox("
        "idempotency_key TEXT PRIMARY KEY,"
        "allocation_id TEXT NOT NULL REFERENCES reservation_allocations(allocation_id),"
        "batch_id TEXT NOT NULL REFERENCES batches(batch_id),"
        "reservation_id TEXT NOT NULL REFERENCES reservations(reservation_id),"
        "fill_id TEXT NOT NULL REFERENCES fills(fill_id),"
        "account_id TEXT NOT NULL,market_id TEXT NOT NULL,"
        "reservation_version INTEGER NOT NULL,allocated_quantity TEXT NOT NULL,"
        "payload_sha256 TEXT NOT NULL,"
        "status TEXT NOT NULL CHECK(status IN ('PENDING','ACKNOWLEDGED')),"
        "receiver_receipt TEXT)"
    ),
}


def _normalize(sql: str) -> str:
    """Normalize SQL formatting without changing quoted literals/identifiers."""
    output = []
    quote = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote is not None:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in ("'", '"', "`", "["):
            quote = "]" if char == "[" else char
            output.append(char)
        elif not char.isspace():
            output.append(char.casefold())
        index += 1
    return "".join(output)


def _verify_account_market_baseline(db: sqlite3.Connection) -> None:
    """Require explicit markers, a valid audit chain and its account genesis event."""
    try:
        markers = dict(db.execute(
            "SELECT key,value FROM main.metadata WHERE key IN "
            "('account_initialization_audit','market_registration_audit')"
        ))
        account = db.execute(
            "SELECT account_id,currency FROM main.account WHERE singleton=1"
        ).fetchone()
    except sqlite3.Error as exc:
        raise ReservationSchemaError(
            "explicit account and market audit baselines must be verified"
        ) from exc
    if markers != {
        "account_initialization_audit": "required-v1",
        "market_registration_audit": "required-v1",
    } or account is None:
        raise ReservationSchemaError(
            "explicit account and market audit baselines must be verified"
        )

    from .sqlite_settlement_store import SQLiteSettlementStore
    verifier = SQLiteSettlementStore.__new__(SQLiteSettlementStore)
    verifier.account_id, verifier.currency = account
    if not verifier._verify_chain(db):
        raise ReservationSchemaError("account and market audit baseline chain is invalid")

    try:
        events = [
            json.loads(row[0])
            for row in db.execute("SELECT event_json FROM main.audit ORDER BY seq")
        ]
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReservationSchemaError("account and market audit baseline JSON is invalid") from exc
    initial = [event for event in events if isinstance(event, dict)
               and event.get("kind") == "ACCOUNT_INITIALIZED"]
    if (
        len(initial) != 1 or not events or events[0] != initial[0]
        or initial[0].get("account_id") != account[0]
        or initial[0].get("currency") != account[1]
        or initial[0].get("market_registration_audit") != "required-v1"
    ):
        raise ReservationSchemaError(
            "account and market audit baseline genesis event is invalid"
        )
    try:
        opening_cash = Decimal(str(initial[0].get("opening_cash")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReservationSchemaError("initial audited cash is invalid") from exc
    if not opening_cash.is_finite() or opening_cash <= 0:
        raise ReservationSchemaError("initial audited cash is invalid")

def ensure_reservation_schema_v2(db: sqlite3.Connection) -> None:
    """Create/verify v2 objects inside a caller-owned transaction.

    This is intentionally not a migration function. It requires the v1 parent
    tables and refuses to run unless the caller has already begun a transaction.
    The caller must commit or roll back the encompassing transaction.
    """
    if not isinstance(db, sqlite3.Connection):
        raise ReservationSchemaError("a trusted SQLite connection is required")
    if not db.in_transaction:
        raise ReservationSchemaError("caller-owned transaction is required")

    required_parents = {"metadata", "markets", "batches", "fills"}
    present = {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    missing_parents = required_parents - present
    if missing_parents:
        raise ReservationSchemaError(
            f"base settlement schema missing: {sorted(missing_parents)}"
        )

    parent_schema = {
        "markets": (
            "CREATE TABLE markets(market_id TEXT PRIMARY KEY, "
            "base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL)"
        ),
        "batches": (
            "CREATE TABLE batches(batch_id TEXT PRIMARY KEY, "
            "request_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN "
            "('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')), "
            "created_at INTEGER NOT NULL, result_json TEXT)"
        ),
        "fills": (
            "CREATE TABLE fills(fill_id TEXT PRIMARY KEY, "
            "batch_id TEXT NOT NULL REFERENCES batches(batch_id), "
            "market_id TEXT NOT NULL REFERENCES markets(market_id), "
            "side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), "
            "quantity TEXT NOT NULL, price TEXT NOT NULL, "
            "fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL)"
        ),
    }
    for table, expected_ddl in parent_schema.items():
        row = db.execute(
            "SELECT sql FROM main.sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None or _normalize(row[0]) != _normalize(expected_ddl):
            raise ReservationSchemaError(
                f"base settlement schema definition mismatch for {table}"
            )

    if db.execute("PRAGMA foreign_keys").fetchone() != (1,):
        raise ReservationSchemaError(
            "SQLite foreign key enforcement must be enabled"
        )

    if db.execute("PRAGMA ignore_check_constraints").fetchone() != (0,):
        raise ReservationSchemaError(
            "SQLite CHECK constraint enforcement must be enabled"
        )

    targets = set(_SCHEMA)
    existing_targets = targets & present
    if existing_targets and existing_targets != targets:
        raise ReservationSchemaError(
            f"partial reservation schema rejected: {sorted(existing_targets)}"
        )

    if not existing_targets:
        # Creating reservation state on a pre-marker legacy store would let
        # callers reserve inventory whose opening account/market authority is
        # not established. Existing v2 tables may still be verified read-only;
        # only creation requires both explicit baseline markers.
        markers = dict(db.execute(
            "SELECT key,value FROM main.metadata WHERE key IN "
            "('account_initialization_audit','market_registration_audit')"
        ))
        if markers != {
            "account_initialization_audit": "required-v1",
            "market_registration_audit": "required-v1",
        }:
            raise ReservationSchemaError(
                "reservation schema creation requires an explicit account and market audit baseline"
            )
        for ddl in _SCHEMA.values():
            db.execute(ddl)

    for table, expected in _SCHEMA.items():
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if row is None or _normalize(row[0]) != _normalize(expected):
            raise ReservationSchemaError(
                f"reservation schema definition mismatch for {table}"
            )

    unexpected = db.execute(
        "SELECT type,name FROM sqlite_master "
        "WHERE (type='index' AND name NOT LIKE 'sqlite_autoindex_%' "
        "AND lower(tbl_name) IN "
        "('markets','batches','fills','reservations','reservation_allocations','reservation_outbox')) "
        "OR (type='trigger' AND lower(tbl_name) IN "
        "('markets','batches','fills','reservations','reservation_allocations','reservation_outbox')) "
        "ORDER BY type,name"
    ).fetchall()
    if unexpected:
        raise ReservationSchemaError(
            f"unapproved reservation schema objects: {unexpected}"
        )

    unexpected_temp_triggers = db.execute(
        "SELECT type,name FROM temp.sqlite_master "
        "WHERE type='trigger' "
        "AND lower(tbl_name) IN "
        "('markets','batches','fills','reservations','reservation_allocations','reservation_outbox') "
        "ORDER BY name"
    ).fetchall()
    if unexpected_temp_triggers:
        raise ReservationSchemaError(
            f"unapproved TEMP reservation triggers: {unexpected_temp_triggers}"
        )

    try:
        foreign_key_violation = db.execute(
            "PRAGMA main.foreign_key_check"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise ReservationSchemaError(
            "SQLite foreign-key integrity check failed"
        ) from exc
    if foreign_key_violation is not None:
        raise ReservationSchemaError(
            f"SQLite foreign-key violation detected: {foreign_key_violation}"
        )

    for table, expected_columns in {
        "reservations": (
            "reservation_id", "account_id", "market_id", "base_asset",
            "quote_asset", "authorized_quantity", "consumed_quantity",
            "created_at", "expires_at", "version", "status",
        ),
        "reservation_allocations": (
            "allocation_id", "batch_id", "fill_id", "reservation_id",
            "account_id", "market_id", "allocated_quantity", "reservation_version",
        ),
        "reservation_outbox": (
            "idempotency_key", "allocation_id", "batch_id", "reservation_id",
            "fill_id", "account_id", "market_id", "reservation_version",
            "allocated_quantity", "payload_sha256", "status", "receiver_receipt",
        ),
    }.items():
        actual = tuple(row[1] for row in db.execute(f"PRAGMA main.table_info({table})"))
        if actual != expected_columns:
            raise ReservationSchemaError(
                f"reservation schema columns mismatch for {table}"
            )
