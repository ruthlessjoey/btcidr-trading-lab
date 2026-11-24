"""Broker-free offline execution and trusted settlement controller.

This is a deterministic synthetic-bar simulator. It does not connect to venues,
submit orders, access accounts, or enable PAPER/LIVE. The controller is trusted
composition-root code and must never be exposed to strategy agents.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from typing import Protocol

from .offline_portfolio import (
    D, SyntheticFill, SyntheticPortfolioLedger,
)
from .offline_batch_journal import SQLiteBatchJournal


def _d(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite")
    return result


def _floor_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


@dataclass(frozen=True)
class ExecutionRules:
    quantity_step: Decimal | str | int | float
    price_tick: Decimal | str | int | float
    fee_bps: Decimal | str | int | float = "10"
    half_spread_bps: Decimal | str | int | float = "5"
    slippage_bps: Decimal | str | int | float = "5"
    max_volume_participation: Decimal | str | int | float = "0.05"

    def validated(self) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
        step, tick = _d(self.quantity_step, "quantity_step"), _d(self.price_tick, "price_tick")
        fee, spread = _d(self.fee_bps, "fee_bps"), _d(self.half_spread_bps, "half_spread_bps")
        slip, participation = _d(self.slippage_bps, "slippage_bps"), _d(self.max_volume_participation, "max_volume_participation")
        if step <= 0 or tick <= 0:
            raise ValueError("quantity step and price tick must be positive")
        if min(fee, spread, slip) < 0 or max(fee, spread, slip) > 10000:
            raise ValueError("fee, spread and slippage bps must be in [0, 10000]")
        if participation <= 0 or participation > 1:
            raise ValueError("volume participation must be in (0, 1]")
        return step, tick, fee, spread, slip, participation


@dataclass(frozen=True)
class SyntheticBar:
    market_id: str
    timestamp: int
    open: Decimal | str | int | float
    high: Decimal | str | int | float
    low: Decimal | str | int | float
    close: Decimal | str | int | float
    volume: Decimal | str | int | float


@dataclass(frozen=True)
class ExecutionResult:
    market_id: str
    side: str
    requested_quantity: Decimal
    authorized_quantity: Decimal
    filled_quantity: Decimal
    fill_price: Decimal | None
    fee_quote: Decimal
    status: str


class ProposalClient(Protocol):
    def propose(self, *, proposals: Mapping[str, object], timestamp: int) -> Mapping[str, object]: ...


class SellSettlement(Protocol):
    def settle_sell(self, *, market_id: str, authorized_quantity: object,
                    filled_quantity: object, timestamp: int) -> None: ...


class OfflineSettlementController:
    """Trusted simulator-only coordinator for risk proposals, fills and settlement."""

    def __init__(self, *, proposal_client: ProposalClient,
                 settlement: SellSettlement,
                 ledger: SyntheticPortfolioLedger,
                 rules: Mapping[str, ExecutionRules],
                 batch_journal: SQLiteBatchJournal) -> None:
        if not isinstance(ledger, SyntheticPortfolioLedger):
            raise ValueError("synthetic offline ledger required")
        if not isinstance(rules, Mapping) or not rules:
            raise ValueError("execution rules are required")
        if not isinstance(batch_journal, SQLiteBatchJournal):
            raise ValueError("durable SQLite batch journal is required")
        self._proposal_client = proposal_client
        self._settlement = settlement
        self._ledger = ledger
        self._rules = dict(rules)
        self._batch_journal = batch_journal
        self._lock = threading.RLock()

    def process(self, *, batch_id: str, proposals: Mapping[str, object],
                bars: Mapping[str, SyntheticBar], timestamp: int) -> tuple[ExecutionResult, ...]:
        """Process one trusted batch with durable fail-closed replay tracking."""
        if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 256:
            raise ValueError("batch_id must be a non-empty trusted identifier up to 256 characters")
        if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
            raise ValueError("timestamp must be a nonnegative epoch second")
        if not isinstance(proposals, Mapping) or not proposals:
            raise ValueError("non-empty proposals are required")
        if not all(isinstance(m, str) and m.strip() for m in proposals):
            raise ValueError("proposal market IDs must be non-empty strings")
        if not isinstance(bars, Mapping) or set(bars) != set(proposals):
            raise ValueError("bars must exactly cover proposed markets")

        # Validate caller-controlled bars and rules before the stateful risk call.
        clean = {}
        for market_id in sorted(proposals):
            if market_id not in self._rules:
                raise ValueError(f"execution rules missing for {market_id}")
            requested_delta = _d(proposals[market_id], "proposal_delta")
            bar = bars[market_id]
            if not isinstance(bar, SyntheticBar) or bar.market_id != market_id or bar.timestamp != timestamp:
                raise ValueError("bar identity or timestamp mismatch")
            o, h, l, c, volume = (_d(bar.open, "open"), _d(bar.high, "high"),
                                  _d(bar.low, "low"), _d(bar.close, "close"),
                                  _d(bar.volume, "volume"))
            if min(o, h, l, c) <= 0 or volume < 0 or h < max(o, c, l) or l > min(o, c, h):
                raise ValueError("invalid OHLCV bar")
            self._rules[market_id].validated()
            clean[market_id] = (requested_delta, o, volume)

        request_record = {
            "timestamp": timestamp,
            "proposals": {key: str(proposals[key]) for key in sorted(proposals)},
            "bars": {key: {
                "timestamp": bars[key].timestamp, "open": str(bars[key].open),
                "high": str(bars[key].high), "low": str(bars[key].low),
                "close": str(bars[key].close), "volume": str(bars[key].volume),
            } for key in sorted(bars)},
            "rules": {key: {
                "quantity_step": str(self._rules[key].quantity_step),
                "price_tick": str(self._rules[key].price_tick),
                "fee_bps": str(self._rules[key].fee_bps),
                "half_spread_bps": str(self._rules[key].half_spread_bps),
                "slippage_bps": str(self._rules[key].slippage_bps),
                "max_volume_participation": str(self._rules[key].max_volume_participation),
            } for key in sorted(proposals)},
        }
        request_hash = hashlib.sha256(
            json.dumps(request_record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        with self._lock:
            previous = self._batch_journal.claim(batch_id, request_hash)
            if previous is not None:
                return tuple(ExecutionResult(
                    item["market_id"], item["side"], D(item["requested_quantity"]),
                    D(item["authorized_quantity"]), D(item["filled_quantity"]),
                    None if item["fill_price"] is None else D(item["fill_price"]),
                    D(item["fee_quote"]), item["status"],
                ) for item in previous)
            batch_digest = hashlib.sha256(batch_id.encode("utf-8")).hexdigest()
            authorization = self._proposal_client.propose(proposals=proposals, timestamp=timestamp)
            if not isinstance(authorization, Mapping):
                raise ValueError("risk gateway returned malformed authorization")
            permitted = authorization.get("permitted_deltas")
            if not isinstance(permitted, Mapping) or set(permitted) != set(proposals):
                raise ValueError("risk gateway authorization does not exactly cover proposals")
            staged = []
            total_buy_debit = D("0")
            holdings = self._ledger.snapshot_holdings(self._ledger.account_id)
            for market_id in sorted(proposals):
                requested_delta, o, volume = clean[market_id]
                step, tick, fee_bps, spread_bps, slip_bps, participation = self._rules[market_id].validated()
                delta = _d(permitted[market_id], "permitted_delta")
                if delta != 0 and (requested_delta == 0 or (delta > 0) != (requested_delta > 0)
                                   or abs(delta) > abs(requested_delta)):
                    raise ValueError("authorization must preserve direction and not exceed requested size")
                if delta == 0:
                    continue
                side = "BUY" if delta > 0 else "SELL"
                requested, authorized = abs(requested_delta), abs(delta)
                capacity = _floor_step(volume * participation, step)
                qty = min(_floor_step(authorized, step), capacity)
                if qty <= 0:
                    staged.append((market_id, side, requested, authorized, D("0"), None, D("0")))
                    continue
                adverse = (spread_bps + slip_bps) / D("10000")
                raw_price = o * (D("1") + adverse if side == "BUY" else D("1") - adverse)
                price = ((raw_price / tick).to_integral_value(rounding=ROUND_UP if side == "BUY" else ROUND_DOWN) * tick)
                if price <= 0:
                    raise ValueError("execution price rounded to nonpositive value")
                fee = qty * price * fee_bps / D("10000")
                if side == "BUY":
                    total_buy_debit += qty * price + fee
                elif qty > _d(holdings[market_id], "held_inventory"):
                    raise ValueError("synthetic SELL fill exceeds pre-batch inventory")
                staged.append((market_id, side, requested, authorized, qty, price, fee))

            if total_buy_debit > _d(self._ledger.snapshot_cash(self._ledger.account_id), "available_cash"):
                raise ValueError("synthetic BUY batch exceeds available quote cash")

            results = []
            for market_id, side, requested, authorized, qty, price, fee in staged:
                if qty > 0 and price is not None:
                    fill = SyntheticFill(
                        fill_id=f"sim:{batch_digest}:{market_id}:{side}",
                        market_id=market_id, side=side, quantity=qty,
                        price=price, fee_quote=fee, timestamp=timestamp,
                    )
                    self._ledger.apply_fill(fill)
                if side == "SELL":
                    # Settlement releases the entire reservation, including unfilled
                    # quantity caused by bar-volume limits or zero executable size.
                    self._settlement.settle_sell(
                        market_id=market_id, authorized_quantity=authorized,
                        filled_quantity=qty, timestamp=timestamp,
                    )
                results.append(ExecutionResult(
                    market_id, side, requested, authorized, qty, price, fee,
                    "FILLED" if qty == authorized else ("PARTIAL" if qty > 0 else "UNFILLED"),
                ))
            journal_results = [{
                "market_id": item.market_id, "side": item.side,
                "requested_quantity": str(item.requested_quantity),
                "authorized_quantity": str(item.authorized_quantity),
                "filled_quantity": str(item.filled_quantity),
                "fill_price": None if item.fill_price is None else str(item.fill_price),
                "fee_quote": str(item.fee_quote), "status": item.status,
            } for item in results]
            self._batch_journal.complete(batch_id, request_hash, journal_results)
            return tuple(results)
