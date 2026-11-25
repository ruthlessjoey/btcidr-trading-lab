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
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise SettlementStoreError("SQLite integrity check failed; store locked")
            if not self._verify_chain(db):
                raise SettlementStoreError("audit chain verification failed; store locked")

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

    def apply_batch(self, *, batch_id: str,
                    fills: Sequence[Mapping[str, object]],
                    sell_settlements: Sequence[Mapping[str, object]] = (),
                    sell_allocations: Sequence[Mapping[str, object]] = (),
                    timestamp: int) -> dict[str, Any]:
        """Atomically commit synthetic fills, balances, audit, batch result and outbox.

        Identical completed batch replay returns the persisted result. Changed content
        under an existing batch ID is rejected. When reservation schema v2 is enabled,
        every SELL fill requires exact per-fill sell_allocations consumed atomically.
        This method does not deliver either outbox; delivery requires a separately
        trusted idempotent receiver.
        """
        if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 256:
            raise SettlementStoreError("batch_id is required")
        if (isinstance(timestamp, bool) or not isinstance(timestamp, int)
                or timestamp < 0 or timestamp > 2**63 - 1):
            raise SettlementStoreError("timestamp must be a nonnegative SQLite integer")
        if not isinstance(fills, Sequence) or isinstance(fills, (str, bytes)):
            raise SettlementStoreError("fills must be a sequence")
        if not isinstance(sell_settlements, Sequence) or isinstance(sell_settlements, (str, bytes)):
            raise SettlementStoreError("sell_settlements must be a sequence")
        if not isinstance(sell_allocations, Sequence) or isinstance(sell_allocations, (str, bytes)):
            raise SettlementStoreError("sell_allocations must be a sequence")
        if len(sell_allocations) > 1000:
            raise SettlementStoreError("sell_allocations exceeds the 1000-row limit")

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

        normalized_allocations = []
        seen_allocation_ids = set()
        for item in sell_allocations:
            if not isinstance(item, Mapping):
                raise SettlementStoreError("each SELL allocation must be a mapping")
            allocation_id = item.get("allocation_id")
            fill_id = item.get("fill_id")
            reservation_id = item.get("reservation_id")
            version = item.get("reservation_version")
            quantity_text = item.get("allocated_quantity")
            if not isinstance(allocation_id, str) or not allocation_id.strip() or len(allocation_id) > 256:
                raise SettlementStoreError("allocation_id is required")
            if allocation_id in seen_allocation_ids:
                raise SettlementStoreError("allocation IDs must be unique")
            if not isinstance(fill_id, str) or not fill_id.strip() or len(fill_id) > 256:
                raise SettlementStoreError("allocation fill_id is required and bounded")
            if (not isinstance(reservation_id, str) or not reservation_id.strip()
                    or len(reservation_id) > 256):
                raise SettlementStoreError("allocation reservation_id is required and bounded")
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise SettlementStoreError("reservation_version must be a positive integer")
            if len(str(quantity_text)) > 128:
                raise SettlementStoreError("allocated_quantity text exceeds the 128-character limit")
            quantity = _decimal(quantity_text, "allocated_quantity")
            if quantity <= 0:
                raise SettlementStoreError("allocated_quantity must be positive")
            seen_allocation_ids.add(allocation_id)
            normalized_allocations.append({
                "allocation_id": allocation_id, "fill_id": fill_id,
                "reservation_id": reservation_id, "reservation_version": version,
                "allocated_quantity": format(quantity, "f"),
            })
        normalized_allocations.sort(key=lambda item: item["allocation_id"])

        request_envelope = {
            "schema": 1, "account_id": self.account_id, "currency": self.currency,
            "batch_id": batch_id, "timestamp": timestamp,
            "fills": normalized_fills, "sell_settlements": normalized_outbox,
        }
        if normalized_allocations:
            request_envelope["sell_allocations"] = normalized_allocations
        request_json = json.dumps(request_envelope, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False)
        request_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        sell_totals: dict[str, Decimal] = {}
        outbox_totals: dict[str, Decimal] = {}
        for fill in normalized_fills:
            if fill["side"] == "SELL":
                market_id = fill["market_id"]
                sell_totals[market_id] = sell_totals.get(market_id, Decimal("0")) + _decimal(fill["quantity"], "SELL quantity")
        for item in normalized_outbox:
            market_id = item["market_id"]
            outbox_totals[market_id] = outbox_totals.get(market_id, Decimal("0")) + _decimal(item["filled_quantity"], "outbox filled_quantity")
        nonzero_outbox = {key: value for key, value in outbox_totals.items() if value != 0}
        if sell_totals != nonzero_outbox:
            raise SettlementStoreError("SELL outbox filled quantities must equal SELL fills per market")
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
                    result = json.loads(result_json)
                    result["status"] = status
                    db.commit()
                    return result
                db.rollback()
                raise SettlementStoreError("batch unresolved; trusted reconciliation required")

            reservation_tables = {
                "reservations", "reservation_allocations", "reservation_outbox"
            }
            reservation_objects = db.execute(
                "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                "('reservations','reservation_allocations','reservation_outbox')"
            ).fetchall()
            if any(kind != "table" for kind, _ in reservation_objects):
                raise SettlementStoreError("unexpected reservation schema object type")
            present_reservation_tables = {name for _, name in reservation_objects}
            if present_reservation_tables and present_reservation_tables != reservation_tables:
                raise SettlementStoreError("partial reservation schema rejected")
            reservations_enabled = present_reservation_tables == reservation_tables
            if sell_totals and not reservations_enabled:
                raise SettlementStoreError(
                    "reservation schema v2 is required before any SELL fill"
                )
            if normalized_allocations and not reservations_enabled:
                raise SettlementStoreError("SELL reservation schema must be enabled before allocations")
            if reservations_enabled:
                from .reservation_schema_v2 import ensure_reservation_schema_v2
                ensure_reservation_schema_v2(db)
                if sell_totals and not normalized_allocations:
                    raise SettlementStoreError("SELL fills require reservation allocations when reservation schema is enabled")

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
                head = self._append_audit(db, event)
            normalized_reservation_allocations = []
            if normalized_allocations:
                from .reservation_allocations import (
                    ReservationAllocationError, consume_sell_allocations,
                )
                try:
                    normalized_reservation_allocations = consume_sell_allocations(
                        db, account_id=self.account_id, batch_id=batch_id,
                        allocations=normalized_allocations, timestamp=timestamp,
                    )
                except ReservationAllocationError as exc:
                    raise SettlementStoreError(str(exc)) from exc
            for item in normalized_outbox:
                db.execute(
                    "INSERT INTO outbox(idempotency_key,batch_id,market_id,authorized_quantity,"
                    "filled_quantity,status) VALUES(?,?,?,?,?,'PENDING')",
                    (item["idempotency_key"], batch_id, item["market_id"],
                     item["authorized_quantity"], item["filled_quantity"]),
                )
            result = {
                "batch_id": batch_id, "request_hash": request_hash,
                "status": "COMMITTED_PENDING_OUTBOX"
                if (normalized_outbox or normalized_reservation_allocations) else "COMPLETE",
                "cash": format(cash, "f"),
                "holdings": {key: format(value, "f") for key, value in sorted(balances.items())},
                "fills": normalized_fills,
                "outbox_keys": [item["idempotency_key"] for item in normalized_outbox],
            }
            if normalized_reservation_allocations:
                result["reservation_allocations"] = normalized_reservation_allocations
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

    def pending_reservation_outbox(self, *, limit: int = 100) -> list[dict[str, str]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise SettlementStoreError("limit must be in [1, 1000]")
        with self._connect() as db:
            objects = db.execute(
                "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                "('reservations','reservation_allocations','reservation_outbox')"
            ).fetchall()
            expected = {"reservations","reservation_allocations","reservation_outbox"}
            if not objects:
                return []
            if any(kind != "table" for kind, _ in objects) or {name for _, name in objects} != expected:
                raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
            db.execute("BEGIN")
            from .reservation_schema_v2 import ensure_reservation_schema_v2
            ensure_reservation_schema_v2(db)
            rows = db.execute(
                "SELECT idempotency_key,allocation_id,batch_id,reservation_id,fill_id,"
                "account_id,market_id,reservation_version,allocated_quantity,payload_sha256 "
                "FROM main.reservation_outbox WHERE status='PENDING' "
                "ORDER BY idempotency_key LIMIT ?", (limit,)
            ).fetchall()
            fields = (
                "idempotency_key","allocation_id","batch_id","reservation_id","fill_id",
                "account_id","market_id","reservation_version","allocated_quantity","payload_sha256",
            )
            result = [dict(zip(fields, row)) for row in rows]
            if any(item["account_id"] != self.account_id for item in result):
                raise SettlementStoreError("reservation outbox account identity mismatch")
            return result

    def _complete_batch_if_outboxes_acknowledged(
        self, db: sqlite3.Connection, batch_id: str,
    ) -> None:
        legacy_pending = db.execute(
            "SELECT COUNT(*) FROM main.outbox WHERE batch_id=? AND status!='ACKNOWLEDGED'",
            (batch_id,),
        ).fetchone()[0]
        reservation_objects = db.execute(
            "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
            "('reservations','reservation_allocations','reservation_outbox')"
        ).fetchall()
        reservation_pending = 0
        if reservation_objects:
            expected = {"reservations","reservation_allocations","reservation_outbox"}
            if (any(kind != "table" for kind, _ in reservation_objects)
                    or {name for _, name in reservation_objects} != expected):
                raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
            from .reservation_schema_v2 import ensure_reservation_schema_v2
            ensure_reservation_schema_v2(db)
            reservation_pending = db.execute(
                "SELECT COUNT(*) FROM main.reservation_outbox "
                "WHERE batch_id=? AND status!='ACKNOWLEDGED'", (batch_id,)
            ).fetchone()[0]
        if legacy_pending == 0 and reservation_pending == 0:
            result_row = db.execute(
                "SELECT result_json FROM main.batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            if result_row is None or result_row[0] is None:
                raise SettlementStoreError("batch result missing during outbox completion")
            result = json.loads(result_row[0])
            result["status"] = "COMPLETE"
            db.execute(
                "UPDATE main.batches SET status='COMPLETE',result_json=? "
                "WHERE batch_id=? AND status='COMMITTED_PENDING_OUTBOX'",
                (json.dumps(result, sort_keys=True, separators=(",", ":")), batch_id),
            )

    def acknowledge_reservation_outbox(
        self, idempotency_key: str, *, receiver_receipt: str,
        expected_payload_sha256: str,
    ) -> None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise SettlementStoreError("idempotency_key is required")
        if not isinstance(receiver_receipt, str) or not receiver_receipt.strip():
            raise SettlementStoreError("receiver_receipt is required")
        if (
            not isinstance(expected_payload_sha256, str)
            or len(expected_payload_sha256) != 64
            or any(char not in "0123456789abcdef" for char in expected_payload_sha256)
        ):
            raise SettlementStoreError("expected_payload_sha256 must be a lowercase SHA-256 hex digest")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            objects = db.execute(
                "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                "('reservations','reservation_allocations','reservation_outbox')"
            ).fetchall()
            expected = {"reservations","reservation_allocations","reservation_outbox"}
            if any(kind != "table" for kind, _ in objects) or {name for _, name in objects} != expected:
                db.rollback()
                raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
            from .reservation_schema_v2 import ensure_reservation_schema_v2
            ensure_reservation_schema_v2(db)
            row = db.execute(
                "SELECT batch_id,status,receiver_receipt,allocation_id,reservation_id,fill_id,"
                "account_id,market_id,reservation_version,allocated_quantity,payload_sha256 "
                "FROM main.reservation_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise SettlementStoreError("unknown reservation outbox key")
            (
                batch_id, status, old_receipt, allocation_id, reservation_id, fill_id,
                account_id, market_id, reservation_version, allocated_quantity, stored_digest,
            ) = row
            if account_id != self.account_id:
                db.rollback()
                raise SettlementStoreError("reservation outbox account identity mismatch")
            payload = {
                "schema": 1, "idempotency_key": idempotency_key,
                "allocation_id": allocation_id, "batch_id": batch_id,
                "fill_id": fill_id, "reservation_id": reservation_id,
                "account_id": account_id, "market_id": market_id,
                "reservation_version": reservation_version,
                "allocated_quantity": allocated_quantity,
            }
            from .reservation_outbox_receiver import (
                ReservationInboxError, _canonical_payload,
            )
            try:
                _, recalculated_digest, expected_receipt = _canonical_payload(payload)
            except (ReservationInboxError, TypeError, ValueError, UnicodeError) as exc:
                db.rollback()
                raise SettlementStoreError("stored reservation outbox payload is invalid") from exc
            if (
                stored_digest != recalculated_digest
                or stored_digest != expected_payload_sha256
            ):
                db.rollback()
                raise SettlementStoreError("reservation outbox payload changed during delivery")
            if receiver_receipt != expected_receipt:
                db.rollback()
                raise SettlementStoreError("reservation outbox receipt does not match current payload")
            if status == "ACKNOWLEDGED":
                if old_receipt != receiver_receipt:
                    db.rollback()
                    raise SettlementStoreError("reservation outbox acknowledgement receipt mismatch")
                db.commit()
                return
            changed = db.execute(
                "UPDATE main.reservation_outbox SET status='ACKNOWLEDGED',receiver_receipt=? "
                "WHERE idempotency_key=? AND status='PENDING' AND payload_sha256=?",
                (receiver_receipt, idempotency_key, expected_payload_sha256),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise SettlementStoreError("reservation outbox changed before acknowledgement")
            receipt_digest = hashlib.sha256(receiver_receipt.encode("utf-8")).hexdigest()
            self._append_audit(db, {
                "kind": "RESERVATION_OUTBOX_ACKNOWLEDGED",
                "account_id": self.account_id, "batch_id": batch_id,
                "allocation_id": allocation_id, "idempotency_key": idempotency_key,
                "payload_sha256": recalculated_digest,
                "receipt_sha256": receipt_digest,
            })
            self._complete_batch_if_outboxes_acknowledged(db, batch_id)
            db.commit()

    def acknowledge_outbox(self, idempotency_key: str, *, receiver_receipt: str) -> None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise SettlementStoreError("idempotency_key is required")
        if not isinstance(receiver_receipt, str) or not receiver_receipt.strip():
            raise SettlementStoreError("receiver_receipt is required")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT batch_id,status,receiver_receipt FROM outbox WHERE idempotency_key=?",
                             (idempotency_key,)).fetchone()
            if row is None:
                db.rollback()
                raise SettlementStoreError("unknown outbox key")
            batch_id, status, old_receipt = row
            if status == "ACKNOWLEDGED":
                if old_receipt != receiver_receipt:
                    db.rollback()
                    raise SettlementStoreError("outbox acknowledgement receipt mismatch")
                db.commit()
                return
            db.execute("UPDATE outbox SET status='ACKNOWLEDGED',receiver_receipt=? "
                       "WHERE idempotency_key=?", (receiver_receipt, idempotency_key))
            receipt_digest = hashlib.sha256(receiver_receipt.encode("utf-8")).hexdigest()
            self._append_audit(db, {
                "kind": "OUTBOX_ACKNOWLEDGED", "account_id": self.account_id,
                "batch_id": batch_id, "idempotency_key": idempotency_key,
                "receipt_sha256": receipt_digest,
            })
            self._complete_batch_if_outboxes_acknowledged(db, batch_id)
            db.commit()

    def snapshot(self) -> dict[str, Any]:
        with self._connect() as db:
            account = db.execute("SELECT cash FROM account WHERE singleton=1").fetchone()
            holdings = dict(db.execute("SELECT market_id,quantity FROM holdings"))
            return {"account_id": self.account_id, "currency": self.currency,
                    "cash": account[0], "holdings": holdings}

    def _append_audit(self, db: sqlite3.Connection, event: Mapping[str, Any]) -> str:
        row = db.execute("SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        previous = row[0] if row else "0" * 64
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        digest = _event_hash(previous, event)
        db.execute("INSERT INTO audit(event_json,previous_hash,event_hash) VALUES(?,?,?)",
                   (encoded, previous, digest))
        return digest

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
        expected_columns = {
            "metadata": ("key", "value"),
            "account": ("singleton", "account_id", "currency", "cash"),
            "markets": ("market_id", "base_asset", "quote_asset"),
            "holdings": ("market_id", "quantity"),
            "batches": ("batch_id", "request_hash", "status", "created_at", "result_json"),
            "fills": ("fill_id", "batch_id", "market_id", "side", "quantity", "price", "fee_quote", "timestamp"),
            "audit": ("seq", "event_json", "previous_hash", "event_hash"),
            "outbox": ("idempotency_key", "batch_id", "market_id", "authorized_quantity", "filled_quantity", "status", "receiver_receipt"),
        }
        existing_tables = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        is_new_database = not existing_tables
        expected_tables = set(expected_columns)
        reservation_tables = {
            "reservations", "reservation_allocations", "reservation_outbox"
        }
        present_reservation_tables = existing_tables & reservation_tables
        if existing_tables:
            missing = sorted(expected_tables - existing_tables)
            unexpected = sorted(existing_tables - expected_tables - reservation_tables)
            if missing or unexpected:
                raise SettlementStoreError(
                    f"database schema mismatch; missing={missing}, unexpected={unexpected}"
                )
            if present_reservation_tables and present_reservation_tables != reservation_tables:
                raise SettlementStoreError(
                    "partial reservation schema rejected; recovery required"
                )

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
        for table, columns in expected_columns.items():
            actual = tuple(row[1] for row in db.execute(f"PRAGMA table_info({table})"))
            if actual != columns:
                raise SettlementStoreError(
                    f"database schema mismatch for {table}: expected {columns}, found {actual}"
                )

        # Column names alone do not protect CHECK, PRIMARY KEY, UNIQUE and
        # FOREIGN KEY constraints. Compare SQLite's stored table definitions
        # against the schema-v1 contract and reject unapproved executable schema
        # objects (indexes/triggers) before trusting persisted accounting state.
        expected_sql = {
            "metadata": "CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
            "account": "CREATE TABLE account(singleton INTEGER PRIMARY KEY CHECK(singleton=1), account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL)",
            "markets": "CREATE TABLE markets(market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL)",
            "holdings": "CREATE TABLE holdings(market_id TEXT PRIMARY KEY REFERENCES markets(market_id), quantity TEXT NOT NULL)",
            "batches": "CREATE TABLE batches(batch_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')), created_at INTEGER NOT NULL, result_json TEXT)",
            "fills": "CREATE TABLE fills(fill_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL, price TEXT NOT NULL, fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL)",
            "audit": "CREATE TABLE audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)",
            "outbox": "CREATE TABLE outbox(idempotency_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), authorized_quantity TEXT NOT NULL, filled_quantity TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','ACKNOWLEDGED')), receiver_receipt TEXT)",
        }
        normalize_sql = lambda value: "".join(value.split()).casefold()
        for table, expected in expected_sql.items():
            row = db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if row is None or normalize_sql(row[0]) != normalize_sql(expected):
                raise SettlementStoreError(
                    f"database schema definition mismatch for {table}; recovery required"
                )

        unexpected_objects = db.execute(
            "SELECT type,name FROM sqlite_master "
            "WHERE type IN ('index','trigger') AND name NOT LIKE 'sqlite_autoindex_%' "
            "ORDER BY type,name"
        ).fetchall()
        if unexpected_objects:
            raise SettlementStoreError(
                f"database contains unapproved schema objects: {unexpected_objects}; recovery required"
            )

        # A persisted current-v2 database is a valid settlement-store state,
        # not an unexpected extension. Verify the complete v2 contract without
        # creating or migrating anything. Partial and older-v2 schemas fail closed.
        if present_reservation_tables == reservation_tables:
            from .reservation_schema_v2 import (
                ReservationSchemaError, ensure_reservation_schema_v2,
            )
            db.execute("BEGIN")
            try:
                ensure_reservation_schema_v2(db)
            except ReservationSchemaError as exc:
                db.rollback()
                raise SettlementStoreError(
                    "reservation schema verification failed; recovery required"
                ) from exc
            else:
                db.rollback()

        version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if version is None:
            if not is_new_database:
                raise SettlementStoreError("existing database is missing schema version; recovery required")
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
