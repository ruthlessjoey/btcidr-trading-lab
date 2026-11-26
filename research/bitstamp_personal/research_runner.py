"""Preregistered personal, noncommercial Bitstamp spot-candle research.

Raw candles remain in memory and are never uploaded as CI artifacts. This
script is exploratory only; it does not produce an installable trading signal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN, localcontext
from typing import Callable

from bitstamp_public_ohlc import (
    BitstampDataError, fetch_spot_history, fetch_spot_markets,
)

D = Decimal
INITIAL_CASH = D("10000")
PARTICIPATION = D("0.05")
FEE_BPS = D("16")  # documented public API example only; not the user's fee tier
STRATEGIES = ("SMA20_50_LONG_ONLY", "RSI14_MEAN_REVERSION_LONG_ONLY")
PREREGISTRATION_ID = "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V1"
PREREGISTERED_START = "2024-01-01"
PREREGISTERED_END = "2026-11-01"
PREREGISTERED_SYMBOLS = (
    "btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd"
)
PREREGISTERED_MIN_MARKETS = 3
PREREGISTERED_REQUIRE_MEME = True
MEME_SYMBOLS = {"dogeusd", "shibusd", "pepeusd", "bonkusd", "flokusd"}

# V1 uses the present-day active market list to select a historical universe.
# This is not point-in-time evidence for the 2024-2026 research window and can
# omit later-delisted or historically unavailable instruments.
POINT_IN_TIME_UNIVERSE_EVIDENCE_STATUS = "NOT_VERIFIED"


def require_point_in_time_universe_evidence() -> None:
    if POINT_IN_TIME_UNIVERSE_EVIDENCE_STATUS != "VERIFIED":
        raise BitstampDataError(
            "public research blocked before network access: V1 selects historical "
            "markets from the current active SPOT list, which can omit delisted or "
            "historically unavailable instruments and create survivorship bias; "
            "a versioned V2 preregistration must provide independently reviewed "
            "point-in-time listing/matching intervals and integrate five-fold OOS "
            "evaluation with the frozen promotion gate"
        )



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
                rsi = D(100) if losses == 0 else D(100) - D(100) / (D(1) + gains / losses)
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
    rebalance_targets: bool,
) -> None:
    """Reject malformed inputs before any portfolio arithmetic is performed."""
    if len(candles) != len(signals) or len(candles) < 2:
        raise ValueError("candles/signals length mismatch or insufficient bars")
    if type(rebalance_targets) is not bool:
        raise ValueError("rebalance_targets must be a boolean")
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
    rebalance_targets: bool,
) -> dict:
    _validate_backtest_inputs(
        candles, signals, fee_bps=fee_bps,
        half_spread_bps=half_spread_bps, slippage_bps=slippage_bps,
        rebalance_targets=rebalance_targets,
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
    fixed_base_target = None

    for index in range(1, len(candles)):
        weight = D(signals[index - 1])
        open_price = D(candles[index]["open"])
        close_price = D(candles[index]["close"])
        prior_volume = D(candles[index - 1]["volume"])
        max_qty = prior_volume * PARTICIPATION
        equity_at_open = cash + base * open_price
        intrabar_equity_curve.append(equity_at_open)
        if rebalance_targets:
            desired_base = (equity_at_open * weight / open_price) if open_price > 0 else D("0")
        else:
            if weight == 0:
                desired_base = D("0")
            else:
                if fixed_base_target is None:
                    initial_buy_price = open_price * (D(1) + cost_rate)
                    fixed_base_target = (
                        cash / (initial_buy_price * (D(1) + fee_rate))
                    ).quantize(quantum, rounding=ROUND_DOWN)
                desired_base = fixed_base_target
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
                if base == 0:
                    cycles.append(cycle_pnl)
                    cycle_pnl = D("0")
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
    mark_to_market_return_pct = (
        (final_equity / INITIAL_CASH - 1) * 100
    ).quantize(D("0.0001"))
    # Base quantities are quantized to `quantum`; exactly one quantum is still a holding.
    # A flat realized-return label therefore requires precisely zero inventory.
    terminal_position_is_flat = base == 0
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
        "initial_cash": str(INITIAL_CASH),
        "execution_policy": (
            "TARGET_WEIGHT_REBALANCING" if rebalance_targets
            else "FIXED_QUANTITY_ENTRY_THEN_HOLD"
        ),
        "final_equity": str(final_equity.quantize(D("0.01"))),
        "net_return_pct": str(mark_to_market_return_pct) if terminal_position_is_flat else None,
        "mark_to_market_return_pct": str(mark_to_market_return_pct),
        "return_valuation": "MARK_TO_MARKET_AFTER_EXECUTED_COSTS",
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
    rebalance_targets: bool = True,
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
            rebalance_targets=rebalance_targets,
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


def evaluate_market(market: dict, dataset: dict) -> dict:
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
    ranges = split_ranges(len(candles))
    is_meme = dataset["market_symbol"] in MEME_SYMBOLS
    base_spread = D(15 if is_meme else 5)
    base_slippage = D(20 if is_meme else 10)
    stress_spread = D(30 if is_meme else 10)
    stress_slippage = D(50 if is_meme else 25)
    results = {}
    for strategy in STRATEGIES:
        results[strategy] = {}
        for split_name, (start, end) in ranges.items():
            segment = candles[start:end]
            segment_signals = _signals_for_segment(strategy, candles, start, end)
            results[strategy][split_name] = {
                "base_costs": backtest(
                    segment, segment_signals, fee_bps=FEE_BPS,
                    half_spread_bps=base_spread, slippage_bps=base_slippage,
                ),
                "stress_costs": backtest(
                    segment, segment_signals, fee_bps=FEE_BPS,
                    half_spread_bps=stress_spread, slippage_bps=stress_slippage,
                ),
            }
    buy_hold_signals = [1] * len(candles)
    holdout_start, holdout_end = ranges["holdout"]
    results["BUY_AND_HOLD_BASELINE"] = {
        "holdout_base_costs": backtest(
            candles[holdout_start:holdout_end], buy_hold_signals[holdout_start:holdout_end],
            fee_bps=FEE_BPS, half_spread_bps=base_spread, slippage_bps=base_slippage,
            rebalance_targets=False,
        )
    }
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
        "preregistered_strategies": list(STRATEGIES),
        "cost_assumptions": {
            "taker_fee_bps_per_side": str(FEE_BPS),
            "base_half_spread_bps": str(base_spread),
            "base_slippage_bps": str(base_slippage),
            "stress_half_spread_bps": str(stress_spread),
            "stress_slippage_bps": str(stress_slippage),
            "note": "Fee is a public API example, not the user's account tier. Spread/slippage are assumptions, not historical observations.",
        },
        "results": results,
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
        # This release gate must run before markets metadata or any OHLC request.
        require_point_in_time_universe_evidence()
        start_ts = _epoch(args.start)
        end_ts = _epoch(args.end)
        markets, markets_hash = fetch_spot_markets()
        selected = [markets[symbol] for symbol in candidates if symbol in markets]
        missing = [symbol for symbol in candidates if symbol not in markets]
        if len(selected) < args.min_markets:
            raise BitstampDataError(f"only {len(selected)} candidate SPOT markets found; need {args.min_markets}")
        if args.require_meme and not any(row["market_symbol"] in MEME_SYMBOLS for row in selected):
            raise BitstampDataError("no preregistered meme-coin SPOT market is available")
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
            "trial_count": len(selected) * len(STRATEGIES),
            "holdout_policy": "fixed preregistered strategies; no parameter search; chronological 60/20/20 with 50-bar embargo; report all results",
            "markets": [],
        }
        for market in selected:
            dataset = fetch_spot_history(
                market["market_symbol"], start_timestamp=start_ts,
                end_timestamp=end_ts, max_pages=40,
            )
            expected_pair = re.sub(r"[^A-Z0-9]", "", str(market.get("name") or "").upper())
            observed_pair = re.sub(r"[^A-Z0-9]", "", str(dataset["pair"]).upper())
            if expected_pair and expected_pair != observed_pair:
                raise BitstampDataError(f"market identity mismatch for {market['market_symbol']}")
            if dataset["row_count"] < 5000:
                raise BitstampDataError(f"insufficient history for {market['market_symbol']}")
            output["markets"].append(evaluate_market(market, dataset))
        print(json.dumps(output, indent=2, sort_keys=True))
        if any(row["coverage_status"] != "CONTIGUOUS" for row in output["markets"]):
            return 3
        return 0
    except (BitstampDataError, ValueError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
