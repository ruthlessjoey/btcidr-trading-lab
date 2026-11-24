"""Atomic SQLite accounting primitives for offline synthetic settlement.

Trusted composition-root code only. No network, broker, account, wallet, PAPER or LIVE
capability is provided. All balance, fill, batch, audit and outbox mutations occur in
one SQLite transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence


class _ClosingConnection(sqlite3.Connection):
    """Connection context manager that also closes the handle on exit."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


class SettlementStoreError(RuntimeError):
    """Unsafe, inconsistent, or unresolved durable settlement state."""


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise SettlementStoreError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SettlementStoreError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise SettlementStoreError(f"{field} must be finite")
    return result


def _canonical_decimal(value: object, field: str) -> str:
    number = _decimal(value, field)
    return format(number, "f")


def _event_hash(previous: str, event: Mapping[str, Any]) -> str:
    encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256((previous + encoded).encode("utf-8")).hexdigest()


class SQLiteSettlementStore:
    """Single-database synthetic portfolio, batch, audit and transactional outbox store.

    Construct and retain only inside a trusted process. The store is not an OS
    security boundary; strategy agents must not receive this object or its path.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | os.PathLike[str], *, account_id: str,
                 currency: str, opening_cash: object) -> None:
        if not isinstance(account_id, str) or not account_id.strip() or len(account_id) > 128:
            raise SettlementStoreError("account_id is required")
        if not isinstance(currency, str) or not currency.strip() or len(currency) > 32:
            raise SettlementStoreError("currency is required")
        cash = _decimal(opening_cash, "opening_cash")
        if cash <= 0:
            raise SettlementStoreError("opening_cash must be positive")
        self.path = Path(path)
        if not self.path.is_absolute():
            raise SettlementStoreError("database path must be absolute")
        self.account_id, self.currency = account_id, currency
        self._lock = threading.RLock()
        self._validate_path()
        with self._connect() as db:
            self._initialize(db, format(cash, "f"))
            row = db.execute(
                "SELECT account_id,currency FROM account WHERE singleton=1"
            ).fetchone()
            if row != (account_id, currency):
                raise SettlementStoreError("database account identity mismatch")
            self._verify_chain(db)

    def register_market(self, market_id: str, base_asset: str, quote_asset: str) -> None:
        if not all(isinstance(v, str) and v.strip() for v in (market_id, base_asset, quote_asset)):
            raise SettlementStoreError("market identity fields are required")
        if quote_asset != self.currency:
            raise SettlementStoreError("market quote asset must equal account currency")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT base_asset,quote_asset FROM markets WHERE market_id=?",
                             (market_id,)).fetchone()
            if row is not None and row != (base_asset, quote_asset):
                db.rollback()
                raise SettlementStoreError("market registration is immutable")
            db.execute("INSERT OR IGNORE INTO markets VALUES(?,?,?)",
                       (market_id, base_asset, quote_asset))
            db.commit()

    def apply_batch(self, *, batch_id: str, request_hash: str,
                    fills: Sequence[Mapping[str, object]],
                    sell_settlements: Sequence[Mapping[str, object]] = (),
                    timestamp: int) -> dict[str, Any]:
        """Atomically commit synthetic fills, balances, audit, batch result and outbox.

        Identical completed batch replay returns the persisted result. Changed content
        under an existing batch ID is rejected. This method does not deliver outbox
        messages; delivery requires a separately trusted idempotent receiver.
        """
        if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 256:
            raise SettlementStoreError("batch_id is required")
        if not isinstance(request_hash, str) or len(request_hash) != 64:
            raise SettlementStoreError("request_hash must be a SHA-256 hex digest")
        try:
            int(request_hash, 16)
        except ValueError as exc:
            raise SettlementStoreError("request_hash must be hexadecimal") from exc
        if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
            raise SettlementStoreError("timestamp must be a nonnegative integer")
        if not isinstance(fills, Sequence) or isinstance(fills, (str, bytes)):
            raise SettlementStoreError("fills must be a sequence")
        if not isinstance(sell_settlements, Sequence) or isinstance(sell_settlements, (str, bytes)):
            raise SettlementStoreError("sell_settlements must be a sequence")

        normalized_fills = []
        seen_fill_ids = set()
        for item in fills:
            if not isinstance(item, Mapping):
                raise SettlementStoreError("each fill must be a mapping")
            fill_id, market_id = item.get("fill_id"), item.get("market_id")
            side = item.get("side")
            if not isinstance(fill_id, str) or not fill_id.strip() or fill_id in seen_fill_ids:
                raise SettlementStoreError("fill IDs must be nonempty and unique within batch")
            if not isinstance(market_id, str) or not market_id.strip():
                raise SettlementStoreError("fill market_id is required")
            if side not in ("BUY", "SELL"):
                raise SettlementStoreError("only BUY and SELL fills are supported")
            qty = _decimal(item.get("quantity"), "quantity")
            price = _decimal(item.get("price"), "price")
            fee = _decimal(item.get("fee_quote"), "fee_quote")
            if qty <= 0 or price <= 0 or fee < 0:
                raise SettlementStoreError("fill quantity/price must be positive and fee nonnegative")
            seen_fill_ids.add(fill_id)
            normalized_fills.append({
                "fill_id": fill_id, "market_id": market_id, "side": side,
                "quantity": format(qty, "f"), "price": format(price, "f"),
                "fee_quote": format(fee, "f"),
            })

        normalized_outbox = []
        seen_keys = set()
        for item in sell_settlements:
            if not isinstance(item, Mapping):
                raise SettlementStoreError("each settlement outbox item must be a mapping")
            key, market_id = item.get("idempotency_key"), item.get("market_id")
            if not isinstance(key, str) or not key.strip() or key in seen_keys:
                raise SettlementStoreError("outbox idempotency keys must be nonempty and unique")
            if not isinstance(market_id, str) or not market_id.strip():
                raise SettlementStoreError("outbox market_id is required")
            authorized = _decimal(item.get("authorized_quantity"), "authorized_quantity")
            filled = _decimal(item.get("filled_quantity"), "filled_quantity")
            if authorized < 0 or filled < 0 or filled > authorized:
                raise SettlementStoreError("invalid SELL reservation quantities")
            seen_keys.add(key)
            normalized_outbox.append({
                "idempotency_key": key, "market_id": market_id,
                "authorized_quantity": format(authorized, "f"),
                "filled_quantity": format(filled, "f"),
            })

        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT request_hash,status,result_json FROM batches WHERE batch_id=?",
                (batch_id,),
            ).fetchone()
            if existing:
                old_hash, status, result_json = existing
                if old_hash != request_hash:
                    db.rollback()
                    raise SettlementStoreError("batch_id reused with different request hash")
                if status in ("COMMITTED_PENDING_OUTBOX", "COMPLETE"):
                    db.commit()
                    return json.loads(result_json)
                db.rollback()
                raise SettlementStoreError("batch unresolved; trusted reconciliation required")

            db.execute(
                "INSERT INTO batches(batch_id,request_hash,status,created_at,result_json) "
                "VALUES(?,?, 'PROCESSING', ?, NULL)", (batch_id, request_hash, timestamp)
            )
            cash = _decimal(db.execute("SELECT cash FROM account WHERE singleton=1").fetchone()[0],
                            "stored cash")
            balances = {
                row[0]: _decimal(row[1], "stored holding")
                for row in db.execute("SELECT market_id,quantity FROM holdings")
            }
            staged = []
            for fill in normalized_fills:
                market = db.execute("SELECT 1 FROM markets WHERE market_id=?",
                                    (fill["market_id"],)).fetchone()
                if market is None:
                    raise SettlementStoreError("fill market is not registered")
                if db.execute("SELECT 1 FROM fills WHERE fill_id=?", (fill["fill_id"],)).fetchone():
                    raise SettlementStoreError("fill ID already exists")
                qty, price, fee = (_decimal(fill["quantity"], "quantity"),
                                   _decimal(fill["price"], "price"),
                                   _decimal(fill["fee_quote"], "fee_quote"))
                current = balances.get(fill["market_id"], Decimal("0"))
                notional = qty * price
                if fill["side"] == "BUY":
                    debit = notional + fee
                    if debit > cash:
                        raise SettlementStoreError("insufficient quote cash")
                    cash -= debit
                    current += qty
                else:
                    if qty > current:
                        raise SettlementStoreError("SELL exceeds long inventory")
                    proceeds = notional - fee
                    if proceeds < 0:
                        raise SettlementStoreError("SELL fee exceeds proceeds")
                    cash += proceeds
                    current -= qty
                balances[fill["market_id"]] = current
                staged.append((fill, current, cash))

            for item in normalized_outbox:
                if db.execute("SELECT 1 FROM markets WHERE market_id=?",
                              (item["market_id"],)).fetchone() is None:
                    raise SettlementStoreError("outbox market is not registered")

            # Persist final account state and all fill records in this same transaction.
            db.execute("UPDATE account SET cash=? WHERE singleton=1", (format(cash, "f"),))
            for market_id, quantity in balances.items():
                db.execute(
                    "INSERT INTO holdings(market_id,quantity) VALUES(?,?) "
                    "ON CONFLICT(market_id) DO UPDATE SET quantity=excluded.quantity",
                    (market_id, format(quantity, "f")),
                )
            previous = db.execute("SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            head = previous[0] if previous else "0" * 64
            for fill, holding_after, cash_after in staged:
                db.execute(
                    "INSERT INTO fills(fill_id,batch_id,market_id,side,quantity,price,fee_quote,timestamp) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (fill["fill_id"], batch_id, fill["market_id"], fill["side"],
                     fill["quantity"], fill["price"], fill["fee_quote"], timestamp),
                )
                event = {
                    "kind": "SYNTHETIC_FILL", "account_id": self.account_id,
                    "batch_id": batch_id, **fill, "cash_after": format(cash_after, "f"),
                    "holding_after": format(holding_after, "f"), "timestamp": timestamp,
                }
                head = _event_hash(head, event)
                db.execute("INSERT INTO audit(event_json,previous_hash,event_hash) VALUES(?,?,?)",
                           (json.dumps(event, sort_keys=True, separators=(",", ":")),
                            "0" * 64 if db.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 0
                            else db.execute("SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()[0],
                            head))
            for item in normalized_outbox:
                db.execute(
                    "INSERT INTO outbox(idempotency_key,batch_id,market_id,authorized_quantity,"
                    "filled_quantity,status) VALUES(?,?,?,?,?,'PENDING')",
                    (item["idempotency_key"], batch_id, item["market_id"],
                     item["authorized_quantity"], item["filled_quantity"]),
                )
            result = {
                "batch_id": batch_id, "request_hash": request_hash,
                "status": "COMMITTED_PENDING_OUTBOX" if normalized_outbox else "COMPLETE",
                "cash": format(cash, "f"),
                "holdings": {key: format(value, "f") for key, value in sorted(balances.items())},
                "fills": normalized_fills,
                "outbox_keys": [item["idempotency_key"] for item in normalized_outbox],
            }
            db.execute("UPDATE batches SET status=?,result_json=? WHERE batch_id=?",
                       (result["status"], json.dumps(result, sort_keys=True, separators=(",", ":")),
                        batch_id))
            db.commit()
            return result

    def pending_outbox(self, *, limit: int = 100) -> list[dict[str, str]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise SettlementStoreError("limit must be in [1, 1000]")
        with self._connect() as db:
            rows = db.execute(
                "SELECT idempotency_key,batch_id,market_id,authorized_quantity,filled_quantity "
                "FROM outbox WHERE status='PENDING' ORDER BY idempotency_key LIMIT ?", (limit,)
            ).fetchall()
            return [dict(zip(("idempotency_key","batch_id","market_id",
                              "authorized_quantity","filled_quantity"), row)) for row in rows]

    def acknowledge_outbox(self, idempotency_key: str, *, receiver_receipt: str) -> None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise SettlementStoreError("idempotency_key is required")
        if not isinstance(receiver_receipt, str) or not receiver_receipt.strip():
            raise SettlementStoreError("receiver_receipt is required")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT batch_id,status FROM outbox WHERE idempotency_key=?",
                             (idempotency_key,)).fetchone()
            if row is None:
                db.rollback()
                raise SettlementStoreError("unknown outbox key")
            batch_id, status = row
            if status == "ACKNOWLEDGED":
                db.commit()
                return
            db.execute("UPDATE outbox SET status='ACKNOWLEDGED',receiver_receipt=? "
                       "WHERE idempotency_key=?", (receiver_receipt, idempotency_key))
            remaining = db.execute(
                "SELECT COUNT(*) FROM outbox WHERE batch_id=? AND status!='ACKNOWLEDGED'",
                (batch_id,),
            ).fetchone()[0]
            if remaining == 0:
                db.execute("UPDATE batches SET status='COMPLETE' WHERE batch_id=? "
                           "AND status='COMMITTED_PENDING_OUTBOX'", (batch_id,))
            db.commit()

    def snapshot(self) -> dict[str, Any]:
        with self._connect() as db:
            account = db.execute("SELECT cash FROM account WHERE singleton=1").fetchone()
            holdings = dict(db.execute("SELECT market_id,quantity FROM holdings"))
            return {"account_id": self.account_id, "currency": self.currency,
                    "cash": account[0], "holdings": holdings}

    def verify_audit_chain(self) -> bool:
        with self._connect() as db:
            return self._verify_chain(db)

    def _verify_chain(self, db: sqlite3.Connection) -> bool:
        previous = "0" * 64
        for event_json, stored_previous, stored_hash in db.execute(
                "SELECT event_json,previous_hash,event_hash FROM audit ORDER BY seq"):
            event = json.loads(event_json)
            if stored_previous != previous or _event_hash(previous, event) != stored_hash:
                return False
            previous = stored_hash
        return True

    def _initialize(self, db: sqlite3.Connection, opening_cash: str) -> None:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS account(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS markets(
            market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS holdings(
            market_id TEXT PRIMARY KEY REFERENCES markets(market_id), quantity TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS batches(
            batch_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN
              ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')),
            created_at INTEGER NOT NULL, result_json TEXT);
        CREATE TABLE IF NOT EXISTS fills(
            fill_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id),
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL,
            price TEXT NOT NULL, fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(
            idempotency_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id),
            market_id TEXT NOT NULL REFERENCES markets(market_id),
            authorized_quantity TEXT NOT NULL, filled_quantity TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING','ACKNOWLEDGED')),
            receiver_receipt TEXT);
        """)
        version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if version is None:
            db.execute("INSERT INTO metadata VALUES('schema_version',?)", (str(self.SCHEMA_VERSION),))
            db.execute("INSERT INTO account VALUES(1,?,?,?)",
                       (self.account_id, self.currency, opening_cash))
        elif version[0] != str(self.SCHEMA_VERSION):
            raise SettlementStoreError("unsupported schema version; explicit migration required")

    def _validate_path(self) -> None:
        parent = self.path.parent
        if not parent.exists() or parent.is_symlink() or not parent.is_dir():
            raise SettlementStoreError("database parent must be an existing real directory")
        current = parent
        while current != current.parent:
            if current.is_symlink():
                raise SettlementStoreError("symlinked path component rejected")
            current = current.parent
        if os.name == "posix":
            info = parent.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise SettlementStoreError("database parent must be current-user-owned and private")
        if self.path.exists() or self.path.is_symlink():
            info = self.path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise SettlementStoreError("database must be regular, non-symlink and single-link")
            if os.name == "posix" and (
                info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise SettlementStoreError("database must be current-user-owned and private")

    def _connect(self) -> sqlite3.Connection:
        self._validate_path()
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None, factory=_ClosingConnection)
        os.chmod(self.path, 0o600)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA busy_timeout=5000")
        return db
