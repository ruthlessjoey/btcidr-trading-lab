"""markets/risk/engine.py - the independent, deterministic risk decision (M6).

evaluate_risk(request, config) -> RiskDecision

It judges one proposal from the M5 strategy engine against an explicit configuration and an explicit account snapshot.
It never fetches, never reads a clock, never imports a provider, and never places an order. Given identical inputs it
returns an identical decision.

Order of checks:
  1. Input validation. Every invalid or conflicting input is collected. Any such problem makes the decision REJECTED,
     with every reason code listed, and no sizing number is reported (absent, never zero).
  2. Gate rules that apply to every decision: listing allowed, price fresh, data complete, decision actionable.
  3. Decision rules:
       HOLD  -> NO_TRADE when the gates pass. No sizing.
       BUY   -> long entry. Risk, notional, cash, exposure, position and duplicate rules, with exact caps.
       SELL  -> sale of an existing long of the same listing. Short selling is not supported, so a SELL with no long
                position is REJECTED.
       NO_DATA, INVALID -> REJECTED (not actionable); no sizing.
  4. Status: REJECTED if any rule failed; otherwise NO_TRADE for HOLD, else ELIGIBLE.

Sizing formulas (BUY; all exact rational arithmetic, see amounts.py):
  d            = price - stop                         per-unit risk, requires 0 < stop < price
  risk_cap     = min(equity * max_risk_fraction, risk_budget)
  caps (quantities, each rounded DOWN to quantity_step):
     risk      = floor(risk_cap / d)
     notional  = floor(max_position_notional / price)
     cash      = floor(cash / price)                  no leverage: notional may not exceed cash
     exposure  = floor(max(0, equity * max_exposure_fraction - exposure_before) / price)
  permitted   = floor_to_step(min(requested, *caps.values()), step)   never exceeds the request
  rules check the REQUESTED quantity against the same limits: requested * d <= risk_cap, etc.
  exposure_before = sum over ALL positions of quantity * mark (existing holdings are valued at their marks; the entry
                    price is used only for the proposed notional, so the equity identity and exposure agree)
  exposure_after  = exposure_before + permitted * price
  Identity: with equity = cash + sum(quantity * mark) and max_exposure_fraction <= 1, the cash rule is implied by the
            exposure rule. The cash rule is kept as an explicit backstop; it cannot fail alone for a consistent account.
Money reported to the caller is rounded UP to money_quantum (conservative). Quantities are rounded DOWN to quantity_step.

SELL: permitted = floor_to_step(min(requested, held)); exposure_after = exposure_before - permitted * held_mark. The risk and
buying-power rules are NOT_APPLICABLE, because a sale reduces exposure and uses no buying power.
"""
from fractions import Fraction

from markets.identity import IdentityError, parse_listing
from markets.risk import model as M
from markets.risk.config import RiskConfig, RiskConfigError
from markets.risk.amounts import (NumberError, ceil_to_quantum, fraction_to_decimal_text, floor_to_step, parse_decimal,
                                  parse_int, parse_non_negative, parse_positive, to_text)
from markets.strategies.contract import BUY, HOLD, SELL
from markets.strategies.decision import StrategyDecision


def _attempt(fn, *args):
    try:
        return fn(*args), None
    except NumberError as e:
        return None, str(e)


def _parse_listing(text):
    if not isinstance(text, str):
        return None
    try:
        return parse_listing(text)
    except (IdentityError, ValueError):
        return None


def _money(amount, quantum):
    return fraction_to_decimal_text(ceil_to_quantum(amount, quantum), quantum)


def _qty(amount, step):
    return fraction_to_decimal_text(floor_to_step(amount, step), step)


def _rule(name, ok, code, detail):
    return M.RuleResult(name, M.PASS if ok else M.FAIL, None if ok else code, detail)


def _na(name, detail):
    return M.RuleResult(name, M.NOT_APPLICABLE, None, detail)


def _unique(codes):
    return tuple(dict.fromkeys(c for c in codes if c is not None))


def _explain(rules, headline):
    lines = [headline]
    for r in rules:
        status = {"PASS": "passed", "FAIL": "FAILED", "NOT_APPLICABLE": "not applicable"}[r.status]
        lines.append(f"{r.name}: {status}. {r.detail}")
    return tuple(lines)


def _invalid_decision(config, request, problems):
    sd = request.strategy_decision if isinstance(request.strategy_decision, StrategyDecision) else None
    rules = tuple(M.RuleResult(rule, M.FAIL, code, detail) for rule, code, detail in problems)
    codes = _unique(code for _, code, _ in problems)
    return M.RiskDecision(
        status=M.REJECTED,
        listing=request.listing if isinstance(request.listing, str) else None,
        side=sd.decision if sd else None,
        strategy_id=sd.strategy_id if sd else None,
        strategy_version=sd.strategy_version if sd else None,
        strategy_decision=sd.decision if sd else None,
        strategy_reference_open_s=sd.reference_open_s if sd else None,
        strategy_config_fingerprint=sd.config_fingerprint if sd else None,
        evaluated_at_s=None,
        risk_config_version=config.version,
        risk_config_fingerprint=config.fingerprint(),
        rules=rules,
        reason_codes=codes,
        explanations=_explain(rules, "REJECTED: one or more inputs are invalid or cannot be reconciled. No size is "
                                     "reported."),
    )


def evaluate_risk(request, config):
    if not isinstance(config, RiskConfig):
        raise RiskConfigError("config must be a RiskConfig built by build_risk_config")
    if not isinstance(request, M.RiskRequest):
        raise TypeError("request must be a RiskRequest")

    problems = []

    def problem(rule, code, detail):
        problems.append((rule, code, detail))

    # ---- 1. Input validation -------------------------------------------------------------------------------------
    listing = _parse_listing(request.listing)
    if listing is None:
        problem("LISTING_VALID", "INVALID_LISTING", "listing must be a canonical listing identity")
    canonical = listing.canonical if listing else None

    sd = request.strategy_decision
    if not isinstance(sd, StrategyDecision):
        problem("STRATEGY_DECISION_VALID", "INVALID_STRATEGY_DECISION",
                "strategy decision must be an M5 StrategyDecision")
    decision = sd.decision if isinstance(sd, StrategyDecision) else None
    if isinstance(sd, StrategyDecision) and canonical is not None and sd.listing != canonical:
        problem("LISTING_MATCH", "LISTING_MISMATCH",
                f"strategy decision is for {sd.listing!r}, the request is for {canonical!r}")

    now, err = _attempt(parse_int, "now_s", request.now_s, 0)
    if err:
        problem("REFERENCE_TIME_VALID", "INVALID_TIME", err)

    price_obj = request.price
    price = as_of = None
    if not isinstance(price_obj, M.PriceObservation):
        problem("PRICE_VALID", "INVALID_PRICE", "a validated price observation is required")
    else:
        price, err = _attempt(parse_positive, "price", price_obj.price)
        if err:
            problem("PRICE_VALID", "INVALID_PRICE", err)
        as_of, err = _attempt(parse_int, "as_of_s", price_obj.as_of_s, 0)
        if err:
            problem("PRICE_VALID", "INVALID_PRICE", err)
        if not isinstance(price_obj.source, str) or not price_obj.source.strip():
            problem("PRICE_VALID", "INVALID_PRICE", "the price observation must name its source")
        price_listing = _parse_listing(price_obj.listing)
        if price_listing is None or canonical is None or price_listing.canonical != canonical:
            problem("LISTING_MATCH", "LISTING_MISMATCH", "the price observation is for a different listing")

    equity = cash = budget = None
    positions = {}        # canonical -> (quantity Fraction, mark Fraction or None)
    pending_listings = set()
    acct = request.account
    if not isinstance(acct, M.AccountSnapshot):
        problem("ACCOUNT_PRESENT", "MISSING_ACCOUNT_STATE", "account state is required and was not supplied")
    else:
        equity, err = _attempt(parse_positive, "equity", acct.equity)
        if err:
            problem("ACCOUNT_VALID", "INVALID_EQUITY", err)
        cash, err = _attempt(parse_non_negative, "cash", acct.cash)
        if err:
            problem("ACCOUNT_VALID", "INVALID_CASH", err)
        budget, err = _attempt(parse_positive, "risk_budget", acct.risk_budget)
        if err:
            problem("ACCOUNT_VALID", "INVALID_RISK_BUDGET", err)
        if not isinstance(acct.positions, tuple) or not isinstance(acct.pending, tuple):
            problem("ACCOUNT_VALID", "INVALID_POSITION", "positions and pending must be tuples")
        else:
            for p in acct.positions:
                pl = _parse_listing(getattr(p, "listing", None)) if isinstance(p, M.PositionState) else None
                if pl is None:
                    problem("POSITION_VALID", "INVALID_POSITION", "each position needs a canonical listing")
                    continue
                if pl.canonical in positions:
                    problem("POSITION_VALID", "INVALID_POSITION", f"two positions for {pl.canonical}")
                    continue
                qty, err = _attempt(parse_decimal, "position quantity", p.quantity)
                if err:
                    problem("POSITION_VALID", "INVALID_POSITION", err)
                    continue
                if qty < 0:
                    problem("DIRECTION_SUPPORTED", "UNSUPPORTED_DIRECTION",
                            f"{pl.canonical} is a short position; short positions are not supported")
                    continue
                mark = None
                if qty > 0:
                    mark, err = _attempt(parse_positive, "mark price", p.mark_price)
                    if err:
                        problem("POSITION_VALID", "INVALID_POSITION", err)
                        continue
                positions[pl.canonical] = (Fraction(qty), None if mark is None else Fraction(mark))
            for pr in acct.pending:
                pl = _parse_listing(getattr(pr, "listing", None)) if isinstance(pr, M.PendingProposal) else None
                if pl is None or getattr(pr, "side", None) not in (BUY, SELL):
                    problem("PENDING_VALID", "INVALID_PENDING_PROPOSAL", "each pending proposal needs a listing and a "
                                                                         "side of BUY or SELL")
                    continue
                pending_listings.add(pl.canonical)
            if equity is not None and cash is not None:
                total = Fraction(cash) + sum((q * m for q, m in positions.values() if m is not None), Fraction(0))
                if total != Fraction(equity):
                    problem("ACCOUNT_CONSISTENT", "INCONSISTENT_ACCOUNT",
                            "equity must equal cash plus the marked value of all positions")

    requested = None
    stop = None
    step = config.quantity_step
    if decision in (BUY, SELL):
        requested, err = _attempt(parse_positive, "requested_quantity", request.requested_quantity)
        if err:
            problem("QUANTITY_VALID", "INVALID_QUANTITY", err)
        elif Fraction(requested) % Fraction(step) != 0:
            problem("QUANTITY_VALID", "QUANTITY_STEP_MISMATCH",
                    f"requested quantity must be a whole multiple of {to_text(step)}")
            requested = None
    elif decision == HOLD and request.requested_quantity is not None:
        problem("QUANTITY_VALID", "INVALID_QUANTITY", "a HOLD decision carries no quantity")

    if decision == BUY:
        stop, err = _attempt(parse_positive, "stop_price", request.stop_price)
        if err:
            problem("STOP_VALID", "INVALID_STOP", err)
        elif price is not None and stop >= price:
            problem("STOP_VALID", "INVALID_STOP", "a BUY stop must be below the entry price")
    elif request.stop_price is not None:
        problem("STOP_VALID", "INVALID_STOP", "a stop price applies only to a BUY")

    if problems:
        return _invalid_decision(config, request, problems)

    # ---- 2. Gates and decision rules ------------------------------------------------------------------------------
    P = Fraction(price)
    E = Fraction(equity)
    C = Fraction(cash)
    B = Fraction(budget)
    held, held_mark = positions.get(canonical, (Fraction(0), None))
    held_mark = held_mark if held_mark is not None else Fraction(0)
    exposure_before = sum((q * m for q, m in positions.values() if m is not None), Fraction(0))
    quantum = config.money_quantum
    max_exposure = E * Fraction(config.max_exposure_fraction)
    listing_allowed = (listing.instrument.asset_class in config.allowed_asset_classes
                       and (not config.allowed_listings or canonical in config.allowed_listings))

    rules = []
    rules.append(_rule("LISTING_ALLOWED", listing.instrument.asset_class in config.allowed_asset_classes,
                       "UNSUPPORTED_ASSET_CLASS", f"asset class {listing.instrument.asset_class!r} is not in the "
                       f"configured allowed set {list(config.allowed_asset_classes)}"))
    if config.allowed_listings:
        rules.append(_rule("LISTING_IN_ALLOWED_SET", canonical in config.allowed_listings, "UNSUPPORTED_LISTING",
                           f"{canonical} must be one of the configured listings"))
    if as_of > now:
        rules.append(_rule("PRICE_FRESH", False, "FUTURE_PRICE",
                           f"price is dated after the evaluation time {now}"))
    else:
        age = now - as_of
        rules.append(_rule("PRICE_FRESH", age <= config.max_price_age_s, "STALE_PRICE",
                           f"price is {age} s old; the limit is {config.max_price_age_s} s"))
    rules.append(_rule("DATA_PROVENANCE", sd.provenance.get("data_status") == "COMPLETE", "DATA_NOT_COMPLETE",
                       f"the strategy decision was produced from {sd.provenance.get('data_status')!r} data; only "
                       f"COMPLETE data may be sized"))
    rules.append(_rule("DECISION_ACTIONABLE", decision in (BUY, SELL, HOLD), "NOT_ACTIONABLE",
                       f"strategy decision {decision} is not actionable"))

    caps = {}
    permitted = None
    notional = max_loss = None
    exposure_after = exposure_before

    if decision == BUY:
        d = P - Fraction(stop)
        risk_cap = min(E * Fraction(config.max_risk_fraction_per_trade), B)
        max_notional = Fraction(config.max_position_notional)
        caps = {
            "risk": floor_to_step(risk_cap / d, step),
            "notional": floor_to_step(max_notional / P, step),
            "cash": floor_to_step(C / P, step),
            "exposure": floor_to_step(max(Fraction(0), max_exposure - exposure_before) / P, step),
        }
        req = Fraction(requested)
        permitted = floor_to_step(min(req, *caps.values()), step)
        rules.append(_rule("POSITION_CONFLICT", not (held > 0 and not config.pyramiding), "POSITION_CONFLICT",
                           f"{canonical} is already held ({_qty(held, step)}); pyramiding is "
                           f"{'enabled' if config.pyramiding else 'disabled'}"))
        rules.append(_rule("DUPLICATE_PROPOSAL", canonical not in pending_listings, "DUPLICATE_PROPOSAL",
                           f"a proposal for {canonical} is already pending"))
        rules.append(_rule("DIRECTION_SUPPORTED", True, None, "a BUY opens a long position; short selling is not "
                                                              "supported and is not used"))
        rules.append(_rule("MAX_RISK_PER_TRADE", req * d <= risk_cap, "MAX_RISK_EXCEEDED",
                           f"requested risk {_money(req * d, quantum)} against cap {_money(risk_cap, quantum)}"))
        rules.append(_rule("MAX_POSITION_NOTIONAL", req * P <= max_notional, "MAX_NOTIONAL_EXCEEDED",
                           f"requested notional {_money(req * P, quantum)} against limit "
                           f"{to_text(config.max_position_notional)}"))
        rules.append(_rule("AVAILABLE_CAPITAL", req * P <= C, "INSUFFICIENT_CAPITAL",
                           f"requested notional {_money(req * P, quantum)} against available cash {to_text(cash)}"))
        rules.append(_rule("MAX_PORTFOLIO_EXPOSURE", exposure_before + req * P <= max_exposure, "MAX_EXPOSURE_EXCEEDED",
                           f"exposure after would be {_money(exposure_before + req * P, quantum)} against limit "
                           f"{_money(max_exposure, quantum)}"))
        exposure_after = exposure_before + permitted * P
        notional = permitted * P
        max_loss = permitted * d
    elif decision == SELL:
        req = Fraction(requested)
        caps = {"position": floor_to_step(held, step) if held > 0 else Fraction(0)}
        permitted = floor_to_step(min(req, held), step) if held > 0 else Fraction(0)
        rules.append(_rule("DIRECTION_SUPPORTED", held > 0, "NO_POSITION_TO_SELL",
                           f"no long position in {canonical}; short selling is not supported"))
        rules.append(_rule("SELL_WITHIN_POSITION", req <= held, "SELL_EXCEEDS_POSITION",
                           f"requested {_qty(req, step)} against held {_qty(held, step)}"))
        rules.append(_rule("DUPLICATE_PROPOSAL", canonical not in pending_listings, "DUPLICATE_PROPOSAL",
                           f"a proposal for {canonical} is already pending"))
        for name in ("POSITION_CONFLICT", "MAX_RISK_PER_TRADE", "MAX_POSITION_NOTIONAL", "AVAILABLE_CAPITAL",
                     "MAX_PORTFOLIO_EXPOSURE"):
            rules.append(_na(name, "not applicable to a sale, which reduces exposure and uses no buying power"))
        exposure_after = exposure_before - permitted * held_mark
        notional = permitted * P
    elif decision == HOLD:
        for name in ("DIRECTION_SUPPORTED", "POSITION_CONFLICT", "DUPLICATE_PROPOSAL", "MAX_RISK_PER_TRADE",
                     "MAX_POSITION_NOTIONAL", "AVAILABLE_CAPITAL", "MAX_PORTFOLIO_EXPOSURE"):
            rules.append(_na(name, "no proposal to size: the strategy decision is HOLD"))
    else:
        for name in ("DIRECTION_SUPPORTED", "POSITION_CONFLICT", "DUPLICATE_PROPOSAL", "MAX_RISK_PER_TRADE",
                     "MAX_POSITION_NOTIONAL", "AVAILABLE_CAPITAL", "MAX_PORTFOLIO_EXPOSURE"):
            rules.append(_na(name, "not sized: the strategy decision is not actionable"))

    rules = tuple(rules)
    fail_codes = _unique(r.reason_code for r in rules if r.status == M.FAIL)
    if fail_codes:
        status = M.REJECTED
        headline = "REJECTED: " + ", ".join(fail_codes) + "."
    elif decision == HOLD:
        status = M.NO_TRADE
        headline = "NO_TRADE: the strategy decision is HOLD. No proposal to size."
    else:
        status = M.ELIGIBLE
        headline = ("ELIGIBLE for paper trading only: every applicable rule passed. This is not an order and not a "
                    "guarantee against loss.")

    sized = decision in (BUY, SELL)
    return M.RiskDecision(
        status=status,
        listing=canonical,
        side=decision,
        strategy_id=sd.strategy_id,
        strategy_version=sd.strategy_version,
        strategy_decision=decision,
        strategy_reference_open_s=sd.reference_open_s,
        strategy_config_fingerprint=sd.config_fingerprint,
        evaluated_at_s=now,
        risk_config_version=config.version,
        risk_config_fingerprint=config.fingerprint(),
        requested_quantity=_qty(requested, step) if sized else None,
        permitted_quantity=_qty(permitted, step) if sized and permitted is not None else None,
        approved_quantity=_qty(requested, step) if sized and status == M.ELIGIBLE else None,
        entry_price=to_text(parse_decimal("price", price_obj.price)),
        stop_price=to_text(parse_decimal("stop", request.stop_price)) if decision == BUY else None,
        notional=_money(notional, quantum) if sized else None,
        max_loss=_money(max_loss, quantum) if decision == BUY else None,
        equity=to_text(parse_decimal("equity", acct.equity)),
        cash=to_text(parse_decimal("cash", acct.cash)),
        exposure_before=_money(exposure_before, quantum),
        exposure_after=_money(exposure_after, quantum) if sized else None,
        caps={k: _qty(v, step) for k, v in caps.items()},
        rules=rules,
        reason_codes=fail_codes,
        explanations=_explain(rules, headline),
    )
