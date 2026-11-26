import json
import sqlite3
import unittest

from tmm_core.sqlite_settlement_store import _event_hash

from tmm_core.reservation_schema_v2 import (
    ReservationSchemaError,
    ensure_reservation_schema_v2,
)


class ReservationSchemaV2Tests(unittest.TestCase):
    def connection(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            INSERT INTO metadata VALUES('account_initialization_audit','required-v1');
            INSERT INTO metadata VALUES('market_registration_audit','required-v1');
            CREATE TABLE account(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL
            );
            INSERT INTO account VALUES(1,'paper-research','USDT','1000');
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL
            );
            CREATE TABLE holdings(
                market_id TEXT PRIMARY KEY REFERENCES markets(market_id),
                quantity TEXT NOT NULL
            );
            CREATE TABLE audit(
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
            );
            CREATE TABLE batches(
                batch_id TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                  ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')),
                created_at INTEGER NOT NULL,
                result_json TEXT
            );
            CREATE TABLE fills(
                fill_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL REFERENCES batches(batch_id),
                market_id TEXT NOT NULL REFERENCES markets(market_id),
                side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
                quantity TEXT NOT NULL,
                price TEXT NOT NULL,
                fee_quote TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            );
        """)
        event = {
            "kind": "ACCOUNT_INITIALIZED", "account_id": "paper-research",
            "currency": "USDT", "opening_cash": "1000",
            "market_registration_audit": "required-v1",
        }
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = _event_hash("0" * 64, event)
        db.execute(
            "INSERT INTO audit(event_json,previous_hash,event_hash) VALUES(?,?,?)",
            (encoded, "0" * 64, digest),
        )
        db.commit()
        return db

    def test_rejects_parent_table_without_referenced_primary_key(self):
        db = self.connection()
        db.execute("DROP TABLE markets")
        db.execute("""
            CREATE TABLE markets(
                market_id TEXT NOT NULL,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL
            )
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "base settlement schema definition mismatch for markets"):
            ensure_reservation_schema_v2(db)
        self.assertIsNone(db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='reservations'"
        ).fetchone())
        db.rollback()
        db.close()

    def test_rejects_parent_table_with_unexpected_columns(self):
        db = self.connection()
        db.execute("DROP TABLE markets")
        db.execute("""
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL,
                injected TEXT
            )
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "base settlement schema definition mismatch for markets"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_generated_parent_column_hidden_from_table_info(self):
        db = self.connection()
        db.execute("DROP TABLE markets")
        db.execute("""
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL,
                shadow TEXT GENERATED ALWAYS AS (base_asset || quote_asset) VIRTUAL
            )
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "base settlement schema definition mismatch for markets"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_parent_collation_change_with_same_columns_and_primary_key(self):
        db = self.connection()
        db.execute("DROP TABLE markets")
        db.execute("""
            CREATE TABLE markets(
                market_id TEXT PRIMARY KEY COLLATE NOCASE,
                base_asset TEXT NOT NULL,
                quote_asset TEXT NOT NULL
            )
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "base settlement schema definition mismatch for markets"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_refuses_schema_creation_without_both_audit_baselines(self):
        db = self.connection()
        db.execute("DELETE FROM metadata")
        db.commit()
        db.execute("BEGIN")
        with self.assertRaisesRegex(
            ReservationSchemaError, "explicit account and market audit baseline"
        ):
            ensure_reservation_schema_v2(db)
        self.assertIsNone(db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='reservations'"
        ).fetchone())
        db.rollback()
        db.close()

    def test_requires_caller_owned_transaction(self):
        db = self.connection()
        with self.assertRaisesRegex(ReservationSchemaError, "transaction"):
            ensure_reservation_schema_v2(db)
        db.close()

    def test_requires_check_constraint_enforcement(self):
        db = self.connection()
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "CHECK constraint enforcement"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_requires_foreign_key_enforcement(self):
        db = self.connection()
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "foreign key enforcement"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_requires_parent_settlement_tables(self):
        db = sqlite3.connect(":memory:")
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "base settlement"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_creates_all_three_objects_in_caller_transaction(self):
        db = self.connection()
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        names = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertTrue({
            "reservations", "reservation_allocations", "reservation_outbox"
        }.issubset(names))
        self.assertTrue(db.in_transaction)
        db.commit()
        db.close()

    def test_is_idempotent_for_exact_schema(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.close()

    def test_rejects_partial_schema_without_completing_it(self):
        db = self.connection()
        db.execute("""
            CREATE TABLE reservations(
                reservation_id TEXT PRIMARY KEY, account_id TEXT NOT NULL
            )
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "partial"):
            ensure_reservation_schema_v2(db)
        self.assertIsNone(db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='reservation_allocations'"
        ).fetchone())
        db.rollback()
        db.close()

    def test_rejects_altered_constraint_with_same_columns(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("PRAGMA writable_schema=ON")
        db.execute(
            "UPDATE sqlite_master SET sql=replace(sql, 'ACTIVE', 'INVALID') "
            "WHERE type='table' AND name='reservations'"
        )
        db.execute("PRAGMA writable_schema=OFF")
        db.commit()
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "definition mismatch"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_whitespace_change_inside_check_literal(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("PRAGMA writable_schema=ON")
        db.execute(
            "UPDATE sqlite_master SET sql=replace(sql, 'ACTIVE', 'ACT IVE') "
            "WHERE type='table' AND name='reservations'"
        )
        db.execute("PRAGMA writable_schema=OFF")
        db.commit()
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "definition mismatch"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_temp_table_cannot_shadow_main_reservation_columns(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("CREATE TEMP TABLE reservations(shadow_only TEXT)")
        db.execute("BEGIN")
        # Verification must inspect main.reservations, not temp.reservations.
        ensure_reservation_schema_v2(db)
        db.commit()
        db.close()

    def test_rejects_case_variant_temp_trigger_target(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("CREATE TEMP TABLE trigger_log(value TEXT)")
        db.execute("""
            CREATE TEMP TRIGGER injected_case_variant_trigger
            AFTER INSERT ON main."RESERVATIONS"
            BEGIN INSERT INTO trigger_log VALUES ('unexpected'); END
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "TEMP reservation triggers"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_temp_trigger_on_main_reservation_table(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("CREATE TEMP TABLE trigger_log(value TEXT)")
        db.execute("""
            CREATE TEMP TRIGGER injected_temp_reservation_trigger
            AFTER INSERT ON main.reservations
            BEGIN INSERT INTO trigger_log VALUES ('unexpected'); END
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "TEMP reservation triggers"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_trigger_on_fill_parent_that_can_mutate_reservations(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("""
            CREATE TRIGGER injected_fill_reservation_trigger
            AFTER INSERT ON fills
            BEGIN
                UPDATE reservations SET version=version+1
                WHERE reservation_id='r1';
            END
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "unapproved"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_temp_trigger_on_fill_parent_that_can_mutate_reservations(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("""
            CREATE TEMP TRIGGER injected_temp_fill_reservation_trigger
            AFTER INSERT ON main.fills
            BEGIN
                UPDATE reservations SET version=version+1
                WHERE reservation_id='r1';
            END
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "TEMP reservation triggers"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_unapproved_index_on_parent_settlement_table(self):
        db = self.connection()
        db.execute("CREATE INDEX injected_fill_market_idx ON fills(market_id)")
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "unapproved reservation schema objects"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_existing_foreign_key_violations(self):
        db = self.connection()
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute(
            "INSERT INTO batches VALUES('b1','hash','COMPLETE',1,NULL)"
        )
        db.execute(
            "INSERT INTO fills VALUES('f1','missing-batch','missing-market','BUY','1','1','0',1)"
        )
        db.commit()
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "foreign-key violation"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_rejects_unapproved_trigger(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        db.execute("""
            CREATE TRIGGER injected_reservation_trigger
            AFTER INSERT ON reservations
            BEGIN SELECT 1; END
        """)
        db.execute("BEGIN")
        with self.assertRaisesRegex(ReservationSchemaError, "unapproved"):
            ensure_reservation_schema_v2(db)
        db.rollback()
        db.close()

    def test_foreign_keys_reject_unknown_parent_rows(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("""
                INSERT INTO reservations VALUES(
                    'r1','acct','UNKNOWN','BTC','USDT','1','0',1,2,1,'ACTIVE'
                )
            """)
        db.close()

    def test_reservation_schema_rejects_version_overflow(self):
        db = self.connection()
        db.execute("INSERT INTO markets VALUES('BTC/USDT','BTC','USDT')")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO reservations VALUES("
                "'r-max','acct','BTC/USDT','BTC','USDT','1','0',100,200,"
                "9223372036854775807,'PENDING')"
            )
        db.rollback()
        db.close()

    def test_reservation_schema_enforces_expiry_and_positive_version(self):
        db = self.connection()
        db.execute("INSERT INTO markets VALUES('BTC/USDT','BTC','USDT')")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        ensure_reservation_schema_v2(db)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO reservations VALUES("
                "'r1','acct','BTC/USDT','BTC','USDT','1','0',100,100,1,'PENDING')"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO reservations VALUES("
                "'r2','acct','BTC/USDT','BTC','USDT','1','0',100,200,0,'PENDING')"
            )
        db.rollback()
        db.close()

    def test_schema_creation_rolls_back_with_callers_transaction(self):
        db = self.connection()
        db.execute("BEGIN")
        ensure_reservation_schema_v2(db)
        db.rollback()
        names = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertNotIn("reservations", names)
        self.assertNotIn("reservation_allocations", names)
        self.assertNotIn("reservation_outbox", names)
        db.close()


if __name__ == "__main__":
    unittest.main()
