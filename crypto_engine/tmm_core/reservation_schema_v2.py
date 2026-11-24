"""SQLite schema-v2 reservation objects for trusted offline settlement.

The caller owns the transaction and must already have the v1 settlement tables.
This helper does not migrate v1 data, authorize reservations, or integrate the
objects into SQLiteSettlementStore.apply_batch. Never expose its connection to
strategy agents.
"""
from __future__ import annotations

import sqlite3


class ReservationSchemaError(RuntimeError):
    """Unsafe or inconsistent reservation schema state."""


_SCHEMA = {
    "reservations": (
        "CREATE TABLE reservations("
        "reservation_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,"
        "market_id TEXT NOT NULL REFERENCES markets(market_id),"
        "base_asset TEXT NOT NULL,quote_asset TEXT NOT NULL,"
        "authorized_quantity TEXT NOT NULL,consumed_quantity TEXT NOT NULL,"
        "created_at INTEGER NOT NULL,version INTEGER NOT NULL,"
        "status TEXT NOT NULL CHECK(status IN ('ACTIVE','RELEASED','CANCELLED','EXPIRED')))"
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

    required_parents = {"markets", "batches", "fills"}
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
            "request_hash TEXT NOT NULL, status TEXT NOT NULL, "
            "created_at INTEGER NOT NULL, result_json TEXT)"
        ),
        "fills": (
            "CREATE TABLE fills(fill_id TEXT PRIMARY KEY, "
            "batch_id TEXT NOT NULL REFERENCES batches(batch_id), "
            "market_id TEXT NOT NULL REFERENCES markets(market_id), "
            "side TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL, "
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
    for table, expected_columns in parent_columns.items():

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
        "AND lower(tbl_name) IN ('reservations','reservation_allocations','reservation_outbox')) "
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

    for table, expected_columns in {
        "reservations": (
            "reservation_id", "account_id", "market_id", "base_asset",
            "quote_asset", "authorized_quantity", "consumed_quantity",
            "created_at", "version", "status",
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
