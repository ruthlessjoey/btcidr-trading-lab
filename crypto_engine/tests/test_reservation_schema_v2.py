import sqlite3
import unittest

from tmm_core.reservation_schema_v2 import (
    ReservationSchemaError,
    ensure_reservation_schema_v2,
)


class ReservationSchemaV2Tests(unittest.TestCase):
    def connection(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE markets(market_id TEXT PRIMARY KEY);
            CREATE TABLE batches(batch_id TEXT PRIMARY KEY);
            CREATE TABLE fills(fill_id TEXT PRIMARY KEY);
        """)
        return db

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
                    'r1','acct','UNKNOWN','BTC','USDT','1','0',1,1,'ACTIVE'
                )
            """)
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
