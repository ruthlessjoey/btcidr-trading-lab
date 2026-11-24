import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tmm_core.exposure_policy import ExposureMark, ExposurePolicy
from tmm_core.policy_gateway import PolicyEnforcedRiskGateway
from tmm_core.risk_gateway import RiskGatewayError, SQLiteRiskStateStore
from tmm_core.session_risk import SessionLossGuard


class Ledger:
    def __init__(self):
        self.holdings = {"BTC/USDT": "0.1", "ETH/USDT": "0.1"}
        self.equity = "1000"

    def snapshot_holdings(self, account_id):
        return dict(self.holdings)

    def snapshot_equity(self, account_id):
        return self.equity


class Marks:
    def __init__(self):
        self.stale = False
        self.omit = False
        self.calls = []

    def snapshot_marks(self, account_id, market_ids, timestamp):
        self.calls.append((account_id, market_ids, timestamp))
        result = {
            "BTC/USDT": ExposureMark(
                "BTC/USDT", "BTC", "USDT", "1000",
                timestamp - (121 if self.stale else 0), "10000"
            ),
            "ETH/USDT": ExposureMark(
                "ETH/USDT", "ETH", "USDT", "1000", timestamp, "10000"
            ),
        }
        if self.omit:
            result.pop("ETH/USDT")
        return result


class Anchor:
    def __init__(self):
        self.heads = {}

    def verify(self, account_id, head_hash):
        return self.heads.get(account_id) == head_hash

    def publish(self, account_id, head_hash):
        self.heads[account_id] = head_hash
        return True


class SessionApproval:
    def verify_session_start(self, request):
        return True


class ResetApproval:
    def verify_reset(self, request):
        return True


class ExposureApproval:
    def __init__(self, approved=True):
        self.approved = approved
        self.requests = []

    def verify_exposure_policy(self, account_id, policy):
        self.requests.append((account_id, dict(policy)))
        return self.approved


class PolicyGatewayTests(unittest.TestCase):
    def make_gateway(self, directory, *, exposure_approved=True):
        ledger = Ledger()
        marks = Marks()
        anchor = Anchor()
        approval = ExposureApproval(exposure_approved)
        gateway = PolicyEnforcedRiskGateway.create_new(
            account_id="paper-test",
            guard=SessionLossGuard(
                session_id="s1", opening_equity="1000",
                max_session_loss=".05", started_at=100,
            ),
            ledger=ledger,
            store=SQLiteRiskStateStore(Path(directory) / "risk.sqlite3"),
            anchor=anchor,
            reset_authorizer=ResetApproval(),
            session_policy_authorizer=SessionApproval(),
            mark_provider=marks,
            exposure_policy=ExposurePolicy(),
            exposure_policy_authorizer=approval,
        )
        return gateway, ledger, marks, anchor, approval

    def test_gateway_caps_buy_to_per_market_exposure_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, marks, _, _ = self.make_gateway(directory)
            result = gateway.propose(proposals={"BTC/USDT": "1"}, timestamp=101)
            self.assertLessEqual(result["permitted_deltas"]["BTC/USDT"], Decimal("0.150000000000000000000000001"))
            self.assertTrue(result["exposure_policy_enforced"])
            self.assertEqual(marks.calls[0][1], ("BTC/USDT", "ETH/USDT"))

    def test_stale_mark_fails_closed_before_inner_gateway_authorizes(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, marks, _, _ = self.make_gateway(directory)
            marks.stale = True
            with self.assertRaises(RiskGatewayError):
                gateway.propose(proposals={"BTC/USDT": "0.01"}, timestamp=200)
            self.assertFalse(gateway.is_halted)

    def test_missing_mark_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, marks, _, _ = self.make_gateway(directory)
            marks.omit = True
            with self.assertRaises(RiskGatewayError):
                gateway.propose(proposals={"BTC/USDT": "0.01"}, timestamp=101)

    def test_agent_cannot_override_holdings_marks_or_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, _, _, _ = self.make_gateway(directory)
            with self.assertRaises(TypeError):
                gateway.propose(
                    proposals={"BTC/USDT": "0.01"},
                    holdings={"BTC/USDT": "1000"},
                    marks={},
                    policy=ExposurePolicy(max_gross_exposure="1"),
                    timestamp=101,
                )

    def test_unknown_market_is_rejected_even_if_agent_proposes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, _, _, _ = self.make_gateway(directory)
            with self.assertRaises(RiskGatewayError):
                gateway.propose(proposals={"SCAM/USDT": "0.01"}, timestamp=101)

    def test_owner_policy_approval_is_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger()
            with self.assertRaises(RiskGatewayError):
                PolicyEnforcedRiskGateway.create_new(
                    account_id="paper-test",
                    guard=SessionLossGuard(
                        session_id="s1", opening_equity="1000",
                        max_session_loss=".05", started_at=100,
                    ),
                    ledger=ledger,
                    store=SQLiteRiskStateStore(Path(directory) / "risk.sqlite3"),
                    anchor=Anchor(),
                    reset_authorizer=ResetApproval(),
                    session_policy_authorizer=SessionApproval(),
                    mark_provider=Marks(),
                    exposure_policy=ExposurePolicy(max_gross_exposure="1"),
                    exposure_policy_authorizer=ExposureApproval(False),
                )

    def test_strategy_facade_exposes_no_settlement_or_reset_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, _, _, _ = self.make_gateway(directory)
            self.assertFalse(hasattr(gateway, "settle_sell"))
            self.assertFalse(hasattr(gateway, "reset"))

    def test_exposure_limits_are_not_agent_selectable(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway, _, _, _, approval = self.make_gateway(directory)
            gateway.propose(proposals={"BTC/USDT": "0.01"}, timestamp=101)
            self.assertEqual(approval.requests[0][0], "paper-test")
            self.assertEqual(approval.requests[0][1]["max_gross_exposure"], "0.95")


if __name__ == "__main__":
    unittest.main()
