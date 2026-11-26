"""Evaluate frozen V2 strategies over five OOS folds with fixed costs and evidence."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import math
import re
from typing import Any

from promotion_gate import evaluate_promotion_gate
from research_runner import STRATEGIES, _signals_for_segment, backtest, five_fold_oos_ranges
from statistical_evidence import (
    deflated_sharpe_probability, non_overlapping_24bar_returns,
    paired_block_bootstrap_excess_lower_bound,
)
from trial_registry import verify_trial_registry
from dataset_manifest import verify_dataset_manifest, DatasetManifestError

RESEARCH_FAMILY = "BITSTAMP_PERSONAL_SPOT_V2"
BASE_FEE_BPS = Decimal("16")
MARKET_COSTS = {
    "btcusd": (Decimal("5"), Decimal("10")),
    "ethusd": (Decimal("5"), Decimal("10")),
    "xrpusd": (Decimal("5"), Decimal("10")),
    "solusd": (Decimal("5"), Decimal("10")),
    "dogeusd": (Decimal("15"), Decimal("20")),
    "shibusd": (Decimal("15"), Decimal("20")),
    "pepeusd": (Decimal("15"), Decimal("20")),
}


class WalkForwardEvaluationError(ValueError):
    """Five-fold evaluation is incomplete or unsafe."""


def canonical_dataset_sha256(market_symbol: str, candles: list[dict]) -> str:
    """Hash the exact normalized in-memory market rows and market identity."""
    if not isinstance(market_symbol, str) or market_symbol.casefold() not in MARKET_COSTS:
        raise WalkForwardEvaluationError("market_symbol is not in the frozen V2 universe")
    if not isinstance(candles, list) or not candles:
        raise WalkForwardEvaluationError("candles must be a non-empty list")
    try:
        encoded = json.dumps(
            {"market_symbol": market_symbol.casefold(), "interval": "1h", "candles": candles},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise WalkForwardEvaluationError("candles are not canonical JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


def _fraction_percent(value: object, field: str) -> float:
    if value is None:
        raise WalkForwardEvaluationError(f"{field} is unavailable; fold cannot be promoted")
    try:
        result = float(Decimal(str(value)) / Decimal(100))
    except Exception as exc:
        raise WalkForwardEvaluationError(f"{field} is invalid") from exc
    if not math.isfinite(result) or result <= -1:
        raise WalkForwardEvaluationError(f"{field} is outside the supported range")
    return result


def evaluate_five_fold_strategy(
    candles: list[dict],
    *,
    market_symbol: str,
    strategy_id: str,
    trial_registry_bytes: bytes,
    dataset_manifest: Mapping[str, object],
) -> dict[str, Any]:
    """Build gate-ready metrics using only frozen market costs and registry bytes.

    Dataset SHA-256 is derived from the normalized candle rows and market
    identity. Costs are selected from the frozen V2 symbol map; callers cannot
    lower them. Base and exactly 2x-all-cost replays use identical signals/data.
    """
    try:
        verified_dataset = verify_dataset_manifest(dataset_manifest)
    except DatasetManifestError as exc:
        raise WalkForwardEvaluationError("dataset manifest failed completeness validation") from exc
    normalized_symbol = verified_dataset["market_symbol"]
    if market_symbol.casefold() != normalized_symbol or candles != verified_dataset["candles"]:
        raise WalkForwardEvaluationError("supplied candles or market identity do not match verified dataset manifest")
    if strategy_id not in STRATEGIES:
        raise WalkForwardEvaluationError("strategy_id is not preregistered")
    dataset_hash = verified_dataset["manifest_sha256"]
    try:
        registry = verify_trial_registry(trial_registry_bytes)
    except ValueError as exc:
        raise WalkForwardEvaluationError("trial registry failed integrity validation") from exc
    trial_count = registry["trial_counts"].get(RESEARCH_FAMILY, 0)
    registered_strategies = registry["trial_strategies"].get(RESEARCH_FAMILY, [])
    if trial_count < 2:
        raise WalkForwardEvaluationError("verified trial registry has fewer than two candidate trials")
    if strategy_id not in registered_strategies:
        raise WalkForwardEvaluationError("strategy_id is missing from the verified trial registry")
    registry_hash = registry["registry_sha256"]
    half_spread_bps, slippage_bps = MARKET_COSTS[normalized_symbol]

    ranges = five_fold_oos_ranges(len(candles))
    fold_rows = []
    for fold_id, (start, end) in ranges.items():
        segment = candles[start:end]
        signals = _signals_for_segment(strategy_id, candles, start, end)
        base = backtest(
            segment, signals, fee_bps=BASE_FEE_BPS,
            half_spread_bps=half_spread_bps, slippage_bps=slippage_bps,
            include_equity_curve=True,
        )
        baseline = backtest(
            segment, [1] * len(segment), fee_bps=BASE_FEE_BPS,
            half_spread_bps=half_spread_bps, slippage_bps=slippage_bps,
            include_equity_curve=True,
        )
        stress = backtest(
            segment, signals, fee_bps=BASE_FEE_BPS * Decimal(2),
            half_spread_bps=half_spread_bps * Decimal(2),
            slippage_bps=slippage_bps * Decimal(2),
            include_equity_curve=True,
        )
        strategy_returns = non_overlapping_24bar_returns(base["equity_curve"])
        baseline_returns = non_overlapping_24bar_returns(baseline["equity_curve"])
        dsr = deflated_sharpe_probability(strategy_returns, registered_trial_count=trial_count)
        bootstrap_lower = paired_block_bootstrap_excess_lower_bound(
            strategy_returns, baseline_returns,
            dataset_sha256=dataset_hash, fold_id=fold_id,
        )
        profit_factor = base["profit_factor"]
        if profit_factor is None:
            raise WalkForwardEvaluationError(
                f"{fold_id}: profit factor is undefined because the fold has no closed losses"
            )
        fold_rows.append({
            "fold_id": fold_id, "test_start": start, "test_end": end,
            "dataset_sha256": dataset_hash, "trial_registry_sha256": registry_hash,
            "registered_trial_count": trial_count,
            "strategy_net_return": _fraction_percent(base["mark_to_market_return_pct"], "strategy return"),
            "buy_hold_net_return": _fraction_percent(baseline["mark_to_market_return_pct"], "buy-and-hold return"),
            "two_x_cost_net_return": _fraction_percent(stress["mark_to_market_return_pct"], "2x-cost strategy return"),
            "max_drawdown": _fraction_percent(base["max_drawdown_intrabar_pct"], "intrabar drawdown"),
            "profit_factor": float(profit_factor),
            "closed_trade_count": base["closed_cycles"],
            "observations": len(strategy_returns),
            "deflated_sharpe_probability": dsr,
            "bootstrap_excess_ci_lower": bootstrap_lower,
        })
    promotion = evaluate_promotion_gate(folds=fold_rows)
    return {
        "market_symbol": normalized_symbol,
        "strategy_id": strategy_id,
        "dataset_sha256": dataset_hash,
        "raw_page_sha256": verified_dataset["raw_page_sha256"],
        "manifest_sha256": verified_dataset["manifest_sha256"],
        "trial_registry_sha256": registry_hash,
        "registered_trial_count": trial_count,
        "costs": {
            "fee_bps_per_side": str(BASE_FEE_BPS),
            "half_spread_bps_per_side": str(half_spread_bps),
            "slippage_bps_per_side": str(slippage_bps),
            "stress_multiplier": "2x_all_costs",
        },
        "folds": fold_rows,
        "promotion_screen": promotion,
        "status": promotion["status"],
        "profitability_status": "NOT_VERIFIED",
        "note": "A passing screen only qualifies for independent human review; no order authority is created.",
    }
