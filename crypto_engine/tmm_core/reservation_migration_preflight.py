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
from decimal import Decimal, InvalidOperation
from typing import Tuple

from .reservation_schema_v2 import _SCHEMA as _CURRENT_V2_SCHEMA


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
    schema_class: str


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


_RESERVATION_TABLES = {'reservations', 'reservation_allocations', 'reservation_outbox'}
_EARLIER_V2_SCHEMA = {
    'reservations': (
        'CREATE TABLE reservations('
        'reservation_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,'
        'market_id TEXT NOT NULL REFERENCES markets(market_id),'
        'base_asset TEXT NOT NULL,quote_asset TEXT NOT NULL,'
        'authorized_quantity TEXT NOT NULL,consumed_quantity TEXT NOT NULL,'
        'created_at INTEGER NOT NULL,version INTEGER NOT NULL,'
        'status TEXT NOT NULL CHECK(status IN (\'ACTIVE\',\'RELEASED\',\'CANCELLED\',\'EXPIRED\')))'
    ),
    'reservation_allocations': (
        'CREATE TABLE reservation_allocations('
        'allocation_id TEXT PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES batches(batch_id),'
        'fill_id TEXT NOT NULL REFERENCES fills(fill_id),'
        'reservation_id TEXT NOT NULL REFERENCES reservations(reservation_id),'
        'account_id TEXT NOT NULL,market_id TEXT NOT NULL,'
        'allocated_quantity TEXT NOT NULL,reservation_version INTEGER NOT NULL,'
        'UNIQUE(fill_id,reservation_id))'
    ),
    'reservation_outbox': (
        'CREATE TABLE reservation_outbox('
        'idempotency_key TEXT PRIMARY KEY,'
        'allocation_id TEXT NOT NULL REFERENCES reservation_allocations(allocation_id),'
        'batch_id TEXT NOT NULL REFERENCES batches(batch_id),'
        'reservation_id TEXT NOT NULL REFERENCES reservations(reservation_id),'
        'fill_id TEXT NOT NULL REFERENCES fills(fill_id),'
        'account_id TEXT NOT NULL,market_id TEXT NOT NULL,'
        'reservation_version INTEGER NOT NULL,allocated_quantity TEXT NOT NULL,'
        'payload_sha256 TEXT NOT NULL,'
        'status TEXT NOT NULL CHECK(status IN (\'PENDING\',\'ACKNOWLEDGED\')),'
        'receiver_receipt TEXT)'
    ),
}
_CURRENT_V2_COLUMNS = {
    'reservations': ('reservation_id','account_id','market_id','base_asset','quote_asset','authorized_quantity','consumed_quantity','created_at','expires_at','version','status'),
    'reservation_allocations': ('allocation_id','batch_id','fill_id','reservation_id','account_id','market_id','allocated_quantity','reservation_version'),
    'reservation_outbox': ('idempotency_key','allocation_id','batch_id','reservation_id','fill_id','account_id','market_id','reservation_version','allocated_quantity','payload_sha256','status','receiver_receipt'),
}
_EARLIER_V2_COLUMNS = {
    'reservations': ('reservation_id','account_id','market_id','base_asset','quote_asset','authorized_quantity','consumed_quantity','created_at','version','status'),
    'reservation_allocations': _CURRENT_V2_COLUMNS['reservation_allocations'],
    'reservation_outbox': _CURRENT_V2_COLUMNS['reservation_outbox'],
}

def _matches_schema(db, tables, expected_tables, expected_sql, expected_columns):
    if tables != expected_tables:
        return False
    for table, expected in expected_sql.items():
        row = db.execute('SELECT sql FROM main.sqlite_master WHERE type=\'table\' AND name=?', (table,)).fetchone()
        if row is None or row[0] is None or _normalize_sql(row[0]) != _normalize_sql(expected):
            return False
        actual = tuple(item[1] for item in db.execute(f'PRAGMA main.table_info({table})'))
        if actual != expected_columns[table]:
            return False
    unexpected = db.execute(
        'SELECT type,name FROM main.sqlite_master WHERE type IN (\'index\',\'trigger\',\'view\') '
        'AND name NOT LIKE \'sqlite_autoindex_%\' ORDER BY type,name'
    ).fetchall()
    if unexpected:
        return False
    target_names = (
        'metadata','account','markets','holdings','batches','fills','audit','outbox',
        'reservations','reservation_allocations','reservation_outbox',
    )
    placeholders = ','.join('?' for _ in target_names)
    temp_objects = db.execute(
        'SELECT type,name,tbl_name FROM temp.sqlite_master '
        f'WHERE lower(name) IN ({placeholders}) OR lower(tbl_name) IN ({placeholders})',
        target_names + target_names,
    ).fetchall()
    return not temp_objects

def classify_reservation_schema(db: sqlite3.Connection) -> str:
    '''Classify a consistent snapshot without creating or changing schema objects.'''
    if not isinstance(db, sqlite3.Connection) or not db.in_transaction:
        raise ValueError('caller must begin a consistent read transaction')
    if db.execute('PRAGMA query_only').fetchone() != (1,):
        raise ValueError('connection must have PRAGMA query_only=ON')
    tables = {row[0] for row in db.execute(
        'SELECT name FROM main.sqlite_master WHERE type=\'table\' AND name NOT LIKE \'sqlite_%\''
    )}
    if _matches_schema(db, tables, _EXPECTED_TABLES, _EXPECTED_SQL, _EXPECTED_COLUMNS):
        return 'V1_EXACT'
    present = tables & _RESERVATION_TABLES
    if present and present != _RESERVATION_TABLES:
        return 'PARTIAL_V2'
    if present == _RESERVATION_TABLES:
        expected_tables = _EXPECTED_TABLES | _RESERVATION_TABLES
        if _matches_schema(db, tables, expected_tables, {**_EXPECTED_SQL, **_CURRENT_V2_SCHEMA}, {**_EXPECTED_COLUMNS, **_CURRENT_V2_COLUMNS}):
            return 'V2_CURRENT_EXACT'
        if _matches_schema(db, tables, expected_tables, {**_EXPECTED_SQL, **_EARLIER_V2_SCHEMA}, {**_EXPECTED_COLUMNS, **_EARLIER_V2_COLUMNS}):
            return 'V2_EARLIER'
    return 'MALFORMED_OR_UNKNOWN'



def _accounting_state_is_consistent(db: sqlite3.Connection) -> bool:
    """Reconcile BUY-only v1 fills, audit events, holdings and ending cash."""
    account = db.execute(
        "SELECT account_id,cash FROM main.account WHERE singleton=1"
    ).fetchone()
    if account is None:
        return False
    account_id, cash_text = account
    try:
        ending_cash = Decimal(str(cash_text))
        if not account_id or not ending_cash.is_finite() or ending_cash < 0:
            return False
        markets = {row[0] for row in db.execute("SELECT market_id FROM main.markets")}
        fills = db.execute(
            "SELECT fill_id,batch_id,market_id,side,quantity,price,fee_quote,timestamp "
            "FROM main.fills ORDER BY rowid"
        ).fetchall()
        audit_rows = db.execute("SELECT event_json FROM main.audit ORDER BY seq").fetchall()
        if len(audit_rows) != len(fills):
            return False
        totals = {}
        expected_cash = None
        for fill, audit_row in zip(fills, audit_rows):
            fill_id,batch_id,market_id,side,quantity_text,price_text,fee_text,timestamp = fill
            if (not fill_id or market_id not in markets or side != "BUY"
                    or isinstance(timestamp,bool) or not isinstance(timestamp,int) or timestamp < 0):
                return False
            quantity,price,fee = Decimal(str(quantity_text)),Decimal(str(price_text)),Decimal(str(fee_text))
            if (not quantity.is_finite() or not price.is_finite() or not fee.is_finite()
                    or quantity <= 0 or price <= 0 or fee < 0):
                return False
            event = json.loads(audit_row[0])
            expected_keys = {
                "kind","account_id","batch_id","fill_id","market_id","side",
                "quantity","price","fee_quote","cash_after","holding_after","timestamp",
            }
            if not isinstance(event,dict) or set(event) != expected_keys:
                return False
            if (event["kind"] != "SYNTHETIC_FILL" or event["account_id"] != account_id
                    or event["batch_id"] != batch_id or event["fill_id"] != fill_id
                    or event["market_id"] != market_id or event["side"] != side
                    or event["quantity"] != quantity_text or event["price"] != price_text
                    or event["fee_quote"] != fee_text or event["timestamp"] != timestamp):
                return False
            totals[market_id] = totals.get(market_id,Decimal("0")) + quantity
            event_holding = Decimal(str(event["holding_after"]))
            event_cash = Decimal(str(event["cash_after"]))
            if (not event_holding.is_finite() or not event_cash.is_finite()
                    or event_cash < 0 or event_holding != totals[market_id]):
                return False
            debit = quantity * price + fee
            if expected_cash is None:
                expected_cash = event_cash + debit
            else:
                expected_cash -= debit
                if expected_cash != event_cash:
                    return False
            expected_cash = event_cash
        holdings = {}
        for market_id, quantity_text in db.execute(
            "SELECT market_id,quantity FROM main.holdings"
        ):
            quantity = Decimal(str(quantity_text))
            if not quantity.is_finite() or quantity < 0:
                return False
            holdings[market_id] = quantity
        for market_id in set(totals) | set(holdings):
            if totals.get(market_id,Decimal("0")) != holdings.get(market_id,Decimal("0")):
                return False
        return expected_cash is None or expected_cash == ending_cash
    except (InvalidOperation, TypeError, ValueError, OverflowError, json.JSONDecodeError, RecursionError):
        return False



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
    try:
        cursor = db.execute(
            "SELECT event_json,previous_hash,event_hash FROM main.audit ORDER BY seq"
        )
        while True:
            try:
                row = cursor.fetchone()
            except (sqlite3.DatabaseError, UnicodeError):
                # SQLite TEXT decoding can fail before Python receives the row
                # when an attacker stores invalid UTF-8 bytes in event_json.
                return False, verified_count
            if row is None:
                break
            event_json, previous_hash, event_hash = row
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
            except (TypeError, ValueError, json.JSONDecodeError, RecursionError, UnicodeError):
                # Malformed or deeply nested JSON is invalid audit evidence.
                return False, verified_count
            expected = hashlib.sha256((previous + encoded).encode("utf-8")).hexdigest()
            if event_hash != expected:
                return False, verified_count
            previous = event_hash
            verified_count += 1
    except (sqlite3.DatabaseError, UnicodeError):
        return False, verified_count
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
    schema_class = classify_reservation_schema(db)
    if schema_class != 'V1_EXACT':
        blockers.append(f'source schema class {schema_class} is not an exact v1 migration source')
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
            "SELECT COUNT(*) FROM main.batches WHERE status!='COMPLETE'"
        ).fetchone()[0]
        if unresolved_count:
            blockers.append("unresolved or processing batches require reconciliation")

    if "audit" in usable_tables:
        audit_ok, audit_count = _audit_is_valid(db)
        if not audit_ok:
            blockers.append("audit chain verification failed")
        elif "account" in usable_tables and "fills" in usable_tables and "holdings" in usable_tables:
            if not _accounting_state_is_consistent(db):
                blockers.append("accounting state does not reconcile with BUY fills and audit events")

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
        schema_class=schema_class,
    )
