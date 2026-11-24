import os
import tempfile
import unittest
from decimal import Decimal

from tmm_core.offline_portfolio import MarketSpec, SyntheticFill, SyntheticMark, SyntheticPortfolioLedger
from tmm_core.offline_batch_journal import BatchJournalError, SQLiteBatchJournal
from tmm_core.offline_settlement import (
    ExecutionRules, OfflineSettlementController, SyntheticBar,
)


class Gateway:
    def __init__(self, permitted):
        self.permitted = permitted
        self.calls = 0
    def propose(self, *, proposals, timestamp):
        self.calls += 1
        return {"permitted_deltas": dict(self.permitted)}


class Settlement:
    def __init__(self):
        self.calls = []
    def settle_sell(self, **kwargs):
        self.calls.append(kwargs)


class OfflineSettlementTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.journal_path = os.path.join(self.tempdir.name, "batches.sqlite3")
        self.journal = SQLiteBatchJournal(self.journal_path, runtime_id="runtime-test")
        self.ledger = SyntheticPortfolioLedger(
            account_id="a", account_currency="USDT", opening_cash="10000",
            markets={"BTC/USDT": MarketSpec("BTC/USDT", "BTC", "USDT")},
        )
        self.ledger.update_marks(
            {"BTC/USDT": SyntheticMark("BTC/USDT", "100", 100, "5000")},
            timestamp=100,
        )
        self.gateway, self.settlement = Gateway({"BTC/USDT": "1"}), Settlement()
        self.controller = OfflineSettlementController(
            proposal_client=self.gateway, settlement=self.settlement,
            ledger=self.ledger,
            rules={"BTC/USDT": ExecutionRules("0.001", "0.1", fee_bps="10",
                                               half_spread_bps="5", slippage_bps="5",
                                               max_volume_participation="0.05")},
            batch_journal=self.journal,
        )
        self.bar = SyntheticBar("BTC/USDT", 101, "100", "105", "95", "102", "10")

    def test_buy_applies_adverse_price_fee_and_volume_cap(self):
        result = self.controller.process(
            batch_id="case-1", proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": self.bar}, timestamp=101
        )[0]
        self.assertEqual(result.filled_quantity, Decimal("0.500"))
        self.assertGreater(result.fill_price, Decimal("100"))
        self.assertGreater(result.fee_quote, 0)
        self.assertEqual(Decimal(self.ledger.snapshot_holdings("a")["BTC/USDT"]), Decimal("0.500"))

    def test_sell_partial_fill_releases_reservation(self):
        self.ledger.apply_fill(SyntheticFill("seed", "BTC/USDT", "BUY", "2", "100", "0", 100))
        self.gateway.permitted = {"BTC/USDT": "-1"}
        result = self.controller.process(
            batch_id="case-2", proposals={"BTC/USDT": "-1"}, bars={"BTC/USDT": self.bar}, timestamp=101
        )[0]
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(len(self.settlement.calls), 1)
        self.assertEqual(self.settlement.calls[0]["authorized_quantity"], Decimal("1"))
        self.assertEqual(self.settlement.calls[0]["filled_quantity"], Decimal("0.500"))

    def test_gateway_must_authorize_exact_market_set(self):
        self.gateway.permitted = {}
        with self.assertRaises(ValueError):
            self.controller.process(
            batch_id="case-3", proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": self.bar}, timestamp=101
            )

    def test_missing_or_wrong_time_bar_rejected(self):
        bad = SyntheticBar("BTC/USDT", 100, "100", "105", "95", "102", "10")
        with self.assertRaises(ValueError):
            self.controller.process(
            batch_id="case-4", proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": bad}, timestamp=101
            )

    def test_invalid_ohlcv_and_unknown_rules_rejected(self):
        bad = SyntheticBar("BTC/USDT", 101, "100", "90", "95", "102", "10")
        with self.assertRaises(ValueError):
            self.controller.process(
            batch_id="case-5", proposals={"BTC/USDT": "1"}, bars={"BTC/USDT": bad}, timestamp=101
            )

    def test_zero_liquidity_sell_is_settled_unfilled(self):
        self.gateway.permitted = {"BTC/USDT": "-1"}
        no_volume = SyntheticBar("BTC/USDT", 101, "100", "105", "95", "102", "0")
        result = self.controller.process(
            batch_id="case-6", proposals={"BTC/USDT": "-1"}, bars={"BTC/USDT": no_volume}, timestamp=101
        )[0]
        self.assertEqual(result.status, "UNFILLED")
        self.assertEqual(self.settlement.calls[0]["filled_quantity"], Decimal("0"))


    def test_duplicate_completed_batch_returns_recorded_result_without_gateway_call(self):
        kwargs = {"batch_id": "stable-batch", "proposals": {"BTC/USDT": "1"},
                  "bars": {"BTC/USDT": self.bar}, "timestamp": 101}
        self.controller.process(**kwargs)
        calls = self.gateway.calls
        cash = self.ledger.snapshot_cash("a")
        replay = self.controller.process(**kwargs)
        self.assertEqual(replay, first)
        self.assertEqual(self.gateway.calls, calls)
        self.assertEqual(self.ledger.snapshot_cash("a"), cash)

    def test_same_batch_id_with_different_payload_is_rejected(self):
        kwargs = {"batch_id": "payload-bound", "proposals": {"BTC/USDT": "1"},
                  "bars": {"BTC/USDT": self.bar}, "timestamp": 101}
        self.controller.process(**kwargs)
        with self.assertRaises(BatchJournalError):
            self.controller.process(batch_id="payload-bound", proposals={"BTC/USDT": "0.5"},
                                    bars={"BTC/USDT": self.bar}, timestamp=101)

    def test_journal_rejects_new_runtime_after_restart(self):
        with self.assertRaises(BatchJournalError):
            SQLiteBatchJournal(self.journal_path, runtime_id="different-runtime")

    def test_invalid_bar_rejected_before_gateway_call(self):
        bad = SyntheticBar("BTC/USDT", 100, "100", "105", "95", "102", "10")
        with self.assertRaises(ValueError):
            self.controller.process(batch_id="bad-bar", proposals={"BTC/USDT": "1"},
                                    bars={"BTC/USDT": bad}, timestamp=101)
        self.assertEqual(self.gateway.calls, 0)

    def test_failed_attempt_burns_batch_id_for_safe_reconciliation(self):
        self.gateway.permitted = {}
        kwargs = {"batch_id": "failed-batch", "proposals": {"BTC/USDT": "1"},
                  "bars": {"BTC/USDT": self.bar}, "timestamp": 101}
        with self.assertRaises(ValueError):
            self.controller.process(**kwargs)
        self.gateway.permitted = {"BTC/USDT": "1"}
        with self.assertRaisesRegex(BatchJournalError, "unresolved"):
            self.controller.process(**kwargs)
        self.assertEqual(self.gateway.calls, 1)

    def tearDown(self):
        self.tempdir.cleanup()


if __name__ == "__main__":
    unittest.main()
