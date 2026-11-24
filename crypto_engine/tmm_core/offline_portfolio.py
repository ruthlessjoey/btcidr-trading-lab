"""Offline synthetic multi-market spot ledger and trusted mark book.

This module is a deterministic research/test foundation only. It has no network,
broker, exchange, account, wallet, or PAPER execution capability.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

D = Decimal


class PortfolioLedgerError(RuntimeError):
    """Invalid synthetic portfolio operation."""


def _d(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise PortfolioLedgerError(f"{field} must be a finite decimal")
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PortfolioLedgerError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise PortfolioLedgerError(f"{field} must be finite")
    return result


@dataclass(frozen=True)
class MarketSpec:
    market_id: str
    base_asset: str
    quote_asset: str


@dataclass(frozen=True)
class SyntheticMark:
    market_id: str
    price: Decimal | str | int | float
    timestamp: int
    max_buy_notional: Decimal | str | int | float


@dataclass(frozen=True)
class SyntheticFill:
    fill_id: str
    market_id: str
    side: str
    quantity: Decimal | str | int | float
    price: Decimal | str | int | float
    fee_quote: Decimal | str | int | float
    timestamp: int


class SyntheticPortfolioLedger:
    """Thread-safe, idempotent, long-only ledger for synthetic fill records.

    The caller is a trusted offline simulator, not a strategy agent. A fill is
    accepted only once, against a registered market and available cash/inventory.
    All quote assets must equal the configured account currency; FX conversion
    is intentionally not guessed or synthesized.
    """

    def __init__(self, *, account_id: str, account_currency: str,
                 opening_cash: object, markets: Mapping[str, MarketSpec]) -> None:
        if not isinstance(account_id, str) or not account_id.strip():
            raise PortfolioLedgerError("account_id is required")
        if not isinstance(account_currency, str) or not account_currency.strip():
            raise PortfolioLedgerError("account_currency is required")
        if not isinstance(markets, Mapping) or not markets:
            raise PortfolioLedgerError("at least one registered market is required")
        cash = _d(opening_cash, "opening_cash")
        if cash <= 0:
            raise PortfolioLedgerError("opening cash must be positive")
        normalized = {}
        for key, spec in markets.items():
            if (not isinstance(spec, MarketSpec) or key != spec.market_id
                    or not spec.base_asset or spec.quote_asset != account_currency):
                raise PortfolioLedgerError("market registry must be exact and quote in account currency")
            normalized[key] = spec
        self.account_id = account_id
        self.account_currency = account_currency
        self._markets = normalized
        self._cash = cash
        self._holdings = {key: D("0") for key in normalized}
        self._marks: dict[str, SyntheticMark] = {}
        self._fills: set[str] = set()
        self._events: list[dict[str, object]] = []
        self._head = "0" * 64
        self._lock = threading.RLock()

    def apply_fill(self, fill: SyntheticFill) -> bool:
        """Apply a definitive synthetic fill exactly once; return False on replay."""
        if not isinstance(fill, SyntheticFill):
            raise PortfolioLedgerError("trusted SyntheticFill record required")
        if not isinstance(fill.fill_id, str) or not fill.fill_id.strip():
            raise PortfolioLedgerError("fill_id is required")
        if fill.market_id not in self._markets:
            raise PortfolioLedgerError("fill market is not registered")
        side = fill.side.upper() if isinstance(fill.side, str) else ""
        if side not in {"BUY", "SELL"}:
            raise PortfolioLedgerError("only BUY and SELL spot fills are supported")
        qty, price, fee = (_d(fill.quantity, "quantity"),
                           _d(fill.price, "price"), _d(fill.fee_quote, "fee_quote"))
        if qty <= 0 or price <= 0 or fee < 0:
            raise PortfolioLedgerError("quantity and price must be positive; fee nonnegative")
        if isinstance(fill.timestamp, bool) or not isinstance(fill.timestamp, int) or fill.timestamp < 0:
            raise PortfolioLedgerError("timestamp must be a nonnegative epoch second")
        notional = qty * price
        with self._lock:
            if fill.fill_id in self._fills:
                return False
            current = self._holdings[fill.market_id]
            if side == "BUY":
                debit = notional + fee
                if debit > self._cash:
                    raise PortfolioLedgerError("insufficient quote cash for BUY fill and fee")
                new_cash, new_qty = self._cash - debit, current + qty
            else:
                if qty > current:
                    raise PortfolioLedgerError("SELL fill exceeds available long inventory")
                proceeds = notional - fee
                if proceeds < 0:
                    raise PortfolioLedgerError("SELL fee exceeds proceeds")
                new_cash, new_qty = self._cash + proceeds, current - qty
            event = {
                "fill_id": fill.fill_id, "market_id": fill.market_id, "side": side,
                "quantity": str(qty), "price": str(price), "fee_quote": str(fee),
                "timestamp": fill.timestamp, "cash_after": str(new_cash),
                "holding_after": str(new_qty),
            }
            encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
            next_hash = hashlib.sha256((self._head + encoded.hex()).encode()).hexdigest()
            self._cash, self._holdings[fill.market_id] = new_cash, new_qty
            self._fills.add(fill.fill_id)
            self._events.append({**event, "previous_hash": self._head, "event_hash": next_hash})
            self._head = next_hash
            return True

    def update_marks(self, marks: Mapping[str, SyntheticMark], *, timestamp: int,
                     max_age_seconds: int = 120) -> None:
        if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
            raise PortfolioLedgerError("timestamp must be a nonnegative epoch second")
        if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool) or max_age_seconds < 0:
            raise PortfolioLedgerError("max_age_seconds must be nonnegative")
        if not isinstance(marks, Mapping) or set(marks) != set(self._markets):
            raise PortfolioLedgerError("marks must exactly cover the registered market universe")
        clean = {}
        for market_id, mark in marks.items():
            if not isinstance(mark, SyntheticMark) or mark.market_id != market_id:
                raise PortfolioLedgerError("mark identity mismatch")
            price, liquidity = _d(mark.price, "mark.price"), _d(mark.max_buy_notional, "mark.max_buy_notional")
            if price <= 0 or liquidity < 0:
                raise PortfolioLedgerError("mark price must be positive and liquidity nonnegative")
            if (not isinstance(mark.timestamp, int) or isinstance(mark.timestamp, bool)
                    or mark.timestamp < 0 or mark.timestamp > timestamp
                    or timestamp - mark.timestamp > max_age_seconds):
                raise PortfolioLedgerError("stale, future, or invalid mark")
            clean[market_id] = SyntheticMark(market_id, price, mark.timestamp, liquidity)
        with self._lock:
            self._marks = clean

    def snapshot_holdings(self, account_id: str) -> Mapping[str, str]:
        with self._lock:
            self._check_account(account_id)
            return {key: str(value) for key, value in self._holdings.items()}

    def snapshot_equity(self, account_id: str) -> str:
        with self._lock:
            self._check_account(account_id)
            if set(self._marks) != set(self._markets):
                raise PortfolioLedgerError("complete fresh marks are required before equity is available")
            return str(self._cash + sum(
                (self._holdings[m] * self._marks[m].price for m in self._markets), D("0")
            ))

    def snapshot_cash(self, account_id: str) -> str:
        with self._lock:
            self._check_account(account_id)
            return str(self._cash)

    def audit_snapshot(self, account_id: str) -> dict[str, object]:
        with self._lock:
            self._check_account(account_id)
            return {
                "account_id": self.account_id, "currency": self.account_currency,
                "cash": str(self._cash),
                "holdings": {key: str(value) for key, value in self._holdings.items()},
                "fills": sorted(self._fills), "events": [dict(event) for event in self._events],
                "head_hash": self._head,
            }

    def verify_audit_chain(self, account_id: str) -> bool:
        snapshot = self.audit_snapshot(account_id)
        previous = "0" * 64
        for event in snapshot["events"]:
            event_body = {k: v for k, v in event.items() if k not in {"previous_hash", "event_hash"}}
            encoded = json.dumps(event_body, sort_keys=True, separators=(",", ":")).encode()
            expected = hashlib.sha256((previous + encoded.hex()).encode()).hexdigest()
            if event.get("previous_hash") != previous or event.get("event_hash") != expected:
                return False
            previous = expected
        return previous == snapshot["head_hash"]

    def _check_account(self, account_id: str) -> None:
        if account_id != self.account_id:
            raise PortfolioLedgerError("account identity mismatch")
