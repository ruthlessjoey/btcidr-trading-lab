import json
import threading
import unittest
from decimal import Decimal as D

from tmm_core.session_risk import SessionLossGuard, SessionRiskError


class SessionLossGuardTests(unittest.TestCase):
    def make_guard(self, limit=".10"):
        return SessionLossGuard(session_id="session-1", opening_equity="1000",
                                max_session_loss=limit, started_at=100)

    def test_loss_threshold_latches_and_blocks_buys_across_all_assets(self):
        guard = self.make_guard(".10")
        result = guard.observe_equity(equity="899", timestamp=101)
        self.assertTrue(result["halted"])
        self.assertEqual(result["halt_reason"], "SESSION_LOSS_LIMIT")
        allowed = guard.authorize_proposals(
            proposals={"BTC/USDT": "2", "ETH/USDT": "-9"},
            holdings={"BTC/USDT": ".5", "ETH/USDT": "3"}, timestamp=102)
        self.assertEqual(allowed["BTC/USDT"], D("0"))
        self.assertEqual(allowed["ETH/USDT"], D("-3"))

    def test_partial_exit_is_capped_and_remaining_inventory_can_exit(self):
        guard = self.make_guard()
        guard.force_halt(timestamp=101, reason="OPERATOR_KILL_SWITCH")
        first = guard.authorize_proposals(
            proposals={"BTC/USDT": "-5", "ETH/USDT": "-.5"},
            holdings={"BTC/USDT": ".75", "ETH/USDT": "2"}, timestamp=102)
        self.assertEqual(first["BTC/USDT"], D("-.75"))
        self.assertEqual(first["ETH/USDT"], D("-.5"))
        guard.settle_sell(market_id="BTC/USDT", authorized_quantity=".75",
                          filled_quantity=".25", timestamp=103)
        second = guard.authorize_proposals(
            proposals={"BTC/USDT": "-5", "ETH/USDT": "1"},
            holdings={"BTC/USDT": ".5", "ETH/USDT": "2"}, timestamp=104)
        self.assertEqual(second["BTC/USDT"], D("-.5"))
        self.assertEqual(second["ETH/USDT"], D("0"))
        self.assertEqual(guard.halt_reason, "OPERATOR_KILL_SWITCH")

    def test_sell_never_exceeds_inventory_even_before_stop(self):
        guard = self.make_guard()
        result = guard.authorize_proposals(
            proposals={"BTC/USDT": "-2"}, holdings={"BTC/USDT": ".4"}, timestamp=101)
        self.assertEqual(result["BTC/USDT"], D("-.4"))
        with self.assertRaises(SessionRiskError):
            guard.authorize_proposals(
                proposals={"BTC/USDT": "1"}, holdings={"BTC/USDT": "-.1"}, timestamp=102)

    def test_concurrent_stale_proposals_cannot_double_reserve_an_exit(self):
        guard = self.make_guard()
        results = []
        failures = []
        barrier = threading.Barrier(12)

        def submit():
            try:
                barrier.wait()
                result = guard.authorize_proposals(
                    proposals={"SOL/USDT": "-.75"}, holdings={"SOL/USDT": ".75"}, timestamp=101)
                results.append(result["SOL/USDT"])
            except Exception as exc:  # surfaced as an assertion below
                failures.append(exc)

        workers = [threading.Thread(target=submit) for _ in range(12)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(failures, [])
        self.assertEqual(sum((-x for x in results if x < 0), D("0")), D(".75"))
        self.assertEqual(sum((x for x in results), D("0")), D("-.75"))

    def test_restart_restores_halt_and_outstanding_sell_reservations(self):
        guard = self.make_guard()
        guard.observe_equity(equity="800", timestamp=101)
        guard.authorize_proposals(
            proposals={"BTC/USDT": "-.5", "ETH/USDT": "1"},
            holdings={"BTC/USDT": ".5", "ETH/USDT": "1"}, timestamp=102)
        snapshot = json.loads(json.dumps(guard.snapshot()))
        restored = SessionLossGuard.restore(snapshot)
        self.assertTrue(restored.is_halted)
        self.assertEqual(restored.halt_reason, "SESSION_LOSS_LIMIT")
        after_restart = restored.authorize_proposals(
            proposals={"BTC/USDT": "-.5", "ETH/USDT": "1"},
            holdings={"BTC/USDT": ".5", "ETH/USDT": "1"}, timestamp=103)
        self.assertEqual(after_restart["BTC/USDT"], D("0"))
        self.assertEqual(after_restart["ETH/USDT"], D("0"))

    def test_corrupt_audit_chain_fails_closed_on_restore(self):
        guard = self.make_guard()
        guard.observe_equity(equity="800", timestamp=101)
        snapshot = guard.snapshot()
        snapshot["events"][0]["payload"]["equity"] = "9999"
        with self.assertRaises(SessionRiskError):
            SessionLossGuard.restore(snapshot)

    def test_reset_requires_explicit_audited_approval_and_new_session(self):
        guard = self.make_guard()
        guard.observe_equity(equity="800", timestamp=101)
        with self.assertRaises(SessionRiskError):
            guard.reset(new_session_id="session-2", opening_equity="800", timestamp=102,
                        actor="", reason="restart", approval_ref="ticket-1")
        guard.reset(new_session_id="session-2", opening_equity="800", timestamp=102,
                    actor="owner", reason="reviewed recovery", approval_ref="approval-123")
        self.assertFalse(guard.is_halted)
        self.assertEqual(guard.session_id, "session-2")
        reset_events = [e for e in guard.snapshot()["events"] if e["event_type"] == "SESSION_RESET"]
        self.assertEqual(len(reset_events), 1)
        self.assertEqual(reset_events[0]["payload"]["approval_ref"], "approval-123")

    def test_reset_refuses_unresolved_exit_reservations(self):
        guard = self.make_guard()
        guard.force_halt(timestamp=101, reason="STOP")
        guard.authorize_proposals(
            proposals={"BTC/USDT": "-.5"}, holdings={"BTC/USDT": ".5"}, timestamp=102)
        with self.assertRaises(SessionRiskError):
            guard.reset(new_session_id="session-2", opening_equity="900", timestamp=103,
                        actor="owner", reason="reset", approval_ref="approval-2")


if __name__ == "__main__":
    unittest.main()
