"""Synchronized multi-market, shared-cash, long-only backtest reference.

Offline only. Prices are in each market's quote currency; FX marks convert the
quote currency into one account currency. No data fetching or order routing.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from .portfolio import PortfolioError, _d
from .market_rules import MarketRules, MarketRulesError

D = Decimal


class MultiMarketBacktestError(ValueError):
    pass


def run_multi_market_backtest(*, bars: Sequence[Mapping[str, object]],
                              signals: Sequence[Mapping[str, object]],
                              market_costs: Mapping[str, Mapping[str, object]],
                              market_rules: Mapping[str, MarketRules],
                              initial_cash: Decimal | str | float,
                              max_gross_weight: Decimal | str | float = "0.95",
                              max_fx_age_seconds: int = 3600,
                              max_portfolio_drawdown: Decimal | str | float | None = None) -> dict[str, object]:
    """Replay synchronized market bars against one shared account-currency cash pool.

    Each bar: {timestamp, open_timestamp, markets: {id: {open_quote, close_quote,
    open_fx, close_fx, volume_base}}}. FX is account-currency units per quote unit.
    Each signal: {timestamp, data_cutoff_timestamp, target_weights: {id: weight}}.
    Signals made at bar close execute at the next bar open. Previous completed
    bar volume caps next-open fills. Sells process before buys; buys are sorted
    by market ID, so shared-cash contention is deterministic.
    """
    try:
        cash = _d(initial_cash, "initial_cash")
        gross_cap = _d(max_gross_weight, "max_gross_weight")
    except PortfolioError as exc:
        raise MultiMarketBacktestError(str(exc)) from exc
    if cash <= 0 or not D("0") < gross_cap <= 1:
        raise MultiMarketBacktestError("initial cash must be positive and gross weight in (0, 1]")
    drawdown_limit = None
    if max_portfolio_drawdown is not None:
        try:
            drawdown_limit = _d(max_portfolio_drawdown, "max_portfolio_drawdown")
        except PortfolioError as exc:
            raise MultiMarketBacktestError(str(exc)) from exc
        if not D("0") < drawdown_limit < D("1"):
            raise MultiMarketBacktestError("max_portfolio_drawdown must be strictly between 0 and 1")
    if len(bars) < 3 or len(signals) != len(bars):
        raise MultiMarketBacktestError("at least three aligned bars and signals are required")

    if (isinstance(max_fx_age_seconds, bool) or not isinstance(max_fx_age_seconds, int)
            or max_fx_age_seconds < 0):
        raise MultiMarketBacktestError("max_fx_age_seconds must be a nonnegative integer")
    clean_bars = []
    previous_close = None
    market_ids = None
    for i, bar in enumerate(bars):
        if not isinstance(bar, Mapping) or not isinstance(bar.get("markets"), Mapping):
            raise MultiMarketBacktestError(f"bar {i} must contain a market mapping")
        ts, open_ts = bar.get("timestamp"), bar.get("open_timestamp")
        if (isinstance(ts, bool) or not isinstance(ts, int) or isinstance(open_ts, bool)
                or not isinstance(open_ts, int) or open_ts < 0 or ts <= open_ts):
            raise MultiMarketBacktestError(f"bar {i} timestamps are invalid")
        if previous_close is not None and open_ts <= previous_close:
            raise MultiMarketBacktestError(f"bar {i} overlaps or is out of chronological order")
        keys = set(bar["markets"])
        if not keys or any(not isinstance(k, str) or not k for k in keys):
            raise MultiMarketBacktestError(f"bar {i} has invalid market IDs")
        if market_ids is None:
            market_ids = keys
        elif keys != market_ids:
            raise MultiMarketBacktestError(f"bar {i} market universe is not aligned; missing/extra markets fail closed")
        clean_market = {}
        for market_id in sorted(keys):
            row = bar["markets"][market_id]
            if not isinstance(row, Mapping):
                raise MultiMarketBacktestError(f"{market_id} bar {i} is invalid")
            vals = {}
            for field in ("open_quote", "close_quote", "open_fx", "close_fx", "volume_base"):
                try:
                    vals[field] = _d(row[field], f"{market_id}.{field}")
                except (KeyError, PortfolioError) as exc:
                    raise MultiMarketBacktestError(f"{market_id} bar {i}: invalid {field}") from exc
            if any(vals[x] <= 0 for x in ("open_quote", "close_quote", "open_fx", "close_fx")):
                raise MultiMarketBacktestError(f"{market_id} bar {i}: prices and FX must be positive")
            if vals["volume_base"] < 0:
                raise MultiMarketBacktestError(f"{market_id} bar {i}: volume cannot be negative")
            for field, cutoff in (("open_fx_timestamp", open_ts), ("close_fx_timestamp", ts)):
                stamp = row.get(field)
                if (isinstance(stamp, bool) or not isinstance(stamp, int)
                        or stamp < 0 or stamp > cutoff or cutoff - stamp > max_fx_age_seconds):
                    raise MultiMarketBacktestError(f"{market_id} bar {i}: {field} is stale, future or invalid")
            clean_market[market_id] = vals
        clean_bars.append({"timestamp": ts, "open_timestamp": open_ts, "markets": clean_market})
        previous_close = ts

    clean_signals = []
    for i, signal in enumerate(signals):
        if not isinstance(signal, Mapping) or not isinstance(signal.get("target_weights"), Mapping):
            raise MultiMarketBacktestError(f"signal {i} must contain target_weights")
        ts, cutoff = signal.get("timestamp"), signal.get("data_cutoff_timestamp")
        if (isinstance(ts, bool) or not isinstance(ts, int) or isinstance(cutoff, bool)
                or not isinstance(cutoff, int) or ts != clean_bars[i]["timestamp"] or cutoff != ts):
            raise MultiMarketBacktestError(f"signal {i} timestamp/cutoff must match its closed decision bar")
        weights = {}
        for market_id, value in signal["target_weights"].items():
            if market_id not in market_ids:
                raise MultiMarketBacktestError(f"signal {i} references unknown market {market_id}")
            try:
                weight = _d(value, f"{market_id}.target_weight")
            except PortfolioError as exc:
                raise MultiMarketBacktestError(str(exc)) from exc
            if weight < 0 or weight > 1:
                raise MultiMarketBacktestError("target weights must be long-only and no greater than 100%")
            weights[market_id] = weight
        if sum(weights.values(), D("0")) > gross_cap:
            raise MultiMarketBacktestError(f"signal {i} breaches shared gross exposure cap")
        clean_signals.append(weights)

    if not isinstance(market_rules, Mapping) or set(market_rules) != set(market_ids):
        raise MultiMarketBacktestError("market rules must exactly cover the synchronized market universe")
    rules = {}
    for market_id, rule in market_rules.items():
        if not isinstance(rule, MarketRules):
            raise MultiMarketBacktestError(f"missing or invalid explicit market rules for {market_id}")
        try:
            rules[market_id] = rule.validated()
        except MarketRulesError as exc:
            raise MultiMarketBacktestError(f"invalid market rules for {market_id}: {exc}") from exc

    costs = {}
    for market_id in market_ids:
        if market_id not in market_costs:
            raise MultiMarketBacktestError(f"missing market cost model for {market_id}")
        row = market_costs[market_id]
        vals = {k: _d(row[k], f"{market_id}.{k}") for k in
                ("fee_bps", "half_spread_bps", "slippage_bps", "max_volume_participation")}
        if (any(vals[k] < 0 or vals[k] >= 10000 for k in ("fee_bps", "half_spread_bps", "slippage_bps"))
                or vals["half_spread_bps"] + vals["slippage_bps"] >= 10000
                or not D("0") < vals["max_volume_participation"] <= 1):
            raise MultiMarketBacktestError(f"invalid costs or volume participation for {market_id}")
        costs[market_id] = vals

    holdings = {market_id: D("0") for market_id in market_ids}
    fills = []
    equity_curve = [{"timestamp": clean_bars[0]["timestamp"], "equity": str(cash)}]
    fees_paid = D("0")
    turnover = D("0")
    max_drawdown = D("0")
    peak = cash
    risk_halted = False
    risk_halt_timestamp = None
    risk_halt_reason = None

    for i in range(1, len(clean_bars)):
        bar = clean_bars[i]
        prior = clean_bars[i - 1]
        open_values = {m: bar["markets"][m]["open_quote"] * bar["markets"][m]["open_fx"]
                       for m in market_ids}
        equity_at_open = cash + sum((holdings[m] * open_values[m] for m in market_ids), D("0"))
        # A portfolio drawdown stop is latched. Once triggered at a completed
        # bar close, all later target signals are ignored and the next opens
        # attempt to liquidate using prior-bar volume capacity. No auto-restart.
        weights = {} if risk_halted else clean_signals[i - 1]
        desired = {m: (equity_at_open * weights.get(m, D("0"))) / open_values[m]
                   for m in market_ids}
        deltas = {m: desired[m] - holdings[m] for m in market_ids}
        capacity = {m: prior["markets"][m]["volume_base"] * costs[m]["max_volume_participation"]
                    for m in market_ids}

        # Sells first to release cash, then buys in stable market-ID order.
        for side, market_order in (("SELL", sorted(market_ids)), ("BUY", sorted(market_ids))):
            for market_id in market_order:
                delta = deltas[market_id]
                if (side == "SELL" and delta >= 0) or (side == "BUY" and delta <= 0):
                    continue
                c = costs[market_id]
                market = bar["markets"][market_id]
                fee_rate = c["fee_bps"] / D("10000")
                cost_rate = (c["half_spread_bps"] + c["slippage_bps"]) / D("10000")
                direction = D("1") - cost_rate if side == "SELL" else D("1") + cost_rate
                fill_price_quote = rules[market_id].round_price(market["open_quote"] * direction, side)
                if fill_price_quote <= 0:
                    raise MultiMarketBacktestError(f"{market_id}: rounded fill price is not positive")
                fill_price_account = fill_price_quote * market["open_fx"]
                if side == "SELL":
                    raw_qty = min(-delta, holdings[market_id], capacity[market_id])
                else:
                    affordable = cash / (fill_price_account * (D("1") + fee_rate))
                    raw_qty = min(delta, capacity[market_id], affordable)
                qty = rules[market_id].round_quantity(raw_qty)
                if qty <= 0 or not rules[market_id].meets_minimums(qty, fill_price_quote):
                    continue
                notional_account = qty * fill_price_account
                fee = notional_account * fee_rate
                if side == "BUY":
                    cash -= notional_account + fee
                    holdings[market_id] += qty
                else:
                    cash += notional_account - fee
                    holdings[market_id] -= qty
                fees_paid += fee
                turnover += notional_account
                fills.append({"timestamp": bar["open_timestamp"], "market_id": market_id,
                              "side": side, "quantity": str(qty),
                              "price_quote": str(fill_price_quote),
                              "price_account": str(fill_price_account),
                              "fee_account": str(fee), "signal_timestamp": prior["timestamp"]})
        if cash < 0 or any(qty < 0 for qty in holdings.values()):
            raise AssertionError("multi-market long-only cash/inventory invariant failed")
        close_equity = cash + sum((holdings[m] * bar["markets"][m]["close_quote"]
                                   * bar["markets"][m]["close_fx"] for m in market_ids), D("0"))
        equity_curve.append({"timestamp": bar["timestamp"], "equity": str(close_equity)})
        peak = max(peak, close_equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - close_equity) / peak)
        if (not risk_halted and drawdown_limit is not None
                and max_drawdown >= drawdown_limit):
            risk_halted = True
            risk_halt_timestamp = bar["timestamp"]
            risk_halt_reason = "MAX_PORTFOLIO_DRAWDOWN"

    final_equity = D(equity_curve[-1]["equity"])
    return {"initial_cash": str(_d(initial_cash, "initial_cash")),
            "final_equity": str(final_equity),
            "total_return": str(final_equity / _d(initial_cash, "initial_cash") - D("1")),
            "max_drawdown": str(max_drawdown), "fees_paid": str(fees_paid),
            "turnover": str(turnover), "fills": fills,
            "risk_halted": risk_halted,
            "risk_halt_timestamp": risk_halt_timestamp,
            "risk_halt_reason": risk_halt_reason,
            "liquidation_complete": all(qty == 0 for qty in holdings.values()) if risk_halted else None,
            "final_cash": str(cash),
            "final_holdings": {m: str(holdings[m]) for m in sorted(holdings)},
            "dust_holdings": {m: str(qty) for m, qty in sorted(holdings.items())
                              if qty > 0 and not rules[m].meets_minimums(
                                  qty, clean_bars[-1]["markets"][m]["close_quote"])},
            "equity_curve": equity_curve}
