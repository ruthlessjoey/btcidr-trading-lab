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
from decimal import Decimal, InvalidOperation, localcontext
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
                    replay_reservation_objects = db.execute(
                        "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                        "('reservations','reservation_allocations','reservation_outbox')"
                    ).fetchall()
                    replay_expected = {"reservations","reservation_allocations","reservation_outbox"}
                    replay_present = {
                        name for kind,name in replay_reservation_objects if kind == "table"
                    }
                    if (any(kind != "table" for kind,_ in replay_reservation_objects)
                            or (replay_present and replay_present != replay_expected)):
                        db.rollback()
                        raise SettlementStoreError(
                            "reservation schema is partial or contains unexpected objects"
                        )
                    if replay_present == replay_expected:
                        from .reservation_schema_v2 import ensure_reservation_schema_v2
                        ensure_reservation_schema_v2(db)
                        self._verify_reservation_audit_coverage(db)
                    else:
                        self._verify_fill_account_state(db)
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
                # Never derive a new settlement from unaudited persisted balances.
                self._verify_reservation_audit_coverage(db)
            else:
                self._verify_fill_account_state(db)

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
            db.execute("BEGIN")
            try:
                self._verify_account_state(db)
                rows = db.execute(
                    "SELECT idempotency_key,batch_id,market_id,authorized_quantity,filled_quantity "
                    "FROM main.outbox WHERE status='PENDING' ORDER BY idempotency_key LIMIT ?", (limit,)
                ).fetchall()
            except Exception:
                db.rollback()
                raise
            else:
                db.rollback()
            return [dict(zip(("idempotency_key","batch_id","market_id",
                              "authorized_quantity","filled_quantity"), row)) for row in rows]

    def _verify_fill_account_state(self, db: sqlite3.Connection) -> None:
        if not self._verify_chain(db):
            raise SettlementStoreError("reservation audit chain verification failed")

        initialization_events = []
        audit_rows = db.execute(
            "SELECT event_json FROM main.audit ORDER BY seq"
        ).fetchall()
        for (event_json,) in audit_rows:
            event = json.loads(event_json)
            if isinstance(event,dict) and event.get("kind") == "ACCOUNT_INITIALIZED":
                initialization_events.append(event)
        baseline_policy = db.execute(
            "SELECT value FROM main.metadata WHERE key='account_initialization_audit'"
        ).fetchone()
        if baseline_policy is not None and baseline_policy != ("required-v1",):
            raise SettlementStoreError("initial account audit policy marker is invalid")
        if baseline_policy == ("required-v1",) and not initialization_events:
            raise SettlementStoreError("required initial account audit event is missing")

        initial_cash: Decimal | None = None
        if initialization_events:
            first_event = json.loads(audit_rows[0][0]) if audit_rows else None
            event = initialization_events[0]
            expected_initial_keys = {"kind","account_id","currency","opening_cash"}
            account_row = db.execute(
                "SELECT account_id,currency,cash FROM main.account WHERE singleton=1"
            ).fetchone()
            if (len(initialization_events) != 1 or first_event != event
                    or set(event) != expected_initial_keys
                    or event.get("account_id") != self.account_id
                    or event.get("currency") != self.currency
                    or account_row is None
                    or account_row[:2] != (self.account_id,self.currency)):
                raise SettlementStoreError("initial account audit identity is invalid")
            initial_cash = _decimal(event["opening_cash"],"initial audited cash")
            if initial_cash <= 0:
                raise SettlementStoreError("initial audited cash must be positive")

        # The hash chain proves ordering/integrity only relative to its stored hashes.
        # Reconcile every canonical fill row to exactly one immutable SYNTHETIC_FILL event.
        fill_rows = db.execute(
            "SELECT fill_id,batch_id,market_id,side,quantity,price,fee_quote,timestamp "
            "FROM main.fills ORDER BY fill_id"
        ).fetchall()
        batch_times = dict(db.execute(
            "SELECT batch_id,created_at FROM main.batches"
        ))
        registered_markets = {
            row[0] for row in db.execute("SELECT market_id FROM main.markets")
        }
        for fill_id,batch_id,market_id,side,quantity_text,price_text,fee_text,timestamp in fill_rows:
            quantity = _decimal(quantity_text,"fill quantity")
            price = _decimal(price_text,"fill price")
            fee = _decimal(fee_text,"fill fee")
            if (not isinstance(fill_id,str) or not fill_id
                    or batch_times.get(batch_id) != timestamp
                    or market_id not in registered_markets
                    or side not in ("BUY","SELL")
                    or isinstance(timestamp,bool) or not isinstance(timestamp,int) or timestamp < 0
                    or quantity <= 0 or price <= 0 or fee < 0):
                raise SettlementStoreError("fill row does not match its batch/market contract")
        expected_fills = {
            row[0]: {
                "fill_id":row[0],"batch_id":row[1],"market_id":row[2],"side":row[3],
                "quantity":row[4],"price":row[5],"fee_quote":row[6],"timestamp":row[7],
            }
            for row in fill_rows
        }
        audit_fills: dict[str,dict[str,object]] = {}
        for (event_json,) in db.execute("SELECT event_json FROM main.audit ORDER BY seq"):
            event = json.loads(event_json)
            if not isinstance(event,dict) or event.get("kind") != "SYNTHETIC_FILL":
                continue
            fill_id = event.get("fill_id")
            if not isinstance(fill_id,str) or not fill_id or fill_id in audit_fills:
                raise SettlementStoreError("synthetic fill audit identity is invalid")
            expected_keys = {
                "kind","account_id","batch_id","fill_id","market_id","side",
                "quantity","price","fee_quote","cash_after","holding_after","timestamp",
            }
            if (set(event) != expected_keys or event.get("account_id") != self.account_id):
                raise SettlementStoreError("synthetic fill audit schema/account mismatch")
            for field in ("cash_after","holding_after"):
                if _decimal(event[field],field) < 0:
                    raise SettlementStoreError("synthetic fill audit balance is invalid")
            audit_fills[fill_id] = {
                key:event[key] for key in (
                    "fill_id","batch_id","market_id","side","quantity",
                    "price","fee_quote","timestamp",
                )
            }
        if audit_fills != expected_fills:
            raise SettlementStoreError("synthetic fill ledger does not match audit events")

        # Reconcile event-to-event balance transitions and the current accounting rows.
        previous_cash: Decimal | None = initial_cash
        latest_cash: Decimal | None = None
        previous_holdings: dict[str,Decimal] = {}
        latest_holdings: dict[str,Decimal] = {}
        with localcontext() as decimal_context:
            decimal_context.prec = 80
            for (event_json,) in db.execute("SELECT event_json FROM main.audit ORDER BY seq"):
                event = json.loads(event_json)
                if not isinstance(event,dict) or event.get("kind") != "SYNTHETIC_FILL":
                    continue
                quantity = _decimal(event["quantity"],"audited fill quantity")
                price = _decimal(event["price"],"audited fill price")
                fee = _decimal(event["fee_quote"],"audited fill fee")
                cash_after = _decimal(event["cash_after"],"audited cash after")
                holding_after = _decimal(event["holding_after"],"audited holding after")
                market_id = event["market_id"]
                if event["side"] == "BUY":
                    cash_delta = -(quantity * price + fee)
                    holding_delta = quantity
                elif event["side"] == "SELL":
                    cash_delta = quantity * price - fee
                    holding_delta = -quantity
                else:
                    raise SettlementStoreError("synthetic fill audit side is invalid")
                if previous_cash is not None and cash_after != previous_cash + cash_delta:
                    raise SettlementStoreError("synthetic fill cash audit transition mismatch")
                if market_id in previous_holdings and (
                    holding_after != previous_holdings[market_id] + holding_delta
                ):
                    raise SettlementStoreError("synthetic fill holding audit transition mismatch")
                previous_cash = latest_cash = cash_after
                previous_holdings[market_id] = holding_after
                latest_holdings[market_id] = holding_after

        if latest_cash is not None or initial_cash is not None:
            stored_cash = _decimal(
                db.execute("SELECT cash FROM main.account WHERE singleton=1").fetchone()[0],
                "stored cash",
            )
            stored_holdings = {
                market_id:_decimal(quantity,"stored holding")
                for market_id,quantity in db.execute(
                    "SELECT market_id,quantity FROM main.holdings"
                )
            }
            expected_cash = latest_cash if latest_cash is not None else initial_cash
            if stored_cash != expected_cash:
                message = (
                    "account cash does not match fill audit state"
                    if latest_cash is not None else
                    "account cash does not match initial account audit"
                )
                raise SettlementStoreError(message)
            if stored_holdings != latest_holdings:
                raise SettlementStoreError("holdings do not match fill audit state")


    def _verify_reservation_audit_coverage(self, db: sqlite3.Connection) -> None:
        """Reconcile reservation state against fill, allocation and audit records."""
        self._verify_fill_account_state(db)

        allocation_rows = db.execute(
            "SELECT allocation_id,batch_id,fill_id,reservation_id,account_id,market_id,"
            "allocated_quantity,reservation_version "
            "FROM main.reservation_allocations ORDER BY batch_id,reservation_id,allocation_id"
        ).fetchall()
        groups: dict[tuple[str, str], dict[str, object]] = {}
        totals_by_reservation: dict[str, Decimal] = {}
        max_version_by_reservation: dict[str, int] = {}
        totals_by_fill: dict[str, Decimal] = {}
        fill_identity: dict[str, tuple[str, str]] = {}
        for allocation_id,batch_id,fill_id,reservation_id,account_id,market_id,quantity_text,version in allocation_rows:
            if (account_id != self.account_id or not isinstance(reservation_id,str)
                    or not isinstance(batch_id,str) or not isinstance(fill_id,str)
                    or not isinstance(market_id,str) or isinstance(version,bool)
                    or not isinstance(version,int) or version < 1):
                raise SettlementStoreError("reservation allocation identity is invalid")
            quantity = _decimal(quantity_text, "allocation quantity")
            if quantity <= 0:
                raise SettlementStoreError("reservation allocation quantity must be positive")
            key = (reservation_id,batch_id)
            group = groups.setdefault(key, {
                "account_id":account_id,"market_id":market_id,
                "version":version,"quantity":Decimal("0"),
            })
            if (group["account_id"] != account_id or group["market_id"] != market_id
                    or group["version"] != version):
                raise SettlementStoreError("reservation allocation group identity/version mismatch")
            with localcontext() as decimal_context:
                decimal_context.prec = 80
                group["quantity"] = group["quantity"] + quantity
                totals_by_reservation[reservation_id] = (
                    totals_by_reservation.get(reservation_id,Decimal("0")) + quantity
                )
            max_version_by_reservation[reservation_id] = max(
                max_version_by_reservation.get(reservation_id,0),version
            )
            with localcontext() as decimal_context:
                decimal_context.prec = 80
                totals_by_fill[fill_id] = totals_by_fill.get(fill_id,Decimal("0")) + quantity
            identity = (batch_id,market_id)
            if fill_id in fill_identity and fill_identity[fill_id] != identity:
                raise SettlementStoreError("SELL fill allocation identity mismatch")
            fill_identity[fill_id] = identity

        sell_fills = db.execute(
            "SELECT fill_id,batch_id,market_id,quantity,timestamp "
            "FROM main.fills WHERE side='SELL'"
        ).fetchall()
        sell_fill_ids = set()
        for fill_id,batch_id,market_id,quantity_text,timestamp in sell_fills:
            sell_fill_ids.add(fill_id)
            if totals_by_fill.get(fill_id,Decimal("0")) != _decimal(
                quantity_text,"SELL fill quantity"
            ):
                raise SettlementStoreError("SELL fill quantity does not match allocation ledger")
            if fill_identity.get(fill_id) != (batch_id,market_id):
                raise SettlementStoreError("SELL fill batch/market does not match allocation ledger")
            batch = db.execute(
                "SELECT created_at FROM main.batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            if batch is None or batch[0] != timestamp:
                raise SettlementStoreError("SELL fill timestamp does not match its batch")
        if set(totals_by_fill) != sell_fill_ids:
            raise SettlementStoreError("allocation ledger contains missing or non-SELL fill references")

        history: dict[str,list[dict[str,object]]] = {}
        consumption_events: dict[tuple[str,str],dict[str,object]] = {}
        for (event_json,) in db.execute("SELECT event_json FROM main.audit ORDER BY seq"):
            event = json.loads(event_json)
            if not isinstance(event,dict):
                continue
            kind = event.get("kind")
            reservation_id = event.get("reservation_id")
            if kind == "RESERVATION_OUTBOX_ACKNOWLEDGED":
                continue
            if isinstance(kind,str) and kind.startswith("RESERVATION_"):
                if not isinstance(reservation_id,str) or not reservation_id:
                    raise SettlementStoreError("reservation lifecycle audit identity is invalid")
                history.setdefault(reservation_id,[]).append(event)
            if kind == "RESERVATION_QUANTITY_CONSUMED":
                batch_id = event.get("batch_id")
                if not isinstance(reservation_id,str) or not isinstance(batch_id,str):
                    raise SettlementStoreError("reservation consumption audit identity is invalid")
                key = (reservation_id,batch_id)
                if key in consumption_events:
                    raise SettlementStoreError("duplicate reservation consumption audit event")
                consumption_events[key] = event
        if set(groups) != set(consumption_events):
            raise SettlementStoreError("reservation allocation/audit coverage mismatch")

        for (reservation_id,batch_id),group in groups.items():
            event = consumption_events[(reservation_id,batch_id)]
            expected_keys = {
                "kind","reservation_id","account_id","market_id",
                "previous_consumed_quantity","consumed_quantity","allocated_quantity",
                "previous_version","version","batch_id","timestamp",
            }
            if set(event) != expected_keys:
                raise SettlementStoreError("reservation consumption audit event schema mismatch")
            batch = db.execute(
                "SELECT created_at FROM main.batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            previous_version,version,timestamp = (
                event["previous_version"],event["version"],event["timestamp"]
            )
            if (event["account_id"] != self.account_id
                    or event["market_id"] != group["market_id"]
                    or isinstance(previous_version,bool) or not isinstance(previous_version,int)
                    or previous_version != group["version"]
                    or isinstance(version,bool) or not isinstance(version,int)
                    or version != previous_version + 1
                    or isinstance(timestamp,bool) or not isinstance(timestamp,int)
                    or batch is None or timestamp != batch[0]):
                raise SettlementStoreError("reservation consumption audit identity/version mismatch")
            previous_consumed = _decimal(event["previous_consumed_quantity"],"previous consumed quantity")
            consumed = _decimal(event["consumed_quantity"],"consumed quantity")
            allocated = _decimal(event["allocated_quantity"],"audited allocated quantity")
            with localcontext() as decimal_context:
                decimal_context.prec = 80
                expected_consumed = previous_consumed + allocated
            if (previous_consumed < 0 or allocated != group["quantity"]
                    or consumed != expected_consumed):
                raise SettlementStoreError("reservation consumption audit quantity mismatch")

        reservations = db.execute(
            "SELECT reservation_id,account_id,market_id,base_asset,quote_asset,"
            "authorized_quantity,consumed_quantity,created_at,expires_at,version,status "
            "FROM main.reservations"
        ).fetchall()
        if {row[0] for row in reservations} != set(history):
            raise SettlementStoreError("reservation rows do not match lifecycle audit history")
        for (reservation_id,account_id,market_id,base_asset,quote_asset,authorized_text,
             consumed_text,created_at,expires_at,current_version,current_status) in reservations:
            events = history[reservation_id]
            if not events or events[0].get("kind") != "RESERVATION_CREATED":
                raise SettlementStoreError("reservation creation audit event is missing")
            created = events[0]
            created_keys = {
                "kind","reservation_id","account_id","market_id","base_asset","quote_asset",
                "authorized_quantity","created_at","expires_at","version","status",
            }
            if (set(created) != created_keys or created.get("version") != 1
                    or created.get("status") != "PENDING"
                    or created.get("account_id") != account_id
                    or created.get("market_id") != market_id
                    or created.get("base_asset") != base_asset
                    or created.get("quote_asset") != quote_asset
                    or created.get("authorized_quantity") != authorized_text
                    or created.get("created_at") != created_at
                    or created.get("expires_at") != expires_at):
                raise SettlementStoreError("reservation creation audit does not match current record")
            audit_version = 1
            audit_status = "PENDING"
            for event in events[1:]:
                kind = event.get("kind")
                previous_version = event.get("previous_version")
                version = event.get("version")
                if (isinstance(previous_version,bool) or not isinstance(previous_version,int)
                        or isinstance(version,bool) or not isinstance(version,int)
                        or previous_version != audit_version or version != audit_version + 1
                        or event.get("account_id") != account_id
                        or event.get("market_id") != market_id):
                    raise SettlementStoreError("reservation lifecycle audit version chain is invalid")
                if kind == "RESERVATION_AUTHORIZED":
                    if audit_status != "PENDING" or event.get("status") != "ACTIVE":
                        raise SettlementStoreError("reservation authorization audit transition is invalid")
                    audit_status = "ACTIVE"
                elif kind == "RESERVATION_QUANTITY_CONSUMED":
                    if audit_status != "ACTIVE":
                        raise SettlementStoreError("reservation consumption audit requires ACTIVE state")
                elif kind in ("RESERVATION_RELEASED","RESERVATION_CANCELLED","RESERVATION_EXPIRED"):
                    target = kind.removeprefix("RESERVATION_")
                    if (event.get("previous_status") != audit_status
                            or event.get("status") != target):
                        raise SettlementStoreError("reservation terminal audit transition is invalid")
                    audit_status = target
                else:
                    raise SettlementStoreError("unknown reservation lifecycle audit event")
                audit_version = version
            authorized = _decimal(authorized_text,"authorized reservation quantity")
            consumed = _decimal(consumed_text,"consumed reservation quantity")
            total = totals_by_reservation.get(reservation_id,Decimal("0"))
            max_allocation_version = max_version_by_reservation.get(reservation_id,0)
            if (account_id != self.account_id or authorized <= 0 or consumed < 0
                    or consumed > authorized or consumed != total
                    or isinstance(current_version,bool) or not isinstance(current_version,int)
                    or current_version != audit_version or current_status != audit_status
                    or current_version < max_allocation_version + (1 if max_allocation_version else 0)):
                raise SettlementStoreError("reservation state does not match allocation and lifecycle audit")


    def _verify_reservation_outbox_cardinality(
        self, db: sqlite3.Connection, *, batch_id: str | None = None,
    ) -> None:
        """Require exactly one durable outbox row for every reservation allocation."""
        sql = (
            "SELECT a.allocation_id,COUNT(o.idempotency_key) "
            "FROM main.reservation_allocations AS a "
            "LEFT JOIN main.reservation_outbox AS o ON o.allocation_id=a.allocation_id "
        )
        params: tuple[object, ...] = ()
        if batch_id is not None:
            sql += "WHERE a.batch_id=? "
            params = (batch_id,)
        sql += (
            "GROUP BY a.allocation_id "
            "HAVING COUNT(o.idempotency_key)!=1 LIMIT 1"
        )
        invalid = db.execute(sql, params).fetchone()
        if invalid is not None:
            raise SettlementStoreError(
                "reservation allocation must have exactly one outbox row"
            )

    def _verify_reservation_outbox_row(
        self, db: sqlite3.Connection, row: Mapping[str, object],
    ) -> str:
        """Bind a delivery row to its authoritative allocation before receiver I/O."""
        if row.get("account_id") != self.account_id:
            raise SettlementStoreError("reservation outbox account identity mismatch")
        allocation = db.execute(
            "SELECT batch_id,fill_id,reservation_id,account_id,market_id,"
            "allocated_quantity,reservation_version "
            "FROM main.reservation_allocations WHERE allocation_id=?",
            (row.get("allocation_id"),),
        ).fetchone()
        if allocation is None:
            raise SettlementStoreError("reservation outbox allocation record is missing")
        expected = (
            row.get("batch_id"), row.get("fill_id"), row.get("reservation_id"),
            row.get("account_id"), row.get("market_id"), row.get("allocated_quantity"),
            row.get("reservation_version"),
        )
        if allocation != expected:
            raise SettlementStoreError("reservation outbox payload differs from its allocation record")
        fill = db.execute(
            "SELECT batch_id,market_id,side,quantity,timestamp "
            "FROM main.fills WHERE fill_id=?",
            (row.get("fill_id"),),
        ).fetchone()
        if fill is None:
            raise SettlementStoreError("reservation allocation fill record is missing")
        fill_batch,fill_market,fill_side,fill_quantity,fill_timestamp = fill
        if (fill_batch != row.get("batch_id") or fill_market != row.get("market_id")
                or fill_side != "SELL"):
            raise SettlementStoreError("reservation allocation differs from its SELL fill")
        reservation = db.execute(
            "SELECT account_id,market_id,base_asset,quote_asset,authorized_quantity,"
            "consumed_quantity,created_at,expires_at,version "
            "FROM main.reservations WHERE reservation_id=?",
            (row.get("reservation_id"),),
        ).fetchone()
        if reservation is None:
            raise SettlementStoreError("reservation allocation reservation record is missing")
        (reservation_account,reservation_market,base_asset,quote_asset,authorized_text,
         consumed_text,created_at,expires_at,current_version) = reservation
        market = db.execute(
            "SELECT base_asset,quote_asset FROM main.markets WHERE market_id=?",
            (row.get("market_id"),),
        ).fetchone()
        if (reservation_account != self.account_id or reservation_market != row.get("market_id")
                or market != (base_asset,quote_asset)):
            raise SettlementStoreError("reservation allocation differs from its account or market")
        if (isinstance(fill_timestamp,bool) or not isinstance(fill_timestamp,int)
                or isinstance(created_at,bool) or not isinstance(created_at,int)
                or isinstance(expires_at,bool) or not isinstance(expires_at,int)
                or fill_timestamp < 0 or created_at < 0 or expires_at <= created_at
                or fill_timestamp < created_at or fill_timestamp >= expires_at
                or isinstance(current_version,bool) or not isinstance(current_version,int)
                or current_version < 1
                or isinstance(row.get("reservation_version"),bool)
                or not isinstance(row.get("reservation_version"),int)
                or row.get("reservation_version") < 1
                or current_version <= row.get("reservation_version")):
            raise SettlementStoreError("reservation allocation is outside its reservation version or expiry")
        try:
            allocated = _decimal(row.get("allocated_quantity"), "allocated_quantity")
            fill_total = Decimal("0")
            reservation_total = Decimal("0")
            with localcontext() as context:
                context.prec = 80
                for (quantity_text,) in db.execute(
                    "SELECT allocated_quantity FROM main.reservation_allocations WHERE fill_id=?",
                    (row.get("fill_id"),),
                ):
                    fill_total += _decimal(quantity_text, "fill allocation quantity")
                for (quantity_text,) in db.execute(
                    "SELECT allocated_quantity FROM main.reservation_allocations WHERE reservation_id=?",
                    (row.get("reservation_id"),),
                ):
                    reservation_total += _decimal(quantity_text, "reservation allocation quantity")
            fill_quantity_decimal = _decimal(fill_quantity, "SELL fill quantity")
            authorized = _decimal(authorized_text, "reservation authorized quantity")
            consumed = _decimal(consumed_text, "reservation consumed quantity")
            if (allocated <= 0 or fill_total != fill_quantity_decimal
                    or reservation_total != consumed or consumed <= 0
                    or consumed > authorized or authorized <= 0):
                raise SettlementStoreError("reservation allocation totals do not reconcile")
        except (InvalidOperation, TypeError, ValueError, ArithmeticError) as exc:
            raise SettlementStoreError("reservation allocation quantities are invalid") from exc
        payload = {
            "schema": 1,
            "idempotency_key": row.get("idempotency_key"),
            "allocation_id": row.get("allocation_id"),
            "batch_id": row.get("batch_id"),
            "fill_id": row.get("fill_id"),
            "reservation_id": row.get("reservation_id"),
            "account_id": row.get("account_id"),
            "market_id": row.get("market_id"),
            "reservation_version": row.get("reservation_version"),
            "allocated_quantity": row.get("allocated_quantity"),
        }
        from .reservation_outbox_receiver import (
            ReservationInboxError, _canonical_payload,
        )
        try:
            _, digest, receipt = _canonical_payload(payload)
        except (ReservationInboxError, TypeError, ValueError, UnicodeError) as exc:
            raise SettlementStoreError("reservation outbox payload is invalid") from exc
        if digest != row.get("payload_sha256"):
            raise SettlementStoreError("reservation outbox payload hash mismatch")
        return receipt

    def _verify_reservation_outbox_rows(
        self, db: sqlite3.Connection, *, batch_id: str | None = None,
    ) -> None:
        """Revalidate every outbox row and its matching acknowledgement audit event."""
        sql = (
            "SELECT idempotency_key,allocation_id,batch_id,reservation_id,fill_id,"
            "account_id,market_id,reservation_version,allocated_quantity,payload_sha256,"
            "status,receiver_receipt FROM main.reservation_outbox "
        )
        params: tuple[object, ...] = ()
        if batch_id is not None:
            sql += "WHERE batch_id=? "
            params = (batch_id,)
        sql += "ORDER BY idempotency_key"
        fields = (
            "idempotency_key","allocation_id","batch_id","reservation_id","fill_id",
            "account_id","market_id","reservation_version","allocated_quantity","payload_sha256",
        )
        expected_ack_events: dict[str,dict[str,object]] = {}
        for values in db.execute(sql,params):
            row = dict(zip(fields,values[:10]))
            status,stored_receipt = values[10],values[11]
            expected_receipt = self._verify_reservation_outbox_row(db,row)
            if status == "PENDING":
                if stored_receipt is not None:
                    raise SettlementStoreError("pending reservation outbox has an unexpected receipt")
            elif status == "ACKNOWLEDGED":
                if stored_receipt != expected_receipt:
                    raise SettlementStoreError("acknowledged reservation outbox receipt mismatch")
                expected_ack_events[row["idempotency_key"]] = {
                    "kind":"RESERVATION_OUTBOX_ACKNOWLEDGED",
                    "account_id":row["account_id"],
                    "batch_id":row["batch_id"],
                    "allocation_id":row["allocation_id"],
                    "idempotency_key":row["idempotency_key"],
                    "payload_sha256":row["payload_sha256"],
                    "receipt_sha256":hashlib.sha256(stored_receipt.encode("utf-8")).hexdigest(),
                }
            else:
                raise SettlementStoreError("reservation outbox status is invalid")

        actual_ack_events: dict[str,dict[str,object]] = {}
        for (event_json,) in db.execute("SELECT event_json FROM main.audit ORDER BY seq"):
            event = json.loads(event_json)
            if not isinstance(event,dict) or event.get("kind") != "RESERVATION_OUTBOX_ACKNOWLEDGED":
                continue
            key = event.get("idempotency_key")
            if not isinstance(key,str) or not key or key in actual_ack_events:
                raise SettlementStoreError("reservation outbox acknowledgement audit identity is invalid")
            actual_ack_events[key] = event
        if set(actual_ack_events) != set(expected_ack_events):
            raise SettlementStoreError("reservation outbox acknowledgement audit coverage mismatch")
        expected_keys = {
            "kind","account_id","batch_id","allocation_id","idempotency_key",
            "payload_sha256","receipt_sha256",
        }
        for key,expected in expected_ack_events.items():
            actual = actual_ack_events[key]
            if set(actual) != expected_keys or actual != expected:
                raise SettlementStoreError("reservation outbox acknowledgement audit mismatch")

    def pending_reservation_outbox(self, *, limit: int = 100) -> list[dict[str, str]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise SettlementStoreError("limit must be in [1, 1000]")
        with self._connect() as db:
            db.execute("BEGIN")
            self._verify_account_state(db)
            objects = db.execute(
                "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                "('reservations','reservation_allocations','reservation_outbox')"
            ).fetchall()
            expected = {"reservations","reservation_allocations","reservation_outbox"}
            if not objects:
                db.rollback()
                return []
            if any(kind != "table" for kind, _ in objects) or {name for _, name in objects} != expected:
                raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
            self._verify_reservation_outbox_cardinality(db)
            self._verify_reservation_outbox_rows(db)
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
            self._verify_reservation_audit_coverage(db)
            self._verify_reservation_outbox_cardinality(db, batch_id=batch_id)
            self._verify_reservation_outbox_rows(db, batch_id=batch_id)
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
            self._verify_account_state(db)
            objects = db.execute(
                "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
                "('reservations','reservation_allocations','reservation_outbox')"
            ).fetchall()
            expected = {"reservations","reservation_allocations","reservation_outbox"}
            if any(kind != "table" for kind, _ in objects) or {name for _, name in objects} != expected:
                db.rollback()
                raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
            self._verify_reservation_outbox_rows(db)
            row = db.execute(
                "SELECT batch_id,status,receiver_receipt,allocation_id,reservation_id,fill_id,"
                "account_id,market_id,reservation_version,allocated_quantity,payload_sha256 "
                "FROM main.reservation_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise SettlementStoreError("unknown reservation outbox key")
            batch_id = row[0]
            try:
                self._verify_reservation_outbox_cardinality(db, batch_id=batch_id)
            except SettlementStoreError:
                db.rollback()
                raise
            (
                batch_id, status, old_receipt, allocation_id, reservation_id, fill_id,
                account_id, market_id, reservation_version, allocated_quantity, stored_digest,
            ) = row
            outbox_row = {
                "idempotency_key": idempotency_key,
                "allocation_id": allocation_id,
                "batch_id": batch_id,
                "fill_id": fill_id,
                "reservation_id": reservation_id,
                "account_id": account_id,
                "market_id": market_id,
                "reservation_version": reservation_version,
                "allocated_quantity": allocated_quantity,
                "payload_sha256": stored_digest,
            }
            try:
                expected_receipt = self._verify_reservation_outbox_row(db, outbox_row)
            except SettlementStoreError:
                db.rollback()
                raise
            if stored_digest != expected_payload_sha256:
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
                "payload_sha256": stored_digest,
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
            self._verify_account_state(db)
            row = db.execute("SELECT batch_id,status,receiver_receipt FROM main.outbox WHERE idempotency_key=?",
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

    def _verify_account_state(self, db: sqlite3.Connection) -> None:
        """Verify fill accounting and, when enabled, the complete reservation ledger."""
        objects = db.execute(
            "SELECT type,name FROM main.sqlite_master WHERE lower(name) IN "
            "('reservations','reservation_allocations','reservation_outbox')"
        ).fetchall()
        expected = {"reservations","reservation_allocations","reservation_outbox"}
        present = {name for kind,name in objects if kind == "table"}
        if (any(kind != "table" for kind,_ in objects)
                or (present and present != expected)):
            raise SettlementStoreError("reservation schema is partial or contains unexpected objects")
        if present == expected:
            from .reservation_schema_v2 import ensure_reservation_schema_v2
            ensure_reservation_schema_v2(db)
            self._verify_reservation_audit_coverage(db)
        else:
            self._verify_fill_account_state(db)

    def snapshot(self) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN")
            try:
                self._verify_account_state(db)
                account = db.execute(
                    "SELECT cash FROM main.account WHERE singleton=1"
                ).fetchone()
                holdings = dict(db.execute(
                    "SELECT market_id,quantity FROM main.holdings"
                ))
            except Exception:
                db.rollback()
                raise
            else:
                db.rollback()
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
            db.execute(
                "INSERT INTO metadata VALUES('account_initialization_audit','required-v1')"
            )
            db.execute("INSERT INTO account VALUES(1,?,?,?)",
                       (self.account_id, self.currency, opening_cash))
            self._append_audit(db, {
                "kind":"ACCOUNT_INITIALIZED",
                "account_id":self.account_id,
                "currency":self.currency,
                "opening_cash":opening_cash,
            })
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
