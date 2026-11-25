import hashlib
import os
import sqlite3
import tempfile
import unittest

from tmm_core.sqlite_settlement_store import SettlementStoreError, SQLiteSettlementStore
from tmm_core.reservation_lifecycle import authorize_reservation, create_reservation
from tmm_core.reservation_schema_v2 import ensure_reservation_schema_v2


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

    def enable_reservations(self, *, quantity="0.5", expires_at=1000):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        create_reservation(
            db, reservation_id="r-1", account_id="paper-research",
            market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
            authorized_quantity=quantity, created_at=0, expires_at=expires_at,
        )
        authorize_reservation(
            db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=1,
        )
        db.commit()
        db.close()

    def sell(self, *, fill_id="sell-1", qty="0.25"):
        return {"fill_id": fill_id, "market_id": "BTC/USDT", "side": "SELL",
                "quantity": qty, "price": "110", "fee_quote": "0"}

    def sell_settlement(self, *, key="settle:reserved", authorized="0.5", filled="0.25"):
        return {"idempotency_key": key, "market_id": "BTC/USDT",
                "authorized_quantity": authorized, "filled_quantity": filled}

    def allocation(self, *, allocation_id="a-1", fill_id="sell-1",
                   reservation_id="r-1", version=2, quantity="0.25"):
        return {"allocation_id": allocation_id, "fill_id": fill_id,
                "reservation_id": reservation_id, "reservation_version": version,
                "allocated_quantity": quantity}

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

    def test_replay_rejects_changed_timestamp(self):
        self.store.apply_batch(batch_id="b-time", fills=[self.buy()], timestamp=10)
        with self.assertRaisesRegex(SettlementStoreError, "different request hash"):
            self.store.apply_batch(batch_id="b-time", fills=[self.buy()], timestamp=11)

    def test_sell_outbox_must_match_actual_sell_fills(self):
        with self.assertRaisesRegex(SettlementStoreError, "SELL outbox filled quantities"):
            self.store.apply_batch(
                batch_id="b-mismatch",
                fills=[self.buy(), {
                    "fill_id": "sell-mismatch", "market_id": "BTC/USDT", "side": "SELL",
                    "quantity": "0.2", "price": "110", "fee_quote": "0"
                }],
                sell_settlements=[{
                    "idempotency_key": "settle:mismatch", "market_id": "BTC/USDT",
                    "authorized_quantity": "0.5", "filled_quantity": "0.1"
                }],
                timestamp=10,
            )
        self.assertEqual(self.store.snapshot()["cash"], "10000")

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

    def test_reserved_sell_consumption_is_atomic_and_replay_safe(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        kwargs = {
            "batch_id": "b-reserved-sell",
            "fills": [self.sell()],
            "sell_settlements": [self.sell_settlement()],
            "sell_allocations": [self.allocation()],
            "timestamp": 20,
        }
        first = self.store.apply_batch(**kwargs)
        second = self.store.apply_batch(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "COMMITTED_PENDING_OUTBOX")
        self.assertEqual(first["reservation_allocations"][0]["idempotency_key"],
                         "reservation-allocation:a-1")
        self.assertEqual(self.store.snapshot()["holdings"]["BTC/USDT"], "0.75")
        self.assertEqual(len(self.store.pending_outbox()), 1)
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)
        self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMMITTED_PENDING_OUTBOX",
            )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt="reservation-receipt"
        )
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT consumed_quantity,version FROM reservations").fetchone(),
                ("0.25", 3),
            )
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservation_allocations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservation_outbox").fetchone()[0], 1)
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMPLETE",
            )
        replay = self.store.apply_batch(**kwargs)
        self.assertEqual(replay["status"], "COMPLETE")
        self.assertTrue(self.store.verify_audit_chain())

    def test_reservation_enabled_sell_without_allocation_is_rejected(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        before = self.store.snapshot()
        with self.assertRaisesRegex(SettlementStoreError, "require reservation allocations"):
            self.store.apply_batch(
                batch_id="b-no-allocation", fills=[self.sell()],
                sell_settlements=[self.sell_settlement()], timestamp=20,
            )
        self.assertEqual(self.store.snapshot(), before)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM batches WHERE batch_id='b-no-allocation'"
            ).fetchone())

    def test_stale_reservation_allocation_rolls_back_entire_batch(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        before = self.store.snapshot()
        with self.assertRaisesRegex(SettlementStoreError, "stale reservation version"):
            self.store.apply_batch(
                batch_id="b-stale-allocation", fills=[self.sell()],
                sell_settlements=[self.sell_settlement()],
                sell_allocations=[self.allocation(version=1)], timestamp=20,
            )
        self.assertEqual(self.store.snapshot(), before)
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM batches WHERE batch_id='b-stale-allocation'"
            ).fetchone())
            self.assertEqual(db.execute(
                "SELECT consumed_quantity FROM reservations"
            ).fetchone()[0], "0")

    def test_duplicate_allocation_id_rolls_back_consumption_and_fill(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-first", fills=[self.sell()],
            sell_settlements=[self.sell_settlement(key="settle:first")],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.apply_batch(
                batch_id="b-reserved-second", fills=[self.sell(fill_id="sell-2")],
                sell_settlements=[self.sell_settlement(key="settle:second")],
                sell_allocations=[self.allocation(fill_id="sell-2")], timestamp=21,
            )
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT consumed_quantity,version FROM reservations").fetchone(),
                ("0.25", 3),
            )
            self.assertIsNone(db.execute(
                "SELECT 1 FROM batches WHERE batch_id='b-reserved-second'"
            ).fetchone())
            self.assertIsNone(db.execute(
                "SELECT 1 FROM fills WHERE fill_id='sell-2'"
            ).fetchone())

    def test_reservation_outbox_acknowledgement_is_receipt_idempotent(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt="receipt-1"
        )
        with self.assertRaisesRegex(SettlementStoreError, "receipt mismatch"):
            self.store.acknowledge_reservation_outbox(
                "reservation-allocation:a-1", receiver_receipt="receipt-2"
            )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt="receipt-1"
        )
        self.assertTrue(self.store.verify_audit_chain())

    def test_reservation_outbox_ack_waits_for_legacy_outbox(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        result = self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        self.assertEqual(result["status"], "COMMITTED_PENDING_OUTBOX")
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt="reservation-receipt"
        )
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMMITTED_PENDING_OUTBOX",
            )
        self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMPLETE",
            )

    def test_reservation_enabled_buy_batch_needs_no_sell_allocation(self):
        self.enable_reservations()
        result = self.store.apply_batch(
            batch_id="b-buy-with-reservations", fills=[self.buy()], timestamp=10
        )
        self.assertEqual(result["status"], "COMPLETE")
        self.assertNotIn("reservation_allocations", result)

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

    def test_missing_table_is_not_silently_recreated(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TABLE outbox")
        with self.assertRaisesRegex(SettlementStoreError, "schema mismatch"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")
        with sqlite3.connect(self.path) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertNotIn("outbox", tables)

    def test_changed_table_constraint_is_rejected_even_when_columns_match(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA writable_schema=ON")
            db.execute(
                "UPDATE sqlite_master SET sql=replace(sql, 'CHECK(singleton=1)', "
                "'CHECK(singleton=2)') WHERE type='table' AND name='account'"
            )
            db.execute("PRAGMA writable_schema=OFF")
        with self.assertRaisesRegex(SettlementStoreError, "schema definition mismatch"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")

    def test_unapproved_trigger_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TRIGGER injected_audit_trigger AFTER INSERT ON fills "
                "BEGIN UPDATE account SET cash='0' WHERE singleton=1; END"
            )
        with self.assertRaisesRegex(SettlementStoreError, "unapproved schema objects"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")

    def test_unapproved_index_is_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE INDEX injected_fill_index ON fills(market_id)")
        with self.assertRaisesRegex(SettlementStoreError, "unapproved schema objects"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")

    def test_audit_corruption_detected(self):
        self.store.apply_batch(batch_id="b-8",
                               fills=[self.buy()], timestamp=10)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE audit SET event_json='{}' WHERE seq=1")
        self.assertFalse(self.store.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
