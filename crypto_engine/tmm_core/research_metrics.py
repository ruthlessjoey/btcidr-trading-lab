"""Evidence-oriented metrics for offline, long-only spot backtests.

All trade outcomes are FIFO matched, net of the entry and exit fees already
recorded in each synthetic fill. Open inventory is reported separately and is
never counted as a win or loss. Tail metrics are withheld for short samples.
This module does not fetch data, select strategies, or authorize orders.
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from decimal import Decimal, DecimalException, localcontext
from math import ceil


D = Decimal
_MAX_NUMERIC_TEXT = 256
_MAX_ADJUSTED_EXPONENT = 512


class ResearchMetricsError(ValueError):
    """Raised when a backtest result cannot support reliable metrics."""


def _number(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ResearchMetricsError(f"{field} must be a finite decimal")
    text = str(value)
    if not text or len(text) > _MAX_NUMERIC_TEXT:
        raise ResearchMetricsError(f"{field} exceeds the numeric input bound")
    try:
        number = D(text)
    except (DecimalException, TypeError, ValueError) as exc:
        raise ResearchMetricsError(f"{field} must be a finite decimal") from exc
    if not number.is_finite():
        raise ResearchMetricsError(f"{field} must be finite")
    if not number.is_zero() and abs(number.adjusted()) > _MAX_ADJUSTED_EXPONENT:
        raise ResearchMetricsError(f"{field} magnitude exceeds the supported bound")
    return number


def _timestamp(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResearchMetricsError(f"{field} must be a nonnegative integer")
    return value


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _trade_metrics(fills: object) -> dict[str, object]:
    if not isinstance(fills, Sequence) or isinstance(fills, (str, bytes)):
        raise ResearchMetricsError("fills must be a sequence")
    queues: dict[str, deque[dict[str, Decimal]]] = defaultdict(deque)
    segments: list[dict[str, Decimal]] = []
    previous_timestamp = -1

    for index, fill in enumerate(fills):
        if not isinstance(fill, Mapping):
            raise ResearchMetricsError(f"fill {index} must be a mapping")
        timestamp = _timestamp(fill.get("timestamp"), f"fills[{index}].timestamp")
        if timestamp < previous_timestamp:
            raise ResearchMetricsError("fills must be in nondecreasing timestamp order")
        previous_timestamp = timestamp
        market_id = fill.get("market_id")
        if not isinstance(market_id, str) or not market_id.strip():
            raise ResearchMetricsError(f"fills[{index}].market_id is required")
        side = fill.get("side")
        if side not in {"BUY", "SELL"}:
            raise ResearchMetricsError(f"fills[{index}].side must be BUY or SELL")
        quantity = _number(fill.get("quantity"), f"fills[{index}].quantity")
        price = _number(fill.get("price_account"), f"fills[{index}].price_account")
        fee = _number(fill.get("fee_account"), f"fills[{index}].fee_account")
        if quantity <= 0 or price <= 0 or fee < 0:
            raise ResearchMetricsError(f"fill {index} quantity/price/fee is outside the accepted range")

        if side == "BUY":
            # Allocate the paid entry fee proportionally to each FIFO-matched unit.
            unit_cost = price + fee / quantity
            queues[market_id].append({"quantity": quantity, "unit_cost": unit_cost})
            continue

        sale_unit_proceeds = price - fee / quantity
        remaining = quantity
        queue = queues[market_id]
        while remaining > 0:
            if not queue:
                raise ResearchMetricsError(
                    f"SELL fill {index} exceeds recorded BUY inventory for {market_id}"
                )
            lot = queue[0]
            matched = min(remaining, lot["quantity"])
            cost_basis = matched * lot["unit_cost"]
            proceeds = matched * sale_unit_proceeds
            segments.append({
                "quantity": matched,
                "cost_basis": cost_basis,
                "proceeds": proceeds,
                "pnl": proceeds - cost_basis,
            })
            remaining -= matched
            lot["quantity"] -= matched
            if lot["quantity"] == 0:
                queue.popleft()

    winners = [item for item in segments if item["pnl"] > 0]
    losers = [item for item in segments if item["pnl"] < 0]
    breakeven = [item for item in segments if item["pnl"] == 0]
    gross_profit = sum((item["pnl"] for item in winners), D("0"))
    gross_loss = -sum((item["pnl"] for item in losers), D("0"))
    realized_pnl = gross_profit - gross_loss
    total_cost = sum((item["cost_basis"] for item in segments), D("0"))
    total_closed_quantity = sum((item["quantity"] for item in segments), D("0"))
    match_count = len(segments)

    open_inventory: dict[str, dict[str, str]] = {}
    for market_id in sorted(queues):
        open_quantity = sum((lot["quantity"] for lot in queues[market_id]), D("0"))
        open_cost = sum((lot["quantity"] * lot["unit_cost"] for lot in queues[market_id]), D("0"))
        if open_quantity > 0:
            open_inventory[market_id] = {
                "quantity": _fmt(open_quantity),
                "cost_basis_account": _fmt(open_cost),
            }

    return {
        "fill_count": len(fills),
        "closed_lot_matches": match_count,
        "winning_matches": len(winners),
        "losing_matches": len(losers),
        "breakeven_matches": len(breakeven),
        "win_rate": _fmt(D(len(winners)) / D(match_count)) if match_count else None,
        "average_win_pnl_account": _fmt(
            gross_profit / D(len(winners)) if winners else None
        ),
        "average_loss_pnl_account": _fmt(
            -gross_loss / D(len(losers)) if losers else None
        ),
        "gross_profit_account": _fmt(gross_profit),
        "gross_loss_account": _fmt(gross_loss),
        "realized_net_pnl_account": _fmt(realized_pnl),
        "net_expectancy_per_closed_match_account": _fmt(
            realized_pnl / D(match_count) if match_count else None
        ),
        "profit_factor": _fmt(gross_profit / gross_loss) if gross_loss else None,
        "profit_factor_status": (
            "DEFINED" if gross_loss else
            "NO_CLOSED_LOSSES" if winners else "NO_CLOSED_MATCHES"
        ),
        "realized_return_on_closed_cost_basis": _fmt(
            realized_pnl / total_cost if total_cost else None
        ),
        "closed_quantity": _fmt(total_closed_quantity),
        "open_inventory": open_inventory,
        "open_market_count": len(open_inventory),
        "trade_metric_basis": "FIFO matched BUY/SELL lot segments; entry and exit fees included; execution prices include modeled spread/slippage",
    }


def _equity_metrics(curve: object) -> dict[str, object]:
    if not isinstance(curve, Sequence) or isinstance(curve, (str, bytes)) or len(curve) < 2:
        raise ResearchMetricsError("equity_curve must contain at least two observations")
    timestamps: list[int] = []
    values: list[Decimal] = []
    for index, row in enumerate(curve):
        if not isinstance(row, Mapping):
            raise ResearchMetricsError(f"equity_curve[{index}] must be a mapping")
        timestamp = _timestamp(row.get("timestamp"), f"equity_curve[{index}].timestamp")
        equity = _number(row.get("equity"), f"equity_curve[{index}].equity")
        if equity <= 0:
            raise ResearchMetricsError("equity observations must remain positive")
        if timestamps and timestamp <= timestamps[-1]:
            raise ResearchMetricsError("equity_curve timestamps must be strictly increasing")
        timestamps.append(timestamp)
        values.append(equity)

    peak = values[0]
    max_drawdown = D("0")
    returns: list[Decimal] = []
    for index, value in enumerate(values):
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak)
        if index:
            returns.append(value / values[index - 1] - D("1"))
    worst_return = min(returns)
    tail_ready = len(returns) >= 20
    if tail_ready:
        worst_count = max(1, ceil(len(returns) * 0.05))
        ordered = sorted(returns)
        lower_tail = ordered[:worst_count]
        lower_5pct = lower_tail[-1]
        expected_shortfall = sum(lower_tail, D("0")) / D(len(lower_tail))
    else:
        lower_5pct = None
        expected_shortfall = None

    return {
        "observation_count": len(values),
        "period_return_count": len(returns),
        "max_drawdown": _fmt(max_drawdown),
        "worst_period_return": _fmt(worst_return),
        "empirical_lower_5pct_period_return": _fmt(lower_5pct),
        "expected_shortfall_5pct_period_return": _fmt(expected_shortfall),
        "tail_metrics_status": "AVAILABLE_20_PLUS_PERIODS" if tail_ready else "INSUFFICIENT_PERIODS_REQUIRES_20_PLUS",
    }


def _exposure_metrics(curve: object) -> dict[str, object]:
    if curve is None:
        return {"exposure_metrics_status": "NOT_RECORDED"}
    if not isinstance(curve, Sequence) or isinstance(curve, (str, bytes)) or not curve:
        raise ResearchMetricsError("exposure_curve must be a non-empty sequence when supplied")

    cash_weights: list[Decimal] = []
    gross_weights: list[Decimal] = []
    market_weights_by_id: dict[str, list[Decimal]] = defaultdict(list)
    previous_timestamp = -1
    market_universe: set[str] | None = None

    for index, row in enumerate(curve):
        if not isinstance(row, Mapping):
            raise ResearchMetricsError(f"exposure_curve[{index}] must be a mapping")
        timestamp = _timestamp(row.get("timestamp"), f"exposure_curve[{index}].timestamp")
        if timestamp <= previous_timestamp:
            raise ResearchMetricsError("exposure_curve timestamps must be strictly increasing")
        previous_timestamp = timestamp
        equity = _number(row.get("equity"), f"exposure_curve[{index}].equity")
        cash = _number(row.get("cash"), f"exposure_curve[{index}].cash")
        market_values = row.get("market_values")
        market_weights = row.get("market_weights")
        if equity <= 0 or cash < 0 or not isinstance(market_values, Mapping) or not isinstance(market_weights, Mapping):
            raise ResearchMetricsError(f"exposure_curve[{index}] contains invalid values")
        keys = set(market_values)
        if (keys != set(market_weights)
                or any(not isinstance(key, str) or not key.strip() for key in keys)):
            raise ResearchMetricsError(f"exposure_curve[{index}] market maps do not align")
        if market_universe is None:
            market_universe = keys
        elif keys != market_universe:
            raise ResearchMetricsError("exposure_curve market universe changed between observations")
        values: dict[str, Decimal] = {}
        weights: dict[str, Decimal] = {}
        for market_id in sorted(keys):
            value = _number(market_values[market_id], f"exposure_curve[{index}].market_values[{market_id}]")
            weight = _number(market_weights[market_id], f"exposure_curve[{index}].market_weights[{market_id}]")
            if value < 0 or weight < 0 or weight != value / equity:
                raise ResearchMetricsError(f"exposure_curve[{index}] has inconsistent market weights")
            values[market_id] = value
            weights[market_id] = weight
        invested = sum(values.values(), D("0"))
        if cash + invested != equity:
            raise ResearchMetricsError(f"exposure_curve[{index}] cash and market values do not reconcile to equity")
        gross = invested / equity
        cash_weight = cash / equity
        if _number(row.get("gross_exposure"), f"exposure_curve[{index}].gross_exposure") != gross:
            raise ResearchMetricsError(f"exposure_curve[{index}] gross exposure does not reconcile")
        if _number(row.get("cash_weight"), f"exposure_curve[{index}].cash_weight") != cash_weight:
            raise ResearchMetricsError(f"exposure_curve[{index}] cash weight does not reconcile")
        gross_weights.append(gross)
        cash_weights.append(cash_weight)
        for market_id, weight in weights.items():
            market_weights_by_id[market_id].append(weight)

    count = D(len(curve))
    return {
        "exposure_metrics_status": "AVAILABLE",
        "average_cash_weight": _fmt(sum(cash_weights, D("0")) / count),
        "minimum_cash_weight": _fmt(min(cash_weights)),
        "maximum_gross_exposure": _fmt(max(gross_weights)),
        "average_gross_exposure": _fmt(sum(gross_weights, D("0")) / count),
        "average_market_weights": {
            market_id: _fmt(sum(weights, D("0")) / count)
            for market_id, weights in sorted(market_weights_by_id.items())
        },
        "maximum_market_weights": {
            market_id: _fmt(max(weights))
            for market_id, weights in sorted(market_weights_by_id.items())
        },
        "exposure_observation_count": len(curve),
        "exposure_basis": "Equal-weighted observations at initial cash and each completed bar close; not intrabar exposure",
    }


def summarize_backtest_result(result: Mapping[str, object]) -> dict[str, object]:
    """Summarize a completed offline backtest without changing its result.

    Win-rate and profit-factor metrics refer only to FIFO-matched closed spot
    inventory. Open positions are kept separate. Tail loss summaries are
    withheld until at least twenty consecutive equity-curve periods exist.
    """
    if not isinstance(result, Mapping):
        raise ResearchMetricsError("backtest result must be a mapping")
    with localcontext() as context:
        context.prec = 640
        initial_cash = _number(result.get("initial_cash"), "initial_cash")
        final_equity = _number(result.get("final_equity"), "final_equity")
        if initial_cash <= 0 or final_equity <= 0:
            raise ResearchMetricsError("initial_cash and final_equity must be positive")
        equity = _equity_metrics(result.get("equity_curve"))
        trade = _trade_metrics(result.get("fills"))
        exposure = _exposure_metrics(result.get("exposure_curve"))
        calculated_total_return = final_equity / initial_cash - D("1")
        curve = result["equity_curve"]
        curve_final = _number(curve[-1]["equity"], "equity_curve final equity")
        if curve_final != final_equity:
            raise ResearchMetricsError("final_equity does not match final equity_curve observation")

        return {
            "schema_version": 1,
            "summary_status": "CALCULATED_FROM_SUPPLIED_BACKTEST_RESULT_ONLY",
            "initial_cash": _fmt(initial_cash),
            "final_equity": _fmt(final_equity),
            "net_total_return": _fmt(calculated_total_return),
            "equity_metrics": equity,
            "trade_metrics": trade,
            "exposure_metrics": exposure,
            "profitability_evidence_status": "NOT_ESTABLISHED_SYNTHETIC_OR_UNAUTHENTICATED_BACKTEST_RESULTS_REQUIRE_INDEPENDENT_DATA_AND_HOLDOUT_VALIDATION",
            "execution_boundary": "OFFLINE_LONG_ONLY_SPOT_RESEARCH_NO_ORDER_AUTHORIZATION",
        }
