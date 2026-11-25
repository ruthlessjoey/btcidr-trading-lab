import hashlib
import os
import sqlite3
import tempfile
from contextlib import contextmanager
import unittest

from tmm_core.sqlite_settlement_store import SettlementStoreError, SQLiteSettlementStore
from tmm_core.reservation_outbox_receiver import _canonical_payload
from tmm_core.reservation_lifecycle import authorize_reservation, create_reservation
from tmm_core.reservation_schema_v2 import ensure_reservation_schema_v2


@contextmanager
def _managed_connection(*args, **kwargs):
    """Preserve sqlite3 transaction semantics and always close the connection."""
    connection = sqlite3.connect(*args, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


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

    def reservation_ack_evidence(self, idempotency_key):
        row = next(
            item for item in self.store.pending_reservation_outbox(limit=1000)
            if item["idempotency_key"] == idempotency_key
        )
        payload = {
            "schema": 1,
            "idempotency_key": row["idempotency_key"],
            "allocation_id": row["allocation_id"],
            "batch_id": row["batch_id"],
            "fill_id": row["fill_id"],
            "reservation_id": row["reservation_id"],
            "account_id": row["account_id"],
            "market_id": row["market_id"],
            "reservation_version": row["reservation_version"],
            "allocated_quantity": row["allocated_quantity"],
        }
        _, digest, receipt = _canonical_payload(payload)
        self.assertEqual(digest, row["payload_sha256"])
        return digest, receipt

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
        with _managed_connection(self.path) as db:
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
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.close()
        with _managed_connection(self.path) as audit_db:
            audit_before = audit_db.execute(
                "SELECT COUNT(*) FROM audit"
            ).fetchone()[0]
        invalid = {"fill_id": "bad", "market_id": "BTC/USDT", "side": "SELL",
                   "quantity": "1", "price": "100", "fee_quote": "0"}
        with self.assertRaisesRegex(SettlementStoreError, "inventory"):
            self.store.apply_batch(
                batch_id="b-4", fills=[invalid],
                sell_settlements=[self.sell_settlement(
                    key="settle:inventory", authorized="1", filled="1"
                )],
                sell_allocations=[self.allocation(
                    allocation_id="a-inventory", fill_id="bad",
                    version=1, quantity="1"
                )],
                timestamp=10,
            )
        self.assertEqual(self.store.snapshot()["cash"], "10000")
        with _managed_connection(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batches").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM fills").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], audit_before)

    def _create_pending_zero_quantity_outbox(self):
        self.store.apply_batch(
            batch_id="b-outbox-guard",
            fills=[self.buy()],
            sell_settlements=[{
                "idempotency_key": "settle:guard",
                "market_id": "BTC/USDT",
                "authorized_quantity": "0",
                "filled_quantity": "0",
            }],
            timestamp=10,
        )

    def test_pending_outbox_rejects_tampered_accounting_state(self):
        self._create_pending_zero_quantity_outbox()
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(
            SettlementStoreError, "account cash does not match fill audit state"
        ):
            self.store.pending_outbox()

    def test_outbox_acknowledgement_rejects_tampered_accounting_state(self):
        self._create_pending_zero_quantity_outbox()
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(
            SettlementStoreError, "account cash does not match fill audit state"
        ):
            self.store.acknowledge_outbox("settle:guard", receiver_receipt="receipt")

    def test_settlement_outbox_methods_reject_tampered_reservation_state(self):
        self.store.apply_batch(
            batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10
        )
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservations SET expires_at=15 WHERE reservation_id='r-1'"
            )
        with self.assertRaisesRegex(
            SettlementStoreError, "reservation creation audit does not match current record"
        ):
            self.store.pending_outbox()
        with self.assertRaisesRegex(
            SettlementStoreError, "reservation creation audit does not match current record"
        ):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="receipt")

    def test_outbox_requires_both_acknowledgements_before_batch_complete(self):
        self.enable_reservations()
        kwargs = {
            "batch_id": "b-5",
            "fills": [self.buy(), {
                "fill_id": "sell-1", "market_id": "BTC/USDT", "side": "SELL",
                "quantity": "0.25", "price": "110", "fee_quote": "0.1"
            }],
            "sell_settlements": [{
                "idempotency_key": "settle:b-5:BTC", "market_id": "BTC/USDT",
                "authorized_quantity": "0.5", "filled_quantity": "0.25"
            }],
            "sell_allocations": [self.allocation()],
            "timestamp": 10,
        }
        result = self.store.apply_batch(**kwargs)
        self.assertEqual(result["status"], "COMMITTED_PENDING_OUTBOX")
        self.assertEqual(len(self.store.pending_outbox()), 1)
        self.assertEqual(len(self.store.pending_reservation_outbox()), 1)

        self.store.acknowledge_outbox("settle:b-5:BTC", receiver_receipt="receipt-1")
        with _managed_connection(self.path) as db:
            status = db.execute("SELECT status FROM batches WHERE batch_id='b-5'").fetchone()[0]
        self.assertEqual(status, "COMMITTED_PENDING_OUTBOX")

        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            status = db.execute("SELECT status FROM batches WHERE batch_id='b-5'").fetchone()[0]
        self.assertEqual(status, "COMPLETE")
        self.assertEqual(self.store.pending_outbox(), [])
        self.assertEqual(self.store.pending_reservation_outbox(), [])
        replay = self.store.apply_batch(**kwargs)
        self.assertEqual(replay["status"], "COMPLETE")
        self.assertTrue(self.store.verify_audit_chain())

    def test_legacy_database_rejects_sell_until_reservation_schema_v2_is_enabled(self):
        self.store.apply_batch(batch_id="b-legacy-buy", fills=[self.buy()], timestamp=10)
        before = self.store.snapshot()
        with self.assertRaisesRegex(
            SettlementStoreError, "reservation schema v2 is required"
        ):
            self.store.apply_batch(
                batch_id="b-legacy-sell",
                fills=[self.sell()],
                sell_settlements=[self.sell_settlement()],
                timestamp=20,
            )
        self.assertEqual(self.store.snapshot(), before)
        with _managed_connection(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM batches WHERE batch_id='b-legacy-sell'"
            ).fetchone())
            self.assertIsNone(db.execute(
                "SELECT 1 FROM fills WHERE fill_id='sell-1'"
            ).fetchone())

    def test_reopen_accepts_exact_current_reservation_v2_schema(self):
        self.store.apply_batch(batch_id="b-reopen-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations(quantity="0.5")
        before = self.store.snapshot()

        reopened = SQLiteSettlementStore(
            self.path, account_id="paper-research",
            currency="USDT", opening_cash="10000",
        )
        self.assertEqual(reopened.snapshot(), before)
        self.assertTrue(reopened.verify_audit_chain())
        with _managed_connection(self.path) as db:
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM main.sqlite_master WHERE type='table'"
                )
            }
        self.assertTrue({
            "reservations", "reservation_allocations", "reservation_outbox"
        }.issubset(tables))

    def test_reopen_rejects_partial_reservation_v2_without_recreating_table(self):
        self.enable_reservations()
        with _managed_connection(self.path) as db:
            db.execute("DROP TABLE reservation_outbox")

        with self.assertRaisesRegex(SettlementStoreError, "partial reservation schema"):
            SQLiteSettlementStore(
                self.path, account_id="paper-research",
                currency="USDT", opening_cash="10000",
            )

        with _managed_connection(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM main.sqlite_master "
                "WHERE type='table' AND name='reservation_outbox'"
            ).fetchone())
            self.assertIsNotNone(db.execute(
                "SELECT 1 FROM main.sqlite_master "
                "WHERE type='table' AND name='reservations'"
            ).fetchone())

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
        with _managed_connection(self.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMMITTED_PENDING_OUTBOX",
            )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
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
        with _managed_connection(self.path) as db:
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
        with _managed_connection(self.path) as db:
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

        # Use a distinct current reservation version so validation reaches the
        # global duplicate allocation_id constraint rather than failing stale CAS.
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            create_reservation(
                db, reservation_id="r-2", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="0.25", created_at=0, expires_at=1000,
            )
            authorize_reservation(
                db, reservation_id="r-2", account_id="paper-research",
                expected_version=1, now=1,
            )
            db.commit()
        finally:
            db.close()

        with self.assertRaises(sqlite3.IntegrityError):
            self.store.apply_batch(
                batch_id="b-reserved-second", fills=[self.sell(fill_id="sell-2")],
                sell_settlements=[self.sell_settlement(key="settle:second")],
                sell_allocations=[self.allocation(
                    fill_id="sell-2", reservation_id="r-2", version=2
                )], timestamp=21,
            )
        with _managed_connection(self.path) as db:
            rows = {
                reservation_id: (consumed, version, status)
                for reservation_id, consumed, version, status in db.execute(
                    "SELECT reservation_id,consumed_quantity,version,status "
                    "FROM reservations ORDER BY reservation_id"
                )
            }
            self.assertEqual(rows["r-1"], ("0.25", 3, "ACTIVE"))
            self.assertEqual(rows["r-2"], ("0", 2, "ACTIVE"))
            self.assertIsNone(db.execute(
                "SELECT 1 FROM batches WHERE batch_id='b-reserved-second'"
            ).fetchone())
            self.assertIsNone(db.execute(
                "SELECT 1 FROM fills WHERE fill_id='sell-2'"
            ).fetchone())
            self.assertIsNone(db.execute(
                "SELECT 1 FROM reservation_allocations WHERE batch_id='b-reserved-second'"
            ).fetchone())

    def test_reservation_outbox_rejects_cross_account_tampering(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservation_outbox SET account_id='other-account' "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "account identity mismatch"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "account identity mismatch"):
            self.store.acknowledge_reservation_outbox(
                "reservation-allocation:a-1", receiver_receipt=expected_receipt,
                expected_payload_sha256=expected_hash,
            )



    def test_deleted_allocation_and_outbox_cannot_hide_sell_audit_event(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "DELETE FROM main.reservation_outbox "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
            db.execute(
                "DELETE FROM main.reservation_allocations WHERE allocation_id='a-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "SELL fill quantity does not match allocation ledger"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "SELL fill quantity does not match allocation ledger"):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
            status = db.execute(
                "SELECT status FROM main.batches WHERE batch_id='b-reserved-sell'"
            ).fetchone()[0]
        self.assertEqual(status, "COMMITTED_PENDING_OUTBOX")

    def test_outbox_read_revalidates_audit_chain_after_store_initialization(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            rows = db.execute("SELECT seq,event_json FROM main.audit ORDER BY seq").fetchall()
            target = next(seq for seq,event in rows if "RESERVATION_QUANTITY_CONSUMED" in event)
            db.execute("UPDATE main.audit SET event_json='{}' WHERE seq=?", (target,))
        with self.assertRaisesRegex(SettlementStoreError, "reservation audit chain verification failed"):
            self.store.pending_reservation_outbox()



    def test_acknowledged_outbox_requires_matching_audit_event(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            seq = db.execute(
                "SELECT seq FROM main.audit WHERE event_json LIKE '%RESERVATION_OUTBOX_ACKNOWLEDGED%'"
            ).fetchone()[0]
            db.execute("DELETE FROM main.audit WHERE seq=?", (seq,))
        with self.assertRaisesRegex(SettlementStoreError, "acknowledgement audit coverage mismatch"):
            self.store.pending_reservation_outbox()

    def test_duplicate_reservation_ack_audit_event_is_rejected_even_with_valid_chain(self):
        import hashlib
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            self.store._append_audit(db, {
                "kind":"RESERVATION_OUTBOX_ACKNOWLEDGED",
                "account_id":"paper","batch_id":"b-reserved-sell",
                "allocation_id":"a-1","idempotency_key":"reservation-allocation:a-1",
                "payload_sha256":expected_hash,"receipt_sha256":"0" * 64,
            })
        with self.assertRaisesRegex(SettlementStoreError, "acknowledgement audit identity is invalid"):
            self.store.pending_reservation_outbox()

    def test_acknowledged_reservation_receipt_tampering_blocks_delivery_and_completion(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservation_outbox SET receiver_receipt='forged-receipt' "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "acknowledged reservation outbox receipt mismatch"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "acknowledged reservation outbox receipt mismatch"):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
            batch_status = db.execute(
                "SELECT status FROM main.batches WHERE batch_id='b-reserved-sell'"
            ).fetchone()[0]
            legacy_status = db.execute(
                "SELECT status FROM main.outbox WHERE idempotency_key='settle:reserved'"
            ).fetchone()[0]
        self.assertEqual(batch_status, "COMMITTED_PENDING_OUTBOX")
        self.assertEqual(legacy_status, "PENDING")

    def test_acknowledged_reservation_payload_hash_tampering_blocks_delivery(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservation_outbox SET payload_sha256=? "
                "WHERE idempotency_key='reservation-allocation:a-1'",
                ("0" * 64,),
            )
        with self.assertRaisesRegex(SettlementStoreError, "reservation outbox payload hash mismatch"):
            self.store.pending_reservation_outbox()


    def test_fill_ledger_tampering_is_detected_against_audit_events(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.fills SET quantity='999' WHERE fill_id='f-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "synthetic fill ledger does not match audit events"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "synthetic fill ledger does not match audit events"):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
            status = db.execute(
                "SELECT status FROM main.batches WHERE batch_id='b-reserved-sell'"
            ).fetchone()[0]
        self.assertEqual(status, "COMMITTED_PENDING_OUTBOX")


    def test_account_cash_tampering_is_detected_against_fill_audit_state(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match fill audit state"):
            self.store.pending_reservation_outbox()

    def test_holdings_tampering_is_detected_against_fill_audit_state(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.holdings SET quantity='999' WHERE market_id='BTC/USDT'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "holdings do not match fill audit state"):
            self.store.pending_reservation_outbox()


    def test_snapshot_rejects_tampered_account_state(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match fill audit state"):
            self.store.snapshot()

    def test_new_batch_rejects_tampered_holdings_before_using_them(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.holdings SET quantity='999' WHERE market_id='BTC/USDT'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "holdings do not match fill audit state"):
            self.store.apply_batch(
                batch_id="b-after-tamper", fills=[self.buy(fill_id="f-new")],
                timestamp=20,
            )
        with _managed_connection(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM main.batches WHERE batch_id='b-after-tamper'"
            ).fetchone())


    def test_idempotent_batch_replay_rejects_tampered_account_state(self):
        original = self.buy()
        self.store.apply_batch(
            batch_id="b-reserve-buy", fills=[original], timestamp=10
        )
        self.enable_reservations()
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match fill audit state"):
            self.store.apply_batch(
                batch_id="b-reserve-buy", fills=[original], timestamp=10
            )


    def test_snapshot_rejects_tampered_account_state_without_reservation_schema(self):
        self.store.apply_batch(
            batch_id="b-legacy-buy", fills=[self.buy()], timestamp=10
        )
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match fill audit state"):
            self.store.snapshot()

    def test_new_batch_rejects_tampered_holdings_without_reservation_schema(self):
        self.store.apply_batch(
            batch_id="b-legacy-buy", fills=[self.buy()], timestamp=10
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.holdings SET quantity='999' WHERE market_id='BTC/USDT'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "holdings do not match fill audit state"):
            self.store.apply_batch(
                batch_id="b-legacy-next", fills=[self.buy(fill_id="f-next")],
                timestamp=20,
            )


    def test_fill_with_tampered_batch_timestamp_is_rejected(self):
        self.store.apply_batch(
            batch_id="b-legacy-buy", fills=[self.buy()], timestamp=10
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.batches SET created_at=11 WHERE batch_id='b-legacy-buy'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "fill row does not match its batch/market contract"):
            self.store.snapshot()


    def test_snapshot_rejects_deleted_initial_account_audit_event(self):
        with _managed_connection(self.path) as db:
            db.execute("DELETE FROM main.audit")
        with self.assertRaisesRegex(
            SettlementStoreError, "required initial account audit event is missing"
        ):
            self.store.snapshot()

    def test_snapshot_rejects_tampered_initial_cash_before_first_fill(self):
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match initial account audit"):
            self.store.snapshot()

    def test_first_batch_rejects_tampered_initial_cash_baseline(self):
        with _managed_connection(self.path) as db:
            db.execute("UPDATE main.account SET cash='999' WHERE singleton=1")
        with self.assertRaisesRegex(SettlementStoreError, "account cash does not match initial account audit"):
            self.store.apply_batch(
                batch_id="b-first", fills=[self.buy()], timestamp=10
            )
        with _managed_connection(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM main.batches WHERE batch_id='b-first'"
            ).fetchone())

    def test_reservation_outbox_rejects_mutated_allocation_and_rehashed_payload(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservation_allocations SET allocated_quantity='0.2' "
                "WHERE allocation_id='a-1'"
            )
            db.execute(
                "UPDATE main.reservations SET consumed_quantity='0.2' "
                "WHERE reservation_id='r-1'"
            )
            db.execute(
                "UPDATE main.reservation_outbox SET allocated_quantity='0.2' "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
            row = db.execute(
                "SELECT idempotency_key,allocation_id,batch_id,fill_id,reservation_id,"
                "account_id,market_id,reservation_version,allocated_quantity "
                "FROM main.reservation_outbox WHERE idempotency_key='reservation-allocation:a-1'"
            ).fetchone()
            payload = dict(zip((
                "idempotency_key","allocation_id","batch_id","fill_id","reservation_id",
                "account_id","market_id","reservation_version","allocated_quantity",
            ), row))
            _, digest, _ = _canonical_payload({"schema": 1, **payload})
            db.execute(
                "UPDATE main.reservation_outbox SET payload_sha256=? "
                "WHERE idempotency_key='reservation-allocation:a-1'", (digest,)
            )
        with self.assertRaisesRegex(SettlementStoreError, "SELL fill quantity does not match allocation ledger"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "SELL fill quantity does not match allocation ledger"):
            self.store.acknowledge_reservation_outbox(
                "reservation-allocation:a-1", receiver_receipt=expected_receipt,
                expected_payload_sha256=expected_hash,
            )

    def test_reservation_outbox_rejects_fill_after_reservation_expiry(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservations SET expires_at=15 WHERE reservation_id='r-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "reservation creation audit does not match current record"):
            self.store.pending_reservation_outbox()

    def test_reservation_outbox_rejects_rehashed_payload_divergence(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "UPDATE main.reservation_outbox "
                "SET allocated_quantity='0.2' "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
            row = db.execute(
                "SELECT idempotency_key,allocation_id,batch_id,fill_id,reservation_id,"
                "account_id,market_id,reservation_version,allocated_quantity "
                "FROM main.reservation_outbox WHERE idempotency_key='reservation-allocation:a-1'"
            ).fetchone()
            payload = dict(zip((
                "idempotency_key","allocation_id","batch_id","fill_id","reservation_id",
                "account_id","market_id","reservation_version","allocated_quantity",
            ), row))
            _, changed_digest, _ = _canonical_payload({"schema": 1, **payload})
            db.execute(
                "UPDATE main.reservation_outbox SET payload_sha256=? "
                "WHERE idempotency_key='reservation-allocation:a-1'",
                (changed_digest,),
            )
        with self.assertRaisesRegex(SettlementStoreError, "differs from its allocation record"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "differs from its allocation record"):
            self.store.acknowledge_reservation_outbox(
                "reservation-allocation:a-1", receiver_receipt=expected_receipt,
                expected_payload_sha256=expected_hash,
            )


    def test_missing_reservation_outbox_blocks_delivery_and_batch_completion(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "DELETE FROM main.reservation_outbox "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "exactly one outbox row"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "exactly one outbox row"):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
            status = db.execute(
                "SELECT status FROM main.batches WHERE batch_id='b-reserved-sell'"
            ).fetchone()[0]
            legacy_status = db.execute(
                "SELECT status FROM main.outbox WHERE idempotency_key='settle:reserved'"
            ).fetchone()[0]
        self.assertEqual(status, "COMMITTED_PENDING_OUTBOX")
        self.assertEqual(legacy_status, "PENDING")

    def test_duplicate_reservation_outbox_rows_block_delivery_and_completion(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        with _managed_connection(self.path) as db:
            db.execute(
                "INSERT INTO main.reservation_outbox "
                "SELECT 'duplicate-key',allocation_id,batch_id,reservation_id,fill_id,"
                "account_id,market_id,reservation_version,allocated_quantity,payload_sha256,"
                "status,receiver_receipt FROM main.reservation_outbox "
                "WHERE idempotency_key='reservation-allocation:a-1'"
            )
        with self.assertRaisesRegex(SettlementStoreError, "exactly one outbox row"):
            self.store.pending_reservation_outbox()
        with self.assertRaisesRegex(SettlementStoreError, "exactly one outbox row"):
            self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
            status = db.execute(
                "SELECT status FROM main.batches WHERE batch_id='b-reserved-sell'"
            ).fetchone()[0]
        self.assertEqual(status, "COMMITTED_PENDING_OUTBOX")

    def test_reservation_outbox_acknowledgement_is_receipt_idempotent(self):
        self.store.apply_batch(batch_id="b-reserve-buy", fills=[self.buy()], timestamp=10)
        self.enable_reservations()
        self.store.apply_batch(
            batch_id="b-reserved-sell", fills=[self.sell()],
            sell_settlements=[self.sell_settlement()],
            sell_allocations=[self.allocation()], timestamp=20,
        )
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with self.assertRaisesRegex(SettlementStoreError, "does not match current payload"):
            self.store.acknowledge_reservation_outbox(
                "reservation-allocation:a-1", receiver_receipt="0" * 64,
                expected_payload_sha256=expected_hash,
            )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
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
        expected_hash, expected_receipt = self.reservation_ack_evidence(
            "reservation-allocation:a-1"
        )
        self.store.acknowledge_reservation_outbox(
            "reservation-allocation:a-1", receiver_receipt=expected_receipt,
            expected_payload_sha256=expected_hash,
        )
        with _managed_connection(self.path) as db:
            self.assertEqual(
                db.execute("SELECT status FROM batches WHERE batch_id='b-reserved-sell'").fetchone()[0],
                "COMMITTED_PENDING_OUTBOX",
            )
        self.store.acknowledge_outbox("settle:reserved", receiver_receipt="legacy-receipt")
        with _managed_connection(self.path) as db:
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
        with _managed_connection(self.path) as db:
            db.execute("DROP TABLE outbox")
        with self.assertRaisesRegex(SettlementStoreError, "schema mismatch"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")
        with _managed_connection(self.path) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertNotIn("outbox", tables)

    def test_changed_table_constraint_is_rejected_even_when_columns_match(self):
        with _managed_connection(self.path) as db:
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
        with _managed_connection(self.path) as db:
            db.execute(
                "CREATE TRIGGER injected_audit_trigger AFTER INSERT ON fills "
                "BEGIN UPDATE account SET cash='0' WHERE singleton=1; END"
            )
        with self.assertRaisesRegex(SettlementStoreError, "unapproved schema objects"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")

    def test_unapproved_index_is_rejected(self):
        with _managed_connection(self.path) as db:
            db.execute("CREATE INDEX injected_fill_index ON fills(market_id)")
        with self.assertRaisesRegex(SettlementStoreError, "unapproved schema objects"):
            SQLiteSettlementStore(self.path, account_id="paper-research",
                                  currency="USDT", opening_cash="10000")

    def test_audit_corruption_detected(self):
        self.store.apply_batch(batch_id="b-8",
                               fills=[self.buy()], timestamp=10)
        with _managed_connection(self.path) as db:
            db.execute("UPDATE audit SET event_json='{}' WHERE seq=1")
        self.assertFalse(self.store.verify_audit_chain())


if __name__ == "__main__":
    unittest.main()
