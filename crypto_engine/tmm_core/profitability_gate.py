"""Fail-closed evidence gate for strategy promotion.

A pass only permits independent review. It never authorizes orders or a
profitability claim. Inputs must describe an untouched, net-of-cost holdout.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

_HASH = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = {
    "dataset_sha256", "result_sha256", "strategy_config_sha256", "experiment_registry_sha256", "holdout_id",
    "holdout_sealed", "holdout_used_for_tuning", "source_license_approved",
    "point_in_time_verified", "coverage_complete", "no_lookahead_verified",
    "execution_costs_included", "execution_cost_model_verified", "benchmark_same_costs_verified", "two_x_costs_positive", "all_trials_registered",
    "spot_long_only_verified", "paper_only_verified", "live_trading_enabled",
    "venue_rules_verified", "registry_replay_verified", "trial_count",
    "observations", "closed_trades", "net_cagr", "net_expectancy", "win_rate",
    "profit_factor", "max_drawdown", "sharpe_annualized",
    "deflated_sharpe_probability", "bootstrap_excess_lower_bound",
    "net_return", "buy_hold_return", "two_x_cost_net_return",
    "walk_forward_folds",
}
_FOLD_KEYS = {"fold_id", "test_start", "test_end", "net_return",
              "max_drawdown", "closed_trades"}
_TRUE_CHECKS = (
    "holdout_sealed", "source_license_approved", "point_in_time_verified",
    "coverage_complete", "no_lookahead_verified", "execution_costs_included", "execution_cost_model_verified", "benchmark_same_costs_verified",
    "two_x_costs_positive", "all_trials_registered", "spot_long_only_verified",
    "paper_only_verified", "venue_rules_verified", "registry_replay_verified",
)
_HASH_FIELDS = ("dataset_sha256", "result_sha256", "strategy_config_sha256", "experiment_registry_sha256")


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _iso_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must use canonical YYYY-MM-DD")
    return parsed


def evaluate_profitability_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a strict, auditable evidence record without granting execution."""
    if not isinstance(evidence, Mapping):
        raise TypeError("evidence must be a mapping")
    reasons: list[str] = []
    missing = sorted(_REQUIRED - set(evidence))
    extra = sorted(str(key) for key in set(evidence) - _REQUIRED)
    if missing:
        reasons.append("missing required fields: " + ", ".join(missing))
    if extra:
        reasons.append("unknown fields: " + ", ".join(map(str, extra)))

    for field in _HASH_FIELDS:
        value = evidence.get(field)
        if not isinstance(value, str) or not _HASH.fullmatch(value):
            reasons.append(f"{field} must be a lowercase SHA-256 digest")

    holdout_id = evidence.get("holdout_id")
    if not isinstance(holdout_id, str) or not holdout_id.strip() or len(holdout_id) > 128:
        reasons.append("holdout_id must be a non-empty label up to 128 characters")

    for field in _TRUE_CHECKS:
        if evidence.get(field) is not True:
            reasons.append(f"{field} must be explicitly true")
    if evidence.get("holdout_used_for_tuning") is not False:
        reasons.append("holdout_used_for_tuning must be explicitly false")
    if evidence.get("live_trading_enabled") is not False:
        reasons.append("live_trading_enabled must be explicitly false")

    counts: dict[str, int] = {}
    for field in ("trial_count", "observations", "closed_trades"):
        try:
            counts[field] = _positive_int(evidence.get(field), field)
        except ValueError as exc:
            reasons.append(str(exc))
    if counts.get("trial_count", 0) < 30:
        reasons.append("at least 30 registered strategy trials are required")
    if counts.get("observations", 0) < 250:
        reasons.append("at least 250 untouched out-of-sample observations are required")
    if counts.get("closed_trades", 0) < 100:
        reasons.append("at least 100 closed out-of-sample trades are required")

    metrics: dict[str, float] = {}
    for field in (
        "net_cagr", "net_expectancy", "win_rate", "profit_factor",
        "max_drawdown", "sharpe_annualized", "deflated_sharpe_probability",
        "bootstrap_excess_lower_bound", "net_return", "buy_hold_return",
        "two_x_cost_net_return",
    ):
        try:
            metrics[field] = _finite_number(evidence.get(field), field)
        except ValueError as exc:
            reasons.append(str(exc))

    if "net_cagr" in metrics and metrics["net_cagr"] <= 0:
        reasons.append("net_cagr must be positive")
    if "net_return" in metrics and metrics["net_return"] <= 0:
        reasons.append("net_return must be positive")
    for field in ("net_return", "buy_hold_return", "two_x_cost_net_return"):
        if field in metrics and metrics[field] <= -1:
            reasons.append(f"{field} must be greater than -1 (loss cannot exceed 100%)")
    if "net_expectancy" in metrics and metrics["net_expectancy"] <= 0:
        reasons.append("net_expectancy must be positive")
    if "win_rate" in metrics and not 0.55 <= metrics["win_rate"] <= 1:
        reasons.append("win_rate must be at least 0.55 and at most 1")
    if "profit_factor" in metrics and metrics["profit_factor"] < 1.30:
        reasons.append("profit_factor must be at least 1.30")
    if "max_drawdown" in metrics and not 0 <= metrics["max_drawdown"] <= 0.25:
        reasons.append("max_drawdown must be between 0 and 0.25")
    if "sharpe_annualized" in metrics and metrics["sharpe_annualized"] < 1.0:
        reasons.append("sharpe_annualized must be at least 1.0")
    if "deflated_sharpe_probability" in metrics and not 0.95 <= metrics["deflated_sharpe_probability"] <= 1:
        reasons.append("deflated_sharpe_probability must be at least 0.95")
    if "bootstrap_excess_lower_bound" in metrics and metrics["bootstrap_excess_lower_bound"] <= 0:
        reasons.append("bootstrap_excess_lower_bound must be positive")
    if "net_return" in metrics and "buy_hold_return" in metrics:
        if metrics["net_return"] <= metrics["buy_hold_return"]:
            reasons.append("net_return must exceed the same-cost buy-and-hold benchmark")
    if "two_x_cost_net_return" in metrics and metrics["two_x_cost_net_return"] <= 0:
        reasons.append("two_x_cost_net_return must remain positive")

    folds = evidence.get("walk_forward_folds")
    positive_folds = 0
    if not isinstance(folds, list) or len(folds) < 4:
        reasons.append("at least four chronological walk-forward folds are required")
    else:
        previous_end: date | None = None
        valid_folds = 0
        for index, fold in enumerate(folds):
            if not isinstance(fold, Mapping) or set(fold) != _FOLD_KEYS:
                reasons.append(f"walk_forward_folds[{index}] has an invalid schema")
                continue
            try:
                fold_id = fold["fold_id"]
                if not isinstance(fold_id, str) or not fold_id.strip():
                    raise ValueError("fold_id must be a non-empty label")
                start = _iso_date(fold["test_start"], f"fold {index} test_start")
                end = _iso_date(fold["test_end"], f"fold {index} test_end")
                if end <= start:
                    raise ValueError(f"fold {index} test_end must be after test_start")
                if previous_end is not None and start <= previous_end:
                    raise ValueError("walk-forward test windows overlap or are out of order")
                net = _finite_number(fold["net_return"], f"fold {index} net_return")
                drawdown = _finite_number(fold["max_drawdown"], f"fold {index} max_drawdown")
                trades = _positive_int(fold["closed_trades"], f"fold {index} closed_trades")
                if net <= -1:
                    raise ValueError(f"fold {index} net_return must be greater than -1")
                if not 0 <= drawdown <= 0.25:
                    raise ValueError(f"fold {index} max_drawdown must be between 0 and 0.25")
                if trades < 1:
                    raise ValueError(f"fold {index} must contain a closed trade")
                if net > 0:
                    positive_folds += 1
                valid_folds += 1
                previous_end = end
            except (KeyError, ValueError) as exc:
                reasons.append(str(exc))
        if valid_folds >= 4 and positive_folds / valid_folds < 0.75:
            reasons.append("at least 75% of walk-forward folds must be net profitable")

    return {
        "promotion_status": "READY_FOR_INDEPENDENT_REVIEW" if not reasons else "BLOCKED",
        "reasons": reasons,
        "walk_forward_positive_fold_ratio": (
            positive_folds / valid_folds if "valid_folds" in locals() and valid_folds else 0.0
        ),
        "order_authorized": False,
        "paper_execution_authorized": False,
        "profitability_claim_authorized": False,
        "gate_version": "1.0.0",
    }
