import hashlib
import json
import sqlite3
import unittest

from tmm_core.reservation_lifecycle import (
    ReservationLifecycleError,
    authorize_reservation,
    cancel_reservation,
    create_reservation,
    expire_reservation,
    get_reservation,
    release_reservation,
)
from tmm_core.reservation_schema_v2 import ensure_reservation_schema_v2
from tmm_core.sqlite_settlement_store import _event_hash


class ReservationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT INTO metadata VALUES('account_initialization_audit','required-v1');
            INSERT INTO metadata VALUES('market_registration_audit','required-v1');
            CREATE TABLE account(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL
            );
            INSERT INTO account VALUES(1,'paper-research','USDT','1000');
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL
            );
            INSERT INTO markets VALUES('BTC/USDT','BTC','USDT');
            CREATE TABLE holdings(
                market_id TEXT PRIMARY KEY REFERENCES markets(market_id), quantity TEXT NOT NULL
            );
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
        initial = {
            "kind": "ACCOUNT_INITIALIZED", "account_id": "paper-research",
            "currency": "USDT", "opening_cash": "1000",
            "market_registration_audit": "required-v1",
        }
        initial_json = json.dumps(initial, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        initial_hash = _event_hash("0" * 64, initial)
        market = {
            "kind": "MARKET_REGISTERED", "account_id": "paper-research",
            "market_id": "BTC/USDT", "base_asset": "BTC", "quote_asset": "USDT",
        }
        market_json = json.dumps(market, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        market_hash = _event_hash(initial_hash, market)
        self.db.executemany(
            "INSERT INTO audit(event_json,previous_hash,event_hash) VALUES(?,?,?)",
            [(initial_json, "0" * 64, initial_hash), (market_json, initial_hash, market_hash)],
        )
        self.db.commit()
        self.db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(self.db)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def begin(self):
        self.db.execute("BEGIN IMMEDIATE")

    def create(self, **overrides):
        args = {
            "reservation_id": "r-1", "account_id": "paper-research",
            "market_id": "BTC/USDT", "base_asset": "BTC", "quote_asset": "USDT",
            "authorized_quantity": "0.75", "created_at": 100, "expires_at": 200,
        }
        args.update(overrides)
        self.begin()
        result = create_reservation(self.db, **args)
        self.db.commit()
        return result

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

    def test_corrupt_base_audit_chain_blocks_reservation_mutation(self):
        self.db.execute("UPDATE audit SET event_hash=? WHERE seq=1", ("0" * 64,))
        self.db.commit()
        with self.assertRaisesRegex(
            ReservationLifecycleError, "explicit account and market audit baselines"
        ):
            self.create(reservation_id="corrupt-audit-r")

    def test_missing_account_genesis_blocks_reservation_mutation(self):
        self.db.execute("DELETE FROM audit")
        self.db.commit()
        with self.assertRaisesRegex(
            ReservationLifecycleError, "explicit account and market audit baselines"
        ):
            self.create(reservation_id="missing-genesis-r")

    def test_pre_marker_store_cannot_create_or_change_reservations(self):
        self.db.execute(
            "DELETE FROM metadata WHERE key IN "
            "('account_initialization_audit','market_registration_audit')"
        )
        self.db.commit()
        self.begin()
        with self.assertRaisesRegex(
            ReservationLifecycleError, "explicit account and market audit baselines"
        ):
            create_reservation(
                self.db, reservation_id="legacy-r", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=200,
            )
        self.db.rollback()
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0
        )

    def test_create_is_pending_and_audited(self):
        row = self.create()
        self.assertEqual((row["status"], row["version"]), ("PENDING", 1))
        self.assertEqual(row["expires_at"], 200)
        self.assertEqual(row["consumed_quantity"], "0")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 3)
        self.assertTrue(self.audit_is_valid())

    def test_create_rejects_timestamp_outside_sqlite_integer_range(self):
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "SQLite integer"):
            create_reservation(
                self.db, reservation_id="r", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=2**63, expires_at=2**63,
            )
        self.db.rollback()

    def test_transition_rejects_version_outside_sqlite_integer_range(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "safe monotonic version increment"):
            authorize_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=2**63 - 2, now=150,
            )
        self.db.rollback()

    def test_create_rejects_expiry_not_after_creation(self):
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "later than created_at"):
            create_reservation(
                self.db, reservation_id="r", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=100,
            )
        self.db.rollback()

    def test_create_rejects_account_or_quote_mismatch(self):
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "account or quote"):
            create_reservation(
                self.db, reservation_id="r", account_id="wrong",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=200,
            )
        self.db.rollback()

    def test_create_rejects_market_asset_mismatch(self):
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "market asset"):
            create_reservation(
                self.db, reservation_id="r", account_id="paper-research",
                market_id="BTC/USDT", base_asset="ETH", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=200,
            )
        self.db.rollback()

    def test_create_rejects_invalid_decimal_precision(self):
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "precision"):
            create_reservation(
                self.db, reservation_id="r", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="0.0000000000000000001",
                created_at=100, expires_at=200,
            )
        self.db.rollback()

    def test_authorize_is_versioned_and_audited(self):
        self.create()
        self.begin()
        row = authorize_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()
        self.assertEqual((row["status"], row["version"]), ("ACTIVE", 2))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 4)
        self.assertTrue(self.audit_is_valid())

    def test_authorize_rejects_stale_version(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "stale"):
            authorize_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=2, now=150,
            )
        self.db.rollback()

    def test_authorize_rejects_timestamp_before_creation(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "predates"):
            authorize_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=1, now=99,
            )
        self.db.rollback()

    def test_authorize_rejects_at_expiry_boundary(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "expired"):
            authorize_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=1, now=200,
            )
        self.db.rollback()

    def test_release_active_increments_version(self):
        self.create()
        self.begin()
        authorize_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()
        self.begin()
        row = release_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=2, now=160,
        )
        self.db.commit()
        self.assertEqual((row["status"], row["version"]), ("RELEASED", 3))
        self.assertTrue(self.audit_is_valid())

    def test_release_rejects_expired_reservation(self):
        self.create()
        self.begin()
        authorize_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "expiry transition"):
            release_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=2, now=200,
            )
        self.db.rollback()

    def test_cancel_pending_reservation(self):
        self.create()
        self.begin()
        row = cancel_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=150,
        )
        self.db.commit()
        self.assertEqual((row["status"], row["version"]), ("CANCELLED", 2))

    def test_expire_at_boundary(self):
        self.create()
        self.begin()
        row = expire_reservation(
            self.db, reservation_id="r-1", account_id="paper-research",
            expected_version=1, now=200,
        )
        self.db.commit()
        self.assertEqual((row["status"], row["version"]), ("EXPIRED", 2))
        self.assertTrue(self.audit_is_valid())

    def test_cancel_after_expiry_must_use_expiry_transition(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "expiry transition"):
            cancel_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=1, now=200,
            )
        self.db.rollback()

    def test_expire_before_boundary_rejected(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "not reached expiry"):
            expire_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                expected_version=1, now=199,
            )
        self.db.rollback()

    def test_wrong_account_cannot_read_or_transition(self):
        self.create()
        self.assertIsNone(get_reservation(
            self.db, reservation_id="r-1", account_id="other"
        ))
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "not found for account"):
            authorize_reservation(
                self.db, reservation_id="r-1", account_id="other",
                expected_version=1, now=150,
            )
        self.db.rollback()

    def test_rollback_reverts_reservation_and_audit_together(self):
        self.begin()
        create_reservation(
            self.db, reservation_id="rollback", account_id="paper-research",
            market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
            authorized_quantity="1", created_at=100, expires_at=200,
        )
        self.db.rollback()
        self.assertIsNone(get_reservation(
            self.db, reservation_id="rollback", account_id="paper-research"
        ))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 2)

    def test_missing_audit_schema_fails_before_reservation_write(self):
        self.db.execute("DROP TABLE audit")
        self.db.commit()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "canonical settlement audit"):
            create_reservation(
                self.db, reservation_id="no-audit", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=200,
            )
        self.assertIsNone(self.db.execute(
            "SELECT 1 FROM reservations WHERE reservation_id='no-audit'"
        ).fetchone())
        self.db.rollback()

    def test_duplicate_reservation_id_is_rejected(self):
        self.create()
        self.begin()
        with self.assertRaisesRegex(ReservationLifecycleError, "identity"):
            create_reservation(
                self.db, reservation_id="r-1", account_id="paper-research",
                market_id="BTC/USDT", base_asset="BTC", quote_asset="USDT",
                authorized_quantity="1", created_at=100, expires_at=200,
            )
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
