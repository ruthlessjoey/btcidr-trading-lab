"""Fail-closed statistical promotion screen for preregistered OOS fold evidence."""
from __future__ import annotations
import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

class PromotionError(ValueError):
    """Malformed or incomplete promotion evidence."""

MINIMUM_FOLDS = 5
MINIMUM_POSITIVE_RATIO = 0.60
MAXIMUM_FOLD_DRAWDOWN = 0.20
MINIMUM_PROFIT_FACTOR = 1.20
MINIMUM_CLOSED_TRADES = 30
MINIMUM_OBSERVATIONS = 100
MINIMUM_DSR_PROBABILITY = 0.95

_REQUIRED = frozenset({
    "fold_id", "test_start", "test_end", "dataset_sha256",
    "trial_registry_sha256", "registered_trial_count", "strategy_net_return", "buy_hold_net_return",
    "two_x_cost_net_return", "max_drawdown", "profit_factor",
    "closed_trade_count", "observations", "deflated_sharpe_probability",
    "bootstrap_excess_ci_lower",
})

def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise PromotionError(f"{name} must be numeric, not a string or boolean")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PromotionError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise PromotionError(f"{name} must be finite")
    return result

def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PromotionError(f"{name} must be a nonnegative integer")
    return value

def evaluate_promotion_gate(*, folds: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    """Screen supplied OOS fold metrics. A pass permits human review only.

    Returns are fractions, not percentages. DSR and paired block-bootstrap
    bounds must be independently computed. This function cannot authenticate
    rights, raw data, holdout non-use, or the calculation of those statistics.
    """
    if isinstance(folds, (str, bytes)) or not isinstance(folds, Sequence):
        raise PromotionError("folds must be a sequence of fold mappings")
    if len(folds) < MINIMUM_FOLDS:
        raise PromotionError(f"at least {MINIMUM_FOLDS} untouched OOS folds are required")
    rows, ids = [], set()
    prior_end, dataset_hash, trial_count, common_registry_hash = -1, None, None, None
    for i, fold in enumerate(folds):
        if not isinstance(fold, Mapping) or set(fold) != _REQUIRED:
            raise PromotionError(f"fold[{i}] must contain exactly: {', '.join(sorted(_REQUIRED))}")
        fid = fold["fold_id"]
        if not isinstance(fid, str) or not fid.strip() or len(fid) > 128:
            raise PromotionError(f"fold[{i}].fold_id must be a non-empty string")
        if fid in ids:
            raise PromotionError("fold_id values must be unique")
        ids.add(fid)
        start = _count(fold["test_start"], f"fold[{i}].test_start")
        end = _count(fold["test_end"], f"fold[{i}].test_end")
        if end <= start or start < prior_end:
            raise PromotionError("OOS test ranges must be ordered, non-empty and non-overlapping")
        prior_end = end
        digest = fold["dataset_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PromotionError(f"fold[{i}].dataset_sha256 must be a lowercase SHA-256 digest")
        if dataset_hash is None:
            dataset_hash = digest
        elif digest != dataset_hash:
            raise PromotionError("all folds must bind to the same immutable dataset hash")
        trials = _count(fold["registered_trial_count"], f"fold[{i}].registered_trial_count")
        if trials < 2:
            raise PromotionError("registered_trial_count must include all candidate trials and baseline")
        if trial_count is None:
            trial_count = trials
        elif trials != trial_count:
            raise PromotionError("all folds must use the same complete registered trial count")
        registry_hash = fold["trial_registry_sha256"]
        if not isinstance(registry_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", registry_hash):
            raise PromotionError(f"fold[{i}].trial_registry_sha256 must be a lowercase SHA-256 digest")
        if common_registry_hash is None:
            common_registry_hash = registry_hash
        elif registry_hash != common_registry_hash:
            raise PromotionError("all folds must bind to the same immutable trial registry hash")
        row = {
            "fold_id": fid, "test_start": start, "test_end": end,
            "strategy_net_return": _finite(fold["strategy_net_return"], f"fold[{i}].strategy_net_return"),
            "buy_hold_net_return": _finite(fold["buy_hold_net_return"], f"fold[{i}].buy_hold_net_return"),
            "two_x_cost_net_return": _finite(fold["two_x_cost_net_return"], f"fold[{i}].two_x_cost_net_return"),
            "max_drawdown": _finite(fold["max_drawdown"], f"fold[{i}].max_drawdown"),
            "profit_factor": _finite(fold["profit_factor"], f"fold[{i}].profit_factor"),
            "closed_trade_count": _count(fold["closed_trade_count"], f"fold[{i}].closed_trade_count"),
            "observations": _count(fold["observations"], f"fold[{i}].observations"),
            "deflated_sharpe_probability": _finite(fold["deflated_sharpe_probability"], f"fold[{i}].deflated_sharpe_probability"),
            "bootstrap_excess_ci_lower": _finite(fold["bootstrap_excess_ci_lower"], f"fold[{i}].bootstrap_excess_ci_lower"),
        }
        if any(row[k] <= -1 for k in ("strategy_net_return", "buy_hold_net_return", "two_x_cost_net_return")):
            raise PromotionError("fold returns must be greater than -100%")
        if not 0 <= row["max_drawdown"] < 1:
            raise PromotionError("max_drawdown must be in [0, 1)")
        if row["profit_factor"] < 0:
            raise PromotionError("profit_factor cannot be negative")
        if not 0 <= row["deflated_sharpe_probability"] <= 1:
            raise PromotionError("deflated_sharpe_probability must be in [0, 1]")
        rows.append(row)

    n = len(rows)
    positive = sum(x["strategy_net_return"] > 0 for x in rows)
    beat = sum(x["strategy_net_return"] > x["buy_hold_net_return"] for x in rows)
    stress_positive = sum(x["two_x_cost_net_return"] > 0 for x in rows)
    mean_net = math.fsum(x["strategy_net_return"] for x in rows) / n
    mean_excess = math.fsum(x["strategy_net_return"] - x["buy_hold_net_return"] for x in rows) / n
    mean_stress = math.fsum(x["two_x_cost_net_return"] for x in rows) / n
    worst_dd = max(x["max_drawdown"] for x in rows)
    min_pf = min(x["profit_factor"] for x in rows)
    min_dsr = min(x["deflated_sharpe_probability"] for x in rows)
    min_bootstrap = min(x["bootstrap_excess_ci_lower"] for x in rows)
    trades = sum(x["closed_trade_count"] for x in rows)
    observations = sum(x["observations"] for x in rows)
    checks = {
        "positive_net_return_each_fold_ratio": positive / n >= MINIMUM_POSITIVE_RATIO,
        "beats_same_cost_buy_hold_each_fold_ratio": beat / n >= MINIMUM_POSITIVE_RATIO,
        "positive_mean_net_return": mean_net > 0,
        "positive_mean_excess_vs_buy_hold": mean_excess > 0,
        "positive_mean_two_x_cost_return": mean_stress > 0,
        "two_x_cost_positive_fold_ratio": stress_positive / n >= MINIMUM_POSITIVE_RATIO,
        "drawdown_within_limit_all_folds": worst_dd <= MAXIMUM_FOLD_DRAWDOWN,
        "profit_factor_floor_all_folds": min_pf >= MINIMUM_PROFIT_FACTOR,
        "deflated_sharpe_floor_all_folds": min_dsr >= MINIMUM_DSR_PROBABILITY,
        "paired_bootstrap_lower_bound_positive_all_folds": min_bootstrap > 0,
        "enough_closed_trades": trades >= MINIMUM_CLOSED_TRADES,
        "enough_observations": observations >= MINIMUM_OBSERVATIONS,
    }
    passed = all(checks.values())
    return {
        "status": "ELIGIBLE_FOR_INDEPENDENT_HUMAN_REVIEW_NOT_PROVEN_PROFITABLE" if passed else "REJECT_OR_RESEARCH_MORE",
        "profitability_status": "NOT_VERIFIED",
        "fold_count": n, "positive_fold_ratio": positive / n,
        "baseline_beat_fold_ratio": beat / n,
        "two_x_cost_positive_fold_ratio": stress_positive / n,
        "mean_strategy_net_return": mean_net, "mean_excess_vs_buy_hold": mean_excess,
        "mean_two_x_cost_net_return": mean_stress,
        "worst_fold_max_drawdown": worst_dd, "minimum_fold_profit_factor": min_pf,
        "minimum_fold_dsr_probability": min_dsr,
        "minimum_fold_bootstrap_excess_ci_lower": min_bootstrap,
        "total_closed_trades": trades, "total_observations": observations,
        "checks": checks,
        "frozen_policy": {
            "minimum_folds": MINIMUM_FOLDS,
            "minimum_positive_fold_ratio": MINIMUM_POSITIVE_RATIO,
            "maximum_fold_drawdown": MAXIMUM_FOLD_DRAWDOWN,
            "minimum_profit_factor": MINIMUM_PROFIT_FACTOR,
            "minimum_closed_trades": MINIMUM_CLOSED_TRADES,
            "minimum_observations": MINIMUM_OBSERVATIONS,
            "minimum_dsr_probability": MINIMUM_DSR_PROBABILITY,
            "same_dataset_hash": True, "same_registered_trial_count": True,
            "ordered_non_overlapping_test_ranges": True,
        },
        "limitations": [
            "Fold summaries must be independently shown to be untouched and chronological.",
            "Dataset hashes must cover exact source bytes and preprocessing.",
            "Returns must include fees, spread, slippage, partial/rejected fills and disclosed impact assumptions.",
            "The 2x-cost replay must use identical signals and data, changing costs only.",
            "DSR and paired block-bootstrap validity depends on assumptions and complete trial registration.",
            "Source rights, independent review and production security are separate mandatory gates.",
            "A pass permits human review only; it never enables PAPER or LIVE execution.",
        ],
    }
