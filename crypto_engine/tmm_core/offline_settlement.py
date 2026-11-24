"""Broker-free offline execution and trusted settlement controller.

This is a deterministic synthetic-bar simulator. It does not connect to venues,
submit orders, access accounts, or enable PAPER/LIVE. The controller is trusted
composition-root code and must never be exposed to strategy agents.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from typing import Protocol

from .offline_portfolio import (
    PortfolioLedgerError, SyntheticFill, SyntheticPortfolioLedger,
)


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
                 rules: Mapping[str, ExecutionRules]) -> None:
        if not isinstance(ledger, SyntheticPortfolioLedger):
            raise ValueError("synthetic offline ledger required")
        if not isinstance(rules, Mapping) or not rules:
            raise ValueError("execution rules are required")
        self._proposal_client = proposal_client
        self._settlement = settlement
        self._ledger = ledger
        self._rules = dict(rules)
        self._lock = threading.RLock()

    def process(self, *, proposals: Mapping[str, object],
                bars: Mapping[str, SyntheticBar], timestamp: int) -> tuple[ExecutionResult, ...]:
        """Authorize once, execute against supplied synthetic bars, then settle sells."""
        if not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0:
            raise ValueError("timestamp must be a nonnegative epoch second")
        if not isinstance(proposals, Mapping) or not proposals:
            raise ValueError("non-empty proposals are required")
        if not isinstance(bars, Mapping) or set(bars) != set(proposals):
            raise ValueError("bars must exactly cover proposed markets")
        with self._lock:
            authorization = self._proposal_client.propose(proposals=proposals, timestamp=timestamp)
            if not isinstance(authorization, Mapping):
                raise ValueError("risk gateway returned malformed authorization")
            permitted = authorization.get("permitted_deltas")
            if not isinstance(permitted, Mapping) or set(permitted) != set(proposals):
                raise ValueError("risk gateway authorization does not exactly cover proposals")
            staged = []
            for market_id in sorted(proposals):
                if market_id not in self._rules:
                    raise ValueError(f"execution rules missing for {market_id}")
                bar = bars[market_id]
                if not isinstance(bar, SyntheticBar) or bar.market_id != market_id or bar.timestamp != timestamp:
                    raise ValueError("bar identity or timestamp mismatch")
                o, h, l, c, volume = (_d(bar.open, "open"), _d(bar.high, "high"),
                                      _d(bar.low, "low"), _d(bar.close, "close"),
                                      _d(bar.volume, "volume"))
                if min(o, h, l, c) <= 0 or volume < 0 or h < max(o, c, l) or l > min(o, c, h):
                    raise ValueError("invalid OHLCV bar")
                step, tick, fee_bps, spread_bps, slip_bps, participation = self._rules[market_id].validated()
                delta = _d(permitted[market_id], "permitted_delta")
                if delta == 0:
                    continue
                side = "BUY" if delta > 0 else "SELL"
                requested = abs(delta)
                capacity = _floor_step(volume * participation, step)
                qty = min(_floor_step(requested, step), capacity)
                if qty <= 0:
                    staged.append((market_id, side, requested, D("0"), None, D("0"), step))
                    continue
                adverse = (spread_bps + slip_bps) / D("10000")
                raw_price = o * (D("1") + adverse if side == "BUY" else D("1") - adverse)
                price = ((raw_price / tick).to_integral_value(rounding=ROUND_UP if side == "BUY" else ROUND_DOWN) * tick)
                if price <= 0:
                    raise ValueError("execution price rounded to nonpositive value")
                fee = qty * price * fee_bps / D("10000")
                staged.append((market_id, side, requested, qty, price, fee, step))

            results = []
            for market_id, side, requested, qty, price, fee, _ in staged:
                if qty > 0 and price is not None:
                    fill = SyntheticFill(
                        fill_id=f"sim:{timestamp}:{market_id}:{side}",
                        market_id=market_id, side=side, quantity=qty,
                        price=price, fee_quote=fee, timestamp=timestamp,
                    )
                    self._ledger.apply_fill(fill)
                if side == "SELL":
                    # Settlement releases the entire reservation, including unfilled
                    # quantity caused by bar-volume limits or zero executable size.
                    self._settlement.settle_sell(
                        market_id=market_id, authorized_quantity=requested,
                        filled_quantity=qty, timestamp=timestamp,
                    )
                results.append(ExecutionResult(
                    market_id, side, requested, requested, qty, price, fee,
                    "FILLED" if qty == requested else ("PARTIAL" if qty > 0 else "UNFILLED"),
                ))
            return tuple(results)
