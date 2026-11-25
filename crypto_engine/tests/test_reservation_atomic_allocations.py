import json
import sqlite3
import unittest

from tmm_core.reservation_allocations import (
    ReservationAllocationError,
    consume_sell_allocations,
)
from tmm_core.reservation_lifecycle import authorize_reservation, create_reservation
from tmm_core.reservation_schema_v2 import ensure_reservation_schema_v2
from tmm_core.sqlite_settlement_store import _event_hash


class AtomicReservationAllocationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE account(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL
            );
            INSERT INTO account VALUES(1,'paper-research','USDT','1000');
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL
            );
            INSERT INTO markets VALUES('BTC/USDT','BTC','USDT');
            CREATE TABLE batches(
                batch_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                  ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')),
                created_at INTEGER NOT NULL, result_json TEXT
            );
            CREATE TABLE fills(
                fill_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                market_id TEXT NOT NULL REFERENCES markets(market_id),
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                quantity TEXT NOT NULL, price TEXT NOT NULL,
                fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL
            );
            CREATE TABLE audit(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
            );
        """)
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(self.db)
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        create_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
            authorized_quantity="1", created_at=100, expires_at=300,
        )
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        authorize_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def prepare_batch(self, fills, *, timestamp=160):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute(
            "INSERT INTO batches(batch_id,request_hash,status,created_at,result_json) "
            "VALUES('b-1','hash','PROCESSING',?,NULL)", (timestamp,)
        )
        for fill_id, market_id, side, quantity in fills:
            self.db.execute(
                "INSERT INTO fills(fill_id,batch_id,market_id,side,quantity,price,fee_quote,timestamp) "
                "VALUES(?, 'b-1', ?, ?, ?, '10', '0', ?)",
                (fill_id, market_id, side, quantity, timestamp),
            )

    def finish(self):
        self.db.commit()

    def allocations(self, quantity="0.4", version=2, **overrides):
        item = {
            "allocation_id": "a-1", "fill_id": "sell-1",
            "reservation_id": "r-1", "reservation_version": version,
            "allocated_quantity": quantity,
        }
        item.update(overrides)
        return [item]

    def audit_is_valid(self):
        previous = "0" * 64
        for event_json, stored_previous, stored_hash in self.db.execute(
            "SELECT event_json,previous_hash,event_hash FROM audit ORDER BY seq"
        ):
            event = json.loads(event_json)
            if stored_previous != previous or _event_hash(previous, event) != stored_hash:
                return False
            previous = stored_hash
        return True

    def test_consumes_exact_sell_fill_and_stages_outbox_atomically(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        result = consume_sell_allocations(
            self.db, account_id="paper-research", batch_id="b-1",
            allocations=self.allocations(), timestamp=160,
        )
        self.assertEqual(result[0]["allocated_quantity"], "0.4")
        self.assertEqual(result[0]["idempotency_key"], "reservation-allocation:a-1")
        self.finish()
        reservation = self.db.execute(
            "SELECT consumed_quantity,version,status FROM reservations WHERE reservation_id='r-1'"
        ).fetchone()
        self.assertEqual(reservation, ("0.4", 3, "ACTIVE"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reservation_allocations").fetchone()[0], 1)
        outbox = self.db.execute(
            "SELECT status,payload_sha256 FROM reservation_outbox"
        ).fetchone()
        self.assertEqual(outbox[0], "PENDING")
        self.assertEqual(len(outbox[1]), 64)
        self.assertTrue(self.audit_is_valid())

    def test_every_sell_fill_requires_exact_allocation(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "equal each fill"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=[], timestamp=160,
            )
        self.db.rollback()

    def test_partial_sell_fill_allocates_only_executed_quantity(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.25")])
        result = consume_sell_allocations(
            self.db, account_id="paper-research", batch_id="b-1",
            allocations=self.allocations("0.25"), timestamp=160,
        )
        self.finish()
        self.assertEqual(result[0]["allocated_quantity"], "0.25")
        self.assertEqual(
            self.db.execute("SELECT consumed_quantity FROM reservations").fetchone()[0],
            "0.25",
        )

    def test_multiple_reservations_can_allocate_one_fill(self):
        self.db.execute("BEGIN IMMEDIATE")
        create_reservation(
            self.db, reservation_id="r-2", account_id="paper-research",
            market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
            authorized_quantity="0.5", created_at=100, expires_at=300,
        )
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        authorize_reservation(
            self.db, reservation_id="r-2", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.5")])
        allocations = self.allocations("0.4") + [{
            "allocation_id": "a-2", "fill_id": "sell-1",
            "reservation_id": "r-2", "reservation_version": 2,
            "allocated_quantity": "0.1",
        }]
        result = consume_sell_allocations(
            self.db, account_id="paper-research", batch_id="b-1",
            allocations=allocations, timestamp=160,
        )
        self.finish()
        self.assertEqual(len(result), 2)
        self.assertEqual(
            self.db.execute(
                "SELECT SUM(CAST(consumed_quantity AS REAL)) FROM reservations"
            ).fetchone()[0], 0.5,
        )

    def test_stale_version_rejected_without_consumption(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "stale"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(version=1), timestamp=160,
            )
        self.db.rollback()
        self.assertEqual(
            self.db.execute("SELECT consumed_quantity FROM reservations").fetchone()[0],
            "0",
        )

    def test_version_without_increment_headroom_is_rejected(self):
        self.db.execute("UPDATE reservations SET version=? WHERE reservation_id='r-1'",
                        (2**63 - 2,))
        self.db.commit()
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "cannot be incremented safely"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(version=2**63 - 2), timestamp=160,
            )
        self.db.rollback()

    def test_expired_reservation_rejected(self):
        # Batch and fill timestamps must match; the reservation expires at 300.
        self.prepare_batch(
            [("sell-1", "BTC/USDT", "SELL", "0.4")], timestamp=300
        )
        with self.assertRaisesRegex(ReservationAllocationError, "expired"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(), timestamp=300,
            )
        self.db.rollback()

    def test_over_consumption_rejected(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "1.1")])
        with self.assertRaisesRegex(ReservationAllocationError, "over-consumption"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations("1.1"), timestamp=160,
            )
        self.db.rollback()

    def test_buy_fill_cannot_use_sell_reservation(self):
        self.prepare_batch([("buy-1", "BTC/USDT", "BUY", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "BUY fills"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(fill_id="buy-1"), timestamp=160,
            )
        self.db.rollback()

    def test_market_mismatch_rejected(self):
        self.db.execute("INSERT INTO markets VALUES('ETH/USDT','ETH','USDT')")
        self.db.commit()
        self.prepare_batch([("sell-1", "ETH/USDT", "SELL", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "cross-market"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(), timestamp=160,
            )
        self.db.rollback()

    def test_batch_timestamp_must_match_fill_timestamp(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        with self.assertRaisesRegex(ReservationAllocationError, "batch timestamp"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(), timestamp=161,
            )
        self.db.rollback()

    def test_non_processing_batch_rejected(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute(
            "INSERT INTO batches(batch_id,request_hash,status,created_at,result_json) "
            "VALUES('b-1','hash','COMPLETE',160,NULL)"
        )
        self.db.execute(
            "INSERT INTO fills(fill_id,batch_id,market_id,side,quantity,price,fee_quote,timestamp) "
            "VALUES('sell-1','b-1','BTC/USDT','SELL','0.4','10','0',160)"
        )
        with self.assertRaisesRegex(ReservationAllocationError, "PROCESSING"):
            consume_sell_allocations(
                self.db, account_id="paper-research", batch_id="b-1",
                allocations=self.allocations(), timestamp=160,
            )
        self.db.rollback()

    def test_rollback_reverts_consumption_allocations_and_outbox(self):
        self.prepare_batch([("sell-1", "BTC/USDT", "SELL", "0.4")])
        consume_sell_allocations(
            self.db, account_id="paper-research", batch_id="b-1",
            allocations=self.allocations(), timestamp=160,
        )
        self.db.rollback()
        self.assertEqual(
            self.db.execute("SELECT consumed_quantity FROM reservations").fetchone()[0],
            "0",
        )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reservation_allocations").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reservation_outbox").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
