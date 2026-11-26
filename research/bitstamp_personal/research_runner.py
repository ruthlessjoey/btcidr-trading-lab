"""Preregistered personal, noncommercial Bitstamp spot-candle research.

Raw candles remain in memory and are never uploaded as CI artifacts. This
script is exploratory only; it does not produce an installable trading signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN, localcontext
from pathlib import Path
from typing import Callable

from bitstamp_public_ohlc import (
    BitstampDataError, fetch_spot_history, fetch_spot_markets,
)
from promotion_gate import PromotionEvidenceError, evaluate_promotion_gate
from experiment_registry import TrialRegistryError, load_trial_registry
from statistical_evidence import (
    StatisticalEvidenceError, deflated_sharpe_probability,
    paired_moving_block_bootstrap_lower_bound,
)

D = Decimal
INITIAL_CASH = D("10000")
PARTICIPATION = D("0.05")
FEE_BPS = D("16")  # documented public API example only; not the user's fee tier
STRATEGIES = ("SMA20_50_LONG_ONLY", "RSI14_MEAN_REVERSION_LONG_ONLY")
PREREGISTRATION_ID = "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2_5FOLD"
PREREGISTERED_START = "2024-01-01"
PREREGISTERED_END = "2026-11-01"
PREREGISTERED_SYMBOLS = (
    "btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd"
)
PREREGISTERED_MIN_MARKETS = 3
PREREGISTERED_REQUIRE_MEME = True
MEME_SYMBOLS = {"dogeusd", "shibusd", "pepeusd", "bonkusd", "flokusd"}


def _epoch(value: str) -> int:
    """Map a preregistered date to its exact 00:00 UTC boundary.

    The start boundary is the first eligible candle open; the end boundary
    is the last eligible candle close. Bitstamp's adapter filters candles by
    close timestamp <= end_timestamp, so do not extend an end date to the
    following midnight.
    """
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc
    moment = datetime.combine(parsed, datetime.min.time(), tzinfo=timezone.utc)
    return int(moment.timestamp())


def validate_preregistered_run(
    start: str, end: str, symbols: str, min_markets: int, require_meme: bool
) -> list[str]:
    """Reject CLI overrides that would silently change the frozen research design."""
    expected_symbols = ",".join(PREREGISTERED_SYMBOLS)
    if start != PREREGISTERED_START or end != PREREGISTERED_END:
        raise BitstampDataError("requested date range differs from the frozen preregistration")
    if symbols.lower() != expected_symbols:
        raise BitstampDataError("candidate market universe differs from the frozen preregistration")
    if min_markets != PREREGISTERED_MIN_MARKETS:
        raise BitstampDataError("minimum market count differs from the frozen preregistration")
    if require_meme is not PREREGISTERED_REQUIRE_MEME:
        raise BitstampDataError("meme-market requirement differs from the frozen preregistration")
    return list(PREREGISTERED_SYMBOLS)


def _wilson(wins: int, total: int, z: float = 1.96):
    if total <= 0:
        return None
    p = wins / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * ((p * (1 - p) / total + z2 / (4 * total * total)) ** 0.5) / denom
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def _make_signals(
    strategy: str,
    candles: list[dict],
    *,
    reset_target_at: int | None = None,
) -> list[int]:
    closes = [D(row["close"]) for row in candles]
    signals = []
    target = 0
    for index, close in enumerate(closes):
        # A stateful strategy must not carry an open target across an
        # independent train/validation/holdout account boundary. Historical
        # closes remain available for indicator warmup; only the position state
        # resets immediately before the first signal in the new segment.
        if index == reset_target_at:
            target = 0
        if strategy == "SMA20_50_LONG_ONLY":
            if index >= 49:
                fast = sum(closes[index - 19:index + 1], D("0")) / D(20)
                slow = sum(closes[index - 49:index + 1], D("0")) / D(50)
                target = int(fast > slow and close > fast)
            else:
                target = 0
        elif strategy == "RSI14_MEAN_REVERSION_LONG_ONLY":
            if index >= 14:
                changes = [closes[j] - closes[j - 1] for j in range(index - 13, index + 1)]
                gains = sum((max(change, D("0")) for change in changes), D("0")) / D(14)
                losses = sum((max(-change, D("0")) for change in changes), D("0")) / D(14)
                if gains == 0 and losses == 0:
                    # A flat 14-period window is neutral, not overbought.
                    rsi = D(50)
                elif losses == 0:
                    rsi = D(100)
                else:
                    rsi = D(100) - D(100) / (D(1) + gains / losses)
                if rsi < D(30):
                    target = 1
                elif rsi > D(55):
                    target = 0
            else:
                target = 0
        else:
            raise ValueError("unregistered strategy")
        signals.append(target)
    return signals


def make_signals(strategy: str, candles: list[dict]) -> list[int]:
    # Keep indicator decisions deterministic even if the caller changes the
    # process-wide Decimal context.
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        return _make_signals(strategy, candles)


def _validate_backtest_inputs(
    candles: list[dict],
    signals: list[int],
    *,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> None:
    """Reject malformed inputs before any portfolio arithmetic is performed."""
    if len(candles) != len(signals) or len(candles) < 2:
        raise ValueError("candles/signals length mismatch or insufficient bars")
    for index, signal in enumerate(signals):
        if type(signal) is not int or signal not in (0, 1):
            raise ValueError(f"signal at index {index} must be integer 0 or 1")
    for name, value in (
        ("fee_bps", fee_bps),
        ("half_spread_bps", half_spread_bps),
        ("slippage_bps", slippage_bps),
    ):
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValueError(f"{name} must be a finite nonnegative Decimal")
    if fee_bps >= D(10000):
        raise ValueError("fee_bps must be below 10000")
    if half_spread_bps + slippage_bps >= D(10000):
        raise ValueError("combined spread and slippage must be below 10000 bps")

    for index, row in enumerate(candles):
        if not isinstance(row, dict):
            raise ValueError(f"candle at index {index} must be an object")
        values = {}
        for field in ("open", "high", "low", "close", "volume"):
            raw = row.get(field)
            if isinstance(raw, bool) or raw is None:
                raise ValueError(f"candle {field} at index {index} is invalid")
            try:
                value = D(str(raw))
            except Exception as exc:
                raise ValueError(f"candle {field} at index {index} is invalid") from exc
            if not value.is_finite():
                raise ValueError(f"candle {field} at index {index} must be finite")
            values[field] = value
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            raise ValueError(f"candle prices at index {index} must be positive")
        if values["volume"] < 0:
            raise ValueError(f"candle volume at index {index} cannot be negative")
        if values["high"] < max(values["open"], values["close"], values["low"]):
            raise ValueError(f"candle high at index {index} violates OHLC bounds")
        if values["low"] > min(values["open"], values["close"], values["high"]):
            raise ValueError(f"candle low at index {index} violates OHLC bounds")


def _backtest(
    candles: list[dict],
    signals: list[int],
    *,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> dict:
    _validate_backtest_inputs(
        candles, signals, fee_bps=fee_bps,
        half_spread_bps=half_spread_bps, slippage_bps=slippage_bps,
    )
    cash = INITIAL_CASH
    base = D("0")
    cost_basis = D("0")
    cycle_pnl = D("0")
    cycles = []
    close_equity_curve = [INITIAL_CASH]
    intrabar_equity_curve = [INITIAL_CASH]
    fees_paid = D("0")
    turnover = D("0")
    fills = 0
    fee_rate = fee_bps / D(10000)
    cost_rate = (half_spread_bps + slippage_bps) / D(10000)
    quantum = D("0.000000000001")

    for index in range(1, len(candles)):
        weight = D(signals[index - 1])
        open_price = D(candles[index]["open"])
        close_price = D(candles[index]["close"])
        prior_volume = D(candles[index - 1]["volume"])
        max_qty = prior_volume * PARTICIPATION
        equity_at_open = cash + base * open_price
        intrabar_equity_curve.append(equity_at_open)
        desired_base = (equity_at_open * weight / open_price) if open_price > 0 else D("0")
        delta = desired_base - base

        if delta > 0 and cash > 0 and max_qty > 0:
            fill_price = open_price * (D(1) + cost_rate)
            affordable = cash / (fill_price * (D(1) + fee_rate))
            quantity = min(delta, max_qty, affordable).quantize(quantum, rounding=ROUND_DOWN)
            if quantity > 0:
                notional = quantity * fill_price
                fee = notional * fee_rate
                cash -= notional + fee
                base += quantity
                cost_basis += notional + fee
                fees_paid += fee
                turnover += notional
                fills += 1

        elif delta < 0 and base > 0 and max_qty > 0:
            quantity = min(-delta, base, max_qty).quantize(quantum, rounding=ROUND_DOWN)
            if quantity > 0:
                fill_price = open_price * (D(1) - cost_rate)
                notional = quantity * fill_price
                fee = notional * fee_rate
                proceeds = notional - fee
                removed_basis = cost_basis * quantity / base
                cycle_pnl += proceeds - removed_basis
                cash += proceeds
                base -= quantity
                cost_basis -= removed_basis
                fees_paid += fee
                turnover += notional
                fills += 1
                if base <= quantum:
                    cycles.append(cycle_pnl)
                    cycle_pnl = D("0")
                    base = D("0")
                    cost_basis = D("0")

        close_equity = cash + base * close_price
        high_price = D(candles[index]["high"])
        low_price = D(candles[index]["low"])
        if (not high_price.is_finite() or high_price <= 0
                or high_price < max(open_price, close_price, low_price)):
            raise ValueError("candle high must be finite, positive and no lower than open, close or low")
        if (not low_price.is_finite() or low_price <= 0
                or low_price > min(open_price, close_price)):
            raise ValueError("candle low must be finite, positive and no higher than open or close")
        close_equity_curve.append(close_equity)
        # Use a deliberately adverse high-first, then low path for a long-only
        # position. OHLC does not reveal event order; this produces a
        # conservative peak-to-trough drawdown bound without claiming the path
        # actually occurred. Keep the open-gap mark before the fill decision.
        intrabar_equity_curve.append(cash + base * high_price)
        intrabar_equity_curve.append(cash + base * low_price)
        intrabar_equity_curve.append(close_equity)

    final_equity = close_equity_curve[-1]
    period_returns = [
        float(current / previous - D(1))
        for previous, current in zip(close_equity_curve, close_equity_curve[1:])
    ]
    mark_to_market_return_pct = (
        (final_equity / INITIAL_CASH - 1) * 100
    ).quantize(D("0.0001"))
    terminal_position_is_flat = base <= quantum
    open_position_mark_value = base * D(candles[-1]["close"])

    def _max_drawdown(curve):
        peak = curve[0]
        drawdown = D("0")
        for equity in curve:
            peak = max(peak, equity)
            if peak > 0:
                drawdown = max(drawdown, (peak - equity) / peak)
        return drawdown

    close_max_drawdown = _max_drawdown(close_equity_curve)
    intrabar_max_drawdown = _max_drawdown(intrabar_equity_curve)
    wins = sum(1 for pnl in cycles if pnl > 0)
    losses = sum(1 for pnl in cycles if pnl < 0)
    gross_wins = sum((pnl for pnl in cycles if pnl > 0), D("0"))
    gross_losses = -sum((pnl for pnl in cycles if pnl < 0), D("0"))
    return {
        "_period_returns": period_returns,
        "initial_cash": str(INITIAL_CASH),
        "final_equity": str(final_equity.quantize(D("0.01"))),
        "net_return_pct": str(mark_to_market_return_pct) if terminal_position_is_flat else None,
        "mark_to_market_return_pct": str(mark_to_market_return_pct),
        "return_valuation": (
            "REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT" if terminal_position_is_flat
            else "MARK_TO_MARKET_AFTER_EXECUTED_COSTS"
        ),
        "terminal_position_status": (
            "FLAT" if terminal_position_is_flat
            else "OPEN_MARKED_TO_MARKET_NO_EXIT_FILL"
        ),
        "open_position_mark_value": str(open_position_mark_value.quantize(D("0.01"))),
        "max_drawdown_pct": str((intrabar_max_drawdown * 100).quantize(D("0.0001"))),
        "max_drawdown_intrabar_pct": str((intrabar_max_drawdown * 100).quantize(D("0.0001"))),
        "max_drawdown_close_pct": str((close_max_drawdown * 100).quantize(D("0.0001"))),
        "drawdown_measurement": "open-gap, worst-case high-first then low then candle-close equity marks; conservative OHLC bound, not observed intrabar sequencing",
        "drawdown_path_assumption": "WORST_CASE_HIGH_BEFORE_LOW",
        "closed_cycles": len(cycles),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": None if not cycles else round(100 * wins / len(cycles), 4),
        "win_rate_wilson_95": _wilson(wins, len(cycles)),
        "profit_factor": None if gross_losses == 0 else str((gross_wins / gross_losses).quantize(D("0.0001"))),
        "expectancy_per_closed_cycle": None if not cycles else str((sum(cycles, D("0")) / D(len(cycles))).quantize(D("0.01"))),
        "fees_paid": str(fees_paid.quantize(D("0.01"))),
        "turnover": str(turnover.quantize(D("0.01"))),
        "fill_count": fills,
        "open_position_at_end": str(base.quantize(quantum)),
        "sample_status": "ADEQUATE_30_PLUS_CLOSED_CYCLES" if len(cycles) >= 30 else "INSUFFICIENT_CLOSED_CYCLES",
    }


def backtest(
    candles: list[dict],
    signals: list[int],
    *,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> dict:
    # One fixed precision policy for indicator-adjacent accounting, fee,
    # spread, slippage and cost-basis arithmetic. The caller's context is restored.
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        return _backtest(
            candles, signals,
            fee_bps=fee_bps,
            half_spread_bps=half_spread_bps,
            slippage_bps=slippage_bps,
        )


def _signals_for_segment(strategy: str, all_candles: list[dict], start: int, end: int) -> list[int]:
    """Build causal signals with indicator warmup but a fresh flat segment state."""
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(all_candles):
        raise ValueError("segment signal bounds are invalid")
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        all_signals = _make_signals(
            strategy, all_candles[:end], reset_target_at=start,
        )
    return all_signals[start:end]



WALK_FORWARD_FOLD_COUNT = 5
WALK_FORWARD_EMBARGO_BARS = 50
WALK_FORWARD_INITIAL_TRAIN_NUMERATOR = 2
WALK_FORWARD_INITIAL_TRAIN_DENOMINATOR = 5
WALK_FORWARD_MINIMUM_TRAIN_BARS = 1500
WALK_FORWARD_MINIMUM_TEST_BARS = 500
WALK_FORWARD_HOLDOUT_START_NUMERATOR = 9
WALK_FORWARD_HOLDOUT_START_DENOMINATOR = 10


def plan_walk_forward_folds(count: int) -> list[dict]:
    """Create five expanding-train, chronological OOS folds with embargo and exit bars.

    Each test range is half-open [test_start, test_end). The candle at test_end
    is reserved for next-open terminal liquidation and is excluded from OOS
    metrics. Fifty additional bars separate one liquidation bar from the next
    test window. Training ends fifty bars before each test starts.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 6000:
        raise ValueError("at least 6000 contiguous candles are required")
    initial_train_end = count * WALK_FORWARD_INITIAL_TRAIN_NUMERATOR // WALK_FORWARD_INITIAL_TRAIN_DENOMINATOR
    final_holdout_start = count * WALK_FORWARD_HOLDOUT_START_NUMERATOR // WALK_FORWARD_HOLDOUT_START_DENOMINATOR
    if initial_train_end - WALK_FORWARD_EMBARGO_BARS < WALK_FORWARD_MINIMUM_TRAIN_BARS:
        raise ValueError("initial training window is too small after embargo")
    cursor = initial_train_end + WALK_FORWARD_EMBARGO_BARS
    folds = []
    for index in range(WALK_FORWARD_FOLD_COUNT):
        remaining = WALK_FORWARD_FOLD_COUNT - index
        # Reserve one next-open liquidation candle and 50 embargo candles
        # after every fold, including the final fold before the untouched holdout.
        reserved = remaining * (1 + WALK_FORWARD_EMBARGO_BARS)
        test_length = (final_holdout_start - cursor - reserved) // remaining
        if test_length < WALK_FORWARD_MINIMUM_TEST_BARS:
            raise ValueError("walk-forward OOS fold is too small")
        test_start = cursor
        test_end = test_start + test_length
        if test_end >= final_holdout_start:
            raise ValueError("walk-forward fold overlaps the untouched final holdout")
        folds.append({
            "fold_id": f"wf-{index + 1:02d}",
            "train_start": 0,
            "train_end": test_start - WALK_FORWARD_EMBARGO_BARS,
            "test_start": test_start,
            "test_end": test_end,
            "liquidation_index": test_end,
        })
        cursor = test_end + 1 + WALK_FORWARD_EMBARGO_BARS
    return folds


def _backtest_walk_forward_fold(
    all_candles: list[dict],
    test_start: int,
    test_end: int,
    test_signals: list[int],
    *,
    initial_target: int,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> dict:
    """Backtest one OOS range, entering at its first open and liquidating next open."""
    if (test_start < 1 or test_end <= test_start or test_end >= len(all_candles)
            or len(test_signals) != test_end - test_start
            or initial_target not in (0, 1)):
        raise ValueError("walk-forward fold bounds or signals are invalid")
    # Include the prior candle for the first next-open execution and one
    # embargo candle after the OOS range for explicit terminal liquidation.
    segment = all_candles[test_start - 1:test_end + 1]
    prepared_signals = [initial_target] + list(test_signals[:-1]) + [0, 0]
    return backtest(
        segment, prepared_signals, fee_bps=fee_bps,
        half_spread_bps=half_spread_bps, slippage_bps=slippage_bps,
    )


def split_ranges(count: int, embargo_bars: int = 50) -> dict[str, tuple[int, int]]:
    if count < 5000:
        raise ValueError("at least 5000 contiguous 1h candles are required")
    train_end = int(count * 0.60)
    validation_end = int(count * 0.80)
    ranges = {
        "train": (0, train_end),
        "validation": (train_end + embargo_bars, validation_end),
        "holdout": (validation_end + embargo_bars, count),
    }
    if any(end - start < 500 for start, end in ranges.values()):
        raise ValueError("chronological split is too small after embargo")
    return ranges



def _evaluate_market_promotion_screens(
    walk_forward_folds: list[dict], *,
    dataset_sha256: str,
    cost_model_sha256: str,
    strategy_config_sha256: str,
    registered_trial_count: int,
    trial_registry_sha256: str,
    trial_series_by_fold: list[list[list[float]]],
    bootstrap_replicates: int = 5000,
) -> dict:
    """Evaluate each strategy against the complete registered trial series for every fold."""
    if len(trial_series_by_fold) != len(walk_forward_folds):
        raise PromotionEvidenceError("global trial-series fold count does not match OOS fold count")
    if any(len(series) != registered_trial_count for series in trial_series_by_fold):
        raise PromotionEvidenceError("all registered market-strategy trial series must be present for DSR")
    screens = {}
    for strategy_index, strategy in enumerate(STRATEGIES):
        gate_folds = []
        fold_statistics = []
        try:
            for fold_index, fold in enumerate(walk_forward_folds):
                candidate = fold["strategies"][strategy]["base_costs"]
                stress = fold["strategies"][strategy]["two_x_costs"]
                benchmark = fold["buy_hold_base_costs"]
                candidate_returns = candidate["_period_returns"]
                benchmark_returns = benchmark["_period_returns"]
                trial_series = trial_series_by_fold[fold_index]
                dsr = deflated_sharpe_probability(
                    candidate_returns, trial_series,
                    registered_trial_count=registered_trial_count,
                )
                bootstrap = paired_moving_block_bootstrap_lower_bound(
                    candidate_returns, benchmark_returns,
                    block_length=24, replicates=bootstrap_replicates,
                    confidence_level=0.95,
                    seed=20261127 + fold_index * 100 + strategy_index,
                )
                if (candidate["terminal_position_status"] != "FLAT"
                        or benchmark["terminal_position_status"] != "FLAT"
                        or candidate["return_valuation"] != "REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT"
                        or benchmark["return_valuation"] != "REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT"):
                    raise PromotionEvidenceError("candidate and same-cost benchmark must both be realized and flat")
                def pct_fraction(result, field):
                    value = result[field]
                    if value is None:
                        raise PromotionEvidenceError(f"{field} is unavailable for a non-realized result")
                    return float(D(str(value)) / D(100))
                gate_folds.append({
                    "fold_id": fold["fold_id"],
                    "test_start": fold["test_start"],
                    "test_end": fold["test_end"],
                    "dataset_sha256": dataset_sha256,
                    "trial_registry_sha256": trial_registry_sha256,
                    "cost_model_sha256": cost_model_sha256,
                    "strategy_config_sha256": strategy_config_sha256,
                    "return_valuation": candidate["return_valuation"],
                    "terminal_position_status": candidate["terminal_position_status"],
                    "registered_trial_count": registered_trial_count,
                    "strategy_net_return": pct_fraction(candidate, "net_return_pct"),
                    "buy_hold_net_return": pct_fraction(benchmark, "net_return_pct"),
                    "two_x_cost_net_return": pct_fraction(stress, "net_return_pct"),
                    "max_drawdown": pct_fraction(candidate, "max_drawdown_pct"),
                    "profit_factor": None if candidate["profit_factor"] is None else float(candidate["profit_factor"]),
                    "closed_trade_count": candidate["closed_cycles"],
                    "observations": fold["test_end"] - fold["test_start"],
                    "deflated_sharpe_probability": dsr["deflated_sharpe_probability"],
                    "bootstrap_excess_ci_lower": bootstrap["bootstrap_excess_ci_lower"],
                })
                fold_statistics.append({
                    "fold_id": fold["fold_id"],
                    "deflated_sharpe": dsr,
                    "paired_block_bootstrap": bootstrap,
                })
            screen = evaluate_promotion_gate(gate_folds)
            screens[strategy] = {
                "status": screen["status"], "screen": screen,
                "fold_statistics": fold_statistics,
            }
        except (StatisticalEvidenceError, PromotionEvidenceError, KeyError, TypeError, ValueError) as exc:
            screens[strategy] = {
                "status": "BLOCKED_STATISTICAL_EVIDENCE_INCOMPLETE",
                "reason": str(exc), "fold_statistics": fold_statistics,
            }
    return screens


def _strip_internal_period_returns(walk_forward_folds: list[dict]) -> None:
    for fold in walk_forward_folds:
        for strategy in STRATEGIES:
            fold["strategies"][strategy]["base_costs"].pop("_period_returns", None)
            fold["strategies"][strategy]["two_x_costs"].pop("_period_returns", None)
        fold["buy_hold_base_costs"].pop("_period_returns", None)
        fold["buy_hold_two_x_costs"].pop("_period_returns", None)


def evaluate_market(
    market: dict, dataset: dict, *,
    registered_trial_count: int | None = None,
    bootstrap_replicates: int = 5000,
    trial_series_by_fold: list[list[list[float]]] | None = None,
    compute_promotion: bool = True,
    trial_registry_sha256: str | None = None,
) -> dict:
    candles = dataset["candles"]
    if dataset["gap_count"]:
        return {
            "market_symbol": dataset["market_symbol"],
            "pair": dataset["pair"],
            "row_count": dataset["row_count"],
            "dataset_sha256": dataset["dataset_sha256"],
            "coverage_status": dataset["coverage_status"],
            "promotion_status": "BLOCKED_GAPS",
            "results": {},
        }
    if registered_trial_count is None:
        registered_trial_count = len(STRATEGIES)
    if trial_registry_sha256 is None:
        trial_registry_sha256 = hashlib.sha256(
            json.dumps([PREREGISTRATION_ID, list(STRATEGIES)], sort_keys=True).encode("utf-8")
        ).hexdigest()
    if (isinstance(registered_trial_count, bool)
            or not isinstance(registered_trial_count, int)
            or registered_trial_count < len(STRATEGIES)):
        raise ValueError("registered_trial_count must include the preregistered strategy family")
    if (isinstance(bootstrap_replicates, bool) or not isinstance(bootstrap_replicates, int)
            or bootstrap_replicates < 1000):
        raise ValueError("bootstrap_replicates must be an integer >= 1000")

    is_meme = dataset["market_symbol"] in MEME_SYMBOLS
    base_spread = D(15 if is_meme else 5)
    base_slippage = D(20 if is_meme else 10)
    two_x_fee = FEE_BPS * D(2)
    two_x_spread = base_spread * D(2)
    two_x_slippage = base_slippage * D(2)
    results = {}
    # Five expanding-training OOS folds, each ending with a next-open
    # liquidation candle. OOS ranges are non-overlapping and embargoed.
    walk_forward_folds = []
    for fold in plan_walk_forward_folds(len(candles)):
        start, end = fold["test_start"], fold["test_end"]
        fold_result = dict(fold)
        fold_result["strategies"] = {}
        for strategy in STRATEGIES:
            signals = _signals_for_segment(strategy, candles, start, end)
            fold_result["strategies"][strategy] = {
                "base_costs": _backtest_walk_forward_fold(
                    candles, start, end, signals, initial_target=0,
                    fee_bps=FEE_BPS, half_spread_bps=base_spread,
                    slippage_bps=base_slippage,
                ),
                "two_x_costs": _backtest_walk_forward_fold(
                    candles, start, end, signals, initial_target=0,
                    fee_bps=two_x_fee, half_spread_bps=two_x_spread,
                    slippage_bps=two_x_slippage,
                ),
            }
        buy_hold_signals = [1] * (end - start)
        fold_result["buy_hold_base_costs"] = _backtest_walk_forward_fold(
            candles, start, end, buy_hold_signals, initial_target=1,
            fee_bps=FEE_BPS, half_spread_bps=base_spread,
            slippage_bps=base_slippage,
        )
        fold_result["buy_hold_two_x_costs"] = _backtest_walk_forward_fold(
            candles, start, end, buy_hold_signals, initial_target=1,
            fee_bps=two_x_fee, half_spread_bps=two_x_spread,
            slippage_bps=two_x_slippage,
        )
        walk_forward_folds.append(fold_result)

    results["walk_forward_folds"] = walk_forward_folds

    runner_source = Path(__file__).read_bytes()
    prereg_source = Path(__file__).with_name("STRATEGY_PREREGISTRATION.md").read_bytes()
    strategy_config_sha256 = hashlib.sha256(
        runner_source + b"\\0" + prereg_source + b"\\0" +
        json.dumps({"preregistration_id": PREREGISTRATION_ID,
                    "strategies": list(STRATEGIES)}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cost_model_sha256 = hashlib.sha256(json.dumps({
        "fee_bps_per_side": str(FEE_BPS),
        "base_half_spread_bps": str(base_spread),
        "base_slippage_bps": str(base_slippage),
        "two_x_fee_bps_per_side": str(two_x_fee),
        "two_x_half_spread_bps": str(two_x_spread),
        "two_x_slippage_bps": str(two_x_slippage),
        "participation": str(PARTICIPATION),
        "initial_cash": str(INITIAL_CASH),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    if trial_series_by_fold is None:
        trial_series_by_fold = [
            [fold["strategies"][trial]["base_costs"]["_period_returns"] for trial in STRATEGIES]
            for fold in walk_forward_folds
        ]
    promotion_screens = (
        _evaluate_market_promotion_screens(
            walk_forward_folds,
            dataset_sha256=dataset["dataset_sha256"],
            cost_model_sha256=cost_model_sha256,
            strategy_config_sha256=strategy_config_sha256,
            registered_trial_count=registered_trial_count,
            trial_registry_sha256=trial_registry_sha256,
            trial_series_by_fold=trial_series_by_fold,
            bootstrap_replicates=bootstrap_replicates,
        )
        if compute_promotion else {}
    )
    if compute_promotion:
        _strip_internal_period_returns(walk_forward_folds)

    return {
        "market_symbol": dataset["market_symbol"],
        "pair": dataset["pair"],
        "row_count": dataset["row_count"],
        "first_open_timestamp": dataset["first_open_timestamp"],
        "last_close_timestamp": dataset["last_close_timestamp"],
        "dataset_sha256": dataset["dataset_sha256"],
        "raw_page_sha256": dataset["raw_page_sha256"],
        "page_count": dataset["page_count"],
        "coverage_status": dataset["coverage_status"],
        "gap_count": dataset["gap_count"],
        "strategy_family_trial_count": len(STRATEGIES),
        "registered_trial_count": registered_trial_count,
        "trial_registry_sha256": trial_registry_sha256,
        "cost_model_sha256": cost_model_sha256,
        "strategy_config_sha256": strategy_config_sha256,
        "promotion_screens": promotion_screens,
        "preregistered_strategies": list(STRATEGIES),
        "cost_assumptions": {
            "taker_fee_bps_per_side": str(FEE_BPS),
            "base_half_spread_bps": str(base_spread),
            "base_slippage_bps": str(base_slippage),
            "two_x_fee_bps_per_side": str(two_x_fee),
            "two_x_half_spread_bps": str(two_x_spread),
            "two_x_slippage_bps": str(two_x_slippage),
            "note": "Fee is a public API example, not the user's account tier. Spread/slippage are assumptions, not historical observations.",
        },
        "results": results,
        "walk_forward_folds": walk_forward_folds,
        "walk_forward_status": "FIVE_OOS_FOLDS_STATISTICAL_SCREEN_COMPUTED_FINAL_HOLDOUT_UNTOUCHED",
        "final_holdout": {
            "start_index": len(candles) * WALK_FORWARD_HOLDOUT_START_NUMERATOR // WALK_FORWARD_HOLDOUT_START_DENOMINATOR,
            "end_index": len(candles),
            "status": "RESERVED_UNTOUCHED_NOT_EVALUATED",
        },
        "promotion_status": "RESEARCH_ONLY_NOT_PROMOTABLE",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2026-11-01")
    parser.add_argument("--symbols", default="btcusd,ethusd,xrpusd,dogeusd,shibusd,pepeusd,solusd")
    parser.add_argument("--min-markets", type=int, default=3)
    parser.add_argument("--require-meme", action="store_true")
    args = parser.parse_args(argv)

    try:
        candidates = validate_preregistered_run(
            args.start, args.end, args.symbols, args.min_markets, args.require_meme
        )
        start_ts = _epoch(args.start)
        end_ts = _epoch(args.end)
        markets, markets_hash = fetch_spot_markets()
        selected = [markets[symbol] for symbol in candidates if symbol in markets]
        missing = [symbol for symbol in candidates if symbol not in markets]
        if len(selected) < args.min_markets:
            raise BitstampDataError(f"only {len(selected)} candidate SPOT markets found; need {args.min_markets}")
        if args.require_meme and not any(row["market_symbol"] in MEME_SYMBOLS for row in selected):
            raise BitstampDataError("no preregistered meme-coin SPOT market is available")
        registry = load_trial_registry(
            Path(__file__).with_name("experiment_registry.jsonl"),
            expected_market_symbols=PREREGISTERED_SYMBOLS,
            expected_strategies=STRATEGIES,
            preregistration_id=PREREGISTRATION_ID,
        )
        registered_trial_count = registry["registered_trial_count"]
        trial_registry_sha256 = registry["registry_sha256"]
        output = {
            "research_only": True,
            "preregistration_id": PREREGISTRATION_ID,
            "provider": "Bitstamp public API",
            "provider_terms_scope": "personal noncommercial research only; no redistribution; commercial use requires a signed data license",
            "markets_response_sha256": markets_hash,
            "requested_start": args.start,
            "requested_end": args.end,
            "missing_candidate_symbols": missing,
            "strategy_family": list(STRATEGIES),
            "trial_count": registered_trial_count,
            "trial_registry_sha256": trial_registry_sha256,
            "holdout_policy": "V2: 40% initial training; five expanding-training, non-overlapping OOS folds in the next 50%; 50-bar embargoes; next-open terminal liquidation candles excluded from OOS test indices; final 10% reserved untouched; fixed strategies and no parameter tuning",
            "markets": [],
        }
        market_datasets = []
        for market in selected:
            dataset = fetch_spot_history(
                market["market_symbol"], start_timestamp=start_ts,
                end_timestamp=end_ts, max_pages=40,
            )
            expected_pair = re.sub(r"[^A-Z0-9]", "", str(market.get("name") or "").upper())
            observed_pair = re.sub(r"[^A-Z0-9]", "", str(dataset["pair"]).upper())
            if expected_pair and expected_pair != observed_pair:
                raise BitstampDataError(f"market identity mismatch for {market['market_symbol']}")
            if dataset["row_count"] < 6000:
                raise BitstampDataError(f"insufficient history for {market['market_symbol']}")
            market_datasets.append((market, dataset))

        # First build every market's fold returns in memory. DSR then sees all
        # registered market-strategy trials for each common fold, not only the
        # two strategies of whichever market happened to be processed first.
        market_results = [
            evaluate_market(
                market, dataset, registered_trial_count=registered_trial_count,
                trial_registry_sha256=trial_registry_sha256,
                compute_promotion=False,
            )
            for market, dataset in market_datasets
        ]
        complete_trial_universe = (
            len(selected) * len(STRATEGIES) == registered_trial_count
            and len(market_results) == len(selected)
            and all(len(row.get("walk_forward_folds", [])) == WALK_FORWARD_FOLD_COUNT
                    for row in market_results)
        )
        if complete_trial_universe:
            global_trial_series_by_fold = []
            for fold_index in range(WALK_FORWARD_FOLD_COUNT):
                trial_series = []
                for row in market_results:
                    for strategy in STRATEGIES:
                        trial_series.append(
                            row["walk_forward_folds"][fold_index]["strategies"][strategy]
                            ["base_costs"]["_period_returns"]
                        )
                global_trial_series_by_fold.append(trial_series)
            for row in market_results:
                row["promotion_screens"] = _evaluate_market_promotion_screens(
                    row["walk_forward_folds"],
                    dataset_sha256=row["dataset_sha256"],
                    cost_model_sha256=row["cost_model_sha256"],
                    strategy_config_sha256=row["strategy_config_sha256"],
                    registered_trial_count=registered_trial_count,
                    trial_registry_sha256=trial_registry_sha256,
                    trial_series_by_fold=global_trial_series_by_fold,
                )
                _strip_internal_period_returns(row["walk_forward_folds"])
        else:
            for row in market_results:
                row["promotion_screens"] = {
                    strategy: {
                        "status": "BLOCKED_STATISTICAL_EVIDENCE_INCOMPLETE",
                        "reason": "not all preregistered markets produced five valid folds; global DSR trial universe incomplete",
                        "fold_statistics": [],
                    } for strategy in STRATEGIES
                }
                _strip_internal_period_returns(row.get("walk_forward_folds", []))
        output["markets"] = market_results
        print(json.dumps(output, indent=2, sort_keys=True))
        if any(row["coverage_status"] != "CONTIGUOUS" for row in output["markets"]):
            return 3
        return 0
    except (BitstampDataError, ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
