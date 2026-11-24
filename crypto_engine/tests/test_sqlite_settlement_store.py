import hashlib
import os
import sqlite3
import tempfile
import unittest

from tmm_core.sqlite_settlement_store import SettlementStoreError, SQLiteSettlementStore


class SQLiteSettlementStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        if os.name == "posix":
            os.chmod(self.tmp.name, 0o700)
        self.path = os.path.join(self.tmp.name, "settlement.sqlite3")
        self.store = SQLiteSettlementStore(
            self.path, account_id="paper-research", currency="USDT", opening_cash="10000"
        )
        self.store.register_market("BTC/USDT", "BTC", "USDT")
        self.hash = hashlib.sha256(b"request-one").hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def buy(self, *, fill_id="f-1", qty="1"):
        return {"fill_id": fill_id, "market_id": "BTC/USDT", "side": "BUY",
                "quantity": qty, "price": "100", "fee_quote": "1"}

    def test_atomic_commit_updates_cash_holdings_audit_and_batch(self):
        result = self.store.apply_batch(batch_id="b-1",
                                        fills=[self.buy()], timestamp=10)
        snap = self.store.snapshot()
        self.assertEqual(snap["cash"], "9899")
        self.assertEqual(snap["holdings"]["BTC/USDT"], "1")
        self.assertEqual(result["status"], "COMPLETE")
        self.assertTrue(self.store.verify_audit_chain())

    def test_identical_replay_returns_saved_result_without_second_fill(self):
        first = self.store.apply_batch(batch_id="b-2",
                                       fills=[self.buy()], timestamp=10)
        second = self.store.apply_batch(batch_id="b-2",
                                        fills=[self.buy()], timestamp=10)
        self.assertEqual(first, second)
        self.assertEqual(self.store.snapshot()["cash"], "9899")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 1)

    def test_changed_payload_hash_is_rejected(self):
        self.store.apply_batch(batch_id="b-3",
                               fills=[self.buy()], timestamp=10)
        with self.assertRaisesRegex(SettlementStoreError, "different request hash"):
            self.store.apply_batch(batch_id="b-3", fills=[self.buy(qty="2")], timestamp=10)

    def test_failed_batch_rolls_back_claim_and_every_accounting_table(self):
        invalid = {"fill_id": "bad", "market_id": "BTC/USDT", "side": "SELL",
                   "quantity": "1", "price": "100", "fee_quote": "0"}
        with self.assertRaisesRegex(SettlementStoreError, "inventory"):
            self.store.apply_batch(batch_id="b-4",
                                   fills=[invalid], timestamp=10)
        self.assertEqual(self.store.snapshot()["cash"], "10000")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batches").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_outbox_requires_ack_before_batch_complete(self):
        result = self.store.apply_batch(
            batch_id="b-5", fills=[self.buy(), {
                "fill_id": "sell-1", "market_id": "BTC/USDT", "side": "SELL",
                "quantity": "0.25", "price": "110", "fee_quote": "0.1"
            }],
            sell_settlements=[{"idempotency_key": "settle:b-5:BTC", "market_id": "BTC/USDT",
                               "authorized_quantity": "0.5", "filled_quantity": "0.25"}],
            timestamp=10,
        )
        self.assertEqual(result["status"], "COMMITTED_PENDING_OUTBOX")
        pending = self.store.pending_outbox()
        self.assertEqual(len(pending), 1)
        self.store.acknowledge_outbox("settle:b-5:BTC", receiver_receipt="receipt-1")
        with sqlite3.connect(self.path) as db:
            status = db.execute("SELECT status FROM batches WHERE batch_id='b-5'").fetchone()[0]
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(self.store.pending_outbox(), [])
        replay = self.store.apply_batch(
            batch_id="b-5", fills=[self.buy(), {
                "fill_id": "sell-1", "market_id": "BTC/USDT", "side": "SELL",
                "quantity": "0.25", "price": "110", "fee_quote": "0.1"
            }],
            sell_settlements=[{"idempotency_key": "settle:b-5:BTC", "market_id": "BTC/USDT",
                               "authorized_quantity": "0.5", "filled_quantity": "0.25"}],
            timestamp=10,
        )
        self.assertEqual(replay["status"], "COMPLETE")
        self.assertTrue(self.store.verify_audit_chain())

    def test_duplicate_fill_id_rejected_and_rolls_back(self):
        self.store.apply_batch(batch_id="b-6",
                               fills=[self.buy()], timestamp=10)
        with self.assertRaisesRegex(SettlementStoreError, "Fill ID already exists|fill ID already exists"):
            self.store.apply_batch(batch_id="b-7", fills=[self.buy()], timestamp=11)
        self.assertEqual(self.store.snapshot()["cash"], "9899")

    def test_account_identity_mismatch_rejected(self):
        with self.assertRaisesRegex(SettlementStoreError, "account identity"):
            SQLiteSettlementStore(self.path, account_id="other", currency="USDT",
                                  opening_cash="10000")

    def test_audit_corruption_detected(self):
        self.store.apply_batch(batch_id="b-8",
                               fills=[self.buy()], timestamp=10)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE audit SET event_json='{}' WHERE seq=1")
        self.assertFalse(self.store.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
