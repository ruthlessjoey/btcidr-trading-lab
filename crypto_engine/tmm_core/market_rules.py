"""Explicit crypto spot tick, lot and minimum-notional rules.

Rules are caller-supplied, versioned market metadata. This module performs no
exchange discovery and never guesses exchange constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR

D = Decimal


class MarketRulesError(ValueError):
    """Raised when market trading increments or order constraints are invalid."""


def _decimal(value: object, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise MarketRulesError(f"{field} must be a finite decimal")
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MarketRulesError(f"{field} must be a finite decimal") from exc
    if not result.is_finite() or (result < 0 if allow_zero else result <= 0):
        qualifier = "nonnegative" if allow_zero else "positive"
        raise MarketRulesError(f"{field} must be finite and {qualifier}")
    return result


@dataclass(frozen=True)
class MarketRules:
    price_tick: Decimal | str | float
    quantity_step: Decimal | str | float
    min_quantity: Decimal | str | float = "0"
    min_notional_quote: Decimal | str | float = "0"

    def validated(self) -> "ValidatedMarketRules":
        return ValidatedMarketRules(
            price_tick=_decimal(self.price_tick, "price_tick"),
            quantity_step=_decimal(self.quantity_step, "quantity_step"),
            min_quantity=_decimal(self.min_quantity, "min_quantity", allow_zero=True),
            min_notional_quote=_decimal(self.min_notional_quote, "min_notional_quote", allow_zero=True),
        )


@dataclass(frozen=True)
class ValidatedMarketRules:
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional_quote: Decimal

    def round_price(self, price: Decimal, side: str) -> Decimal:
        if side not in {"BUY", "SELL"}:
            raise MarketRulesError("side must be BUY or SELL")
        units = price / self.price_tick
        rounding = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
        return units.to_integral_value(rounding=rounding) * self.price_tick

    def round_quantity(self, quantity: Decimal) -> Decimal:
        if quantity < 0:
            raise MarketRulesError("quantity cannot be negative")
        units = (quantity / self.quantity_step).to_integral_value(rounding=ROUND_DOWN)
        return units * self.quantity_step

    def meets_minimums(self, quantity: Decimal, price_quote: Decimal) -> bool:
        return quantity >= self.min_quantity and quantity * price_quote >= self.min_notional_quote
