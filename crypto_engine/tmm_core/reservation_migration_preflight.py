"""Read-only eligibility gate for a future SQLite v1 -> reservation v2 migration.

This module never mutates a database. Callers must open the database read-only,
enable PRAGMA query_only, and begin a consistent read transaction before calling.
A positive result is only a preflight decision; it is not a migration.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Tuple


# Must match sqlite_settlement_store.py. Oversized history blocks migration;
# preflight never truncates, skips, or rewrites audit evidence.
_AUDIT_MAX_EVENT_BYTES = 64 * 1024
_AUDIT_MAX_TOTAL_BYTES = 256 * 1024 * 1024
_AUDIT_MAX_EVENTS = 1_000_000


@dataclass(frozen=True)
class MigrationPreflight:
    eligible: bool
    blockers: Tuple[str, ...]
    schema_version: str
    sell_fill_count: int
    outbox_row_count: int
    unresolved_batch_count: int
    audit_event_count: int


_EXPECTED_COLUMNS = {
    "metadata": ("key", "value"),
    "account": ("singleton", "account_id", "currency", "cash"),
    "markets": ("market_id", "base_asset", "quote_asset"),
    "holdings": ("market_id", "quantity"),
    "batches": ("batch_id", "request_hash", "status", "created_at", "result_json"),
    "fills": ("fill_id", "batch_id", "market_id", "side", "quantity", "price", "fee_quote", "timestamp"),
    "audit": ("seq", "event_json", "previous_hash", "event_hash"),
    "outbox": ("idempotency_key", "batch_id", "market_id", "authorized_quantity", "filled_quantity", "status", "receiver_receipt"),
}
_EXPECTED_TABLES = set(_EXPECTED_COLUMNS)
_EXPECTED_SQL = {
    "metadata": "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
    "account": "CREATE TABLE account(singleton INTEGER PRIMARY KEY CHECK(singleton=1), account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL)",
    "markets": "CREATE TABLE markets(market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL)",
    "holdings": "CREATE TABLE holdings(market_id TEXT PRIMARY KEY REFERENCES markets(market_id), quantity TEXT NOT NULL)",
    "batches": "CREATE TABLE batches(batch_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')), created_at INTEGER NOT NULL, result_json TEXT)",
    "fills": "CREATE TABLE fills(fill_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL, price TEXT NOT NULL, fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL)",
    "audit": "CREATE TABLE audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)",
    "outbox": "CREATE TABLE outbox(idempotency_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), authorized_quantity TEXT NOT NULL, filled_quantity TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','ACKNOWLEDGED')), receiver_receipt TEXT)",
}


def _normalize_sql(value: str) -> str:
    """Normalize SQL formatting without changing quoted literals or identifiers."""
    output = []
    quote = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote is not None:
            output.append(char)
            if char == quote:
                if index + 1 < len(value) and value[index + 1] == quote:
                    output.append(value[index + 1])
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


def _audit_is_valid(db: sqlite3.Connection) -> tuple[bool, int]:
    try:
        count, total_bytes, max_bytes = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(length(CAST(event_json AS BLOB))),0),"
            "COALESCE(MAX(length(CAST(event_json AS BLOB))),0) FROM main.audit"
        ).fetchone()
    except sqlite3.DatabaseError:
        return False, 0
    if (count > _AUDIT_MAX_EVENTS or total_bytes > _AUDIT_MAX_TOTAL_BYTES
            or max_bytes > _AUDIT_MAX_EVENT_BYTES):
        return False, count
    previous = "0" * 64
    verified_count = 0
    for event_json, previous_hash, event_hash in db.execute(
        "SELECT event_json,previous_hash,event_hash FROM main.audit ORDER BY seq"
    ):
        if previous_hash != previous:
            return False, verified_count
        try:
            event = json.loads(event_json)
            if not isinstance(event, dict):
                return False, verified_count
            encoded = json.dumps(
                event, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            if encoded != event_json:
                return False, verified_count
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            # Deeply nested JSON can exceed Python's parser/encoder recursion limit.
            # Treat it as invalid audit evidence rather than leaking an exception.
            return False, verified_count
        expected = hashlib.sha256((previous + encoded).encode("utf-8")).hexdigest()
        if event_hash != expected:
            return False, verified_count
        previous = event_hash
        verified_count += 1
    return True, verified_count


def inspect_v1_migration_eligibility(
    db: sqlite3.Connection,
) -> MigrationPreflight:
    """Inspect a consistent read-only v1 snapshot and report migration blockers.

    This deliberately rejects any historical SELL fill or outbox row: v1 does
    not retain durable reservation/fill allocation identity, so inventing it
    during migration would fabricate authorization evidence. It also rejects
    unresolved batches, schema drift, integrity/FK failures and broken audit
    chains. No SQL writes or schema changes are performed.
    """
    if not isinstance(db, sqlite3.Connection):
        raise TypeError("a SQLite connection is required")
    if not db.in_transaction:
        raise ValueError("caller must begin a consistent read transaction")
    if db.execute("PRAGMA query_only").fetchone() != (1,):
        raise ValueError("connection must have PRAGMA query_only=ON")

    blockers: list[str] = []
    tables = {
        row[0] for row in db.execute(
            "SELECT name FROM main.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != _EXPECTED_TABLES:
        blockers.append("v1 table set mismatch")

    # Never issue data queries against a table whose required columns are absent.
    # Schema drift is a deterministic blocker, not an uncontrolled SQL exception.
    usable_tables = set()
    for table in sorted(tables & _EXPECTED_TABLES):
        columns = _EXPECTED_COLUMNS[table]
        actual = tuple(row[1] for row in db.execute(f"PRAGMA main.table_info({table})"))
        if actual != columns:
            blockers.append(f"v1 column contract mismatch: {table}")
            continue
        usable_tables.add(table)
        ddl_row = db.execute(
            "SELECT sql FROM main.sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if ddl_row is None or ddl_row[0] is None or _normalize_sql(ddl_row[0]) != _normalize_sql(_EXPECTED_SQL[table]):
            blockers.append(f"v1 schema definition mismatch: {table}")

    if tables == _EXPECTED_TABLES:
        unexpected_objects = db.execute(
            "SELECT type,name FROM main.sqlite_master "
            "WHERE type IN ('index','trigger','view') "
            "AND name NOT LIKE 'sqlite_autoindex_%' ORDER BY type,name"
        ).fetchall()
        if unexpected_objects:
            blockers.append("unapproved indexes, triggers, or views are present")

    version = None
    sell_count = outbox_count = unresolved_count = audit_count = 0
    if "metadata" in usable_tables:
        row = db.execute(
            "SELECT value FROM main.metadata WHERE key='schema_version'"
        ).fetchone()
        version = row[0] if row else None
        if version != "1":
            blockers.append("database is not schema version 1")

    if "fills" in usable_tables:
        sell_count = db.execute(
            "SELECT COUNT(*) FROM main.fills WHERE side='SELL'"
        ).fetchone()[0]
        invalid_sides = db.execute(
            "SELECT COUNT(*) FROM main.fills WHERE side NOT IN ('BUY','SELL')"
        ).fetchone()[0]
        if invalid_sides:
            blockers.append("fill side values violate v1 contract")
        if sell_count:
            blockers.append(
                "historical SELL fills have no provable v1 reservation allocation identity"
            )

    if "outbox" in usable_tables:
        outbox_count = db.execute("SELECT COUNT(*) FROM main.outbox").fetchone()[0]
        if outbox_count:
            blockers.append(
                "historical outbox rows lack allocation-bound v2 identity and require reconciliation"
            )

    if "batches" in usable_tables:
        unresolved_count = db.execute(
            "SELECT COUNT(*) FROM main.batches WHERE status IN "
            "('PROCESSING','RECONCILIATION_REQUIRED')"
        ).fetchone()[0]
        if unresolved_count:
            blockers.append("unresolved or processing batches require reconciliation")

    if "audit" in usable_tables:
        audit_ok, audit_count = _audit_is_valid(db)
        if not audit_ok:
            blockers.append("audit chain verification failed")

    # Malformed database metadata can make SQLite's PRAGMA checks raise
    # DatabaseError (for example, a foreign key referencing a missing table).
    # Treat inability to complete either check as a deterministic blocker.
    try:
        integrity = db.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError:
        blockers.append("SQLite integrity_check could not be completed")
    else:
        if integrity != ("ok",):
            blockers.append("SQLite integrity_check failed")

    try:
        fk_errors = db.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.DatabaseError:
        blockers.append("SQLite foreign_key_check could not be completed")
    else:
        if fk_errors:
            blockers.append("SQLite foreign_key_check failed")

    return MigrationPreflight(
        eligible=not blockers,
        blockers=tuple(blockers),
        schema_version=str(version) if version is not None else "",
        sell_fill_count=sell_count,
        outbox_row_count=outbox_count,
        unresolved_batch_count=unresolved_count,
        audit_event_count=audit_count,
    )
