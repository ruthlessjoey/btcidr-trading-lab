"""Deterministic multi-market, long-only portfolio allocation reference.

No data fetching, strategy generation, broker, or order execution. Inputs must
already be validated, point-in-time market marks and quote-to-account FX rates.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from collections.abc import Iterable

D = Decimal


class PortfolioError(ValueError):
    pass


def _d(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise PortfolioError(f"{field} must be a finite decimal")
    try:
        result = D(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PortfolioError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise PortfolioError(f"{field} must be finite")
    return result


@dataclass(frozen=True)
class MarketIntent:
    market_id: str
    base_asset: str
    quote_asset: str
    target_weight: Decimal | str | float
    price_quote: Decimal | str | float
    quote_to_account_rate: Decimal | str | float
    price_timestamp: int
    fx_timestamp: int


@dataclass(frozen=True)
class PortfolioPolicy:
    max_gross_exposure: Decimal | str | float = "0.95"
    max_market_weight: Decimal | str | float = "0.25"
    max_base_asset_weight: Decimal | str | float = "0.35"
    max_quote_asset_weight: Decimal | str | float = "0.60"
    max_positions: int = 8
    max_mark_age_seconds: int = 120


@dataclass(frozen=True)
class Allocation:
    market_id: str
    base_asset: str
    quote_asset: str
    weight: Decimal
    quote_notional: Decimal
    base_quantity: Decimal
    reason: str


def allocate_long_only_portfolio(*, account_equity: Decimal | str | float,
                                 account_currency: str,
                                 decision_time: int,
                                 intents: Iterable[MarketIntent],
                                 policy: PortfolioPolicy = PortfolioPolicy()) -> list[Allocation]:
    """Scale desired weights down to deterministic portfolio and concentration caps.

    `quote_to_account_rate` means account-currency units per one quote-currency
    unit. All timestamps are UTC epoch seconds. No leverage or short weights.
    Any stale/missing/invalid input rejects the whole allocation (fail closed).
    Constraints are enforced by monotone proportional scaling; no expected-return
    optimizer or covariance estimate is used here.
    """
    equity = _d(account_equity, "account_equity")
    gross_cap = _d(policy.max_gross_exposure, "max_gross_exposure")
    market_cap = _d(policy.max_market_weight, "max_market_weight")
    base_cap = _d(policy.max_base_asset_weight, "max_base_asset_weight")
    quote_cap = _d(policy.max_quote_asset_weight, "max_quote_asset_weight")
    if equity <= 0 or not account_currency or not account_currency.strip():
        raise PortfolioError("positive account equity and account currency are required")
    if not isinstance(decision_time, int) or isinstance(decision_time, bool) or decision_time < 0:
        raise PortfolioError("decision_time must be a nonnegative UTC epoch second")
    if any(x <= 0 or x > 1 for x in (gross_cap, market_cap, base_cap, quote_cap)):
        raise PortfolioError("all exposure caps must be in (0, 1]")
    if (not isinstance(policy.max_positions, int) or isinstance(policy.max_positions, bool)
            or policy.max_positions < 1 or not isinstance(policy.max_mark_age_seconds, int)
            or isinstance(policy.max_mark_age_seconds, bool) or policy.max_mark_age_seconds < 0):
        raise PortfolioError("position and mark-age limits must be nonnegative integers")

    rows = list(intents)
    if not rows:
        raise PortfolioError("at least one market intent is required")
    ids: set[str] = set()
    clean = []
    for item in rows:
        if not isinstance(item, MarketIntent):
            raise PortfolioError("all intents must be MarketIntent records")
        if (not item.market_id or not item.base_asset or not item.quote_asset
                or item.market_id in ids):
            raise PortfolioError("market identifiers/assets must be nonempty and market IDs unique")
        ids.add(item.market_id)
        weight = _d(item.target_weight, f"{item.market_id}.target_weight")
        price = _d(item.price_quote, f"{item.market_id}.price_quote")
        fx = _d(item.quote_to_account_rate, f"{item.market_id}.quote_to_account_rate")
        if weight < 0 or weight > 1:
            raise PortfolioError("target weights must be long-only and no greater than 100%")
        if price <= 0 or fx <= 0:
            raise PortfolioError("price and FX conversion rate must be positive")
        if item.quote_asset == account_currency and fx != D("1"):
            raise PortfolioError("quote-to-account FX must equal 1 when quote equals account currency")
        for field, stamp in (("price_timestamp", item.price_timestamp), ("fx_timestamp", item.fx_timestamp)):
            if isinstance(stamp, bool) or not isinstance(stamp, int) or stamp < 0 or stamp > decision_time:
                raise PortfolioError(f"{item.market_id}.{field} is invalid or from the future")
            if decision_time - stamp > policy.max_mark_age_seconds:
                raise PortfolioError(f"{item.market_id}.{field} is stale")
        clean.append({"item": item, "weight": min(weight, market_cap),
                      "price": price, "fx": fx, "reason": "TARGET"})

    ranked = sorted(clean, key=lambda r: (-r["weight"], r["item"].market_id))
    keep = {r["item"].market_id for r in ranked[:policy.max_positions]}
    for r in clean:
        if r["item"].market_id not in keep:
            r["weight"] = D("0")
            r["reason"] = "POSITION_COUNT_CAP"
        elif r["weight"] < _d(r["item"].target_weight, "target_weight"):
            r["reason"] = "MARKET_WEIGHT_CAP"

    for _ in range(len(clean) + 3):
        changed = False
        total = sum((r["weight"] for r in clean), D("0"))
        gross_effective = gross_cap - min(D("1e-18"), gross_cap / D("1000000000000"))
        if total > gross_effective:
            factor = gross_effective / total
            for r in clean:
                if r["weight"]:
                    r["weight"] *= factor
                    r["reason"] = "GROSS_EXPOSURE_CAP"
            changed = True
        for field, cap, reason in (("base_asset", base_cap, "BASE_ASSET_CONCENTRATION_CAP"),
                                   ("quote_asset", quote_cap, "QUOTE_CURRENCY_CONCENTRATION_CAP")):
            groups: dict[str, list[dict]] = {}
            for r in clean:
                groups.setdefault(getattr(r["item"], field), []).append(r)
            for group in groups.values():
                total = sum((r["weight"] for r in group), D("0"))
                effective_cap = cap - min(D("1e-18"), cap / D("1000000000000"))
                if total > effective_cap:
                    factor = effective_cap / total
                    for r in group:
                        if r["weight"]:
                            r["weight"] *= factor
                            r["reason"] = reason
                    changed = True
        if not changed:
            break

    final_total = sum((r["weight"] for r in clean), D("0"))
    if final_total >= gross_cap:
        largest = max(clean, key=lambda r: (r["weight"], r["item"].market_id))
        others = sum((r["weight"] for r in clean if r is not largest), D("0"))
        largest["weight"] = max(D("0"), gross_cap - others - min(D("1e-18"), gross_cap / D("1000000000000")))
        largest["reason"] = "GROSS_EXPOSURE_CAP_ROUNDING_ADJUSTMENT"

    result = []
    for r in sorted(clean, key=lambda x: x["item"].market_id):
        item = r["item"]
        weight = r["weight"]
        quote_notional = equity * weight / r["fx"]
        base_qty = quote_notional / r["price"]
        result.append(Allocation(item.market_id, item.base_asset, item.quote_asset,
                                 weight, quote_notional, base_qty, r["reason"]))
    if sum((x.weight for x in result), D("0")) > gross_cap:
        raise AssertionError("gross exposure cap invariant failed")
    return result
