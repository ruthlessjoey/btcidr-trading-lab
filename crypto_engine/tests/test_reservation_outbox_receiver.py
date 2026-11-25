import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from tmm_core.reservation_lifecycle import authorize_reservation, create_reservation
from tmm_core.reservation_outbox_receiver import (
    ReservationInboxError,
    accept_reservation_outbox,
    deliver_pending_reservation_outbox,
    ensure_reservation_inbox_schema,
)
from tmm_core.reservation_schema_v2 import ensure_reservation_schema_v2
from tmm_core.sqlite_settlement_store import SQLiteSettlementStore


class ReservationOutboxReceiverTests(unittest.TestCase):
    def setUp(self):
        self.receiver_db = sqlite3.connect(":memory:")
        self.receiver_db.execute("BEGIN IMMEDIATE")
        ensure_reservation_inbox_schema(self.receiver_db)
        self.receiver_db.commit()

        self.tmp = tempfile.TemporaryDirectory()
        if os.name == "posix":
            os.chmod(self.tmp.name, 0o700)
        self.store = SQLiteSettlementStore(
            os.path.join(self.tmp.name, "settlement.sqlite3"),
            account_id="paper-research", currency="USDT", opening_cash="10000",
        )
        self.store.register_market("BTC/USDT", "BTC", "USDT")
        self.store.apply_batch(
            batch_id="b-buy",
            fills=[{"fill_id":"buy-1","market_id":"BTC/USDT","side":"BUY",
                    "quantity":"1","price":"100","fee_quote":"0"}],
            timestamp=10,
        )
        db = sqlite3.connect(self.store.path)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        create_reservation(
            db, reservation_id="r-1", account_id="paper-research",
            market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
            authorized_quantity="0.5", created_at=11, expires_at=1000,
        )
        authorize_reservation(
            db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=12,
        )
        db.commit()
        db.close()
        self.store.apply_batch(
            batch_id="b-sell",
            fills=[{"fill_id":"sell-1","market_id":"BTC/USDT","side":"SELL",
                    "quantity":"0.25","price":"110","fee_quote":"0"}],
            sell_settlements=[{"idempotency_key":"settle:sell","market_id":"BTC/USDT",
                               "authorized_quantity":"0.5","filled_quantity":"0.25"}],
            sell_allocations=[{"allocation_id":"a-1","fill_id":"sell-1",
                               "reservation_id":"r-1","reservation_version":2,
                               "allocated_quantity":"0.25"}],
            timestamp=20,
        )

    def tearDown(self):
        self.receiver_db.close()
        self.tmp.cleanup()

    def payload(self, *, quantity="0.25"):
        return {
            "schema": 1, "idempotency_key": "reservation-allocation:a-1",
            "allocation_id": "a-1", "batch_id": "b-sell", "fill_id": "sell-1",
            "reservation_id": "r-1", "account_id": "paper-research",
            "market_id": "BTC/USDT", "reservation_version": 2,
            "allocated_quantity": quantity,
        }

    def receive(self, payload):
        self.receiver_db.execute("BEGIN IMMEDIATE")
        receipt = accept_reservation_outbox(self.receiver_db, payload)
        self.receiver_db.commit()
        return receipt

    def test_receiver_acceptance_is_idempotent(self):
        first = self.receive(self.payload())
        second = self.receive(self.payload())
        self.assertEqual(first, second)
        self.assertEqual(
            self.receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
            1,
        )

    def test_same_idempotency_key_with_changed_payload_is_rejected(self):
        self.receive(self.payload())
        self.receiver_db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(ReservationInboxError, "different reservation payload"):
            accept_reservation_outbox(self.receiver_db, self.payload(quantity="0.3"))
        self.receiver_db.rollback()

    def test_extreme_decimal_exponent_is_rejected_without_expansion(self):
        self.receiver_db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(ReservationInboxError, "precision"):
            accept_reservation_outbox(
                self.receiver_db, self.payload(quantity="1E+999999")
            )
        self.receiver_db.rollback()

    def test_invalid_payload_schema_is_rejected(self):
        bad = self.payload()
        bad["unexpected"] = "value"
        self.receiver_db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(ReservationInboxError, "fields do not match"):
            accept_reservation_outbox(self.receiver_db, bad)
        self.receiver_db.rollback()

    def test_inbox_write_rolls_back_with_caller_transaction(self):
        self.receiver_db.execute("BEGIN IMMEDIATE")
        receipt = accept_reservation_outbox(self.receiver_db, self.payload())
        self.assertTrue(receipt)
        self.receiver_db.rollback()
        self.assertEqual(
            self.receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
            0,
        )

    def test_delivery_worker_acknowledges_and_batch_waits_for_both_outboxes(self):
        delivered = deliver_pending_reservation_outbox(self.store, self.receive)
        self.assertEqual(delivered, ["reservation-allocation:a-1"])
        self.assertEqual(self.store.pending_reservation_outbox(), [])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-sell'").fetchone()[0],
                "COMMITTED_PENDING_OUTBOX",
            )
        self.store.acknowledge_outbox("settle:sell", receiver_receipt="legacy-receipt")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-sell'").fetchone()[0],
                "COMPLETE",
            )

    def test_temp_trigger_on_main_inbox_is_rejected_before_acceptance(self):
        self.receiver_db.execute("BEGIN IMMEDIATE")
        self.receiver_db.execute(
            "CREATE TEMP TRIGGER temp_inbox_mutator "
            "AFTER INSERT ON main.reservation_inbox "
            "BEGIN UPDATE reservation_inbox SET receipt='tampered' "
            "WHERE idempotency_key=NEW.idempotency_key; END"
        )
        with self.assertRaisesRegex(
            ReservationInboxError, "TEMP reservation inbox triggers"
        ):
            accept_reservation_outbox(self.receiver_db, self.payload())
        self.receiver_db.rollback()
        self.assertEqual(
            self.receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
            0,
        )

    def test_ambiguous_receiver_response_retries_without_duplicate_effect(self):
        calls = {"count": 0}
        def ambiguous(payload):
            receipt = self.receive(payload)
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("simulated lost response after receiver commit")
            return receipt

        with self.assertRaisesRegex(TimeoutError, "lost response"):
            deliver_pending_reservation_outbox(self.store, ambiguous)
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)
        self.assertEqual(
            self.receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
            1,
        )
        delivered = deliver_pending_reservation_outbox(self.store, ambiguous)
        self.assertEqual(delivered, ["reservation-allocation:a-1"])
        self.assertEqual(
            self.receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
            1,
        )
        self.assertEqual(self.store.pending_reservation_outbox(), [])

    def test_existing_receipt_tampering_is_rejected_on_replay(self):
        self.receive(self.payload())
        with sqlite3.connect(self.store.path) as db:
            db.execute(
                "UPDATE reservation_inbox SET receipt='tampered' "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
        self.receiver_db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(
            ReservationInboxError, "stored reservation inbox receipt mismatch"
        ):
            accept_reservation_outbox(self.receiver_db, self.payload())
        self.receiver_db.rollback()

    def test_ambiguous_response_survives_receiver_connection_restart(self):
        receiver_path = os.path.join(self.tmp.name, "durable-receiver.sqlite3")
        db = sqlite3.connect(receiver_path)
        try:
            db.execute("BEGIN IMMEDIATE")
            ensure_reservation_inbox_schema(db)
            db.commit()
        finally:
            db.close()

        calls = {"count": 0}

        def durable_receiver(payload):
            receiver_db = sqlite3.connect(receiver_path)
            try:
                receiver_db.execute("BEGIN IMMEDIATE")
                receipt = accept_reservation_outbox(receiver_db, payload)
                receiver_db.commit()
            finally:
                receiver_db.close()
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("simulated lost response after durable receiver commit")
            return receipt

        with self.assertRaisesRegex(TimeoutError, "durable receiver commit"):
            deliver_pending_reservation_outbox(self.store, durable_receiver)
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)
        with sqlite3.connect(receiver_path) as receiver_db:
            self.assertEqual(
                receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
                1,
            )

        delivered = deliver_pending_reservation_outbox(self.store, durable_receiver)
        self.assertEqual(delivered, ["reservation-allocation:a-1"])
        self.assertEqual(self.store.pending_reservation_outbox(), [])
        with sqlite3.connect(receiver_path) as receiver_db:
            self.assertEqual(
                receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
                1,
            )

    def test_concurrent_delivery_workers_share_one_durable_receipt(self):
        receiver_path = os.path.join(self.tmp.name, "concurrent-receiver.sqlite3")
        db = sqlite3.connect(receiver_path)
        try:
            db.execute("BEGIN IMMEDIATE")
            ensure_reservation_inbox_schema(db)
            db.commit()
        finally:
            db.close()

        ready = threading.Barrier(2)

        def concurrent_receiver(payload):
            ready.wait(timeout=10)
            receiver_db = sqlite3.connect(receiver_path)
            try:
                receiver_db.execute("BEGIN IMMEDIATE")
                receipt = accept_reservation_outbox(receiver_db, payload)
                receiver_db.commit()
                return receipt
            finally:
                receiver_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(deliver_pending_reservation_outbox, self.store, concurrent_receiver)
                for _ in range(2)
            ]
            results = [future.result(timeout=20) for future in futures]

        self.assertEqual(
            results,
            [["reservation-allocation:a-1"], ["reservation-allocation:a-1"]],
        )
        self.assertEqual(self.store.pending_reservation_outbox(), [])
        with sqlite3.connect(receiver_path) as receiver_db:
            self.assertEqual(
                receiver_db.execute("SELECT COUNT(*) FROM reservation_inbox").fetchone()[0],
                1,
            )

    def test_worker_rejects_receiver_receipt_not_bound_to_payload(self):
        def bad_receiver(payload):
            return "unrelated-receipt"
        with self.assertRaisesRegex(ReservationInboxError, "not bound to this payload"):
            deliver_pending_reservation_outbox(self.store, bad_receiver)
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)

    def test_worker_rejects_tampered_outbox_payload_hash_before_receiver(self):
        with sqlite3.connect(self.store.path) as db:
            db.execute(
                "UPDATE reservation_outbox SET payload_sha256=? "
                "WHERE idempotency_key='reservation-allocation:a-1'",
                ("0" * 64,),
            )
        called = {"value": False}
        def receiver(payload):
            called["value"] = True
            return "receipt"
        with self.assertRaisesRegex(ReservationInboxError, "payload hash mismatch"):
            deliver_pending_reservation_outbox(self.store, receiver)
        self.assertFalse(called["value"])
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)


if __name__ == "__main__":
    unittest.main()
