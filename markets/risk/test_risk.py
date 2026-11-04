"""markets/risk/test_risk.py - offline tests for the M6 risk engine.

No network, no providers, no clock, no credentials. Every input is built here from explicit values.
Run: python3 -B -m unittest discover -s markets/risk -p "test_*.py"   (from the repository root)
"""
import ast
import copy
import dataclasses
import json
import os
import sys
import unittest
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from markets.risk import (ELIGIBLE, NO_TRADE, REJECTED, REASON_CODES, AccountSnapshot, PendingProposal,  # noqa: E402
                          PositionState, PriceObservation, RiskConfigError, RiskRequest, build_risk_config,
                          evaluate_risk)
from markets.risk import model as M  # noqa: E402
from markets.strategies.contract import BUY, HOLD, INVALID, NO_DATA, SELL  # noqa: E402
from markets.strategies.decision import StrategyDecision  # noqa: E402

BTC = "crypto:binance-spot:BTC-USDT"
ETH = "crypto:binance-spot:ETH-USDT"
NOW = 1000

BASE_CFG = {
    "version": "risk-test-v1",
    "allowed_asset_classes": ["crypto"],
    "allowed_listings": [],
    "max_risk_fraction_per_trade": "0.01",     # 1% of equity
    "max_position_notional": "5000",
    "max_exposure_fraction": "0.5",
    "quantity_step": "1",
    "money_quantum": "0.01",
    "max_price_age_s": 60,
    "pyramiding": False,
}


def cfg(**over):
    mapping = dict(BASE_CFG)
    mapping.update(over)
    return build_risk_config(mapping)


CFG = cfg()


def sdec(decision=BUY, listing=BTC, data_status="COMPLETE"):
    return StrategyDecision("test-strategy", "1", listing, 86400, NOW, 0, 86400, decision, ("R",), ("test reason",),
                            provenance={"data_status": data_status}, config={}, config_fingerprint="f")


def account(equity="10000", cash="10000", budget="500", positions=(), pending=()):
    return AccountSnapshot(equity=equity, cash=cash, risk_budget=budget, positions=tuple(positions),
                           pending=tuple(pending))


DEFAULT = object()


def request(decision=BUY, qty="20", stop="95", acct=DEFAULT, price="100", as_of=990, now=NOW, listing=BTC,
            sd=None, price_listing=None, stop_given=True):
    if acct is DEFAULT:
        acct = account()
    obs = PriceObservation(listing=price_listing or listing, price=price, as_of_s=as_of,
                           source="test-dataset-sha256:abc")
    return RiskRequest(strategy_decision=sdec(decision, listing) if sd is None else sd, listing=listing, price=obs,
                       now_s=now, account=acct, requested_quantity=qty,
                       stop_price=stop if stop_given else None)


def run(req, config=CFG):
    return evaluate_risk(req, config)


def codes(d):
    return set(d.reason_codes)


def failed_rules(d):
    return {r.name for r in d.rules if r.status == M.FAIL}


class TestBuyEligibility(unittest.TestCase):

    def test_valid_buy_is_eligible_with_exact_sizing(self):
        d = run(request())
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.permitted_quantity, "20")
        self.assertEqual(d.caps, {"risk": "20", "notional": "50", "cash": "100", "exposure": "50"})
        self.assertEqual(d.notional, "2000")
        self.assertEqual(d.max_loss, "100")
        self.assertEqual(d.exposure_before, "0")
        self.assertEqual(d.exposure_after, "2000")
        self.assertEqual(d.reason_codes, ())
        self.assertIn("paper trading only", d.explanations[0])

    def test_permitted_is_the_minimum_of_the_caps(self):
        from decimal import Decimal
        d = run(request(qty="50"))      # request above every cap, so the permitted quantity is the smallest cap
        self.assertEqual(Decimal(min(Decimal(v) for v in d.caps.values())), Decimal(d.permitted_quantity))

    def test_buy_needs_no_pending_or_position(self):
        self.assertEqual(run(request()).status, ELIGIBLE)


class TestHold(unittest.TestCase):

    def test_hold_gives_no_trade_and_no_sizing(self):
        d = run(request(decision=HOLD, qty=None, stop=None))
        self.assertEqual(d.status, NO_TRADE)
        self.assertIsNone(d.permitted_quantity)
        self.assertIsNone(d.requested_quantity)
        self.assertIsNone(d.notional)
        self.assertIsNone(d.max_loss)
        self.assertEqual(d.caps, {})
        self.assertEqual(d.reason_codes, ())

    def test_hold_with_a_quantity_is_refused(self):
        d = run(request(decision=HOLD, qty="5", stop=None))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INVALID_QUANTITY", codes(d))

    def test_hold_with_a_stop_is_refused(self):
        d = run(request(decision=HOLD, qty=None, stop="95"))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INVALID_STOP", codes(d))


class TestSell(unittest.TestCase):

    LONG = (PositionState(BTC, "10", "100"),)

    def sell(self, qty="4", positions=None, price="100", acct=None):
        pos = self.LONG if positions is None else positions
        cash = "9000" if pos else "10000"      # equity 10000 = cash + 10 * 100 when long
        a = acct if acct is not None else account(cash=cash, positions=pos)
        return run(request(decision=SELL, qty=qty, stop=None, acct=a, price=price))

    def test_sell_reduces_an_existing_long(self):
        d = self.sell()
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.permitted_quantity, "4")
        self.assertEqual(d.exposure_before, "1000")
        self.assertEqual(d.exposure_after, "600")
        self.assertEqual(d.notional, "400")
        self.assertIsNone(d.max_loss)
        for name in ("MAX_RISK_PER_TRADE", "MAX_POSITION_NOTIONAL", "AVAILABLE_CAPITAL", "MAX_PORTFOLIO_EXPOSURE"):
            self.assertIn(name, {r.name for r in d.rules})
            self.assertEqual([r for r in d.rules if r.name == name][0].status, M.NOT_APPLICABLE)

    def test_sell_exposure_reduction_uses_the_held_mark_not_the_proposal_price(self):
        positions = (PositionState(BTC, "10", "120"),)
        d = self.sell(qty="4", positions=positions, price="100", acct=account(cash="8800", positions=positions))
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.exposure_before, "1200")
        self.assertEqual(d.exposure_after, "720")

    def test_sell_without_position_is_rejected(self):
        d = self.sell(positions=())
        self.assertEqual(d.status, REJECTED)
        self.assertIn("NO_POSITION_TO_SELL", codes(d))

    def test_sell_more_than_held_is_rejected(self):
        d = self.sell(qty="11")
        self.assertEqual(d.status, REJECTED)
        self.assertIn("SELL_EXCEEDS_POSITION", codes(d))

    def test_sell_of_the_exact_position_is_allowed(self):
        self.assertEqual(self.sell(qty="10").status, ELIGIBLE)

    def test_sell_with_a_stop_is_refused(self):
        a = account(cash="9000", positions=self.LONG)
        d = run(request(decision=SELL, qty="4", stop="95", acct=a))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INVALID_STOP", codes(d))

    def test_sell_is_refused_for_a_short_position_held(self):
        shorts = (PositionState(BTC, "-3", "100"),)
        d = self.sell(positions=shorts, acct=account(cash="10000", positions=shorts))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("UNSUPPORTED_DIRECTION", codes(d))

    def test_sell_quantity_rounds_permitted_down_to_step(self):
        d = run(request(decision=SELL, qty="11", stop=None, acct=account(cash="8950", positions=(
            PositionState(BTC, "10.5", "100"),)), price="100"))
        self.assertEqual(d.status, REJECTED)          # 11 exceeds the 10.5 holding
        self.assertEqual(d.permitted_quantity, "10")


class TestRiskBoundary(unittest.TestCase):
    """Risk cap for the base account is min(10000 * 0.01, 500) = 100. Stop 95 gives 5 per unit, so 20 units."""

    def test_exactly_at_risk_cap_passes(self):
        self.assertEqual(run(request(qty="20", stop="95")).status, ELIGIBLE)

    def test_one_step_over_risk_cap_fails_only_the_risk_rule(self):
        d = run(request(qty="21", stop="95"))
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(codes(d), {"MAX_RISK_EXCEEDED"})
        self.assertEqual(failed_rules(d), {"MAX_RISK_PER_TRADE"})

    def test_risk_budget_lower_than_fraction_cap_is_the_binding_cap(self):
        d = run(request(qty="10", stop="95", acct=account(budget="50")))
        self.assertEqual(d.caps["risk"], "10")
        self.assertEqual(d.permitted_quantity, "10")
        self.assertEqual(run(request(qty="11", stop="95", acct=account(budget="50"))).status, REJECTED)


class TestNotionalBoundary(unittest.TestCase):
    """Stop 99 gives 1 per unit so risk never binds. Notional limit set to 2000."""

    CFG = cfg(max_position_notional="2000")

    def test_exactly_at_notional_limit_passes(self):
        self.assertEqual(run(request(qty="20", stop="99"), self.CFG).status, ELIGIBLE)

    def test_one_step_over_notional_limit_fails_only_notional(self):
        d = run(request(qty="21", stop="99"), self.CFG)
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(codes(d), {"MAX_NOTIONAL_EXCEEDED"})


class TestExposureBoundary(unittest.TestCase):
    """Equity 10000, max exposure 0.5 -> 5000. Another listing holds 30 at mark 100 (3000), cash 7000."""

    OTHER = (PositionState(ETH, "30", "100"),)

    def acct(self):
        return account(cash="7000", positions=self.OTHER)

    def test_exposure_exactly_at_limit_passes(self):
        d = run(request(qty="20", stop="99", acct=self.acct()))
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.exposure_before, "3000")
        self.assertEqual(d.exposure_after, "5000")
        self.assertEqual(d.caps["exposure"], "20")

    def test_one_step_over_exposure_limit_fails_only_exposure(self):
        d = run(request(qty="21", stop="99", acct=self.acct()))
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(codes(d), {"MAX_EXPOSURE_EXCEEDED"})


class TestCapital(unittest.TestCase):

    def test_insufficient_cash_fails_the_cash_rule(self):
        # Equity 10000 with 9000 held at mark leaves 1000 cash. Buying 20 at 100 needs 2000.
        held = (PositionState(ETH, "90", "100"),)
        d = run(request(qty="20", stop="95", acct=account(cash="1000", positions=held)),
                cfg(pyramiding=True, max_exposure_fraction="1"))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INSUFFICIENT_CAPITAL", codes(d))

    def test_cash_rule_is_implied_by_exposure_rule_for_consistent_accounts(self):
        # With max_exposure_fraction <= 1, a consistent account cannot fail the cash rule alone.
        held = (PositionState(ETH, "90", "100"),)
        d = run(request(qty="20", stop="95", acct=account(cash="1000", positions=held)),
                cfg(pyramiding=True, max_exposure_fraction="1"))
        self.assertIn("MAX_EXPOSURE_EXCEEDED", codes(d))

    def test_zero_cash_with_full_marked_exposure_is_rejected(self):
        held = (PositionState(ETH, "100", "100"),)
        d = run(request(qty="1", stop="95", acct=account(cash="0", positions=held)), cfg(max_exposure_fraction="1"))
        self.assertEqual(d.status, REJECTED)


class TestPositionConflict(unittest.TestCase):

    HELD = (PositionState(BTC, "5", "100"),)

    def acct(self):
        return account(cash="9500", positions=self.HELD)

    def test_existing_position_without_pyramiding_is_refused(self):
        d = run(request(qty="20", stop="99", acct=self.acct()))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("POSITION_CONFLICT", codes(d))

    def test_existing_position_with_pyramiding_is_allowed_and_counted_in_exposure(self):
        d = run(request(qty="20", stop="99", acct=self.acct()), cfg(pyramiding=True))
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.exposure_before, "500")
        self.assertEqual(d.exposure_after, "2500")
        self.assertEqual(d.permitted_quantity, "20")
        self.assertNotIn("POSITION_CONFLICT", codes(d))

    def test_pyramiding_request_above_exposure_cap_is_reduced_to_that_cap(self):
        d = run(request(qty="50", stop="99", acct=self.acct()), cfg(pyramiding=True))
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(d.permitted_quantity, "45")
        self.assertEqual(d.caps["exposure"], "45")
        self.assertEqual(d.exposure_after, "5000")
        self.assertEqual(codes(d), {"MAX_EXPOSURE_EXCEEDED"})


class TestPending(unittest.TestCase):

    def test_duplicate_pending_buy_is_refused(self):
        a = account(pending=(PendingProposal(BTC, BUY),))
        d = run(request(acct=a))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("DUPLICATE_PROPOSAL", codes(d))

    def test_pending_proposal_for_another_listing_does_not_block(self):
        a = account(pending=(PendingProposal(ETH, BUY),))
        self.assertEqual(run(request(acct=a)).status, ELIGIBLE)

    def test_pending_proposal_must_have_a_valid_side(self):
        a = account(pending=(PendingProposal(BTC, "HOLD"),))
        d = run(request(acct=a))
        self.assertIn("INVALID_PENDING_PROPOSAL", codes(d))
        self.assertIsNone(d.permitted_quantity)


class TestListingAndAsset(unittest.TestCase):

    def test_unsupported_asset_class_is_refused(self):
        d = run(request(), cfg(allowed_asset_classes=["fx"]))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("UNSUPPORTED_ASSET_CLASS", codes(d))

    def test_listing_outside_configured_set_is_refused(self):
        d = run(request(), cfg(allowed_listings=[ETH]))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("UNSUPPORTED_LISTING", codes(d))

    def test_configured_listing_is_allowed(self):
        self.assertEqual(run(request(), cfg(allowed_listings=[BTC])).status, ELIGIBLE)

    def test_strategy_decision_for_another_listing_is_a_mismatch(self):
        req = request(sd=sdec(BUY, ETH))
        d = run(req)
        self.assertEqual(d.status, REJECTED)
        self.assertIn("LISTING_MISMATCH", codes(d))

    def test_price_for_another_listing_is_a_mismatch(self):
        d = run(request(price_listing=ETH))
        self.assertIn("LISTING_MISMATCH", codes(d))

    def test_invalid_listing_text_is_refused(self):
        for bad in ("bogus", "", "crypto:binance-spot:BTC", None, 5):
            with self.subTest(listing=bad):
                req = dataclasses.replace(request(), listing=bad)
                d = run(req)
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_LISTING", codes(d))
                self.assertIsNone(d.permitted_quantity)


class TestPriceAndTime(unittest.TestCase):

    def test_price_at_exact_age_limit_passes(self):
        self.assertEqual(run(request(as_of=NOW - 60)).status, ELIGIBLE)

    def test_price_one_second_too_old_is_stale(self):
        d = run(request(as_of=NOW - 61))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("STALE_PRICE", codes(d))

    def test_price_dated_after_evaluation_time_is_future(self):
        d = run(request(as_of=NOW + 1))
        self.assertIn("FUTURE_PRICE", codes(d))

    def test_price_dated_exactly_at_evaluation_time_is_fresh(self):
        self.assertEqual(run(request(as_of=NOW)).status, ELIGIBLE)

    def test_invalid_prices_fail_closed(self):
        bad = [0, "0", "-1", -5, 100.0, True, "NaN", "inf", "-inf", "1e3", "", " 100", "100 ", None, [100]]
        for value in bad:
            with self.subTest(price=value):
                d = run(request(price=value))
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_PRICE", codes(d))
                self.assertIsNone(d.permitted_quantity)
                self.assertEqual(d.caps, {})

    def test_price_without_source_is_refused(self):
        req = request()
        obs = PriceObservation(listing=BTC, price="100", as_of_s=990, source="   ")
        d = run(dataclasses.replace(req, price=obs))
        self.assertIn("INVALID_PRICE", codes(d))

    def test_price_must_be_an_observation_object(self):
        d = run(dataclasses.replace(request(), price="100"))
        self.assertIn("INVALID_PRICE", codes(d))

    def test_invalid_reference_time_fails_closed(self):
        for value in (1000.0, True, -1, "1000", None):
            with self.subTest(now=value):
                d = run(request(now=value))
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_TIME", codes(d))


class TestAccountValidation(unittest.TestCase):

    def test_missing_account_is_refused(self):
        d = run(request(acct=None))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("MISSING_ACCOUNT_STATE", codes(d))
        self.assertIsNone(d.permitted_quantity)

    def test_invalid_equity_fails_closed(self):
        for value in (0, "0", "-1", 100.0, True, "NaN", "inf", None, "", "1,000"):
            with self.subTest(equity=value):
                d = run(request(acct=account(equity=value)))
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_EQUITY", codes(d))
                self.assertIsNone(d.permitted_quantity)

    def test_invalid_cash_fails_closed(self):
        for value in ("-1", 10000.0, True, "NaN", None):
            with self.subTest(cash=value):
                d = run(request(acct=account(cash=value)))
                self.assertIn("INVALID_CASH", codes(d))

    def test_zero_cash_is_a_valid_value(self):
        held = (PositionState(ETH, "100", "100"),)
        d = run(request(acct=account(cash="0", positions=held)), cfg(max_exposure_fraction="1"))
        self.assertNotIn("INVALID_CASH", codes(d))

    def test_invalid_risk_budget_fails_closed(self):
        for value in ("0", "-5", 500.0, False, "NaN", None):
            with self.subTest(budget=value):
                d = run(request(acct=account(budget=value)))
                self.assertIn("INVALID_RISK_BUDGET", codes(d))

    def test_inconsistent_account_is_refused(self):
        # 9000 cash with no positions, equity 10000: the 1000 is unexplained.
        d = run(request(acct=account(cash="9000")))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INCONSISTENT_ACCOUNT", codes(d))

    def test_equity_must_match_marked_positions(self):
        held = (PositionState(ETH, "10", "100"),)
        ok = run(request(acct=account(cash="9000", positions=held)), cfg(max_exposure_fraction="1"))
        self.assertNotIn("INCONSISTENT_ACCOUNT", codes(ok))
        bad = run(request(acct=account(cash="9001", positions=held)), cfg(max_exposure_fraction="1"))
        self.assertIn("INCONSISTENT_ACCOUNT", codes(bad))

    def test_duplicate_positions_for_one_listing_are_refused(self):
        held = (PositionState(BTC, "1", "100"), PositionState(BTC, "1", "100"))
        d = run(request(acct=account(cash="9800", positions=held)))
        self.assertIn("INVALID_POSITION", codes(d))

    def test_position_with_missing_mark_is_refused(self):
        held = (PositionState(ETH, "1", None),)
        d = run(request(acct=account(cash="10000", positions=held)))
        self.assertIn("INVALID_POSITION", codes(d))

    def test_positions_and_pending_must_be_tuples(self):
        a = AccountSnapshot(equity="10000", cash="10000", risk_budget="500", positions=[], pending=())
        d = run(request(acct=a))
        self.assertIn("INVALID_POSITION", codes(d))

    def test_position_entry_of_the_wrong_type_is_refused(self):
        a = account(positions=({"listing": ETH, "quantity": "1", "mark_price": "100"},))
        d = run(request(acct=a))
        self.assertIn("INVALID_POSITION", codes(d))


class TestQuantityAndStop(unittest.TestCase):

    def test_quantity_must_be_a_multiple_of_the_step(self):
        d = run(request(qty="22"), cfg(quantity_step="5"))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("QUANTITY_STEP_MISMATCH", codes(d))

    def test_quantity_on_the_step_passes(self):
        self.assertEqual(run(request(qty="20"), cfg(quantity_step="5")).status, ELIGIBLE)

    def test_invalid_quantities_fail_closed(self):
        for value in (None, "0", "-1", 20.0, True, "abc", ""):
            with self.subTest(qty=value):
                d = run(request(qty=value))
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_QUANTITY", codes(d))

    def test_stop_must_be_below_entry(self):
        for value in ("100", "101", "150"):
            with self.subTest(stop=value):
                d = run(request(stop=value))
                self.assertIn("INVALID_STOP", codes(d))

    def test_stop_must_be_positive(self):
        for value in ("0", "-1", None, 95.0, True):
            with self.subTest(stop=value):
                d = run(request(stop=value))
                self.assertIn("INVALID_STOP", codes(d))

    def test_buy_without_stop_is_refused(self):
        d = run(request(stop_given=False))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("INVALID_STOP", codes(d))


class TestStrategyDecisionGates(unittest.TestCase):

    def test_partial_data_is_refused_for_buy(self):
        d = run(request(sd=sdec(BUY, BTC, data_status="PARTIAL")))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("DATA_NOT_COMPLETE", codes(d))

    def test_partial_data_is_refused_for_sell(self):
        a = account(cash="9000", positions=(PositionState(BTC, "10", "100"),))
        req = dataclasses.replace(request(decision=SELL, qty="4", stop=None, acct=a),
                                  strategy_decision=sdec(SELL, BTC, data_status="PARTIAL"))
        self.assertIn("DATA_NOT_COMPLETE", codes(run(req)))

    def test_no_data_decision_is_rejected_and_not_sized(self):
        d = run(request(sd=sdec(NO_DATA, BTC), qty=None, stop=None))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("NOT_ACTIONABLE", codes(d))
        self.assertIsNone(d.permitted_quantity)
        self.assertEqual(d.caps, {})

    def test_invalid_decision_is_rejected_and_not_sized(self):
        d = run(request(sd=sdec(INVALID, BTC), qty=None, stop=None))
        self.assertEqual(d.status, REJECTED)
        self.assertIn("NOT_ACTIONABLE", codes(d))
        self.assertIsNone(d.permitted_quantity)

    def test_non_strategy_decision_object_is_refused(self):
        for value in ("BUY", None, {"decision": "BUY"}):
            with self.subTest(sd=value):
                d = run(dataclasses.replace(request(), strategy_decision=value))
                self.assertEqual(d.status, REJECTED)
                self.assertIn("INVALID_STRATEGY_DECISION", codes(d))

    def test_request_must_be_a_risk_request_and_config_a_risk_config(self):
        with self.assertRaises(TypeError):
            evaluate_risk({"not": "a request"}, CFG)
        with self.assertRaises(RiskConfigError):
            evaluate_risk(request(), {"version": "x"})


class TestRiskConfiguration(unittest.TestCase):

    def test_valid_configuration_builds(self):
        c = cfg()
        self.assertEqual(c.version, "risk-test-v1")
        self.assertEqual(c.pyramiding, False)

    def test_every_field_is_required(self):
        for key in BASE_CFG:
            with self.subTest(missing=key):
                m = {k: v for k, v in BASE_CFG.items() if k != key}
                with self.assertRaises(RiskConfigError):
                    build_risk_config(m)

    def test_unknown_key_is_refused(self):
        with self.assertRaises(RiskConfigError):
            build_risk_config(dict(BASE_CFG, surprise=1))

    def test_non_mapping_is_refused(self):
        for value in (None, [], "config"):
            with self.subTest(value=value):
                with self.assertRaises(RiskConfigError):
                    build_risk_config(value)

    def test_fractions_must_be_in_zero_to_one(self):
        for key in ("max_risk_fraction_per_trade", "max_exposure_fraction"):
            for value in ("0", "-0.1", "1.5", 0.01, True, "NaN"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(RiskConfigError):
                        cfg(**{key: value})

    def test_fraction_of_exactly_one_is_accepted(self):
        self.assertEqual(cfg(max_exposure_fraction="1").max_exposure_fraction, 1)

    def test_positive_fields_refuse_zero_negative_and_float(self):
        for key in ("max_position_notional", "quantity_step", "money_quantum"):
            for value in ("0", "-1", 1.0, False, "inf"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(RiskConfigError):
                        cfg(**{key: value})

    def test_price_age_must_be_a_non_negative_integer(self):
        for value in (-1, 60.0, True, "60", None):
            with self.subTest(value=value):
                with self.assertRaises(RiskConfigError):
                    cfg(max_price_age_s=value)

    def test_zero_price_age_is_accepted(self):
        self.assertEqual(cfg(max_price_age_s=0).max_price_age_s, 0)

    def test_pyramiding_must_be_a_real_boolean(self):
        for value in (1, 0, "False", None, "true"):
            with self.subTest(value=value):
                with self.assertRaises(RiskConfigError):
                    cfg(pyramiding=value)

    def test_asset_classes_must_be_non_empty(self):
        with self.assertRaises(RiskConfigError):
            cfg(allowed_asset_classes=[])
        with self.assertRaises(RiskConfigError):
            cfg(allowed_asset_classes="crypto")
        with self.assertRaises(RiskConfigError):
            cfg(allowed_asset_classes=["crypto", "crypto"])

    def test_allowed_listings_may_be_empty_but_must_be_text(self):
        self.assertEqual(cfg(allowed_listings=[]).allowed_listings, ())
        with self.assertRaises(RiskConfigError):
            cfg(allowed_listings=[""])

    def test_version_must_be_non_empty_text(self):
        for value in ("", None, 1, "x" * 65):
            with self.subTest(value=value):
                with self.assertRaises(RiskConfigError):
                    cfg(version=value)

    def test_fingerprint_is_deterministic_and_changes_with_any_limit(self):
        self.assertEqual(cfg().fingerprint(), cfg().fingerprint())
        self.assertNotEqual(cfg().fingerprint(), cfg(max_position_notional="5001").fingerprint())
        self.assertNotEqual(cfg().fingerprint(), cfg(pyramiding=True).fingerprint())
        self.assertEqual(len(cfg().fingerprint()), 64)

    def test_config_is_frozen(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            CFG.version = "changed"


class TestRounding(unittest.TestCase):

    def test_quantity_rounds_down_so_caps_are_never_exceeded(self):
        # Price 10, stop 7 -> 3 per unit. Risk cap 100 -> 33.33... units, rounded DOWN to 33.33.
        c = cfg(quantity_step="0.01")
        d = run(request(qty="33.33", price="10", stop="7"), c)
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.permitted_quantity, "33.33")
        self.assertEqual(d.caps["risk"], "33.33")
        self.assertEqual(d.max_loss, "99.99")

    def test_one_hundredth_over_the_rounded_cap_fails(self):
        c = cfg(quantity_step="0.01")
        d = run(request(qty="33.34", price="10", stop="7"), c)
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(codes(d), {"MAX_RISK_EXCEEDED"})

    def test_money_outputs_round_up_to_the_quantum(self):
        # Max loss 1 * (10 - 6.999) = 3.001 -> reported UP to 3.01.
        c = cfg(quantity_step="0.01")
        d = run(request(qty="1", price="10", stop="6.999"), c)
        self.assertEqual(d.max_loss, "3.01")

    def test_notional_rounds_up_to_the_quantum(self):
        # 3 * 3.333 = 9.999 -> reported UP to 10.
        c = cfg(quantity_step="0.01")
        d = run(request(qty="3", price="3.333", stop="3.0"), c)
        self.assertEqual(d.notional, "10")

    def test_exact_money_is_not_inflated(self):
        d = run(request())
        self.assertEqual(d.notional, "2000")
        self.assertEqual(d.max_loss, "100")

    def test_decimal_strings_are_exact_not_binary(self):
        # 0.1 + 0.2 must not drift. 0.1 + 0.2 = 0.3 exactly in decimal.
        held = (PositionState(ETH, "1", "0.2"),)
        d = run(request(acct=account(cash="9999.9", positions=held, equity="10000.1"), price="0.1",
                        stop="0.05", qty="1"), cfg(max_position_notional="5000", max_exposure_fraction="1",
                                                    quantity_step="1", money_quantum="0.001", pyramiding=True))
        self.assertEqual(d.exposure_before, "0.2")
        self.assertEqual(d.status, ELIGIBLE)

    def test_outputs_are_plain_text_not_exponent(self):
        d = run(request(qty="20", stop="99"))
        for value in (d.notional, d.max_loss, d.exposure_before, d.exposure_after, d.permitted_quantity):
            self.assertNotIn("E", str(value))
            self.assertNotIn("e", str(value))


class TestDeterminismAndImmutability(unittest.TestCase):

    def test_repeated_evaluation_is_byte_identical(self):
        req = request()
        outputs = {run(req).to_json() for _ in range(5)}
        self.assertEqual(len(outputs), 1)

    def test_equal_inputs_built_separately_give_identical_output(self):
        a = run(request()).to_json()
        b = run(request()).to_json()
        self.assertEqual(a, b)

    def test_inputs_are_not_mutated(self):
        held = (PositionState(ETH, "30", "100"),)
        acct = account(cash="7000", positions=held, pending=(PendingProposal(ETH, SELL),))
        req = request(acct=acct, qty="20", stop="99")
        before = (repr(req), repr(CFG), copy.deepcopy(req.strategy_decision.provenance),
                  copy.deepcopy(req.strategy_decision.indicators))
        run(req)
        run(req)
        after = (repr(req), repr(CFG), copy.deepcopy(req.strategy_decision.provenance),
                 copy.deepcopy(req.strategy_decision.indicators))
        self.assertEqual(before, after)

    def test_invalid_inputs_are_not_mutated(self):
        req = dataclasses.replace(request(), price="bad", account=account(equity="-1"))
        before = repr(req)
        run(req)
        self.assertEqual(before, repr(req))

    def test_output_is_strict_json_and_matches_to_dict(self):
        d = run(request())
        parsed = json.loads(d.to_json())
        self.assertEqual(parsed, json.loads(json.dumps(d.to_dict(), allow_nan=False)))
        self.assertEqual(parsed["schema"], M.SCHEMA)
        self.assertEqual(parsed["disclaimer"], M.NO_RISK_DISCLAIMER)

    def test_output_has_no_account_or_credential_fields(self):
        d = run(request())
        text = d.to_json().lower()
        for word in ("api_key", "secret", "token", "password", "credential", "account_id", "order_id"):
            self.assertNotIn(word, text)

    def test_reason_codes_are_all_registered(self):
        samples = [run(request(qty="21", stop="95")), run(request(acct=None)), run(request(price="bad")),
                   run(request(sd=sdec(NO_DATA, BTC)))]
        for d in samples:
            for c in d.reason_codes:
                self.assertIn(c, REASON_CODES)


class TestFailClosed(unittest.TestCase):
    """Every invalid input returns REJECTED with a reason code, never a size."""

    def assertFailsClosed(self, d):
        self.assertEqual(d.status, REJECTED)
        self.assertTrue(d.reason_codes)
        self.assertIsNone(d.permitted_quantity)
        self.assertIsNone(d.notional)
        self.assertEqual(d.caps, {})

    def test_every_invalid_case_fails_closed(self):
        cases = {
            "missing account": request(acct=None),
            "bad price": request(price="0"),
            "bad equity": request(acct=account(equity="0")),
            "bad cash": request(acct=account(cash="-1")),
            "bad budget": request(acct=account(budget="0")),
            "bad time": request(now=-1),
            "bad quantity": request(qty="0"),
            "bad stop": request(stop="200"),
            "not actionable": request(sd=sdec(NO_DATA, BTC), qty=None, stop=None),
            "listing mismatch": request(sd=sdec(BUY, ETH)),
            "inconsistent account": request(acct=account(cash="9000")),
            "short position": request(acct=account(positions=(PositionState(ETH, "-1", "100"),), cash="10000")),
        }
        for name, req in cases.items():
            with self.subTest(case=name):
                self.assertFailsClosed(run(req))

    def test_multiple_problems_are_all_reported(self):
        d = run(request(price="bad", acct=account(equity="-1", cash="-1")))
        self.assertTrue({"INVALID_PRICE", "INVALID_EQUITY", "INVALID_CASH"} <= codes(d))

    def test_every_reason_code_listed_is_a_rule_failure_or_invalid_input(self):
        d = run(request(price="bad", acct=account(equity="-1", cash="-1")))
        self.assertEqual(len(d.reason_codes), len(set(d.reason_codes)))


class TestQuantityIsCappedByRequest(unittest.TestCase):
    """BUY: permitted = floor_to_step(min(requested, every cap)). SELL: permitted = floor_to_step(min(requested, held)).
    Quantity-dependent outputs (notional, max loss, exposure after) use permitted, not requested."""

    def test_buy_below_every_cap_is_unchanged(self):
        d = run(request(qty="5", stop="95"))
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.permitted_quantity, "5")
        self.assertEqual(d.approved_quantity, "5")
        self.assertEqual(d.notional, "500")
        self.assertEqual(d.max_loss, "25")
        self.assertEqual(d.exposure_after, "500")

    def test_buy_above_risk_cap_is_reduced_to_risk_cap_and_rejected(self):
        d = run(request(qty="50", stop="95"))
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(d.requested_quantity, "50")
        self.assertEqual(d.permitted_quantity, "20")
        self.assertIsNone(d.approved_quantity)
        self.assertEqual(codes(d), {"MAX_RISK_EXCEEDED"})
        self.assertEqual(d.notional, "2000")
        self.assertEqual(d.max_loss, "100")
        self.assertEqual(d.exposure_after, "2000")
        self.assertIsNone(d.to_dict()["approved_quantity"])

    def test_buy_above_notional_cap_is_reduced(self):
        d = run(request(qty="30", stop="99"), cfg(max_position_notional="2000"))
        self.assertEqual(d.permitted_quantity, "20")
        self.assertEqual(codes(d), {"MAX_NOTIONAL_EXCEEDED"})
        self.assertEqual(d.notional, "2000")
        self.assertEqual(d.max_loss, "20")

    def test_buy_above_cash_cap_is_reduced(self):
        # Cash caps the BUY at 10 units. Caps: risk 20, notional 50, cash 10, exposure 10.
        held = (PositionState(ETH, "90", "100"),)
        d = run(request(qty="20", stop="95", acct=account(cash="1000", positions=held)),
                cfg(pyramiding=True, max_exposure_fraction="1"))
        self.assertEqual(d.permitted_quantity, "10")
        self.assertEqual(d.notional, "1000")
        self.assertEqual(d.exposure_after, "10000")
        self.assertIn("INSUFFICIENT_CAPITAL", codes(d))

    def test_buy_above_exposure_cap_is_reduced(self):
        other = (PositionState(ETH, "30", "100"),)
        d = run(request(qty="21", stop="99", acct=account(cash="7000", positions=other)))
        self.assertEqual(d.permitted_quantity, "20")
        self.assertEqual(d.exposure_after, "5000")
        self.assertEqual(codes(d), {"MAX_EXPOSURE_EXCEEDED"})

    def test_quantity_step_rounding_never_increases_the_requested_quantity(self):
        # Risk cap 100 / 3 = 33.333... units, rounded DOWN to 33.33 (never up to 33.34).
        d = run(request(qty="40", price="10", stop="7"), cfg(quantity_step="0.01"))
        self.assertEqual(d.permitted_quantity, "33.33")
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(d.max_loss, "99.99")

    def test_buy_permitted_never_exceeds_request_over_a_sweep(self):
        c = cfg(quantity_step="0.01")
        for raw in ("0.01", "1", "7.77", "20", "20.01", "33.33", "33.34", "40", "500", "5000"):
            d = run(request(qty=raw, price="10", stop="7"), c)
            self.assertLessEqual(Decimal(d.permitted_quantity), Decimal(raw))

    def test_only_eligible_proposals_carry_an_approved_quantity(self):
        for raw in range(1, 61):
            d = run(request(qty=str(raw), stop="95"))
            self.assertLessEqual(Decimal(d.permitted_quantity), Decimal(raw))
            if d.status == ELIGIBLE:
                self.assertEqual(d.approved_quantity, str(raw))
                self.assertEqual(Decimal(d.permitted_quantity), Decimal(raw))
            else:
                self.assertEqual(d.status, REJECTED)
                self.assertIsNone(d.approved_quantity)
                self.assertLess(Decimal(d.permitted_quantity), Decimal(raw))

    def test_sell_below_holding_is_unchanged(self):
        d = run(request(decision=SELL, qty="4", stop=None,
                        acct=account(cash="9000", positions=(PositionState(BTC, "10", "100"),))))
        self.assertEqual(d.status, ELIGIBLE)
        self.assertEqual(d.permitted_quantity, "4")
        self.assertEqual(d.approved_quantity, "4")
        self.assertEqual(d.notional, "400")
        self.assertEqual(d.exposure_after, "600")

    def test_sell_above_holding_is_capped_at_holding_and_rejected(self):
        d = run(request(decision=SELL, qty="11", stop=None,
                        acct=account(cash="9000", positions=(PositionState(BTC, "10", "100"),))))
        self.assertEqual(d.status, REJECTED)
        self.assertEqual(d.requested_quantity, "11")
        self.assertEqual(d.permitted_quantity, "10")
        self.assertIsNone(d.approved_quantity)
        self.assertEqual(d.notional, "1000")
        self.assertEqual(d.exposure_after, "0")
        self.assertEqual(codes(d), {"SELL_EXCEEDS_POSITION"})

    def test_sell_step_rounding_never_increases_the_sale(self):
        held = (PositionState(BTC, "10.5", "100"),)
        d = run(request(decision=SELL, qty="11", stop=None, acct=account(cash="8950", positions=held)),
                cfg(quantity_step="0.5"))
        self.assertEqual(d.permitted_quantity, "10.5")
        self.assertEqual(d.status, REJECTED)

    def test_sell_permitted_never_exceeds_request_or_holding_over_a_sweep(self):
        held = (PositionState(BTC, "10", "100"),)
        for raw in range(1, 15):
            d = run(request(decision=SELL, qty=str(raw), stop=None, acct=account(cash="9000", positions=held)))
            self.assertLessEqual(Decimal(d.permitted_quantity), min(Decimal(raw), Decimal(10)))


class TestPackageBoundary(unittest.TestCase):
    """Static checks on the shipped package. These are not behaviour tests of the engine."""

    FORBIDDEN = ("markets.providers", "markets.data_pipeline", "markets.provider", "pipeline", "signal",
                 "btc_signal", "socket", "urllib", "http", "ssl", "requests", "subprocess", "ftplib", "smtplib",
                 "time", "datetime", "random", "os", "secrets", "getpass", "keyring", "importlib", "ctypes",
                 "multiprocessing", "threading", "asyncio", "sys", "webbrowser")

    def package_files(self):
        out = []
        for name in sorted(os.listdir(HERE)):
            if name.endswith(".py") and not name.startswith("test_"):
                out.append(os.path.join(HERE, name))
        return out

    def imports_of(self, path):
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module)
        return names

    def test_package_imports_no_providers_network_clock_or_execution(self):
        for path in self.package_files():
            with self.subTest(file=os.path.basename(path)):
                for name in self.imports_of(path):
                    for bad in self.FORBIDDEN:
                        self.assertFalse(name == bad or name.startswith(bad + "."),
                                         f"{os.path.basename(path)} imports {name}")

    def test_package_imports_only_expected_modules(self):
        allowed_prefix = ("markets.identity", "markets.strategies", "markets.risk", "dataclasses", "fractions",
                          "decimal", "hashlib", "json", "math", "re", "__future__")
        for path in self.package_files():
            with self.subTest(file=os.path.basename(path)):
                for name in self.imports_of(path):
                    self.assertTrue(name.startswith(allowed_prefix), f"unexpected import {name}")

    def test_shared_risk_code_has_no_venue_asset_or_provider_specific_logic(self):
        banned = ("btc", "binance", "usdt", "kraken", "bitcoin")
        for path in self.package_files():
            with self.subTest(file=os.path.basename(path)):
                with open(path, encoding="utf-8") as f:
                    text = f.read().lower()
                for word in banned:
                    self.assertNotIn(word, text, f"{os.path.basename(path)} mentions {word!r}")


if __name__ == "__main__":
    unittest.main()
