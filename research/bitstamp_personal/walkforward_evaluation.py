"""Evaluate frozen V2 strategies over five OOS folds with cost and statistical evidence."""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Any

from promotion_gate import evaluate_promotion_gate
from research_runner import (
    STRATEGIES, _signals_for_segment, backtest, five_fold_oos_ranges,
)
from statistical_evidence import (
    deflated_sharpe_probability,
    non_overlapping_24bar_returns,
    paired_block_bootstrap_excess_lower_bound,
)
from trial_registry import verify_trial_registry

RESEARCH_FAMILY = "BITSTAMP_PERSONAL_SPOT_V2"


class WalkForwardEvaluationError(ValueError):
    """Five-fold evaluation is incomplete or unsafe."""


def _fraction_percent(value: object, field: str) -> float:
    if value is None:
        raise WalkForwardEvaluationError(f"{field} is unavailable; fold cannot be promoted")
    try:
        result = float(Decimal(str(value)) / Decimal(100))
    except Exception as exc:
        raise WalkForwardEvaluationError(f"{field} is invalid") from exc
    if not (-1 < result < 1000):
        raise WalkForwardEvaluationError(f"{field} is outside the supported range")
    return result


def evaluate_five_fold_strategy(
    candles: list[dict],
    *,
    strategy_id: str,
    dataset_sha256: str,
    trial_registry_bytes: bytes,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> dict[str, Any]:
    """Build gate-ready fold metrics; all returns are mark-to-market fractions.

    The same frozen signals/data are replayed at base and exactly 2x all costs.
    Buy-and-hold uses the same base costs. The trial count and registry hash are
    taken from verified hash-chained JSONL bytes, never caller-entered numbers.
    """
    if strategy_id not in STRATEGIES:
        raise WalkForwardEvaluationError("strategy_id is not preregistered")
    if not isinstance(dataset_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", dataset_sha256):
        raise WalkForwardEvaluationError("dataset_sha256 must be lowercase SHA-256")
    try:
        registry = verify_trial_registry(trial_registry_bytes)
    except ValueError as exc:
        raise WalkForwardEvaluationError("trial registry failed integrity validation") from exc
    trial_count = registry["trial_counts"].get(RESEARCH_FAMILY, 0)
    if trial_count < 2:
        raise WalkForwardEvaluationError("verified trial registry has fewer than two candidate trials")
    registry_hash = registry["registry_sha256"]

    ranges = five_fold_oos_ranges(len(candles))
    fold_rows = []
    for fold_id, (start, end) in ranges.items():
        segment = candles[start:end]
        signals = _signals_for_segment(strategy_id, candles, start, end)
        base = backtest(
            segment, signals,
            fee_bps=fee_bps,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
            include_equity_curve=True,
        )
        baseline = backtest(
            segment, [1] * len(segment),
            fee_bps=fee_bps,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
            include_equity_curve=True,
        )
        stress = backtest(
            segment, signals,
            fee_bps=fee_bps * Decimal(2),
            half_spread_bps=half_spread_bps * Decimal(2),
            slippage_bps=slippage_bps * Decimal(2),
            include_equity_curve=True,
        )
        strategy_returns = non_overlapping_24bar_returns(base["equity_curve"])
        baseline_returns = non_overlapping_24bar_returns(baseline["equity_curve"])
        dsr = deflated_sharpe_probability(
            strategy_returns, registered_trial_count=trial_count,
        )
        bootstrap_lower = paired_block_bootstrap_excess_lower_bound(
            strategy_returns, baseline_returns,
            dataset_sha256=dataset_sha256, fold_id=fold_id,
        )
        profit_factor = base["profit_factor"]
        if profit_factor is None:
            raise WalkForwardEvaluationError(
                f"{fold_id}: profit factor is undefined because the fold has no closed losses"
            )
        fold_rows.append({
            "fold_id": fold_id,
            "test_start": start,
            "test_end": end,
            "dataset_sha256": dataset_sha256,
            "trial_registry_sha256": registry_hash,
            "registered_trial_count": trial_count,
            "strategy_net_return": _fraction_percent(
                base["mark_to_market_return_pct"], "strategy return",
            ),
            "buy_hold_net_return": _fraction_percent(
                baseline["mark_to_market_return_pct"], "buy-and-hold return",
            ),
            "two_x_cost_net_return": _fraction_percent(
                stress["mark_to_market_return_pct"], "2x-cost strategy return",
            ),
            "max_drawdown": _fraction_percent(
                base["max_drawdown_intrabar_pct"], "intrabar drawdown",
            ),
            "profit_factor": float(profit_factor),
            "closed_trade_count": base["closed_cycles"],
            "observations": len(strategy_returns),
            "deflated_sharpe_probability": dsr,
            "bootstrap_excess_ci_lower": bootstrap_lower,
        })
    promotion = evaluate_promotion_gate(folds=fold_rows)
    return {
        "strategy_id": strategy_id,
        "dataset_sha256": dataset_sha256,
        "trial_registry_sha256": registry_hash,
        "registered_trial_count": trial_count,
        "folds": fold_rows,
        "promotion_screen": promotion,
        "status": promotion["status"],
        "profitability_status": "NOT_VERIFIED",
        "note": "A passing screen only qualifies for independent human review; no order authority is created.",
    }
