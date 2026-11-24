"""Fail-closed deterministic exposure and liquidity policy for long-only spot portfolios.

Inputs must be supplied by a trusted account/market-data service. This module is
offline and has no broker, exchange, network, or strategy-agent authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

D = Decimal


class ExposurePolicyError(ValueError):
    """Invalid or incomplete trusted exposure input."""


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ExposurePolicyError(f"{field} must be a finite decimal")
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ExposurePolicyError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise ExposurePolicyError(f"{field} must be finite")
    return result


@dataclass(frozen=True)
class ExposureMark:
    market_id: str
    base_asset: str
    quote_asset: str
    unit_value_account: Decimal | str | int | float
    timestamp: int
    max_buy_notional_account: Decimal | str | int | float


@dataclass(frozen=True)
class ExposurePolicy:
    max_gross_exposure: Decimal | str | int | float = "0.95"
    max_market_weight: Decimal | str | int | float = "0.25"
    max_base_asset_weight: Decimal | str | int | float = "0.35"
    max_quote_asset_weight: Decimal | str | int | float = "0.60"
    max_mark_age_seconds: int = 120


def authorize_exposure(*, account_equity: object, holdings: Mapping[str, object],
                        proposals: Mapping[str, object], marks: Mapping[str, ExposureMark],
                        timestamp: int, policy: ExposurePolicy = ExposurePolicy()
                        ) -> dict[str, Decimal]:
    """Return permitted base-quantity deltas.

    Existing holdings and all proposal markets require authoritative marks.
    Sells are capped to inventory. Buys are first liquidity-capped, then scaled
    uniformly to the largest feasible amount satisfying gross, per-market,
    base-asset concentration, and quote-asset concentration limits. If existing
    exposure already breaches policy, new buys are blocked while risk-reducing
    sells remain permitted. Missing, stale, future, duplicate, or malformed
    evidence rejects the whole request.
    """
    equity = _decimal(account_equity, "account_equity")
    if equity <= 0:
        raise ExposurePolicyError("account equity must be positive")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise ExposurePolicyError("timestamp must be a nonnegative UTC epoch second")
    caps = {
        "gross": _decimal(policy.max_gross_exposure, "max_gross_exposure"),
        "market": _decimal(policy.max_market_weight, "max_market_weight"),
        "base": _decimal(policy.max_base_asset_weight, "max_base_asset_weight"),
        "quote": _decimal(policy.max_quote_asset_weight, "max_quote_asset_weight"),
    }
    if any(v <= 0 or v > 1 for v in caps.values()):
        raise ExposurePolicyError("exposure caps must be in (0, 1]")
    if (isinstance(policy.max_mark_age_seconds, bool)
            or not isinstance(policy.max_mark_age_seconds, int)
            or policy.max_mark_age_seconds < 0):
        raise ExposurePolicyError("max_mark_age_seconds must be a nonnegative integer")
    if not isinstance(holdings, Mapping) or not isinstance(proposals, Mapping) or not isinstance(marks, Mapping):
        raise ExposurePolicyError("holdings, proposals, and marks must be mappings")
    market_ids = set(holdings) | set(proposals)
    if not market_ids or market_ids != set(marks):
        raise ExposurePolicyError("trusted marks must exactly cover held and proposed markets")

    qty: dict[str, Decimal] = {}
    delta: dict[str, Decimal] = {}
    clean_marks: dict[str, tuple[str, str, Decimal, Decimal]] = {}
    for market_id in market_ids:
        mark = marks[market_id]
        if (not isinstance(mark, ExposureMark) or mark.market_id != market_id
                or not mark.base_asset or not mark.quote_asset):
            raise ExposurePolicyError(f"{market_id}: invalid or mismatched exposure mark")
        if (isinstance(mark.timestamp, bool) or not isinstance(mark.timestamp, int)
                or mark.timestamp < 0 or mark.timestamp > timestamp
                or timestamp - mark.timestamp > policy.max_mark_age_seconds):
            raise ExposurePolicyError(f"{market_id}: mark is stale, future, or invalid")
        unit = _decimal(mark.unit_value_account, f"{market_id}.unit_value_account")
        liquidity = _decimal(mark.max_buy_notional_account, f"{market_id}.max_buy_notional_account")
        if unit <= 0 or liquidity < 0:
            raise ExposurePolicyError(f"{market_id}: unit value must be positive and liquidity nonnegative")
        h = _decimal(holdings.get(market_id, "0"), f"{market_id}.holding")
        d = _decimal(proposals.get(market_id, "0"), f"{market_id}.proposal")
        if h < 0:
            raise ExposurePolicyError(f"{market_id}: short inventory is prohibited")
        qty[market_id] = h
        delta[market_id] = min(d, h) if d < 0 else d
        clean_marks[market_id] = (mark.base_asset, mark.quote_asset, unit, liquidity)

    # Liquidity cap each positive proposal before evaluating portfolio limits.
    buys = {}
    for market_id, value in delta.items():
        if value <= 0:
            buys[market_id] = D("0")
            continue
        _, _, unit, liquidity = clean_marks[market_id]
        buys[market_id] = min(value, liquidity / unit)

    def feasible(scale: Decimal) -> bool:
        projected = {m: max(D("0"), qty[m] + (delta[m] if delta[m] < 0 else buys[m] * scale))
                     for m in market_ids}
        values = {m: projected[m] * clean_marks[m][2] for m in market_ids}
        if sum(values.values(), D("0")) > equity * caps["gross"]:
            return False
        by_market: dict[str, Decimal] = {}
        by_base: dict[str, Decimal] = {}
        by_quote: dict[str, Decimal] = {}
        for m, value in values.items():
            base, quote, _, _ = clean_marks[m]
            by_market[m] = value
            by_base[base] = by_base.get(base, D("0")) + value
            by_quote[quote] = by_quote.get(quote, D("0")) + value
        if any(v > equity * caps["market"] for v in by_market.values()):
            return False
        if any(v > equity * caps["base"] for v in by_base.values()):
            return False
        if any(v > equity * caps["quote"] for v in by_quote.values()):
            return False
        return True

    if not feasible(D("0")):
        scale = D("0")
    else:
        low, high = D("0"), D("1")
        for _ in range(80):
            mid = (low + high) / D("2")
            if feasible(mid):
                low = mid
            else:
                high = mid
        scale = low

    result = {}
    for market_id in sorted(market_ids):
        original = delta[market_id]
        result[market_id] = original if original <= 0 else buys[market_id] * scale
    return result
