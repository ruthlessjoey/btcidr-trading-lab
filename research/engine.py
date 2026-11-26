"""research/engine.py - research-only spot backtest engine (long-only, no leverage).

Rules that prevent look-ahead bias:
  * A signal for bar i is computed from candles up to and including bar i (a COMPLETED candle).
  * The resulting order is filled at the OPEN of bar i+1, never at the close that produced it.
  * The last bar's signal is never executed (there is no next open).
Costs are explicit: a fee per side on the traded value, and slippage that worsens every fill.
All cost and trading-rule numbers are ASSUMPTIONS; none is verified for any exchange account.
"""
import math
from dataclasses import dataclass

import validator

DAY = 86400


class EngineError(Exception):
    """The input data or request is not acceptable for a backtest."""


@dataclass(frozen=True)
class Costs:
    name: str
    fee: float      # fraction of traded value, charged on every buy and every sell
    slip: float     # fraction by which each fill is worse than the bar's open


@dataclass(frozen=True)
class Rules:
    """Trading-rule ASSUMPTIONS (unverified for Tokocrypto)."""
    capital: float = 1000.0       # hypothetical starting USDT for every segment
    fraction: float = 1.0         # share of cash used when entering; 1.0 = fully invested
    min_notional: float = 10.0    # smaller orders are rejected
    qty_step: float = 1e-5        # BTC quantity is rounded DOWN to a multiple of this


def check_series(candles, tf_sec=DAY, skipped_times=()):
    """Raises EngineError unless candles are sorted, unique, consecutive and sane.
    `skipped_times` lists open times deliberately removed (sensitivity runs only)."""
    if not candles:
        raise EngineError("no candles")
    skipped = set(skipped_times)
    for i, c in enumerate(candles):
        if validator.bad_ohlc(c) or c.volume < 0 or not all(
                math.isfinite(x) for x in (c.open, c.high, c.low, c.close, c.volume)):
            raise EngineError(f"candle #{i} has impossible prices or volume")
        if i == 0:
            continue
        step = c.time - candles[i - 1].time
        if step == 0:
            raise EngineError(f"duplicate candle at {c.time}")
        if step < 0:
            raise EngineError(f"candles are not in chronological order at index {i}")
        if step != tf_sec:
            if step % tf_sec:
                raise EngineError(f"candle #{i} is off the {tf_sec}s grid")
            missing = [candles[i - 1].time + k * tf_sec for k in range(1, step // tf_sec)]
            if any(t not in skipped for t in missing):
                raise EngineError(f"missing candle(s) before index {i} (time {c.time})")


def assert_completed(candles, as_of_ts, tf_sec=DAY):
    """Every candle must be finished at `as_of_ts` (its open time + timeframe <= as_of)."""
    if candles and candles[-1].time + tf_sec > as_of_ts:
        raise EngineError("the last candle is still forming (incomplete); it must not be used")


def _floor_step(x, step):
    return round(math.floor(x / step + 1e-9) * step, 12)


def simulate(candles, signals, start, end, costs, rules=Rules()):
    """Runs bars [start, end). Bar i trades at its open using signals[i-1]."""
    if len(signals) != len(candles):
        raise EngineError("signals and candles differ in length")
    if not 1 <= start < end <= len(candles):
        raise EngineError(f"bad bar range [{start}, {end}) for {len(candles)} candles")
    if not 0 < rules.fraction <= 1:
        raise EngineError("fraction must be in (0, 1]: no leverage")
    cash, qty, entry = rules.capital, 0.0, None
    orders, trades, equity, held = [], [], [], 0
    for i in range(start, end):
        c, want = candles[i], signals[i - 1]
        if want not in (0, 1):
            raise EngineError(f"signal must be 0 or 1, got {want!r}")
        if want == 1 and qty == 0:
            fill = c.open * (1 + costs.slip)
            q = _floor_step(cash * rules.fraction / (fill * (1 + costs.fee)), rules.qty_step)
            notional = q * fill
            if q <= 0 or notional < rules.min_notional:
                orders.append({"time": c.time, "side": "buy", "status": "rejected",
                               "reason": f"order value {notional:.2f} below minimum {rules.min_notional}"})
            else:
                fee = notional * costs.fee
                cash -= notional + fee
                qty = q
                entry = {"time": c.time, "price": fill, "qty": q, "cost": notional + fee, "fee": fee}
                orders.append({"time": c.time, "side": "buy", "status": "filled", "ref_open": c.open,
                               "fill": fill, "qty": q, "fee": fee})
        elif want == 0 and qty > 0:
            fill = c.open * (1 - costs.slip)
            notional = qty * fill
            fee = notional * costs.fee
            cash += notional - fee
            orders.append({"time": c.time, "side": "sell", "status": "filled", "ref_open": c.open,
                           "fill": fill, "qty": qty, "fee": fee})
            trades.append({"entry_time": entry["time"], "entry_price": entry["price"],
                           "exit_time": c.time, "exit_price": fill, "qty": qty,
                           "fees": entry["fee"] + fee, "pnl": (notional - fee) - entry["cost"],
                           "ret": ((notional - fee) - entry["cost"]) / entry["cost"]})
            qty, entry = 0.0, None
        if cash < -1e-9:
            raise EngineError("cash went negative: leverage is not allowed")
        if qty > 0:
            held += 1
        equity.append(cash + qty * c.close)
    last = candles[end - 1]
    open_pos = None
    if qty > 0:
        open_pos = {"entry_time": entry["time"], "entry_price": entry["price"], "qty": qty,
                    "mark_price": last.close,
                    "unrealized_pnl_before_exit_costs": qty * last.close - entry["cost"]}
    return {"costs": costs, "rules": rules, "start": start, "end": end,
            "times": [candles[i].time for i in range(start, end)], "equity": equity,
            "orders": orders, "trades": trades, "open_position": open_pos, "held_bars": held}


def metrics(run):
    """Summary numbers for one simulate() result. See the report for what each one can mislead about."""
    cap, eq = run["rules"].capital, run["equity"]
    peak, max_dd = cap, 0.0
    for v in eq:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak)
    pnls = [t["pnl"] for t in run["trades"]]
    wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
    return {"total_return": eq[-1] / cap - 1, "max_drawdown": max_dd,
            "closed_trades": len(pnls), "open_position": run["open_position"] is not None,
            "win_rate": len(wins) / len(pnls) if pnls else None,
            "profit_factor": sum(wins) / -sum(losses) if losses else None,
            "gross_profit": sum(wins), "gross_loss": sum(losses),
            "exposure": run["held_bars"] / len(eq), "bars": len(eq),
            "rejected_orders": sum(1 for o in run["orders"] if o["status"] == "rejected"),
            "total_fees": sum(o.get("fee", 0.0) for o in run["orders"]),
            "final_equity": eq[-1]}


def buy_and_hold(candles, start, end, costs, rules=Rules()):
    """Buys once at the first bar's open with the same costs and sizing, then holds."""
    return simulate(candles, [1] * len(candles), start, end, costs, rules)


def cash_only(candles, start, end, costs, rules=Rules()):
    return simulate(candles, [0] * len(candles), start, end, costs, rules)
