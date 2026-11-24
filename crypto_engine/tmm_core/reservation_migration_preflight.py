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


def _audit_is_valid(db: sqlite3.Connection) -> tuple[bool, int]:
    previous = "0" * 64
    count = 0
    for event_json, previous_hash, event_hash in db.execute(
        "SELECT event_json,previous_hash,event_hash FROM audit ORDER BY seq"
    ):
        if previous_hash != previous:
            return False, count
        try:
            event = json.loads(event_json)
            encoded = json.dumps(
                event, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return False, count
        expected = hashlib.sha256((previous + encoded).encode("utf-8")).hexdigest()
        if event_hash != expected:
            return False, count
        previous = event_hash
        count += 1
    return True, count


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
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != _EXPECTED_TABLES:
        blockers.append("v1 table set mismatch")
    else:
        for table, columns in _EXPECTED_COLUMNS.items():
            actual = tuple(row[1] for row in db.execute(f"PRAGMA table_info({table})"))
            if actual != columns:
                blockers.append(f"v1 column contract mismatch: {table}")

    version = None
    sell_count = outbox_count = unresolved_count = audit_count = 0
    if "metadata" in tables:
        row = db.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        version = row[0] if row else None
        if version != "1":
            blockers.append("database is not schema version 1")

    if "fills" in tables:
        sell_count = db.execute(
            "SELECT COUNT(*) FROM fills WHERE side='SELL'"
        ).fetchone()[0]
        invalid_sides = db.execute(
            "SELECT COUNT(*) FROM fills WHERE side NOT IN ('BUY','SELL')"
        ).fetchone()[0]
        if invalid_sides:
            blockers.append("fill side values violate v1 contract")
        if sell_count:
            blockers.append(
                "historical SELL fills have no provable v1 reservation allocation identity"
            )

    if "outbox" in tables:
        outbox_count = db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
        if outbox_count:
            blockers.append(
                "historical outbox rows lack allocation-bound v2 identity and require reconciliation"
            )

    if "batches" in tables:
        unresolved_count = db.execute(
            "SELECT COUNT(*) FROM batches WHERE status IN "
            "('PROCESSING','RECONCILIATION_REQUIRED')"
        ).fetchone()[0]
        if unresolved_count:
            blockers.append("unresolved or processing batches require reconciliation")

    if "audit" in tables:
        audit_ok, audit_count = _audit_is_valid(db)
        if not audit_ok:
            blockers.append("audit chain verification failed")

    integrity = db.execute("PRAGMA integrity_check").fetchone()
    if integrity != ("ok",):
        blockers.append("SQLite integrity_check failed")

    fk_errors = db.execute("PRAGMA foreign_key_check").fetchall()
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
