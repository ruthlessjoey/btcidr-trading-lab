import os
import tempfile
import unittest
from pathlib import Path

from tmm_core.risk_gateway import (
    RiskGateway, RiskGatewayError, SQLiteRiskStateStore,
)
from tmm_core.session_risk import SessionLossGuard


class Ledger:
    def __init__(self, holdings):
        self.holdings = holdings
        self.equity = "1000"
        self.requested_account = None

    def snapshot_holdings(self, account_id):
        self.requested_account = account_id
        return dict(self.holdings)

    def snapshot_equity(self, account_id):
        self.requested_account = account_id
        return self.equity


class Anchor:
    def __init__(self):
        self.heads = {}
        self.fail_publish = False

    def verify(self, account_id, head_hash):
        return self.heads.get(account_id) == head_hash

    def publish(self, account_id, head_hash):
        if self.fail_publish:
            return False
        self.heads[account_id] = head_hash
        return True


class SessionPolicyAuthorizer:
    def __init__(self, approved=True):
        self.approved = approved
        self.requests = []

    def verify_session_start(self, request):
        self.requests.append(dict(request))
        return self.approved


class ResetAuthorizer:
    def __init__(self, approved=False):
        self.approved = approved
        self.requests = []

    def verify_reset(self, request):
        self.requests.append(dict(request))
        return self.approved


class RiskGatewayTests(unittest.TestCase):
    def make_gateway(self, directory, *, approved=False, halted=False):
        store = SQLiteRiskStateStore(Path(directory) / "risk.sqlite3")
        anchor = Anchor()
        ledger = Ledger({"BTC/USDT": "0.25", "ETH/USDT": "1.0"})
        authorizer = ResetAuthorizer(approved)
        policy_authorizer = SessionPolicyAuthorizer()
        guard = SessionLossGuard(session_id="s1", opening_equity="1000",
                                 max_session_loss=".05", started_at=100)
        if halted:
            guard.force_halt(timestamp=101, reason="TEST_STOP")
        gateway = RiskGateway.create_new(
            account_id="paper-account-1", guard=guard, ledger=ledger,
            store=store, anchor=anchor, reset_authorizer=authorizer,
            session_policy_authorizer=policy_authorizer)
        return gateway, store, anchor, ledger, authorizer, policy_authorizer

    def test_sqlite_store_rejects_shared_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "shared"
            parent.mkdir()
            os.chmod(parent, 0o755)
            try:
                with self.assertRaises(RiskGatewayError):
                    SQLiteRiskStateStore(parent / "risk.sqlite3")
            finally:
                os.chmod(parent, 0o700)

    def test_sqlite_store_rejects_symlink_database(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.db"
            target.write_bytes(b"not a database")
            link = Path(directory) / "risk.sqlite3"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaises(RiskGatewayError):
                SQLiteRiskStateStore(link)

    def test_sqlite_store_rejects_hard_linked_database(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.db"
            original.write_bytes(b"not a database")
            linked = Path(directory) / "risk.sqlite3"
            try:
                os.link(original, linked)
            except (OSError, NotImplementedError):
                self.skipTest("hard links are unavailable on this platform")
            with self.assertRaises(RiskGatewayError):
                SQLiteRiskStateStore(linked)

    def test_account_start_requires_owner_approved_non_null_loss_limit(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteRiskStateStore(Path(d) / "risk.sqlite3")
            ledger = Ledger({"BTC/USDT": "0.25"})
            anchor = Anchor()
            reset_authorizer = ResetAuthorizer()
            policy_authorizer = SessionPolicyAuthorizer(approved=False)
            guard = SessionLossGuard(session_id="s1", opening_equity="1000",
                                     max_session_loss=".05", started_at=100)
            with self.assertRaises(RiskGatewayError):
                RiskGateway.create_new(
                    account_id="paper-account-1", guard=guard, ledger=ledger,
                    store=store, anchor=anchor, reset_authorizer=reset_authorizer,
                    session_policy_authorizer=policy_authorizer)
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteRiskStateStore(Path(d) / "risk.sqlite3")
            ledger = Ledger({"BTC/USDT": "0.25"})
            anchor = Anchor()
            with self.assertRaises(RiskGatewayError):
                RiskGateway.create_new(
                    account_id="paper-account-1",
                    guard=SessionLossGuard(session_id="s1", opening_equity="1000",
                                           max_session_loss=None, started_at=100),
                    ledger=ledger, store=store, anchor=anchor,
                    reset_authorizer=ResetAuthorizer(),
                    session_policy_authorizer=SessionPolicyAuthorizer())

    def test_proposal_reads_holdings_from_authoritative_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            gateway, _, _, ledger, _, _ = self.make_gateway(d)
            result = gateway.propose(proposals={"BTC/USDT": "-9"}, timestamp=101)
            self.assertEqual(ledger.requested_account, "paper-account-1")
            self.assertEqual(str(result["permitted_deltas"]["BTC/USDT"]), "-0.25")

    def test_caller_cannot_supply_holdings_override(self):
        with tempfile.TemporaryDirectory() as d:
            gateway, _, _, _, _, _ = self.make_gateway(d)
            with self.assertRaises(TypeError):
                gateway.propose(proposals={"BTC/USDT": "-9"},
                                holdings={"BTC/USDT": "99"}, timestamp=101)

    def test_restore_requires_matching_external_anchor(self):
        with tempfile.TemporaryDirectory() as d:
            _, store, anchor, ledger, authorizer, policy_authorizer = self.make_gateway(d)
            restored = RiskGateway.restore(account_id="paper-account-1", ledger=ledger,
                                           store=store, anchor=anchor,
                                           reset_authorizer=authorizer,
                                           session_policy_authorizer=policy_authorizer)
            self.assertFalse(restored.is_halted)
            anchor.heads["paper-account-1"] = "f" * 64
            with self.assertRaises(RiskGatewayError):
                RiskGateway.restore(account_id="paper-account-1", ledger=ledger,
                                    store=store, anchor=anchor,
                                    reset_authorizer=authorizer,
                                    session_policy_authorizer=policy_authorizer)

    def test_unverified_reset_is_refused_and_verified_reset_is_audited(self):
        with tempfile.TemporaryDirectory() as d:
            gateway, _, _, _, authorizer, _ = self.make_gateway(d, approved=False, halted=True)
            with self.assertRaises(RiskGatewayError):
                gateway.reset(new_session_id="s2", opening_equity="1000", timestamp=102,
                              actor="owner", reason="test", approval_ref="fake")
            self.assertEqual(authorizer.requests[0]["account_id"], "paper-account-1")
        with tempfile.TemporaryDirectory() as d:
            gateway, _, _, _, authorizer, _ = self.make_gateway(d, approved=True, halted=True)
            gateway.reset(new_session_id="s2", opening_equity="1000", timestamp=102,
                          actor="owner", reason="reviewed", approval_ref="verified-123")
            self.assertEqual(authorizer.requests[0]["approval_ref"], "verified-123")
            self.assertFalse(gateway.is_halted)

    def test_ledger_equity_triggers_stop_before_any_new_buy(self):
        with tempfile.TemporaryDirectory() as d:
            gateway, _, _, ledger, _, _ = self.make_gateway(d)
            ledger.equity = "949"
            result = gateway.propose(proposals={"BTC/USDT": "0.1", "ETH/USDT": "0"},
                                     timestamp=101)
            self.assertEqual(str(result["permitted_deltas"]["BTC/USDT"]), "0")
            self.assertTrue(result["risk_halted"])

    def test_anchor_failure_locks_gateway(self):
        with tempfile.TemporaryDirectory() as d:
            gateway, _, anchor, _, _, _ = self.make_gateway(d)
            anchor.fail_publish = True
            with self.assertRaises(RiskGatewayError):
                gateway.propose(proposals={"BTC/USDT": "0"}, timestamp=101)
            with self.assertRaises(RiskGatewayError):
                gateway.propose(proposals={"BTC/USDT": "0"}, timestamp=102)


if __name__ == "__main__":
    unittest.main()
