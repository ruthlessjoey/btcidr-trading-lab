"""Preregistered personal, noncommercial Bitstamp spot-candle research.

Raw candles remain in memory and are never uploaded as CI artifacts. This
script is exploratory only; it does not produce an installable trading signal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_DOWN
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


def _epoch(value: str, *, end: bool = False) -> int:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc
    moment = datetime.combine(
        parsed, time(23, 0) if end else time(0, 0), tzinfo=timezone.utc
    )
    if end:
        moment = moment.replace(hour=23, minute=0)
    return int(moment.timestamp()) + (3600 if end else 0)


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


def make_signals(strategy: str, candles: list[dict]) -> list[int]:
    closes = [D(row["close"]) for row in candles]
    signals = []
    target = 0
    for index, close in enumerate(closes):
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


def backtest(
    candles: list[dict],
    signals: list[int],
    *,
    fee_bps: Decimal,
    half_spread_bps: Decimal,
    slippage_bps: Decimal,
) -> dict:
    if len(candles) != len(signals) or len(candles) < 2:
        raise ValueError("candles/signals length mismatch or insufficient bars")
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
        low_price = D(candles[index]["low"])
        if not low_price.is_finite() or low_price <= 0 or low_price > min(open_price, close_price):
            raise ValueError("candle low must be finite, positive and no higher than open or close")
        close_equity_curve.append(close_equity)
        # A long-only portfolio is most adversely marked at the candle low.
        # Mark after the next-open fill decision and retain the open-gap mark.
        intrabar_equity_curve.append(cash + base * low_price)
        intrabar_equity_curve.append(close_equity)

    final_equity = close_equity_curve[-1]

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
        "final_equity": str(final_equity.quantize(D("0.01"))),
        "net_return_pct": str(((final_equity / INITIAL_CASH - 1) * 100).quantize(D("0.0001"))),
        "max_drawdown_pct": str((intrabar_max_drawdown * 100).quantize(D("0.0001"))),
        "max_drawdown_intrabar_pct": str((intrabar_max_drawdown * 100).quantize(D("0.0001"))),
        "max_drawdown_close_pct": str((close_max_drawdown * 100).quantize(D("0.0001"))),
        "drawdown_measurement": "open-gap, intrabar low and candle-close equity marks; adverse intrabar path is conservative but OHLC does not reveal event ordering",
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


def _signals_for_segment(strategy: str, all_candles: list[dict], start: int, end: int) -> list[int]:
    # Indicators are computed causally from history through each candle close.
    all_signals = make_signals(strategy, all_candles[:end])
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
        signals = make_signals(strategy, candles)
        results[strategy] = {}
        for split_name, (start, end) in ranges.items():
            segment = candles[start:end]
            segment_signals = signals[start:end]
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
        start_ts = _epoch(args.start)
        end_ts = _epoch(args.end, end=True)
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
