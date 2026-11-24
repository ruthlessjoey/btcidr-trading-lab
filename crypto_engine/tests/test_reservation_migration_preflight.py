import sqlite3
import unittest

from tmm_core.reservation_migration_preflight import (
    inspect_v1_migration_eligibility,
)


DDL = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE account(singleton INTEGER PRIMARY KEY,account_id TEXT,currency TEXT,cash TEXT);
CREATE TABLE markets(market_id TEXT PRIMARY KEY,base_asset TEXT,quote_asset TEXT);
CREATE TABLE holdings(market_id TEXT PRIMARY KEY,quantity TEXT);
CREATE TABLE batches(batch_id TEXT PRIMARY KEY,request_hash TEXT,status TEXT,created_at INTEGER,result_json TEXT);
CREATE TABLE fills(fill_id TEXT PRIMARY KEY,batch_id TEXT,market_id TEXT,side TEXT,quantity TEXT,price TEXT,fee_quote TEXT,timestamp INTEGER);
CREATE TABLE audit(seq INTEGER PRIMARY KEY,event_json TEXT,previous_hash TEXT,event_hash TEXT);
CREATE TABLE outbox(idempotency_key TEXT PRIMARY KEY,batch_id TEXT,market_id TEXT,authorized_quantity TEXT,filled_quantity TEXT,status TEXT,receiver_receipt TEXT);
"""


class ReservationMigrationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(DDL)
        self.db.execute("INSERT INTO metadata VALUES('schema_version','1')")
        self.db.execute("INSERT INTO account VALUES(1,'paper','USDT','1000')")
        self.db.execute("INSERT INTO markets VALUES('BTC/USDT','BTC','USDT')")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def inspect(self):
        self.db.execute("PRAGMA query_only=ON")
        self.db.execute("BEGIN")
        try:
            return inspect_v1_migration_eligibility(self.db)
        finally:
            self.db.rollback()
            self.db.execute("PRAGMA query_only=OFF")

    def test_clean_buy_only_v1_database_is_preflight_eligible(self):
        result = self.inspect()
        self.assertTrue(result.eligible)
        self.assertEqual(result.blockers, ())
        self.assertEqual(result.schema_version, "1")

    def test_historical_sell_fill_is_blocked(self):
        self.db.execute(
            "INSERT INTO fills VALUES('s1','b1','BTC/USDT','SELL','1','10','0',1)"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertEqual(result.sell_fill_count, 1)
        self.assertTrue(any("SELL fills" in item for item in result.blockers))

    def test_any_legacy_outbox_row_is_blocked_even_if_acknowledged(self):
        self.db.execute(
            "INSERT INTO outbox VALUES('k1','b1','BTC/USDT','1','1','ACKNOWLEDGED','r1')"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertEqual(result.outbox_row_count, 1)
        self.assertTrue(any("outbox rows" in item for item in result.blockers))

    def test_processing_batch_is_blocked(self):
        self.db.execute(
            "INSERT INTO batches VALUES('b1','h','PROCESSING',1,NULL)"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertEqual(result.unresolved_batch_count, 1)

    def test_reconciliation_required_batch_is_blocked(self):
        self.db.execute(
            "INSERT INTO batches VALUES('b1','h','RECONCILIATION_REQUIRED',1,NULL)"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertEqual(result.unresolved_batch_count, 1)

    def test_wrong_schema_version_is_blocked(self):
        self.db.execute(
            "UPDATE metadata SET value='9' WHERE key='schema_version'"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("schema version" in item for item in result.blockers))

    def test_changed_column_contract_is_blocked(self):
        self.db.execute("ALTER TABLE outbox ADD COLUMN unexpected TEXT")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("column contract mismatch" in item for item in result.blockers))

    def test_broken_audit_chain_is_blocked(self):
        self.db.execute(
            "INSERT INTO audit VALUES(1,'{}',?,?)",
            ("0" * 64, "f" * 64),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_requires_read_only_query_mode(self):
        self.db.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "query_only"):
            inspect_v1_migration_eligibility(self.db)
        self.db.rollback()

    def test_requires_consistent_transaction(self):
        self.db.execute("PRAGMA query_only=ON")
        with self.assertRaisesRegex(ValueError, "read transaction"):
            inspect_v1_migration_eligibility(self.db)
        self.db.execute("PRAGMA query_only=OFF")

    def test_preflight_does_not_modify_database(self):
        before = self.db.execute(
            "SELECT name,sql FROM sqlite_master ORDER BY name"
        ).fetchall()
        self.inspect()
        after = self.db.execute(
            "SELECT name,sql FROM sqlite_master ORDER BY name"
        ).fetchall()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
