import sqlite3
import unittest

from tmm_core import reservation_migration_preflight as preflight_module
from tmm_core.reservation_migration_preflight import (
    inspect_v1_migration_eligibility,
)


DDL = """
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE account(singleton INTEGER PRIMARY KEY CHECK(singleton=1), account_id TEXT NOT NULL, currency TEXT NOT NULL, cash TEXT NOT NULL);
CREATE TABLE markets(market_id TEXT PRIMARY KEY, base_asset TEXT NOT NULL, quote_asset TEXT NOT NULL);
CREATE TABLE holdings(market_id TEXT PRIMARY KEY REFERENCES markets(market_id), quantity TEXT NOT NULL);
CREATE TABLE batches(batch_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PROCESSING','COMMITTED_PENDING_OUTBOX','COMPLETE','RECONCILIATION_REQUIRED')), created_at INTEGER NOT NULL, result_json TEXT);
CREATE TABLE fills(fill_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL, price TEXT NOT NULL, fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL);
CREATE TABLE audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TABLE outbox(idempotency_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), market_id TEXT NOT NULL REFERENCES markets(market_id), authorized_quantity TEXT NOT NULL, filled_quantity TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('PENDING','ACKNOWLEDGED')), receiver_receipt TEXT);
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
        self.db.commit()
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

    def test_altered_constraint_with_same_columns_is_blocked(self):
        self.db.execute("PRAGMA writable_schema=ON")
        self.db.execute(
            "UPDATE sqlite_master SET sql=replace(sql, 'CHECK(singleton=1)', "
            "'CHECK(singleton=2)') WHERE type='table' AND name='account'"
        )
        self.db.execute("PRAGMA writable_schema=OFF")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("schema definition mismatch: account" in item for item in result.blockers))

    def test_whitespace_inside_check_literal_is_not_normalized_away(self):
        self.db.execute("PRAGMA writable_schema=ON")
        self.db.execute(
            "UPDATE sqlite_master SET sql=replace(sql, "
            "'PROCESSING','PRO CESSING') "
            "WHERE type='table' AND name='batches'"
        )
        self.db.execute("PRAGMA writable_schema=OFF")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("schema definition mismatch: batches" in item for item in result.blockers))

    def test_missing_required_column_is_reported_without_sql_crash(self):
        self.db.execute("ALTER TABLE fills RENAME TO fills_old")
        self.db.execute(
            "CREATE TABLE fills(fill_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, "
            "market_id TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL, "
            "fee_quote TEXT NOT NULL, timestamp INTEGER NOT NULL)"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("column contract mismatch: fills" in item for item in result.blockers))

    def test_non_object_audit_event_is_blocked(self):
        import hashlib
        payload = "[]"
        digest = hashlib.sha256(("0" * 64 + payload).encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO audit VALUES(1,?,?,?)",
            (payload, "0" * 64, digest),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_noncanonical_audit_json_is_blocked(self):
        import hashlib
        payload = '{ "kind" : "TEST" }'
        canonical = '{"kind":"TEST"}'
        digest = hashlib.sha256(("0" * 64 + canonical).encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO audit VALUES(1,?,?,?)",
            (payload, "0" * 64, digest),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_deeply_nested_audit_json_is_blocked_without_recursion_error(self):
        payload = "[" * 10000 + "0" + "]" * 10000
        self.db.execute(
            "INSERT INTO audit VALUES(1,?,?,?)",
            (payload, "0" * 64, "f" * 64),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_changed_column_contract_is_blocked(self):
        self.db.execute("ALTER TABLE outbox ADD COLUMN unexpected TEXT")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("column contract mismatch" in item for item in result.blockers))

    def test_temp_view_cannot_shadow_main_audit_table(self):
        self.db.execute(
            "INSERT INTO main.audit VALUES(1,'{}',?,?)",
            ("0" * 64, "f" * 64),
        )
        self.db.execute(
            "CREATE TEMP VIEW audit AS "
            "SELECT seq,event_json,previous_hash,event_hash "
            "FROM main.audit WHERE 0"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_oversized_audit_event_blocks_preflight_without_parsing(self):
        payload = " " * (64 * 1024 + 1)
        self.db.execute(
            "INSERT INTO audit VALUES(1,?,?,?)",
            (payload, "0" * 64, "f" * 64),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_audit_total_byte_budget_blocks_preflight(self):
        self.db.execute(
            "INSERT INTO audit VALUES(1,'{}',?,?)",
            ("0" * 64, "f" * 64),
        )
        original = preflight_module._AUDIT_MAX_TOTAL_BYTES
        preflight_module._AUDIT_MAX_TOTAL_BYTES = 1
        try:
            result = self.inspect()
        finally:
            preflight_module._AUDIT_MAX_TOTAL_BYTES = original
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_audit_event_count_budget_blocks_preflight(self):
        self.db.execute(
            "INSERT INTO audit VALUES(1,'{}',?,?)",
            ("0" * 64, "f" * 64),
        )
        original = preflight_module._AUDIT_MAX_EVENTS
        preflight_module._AUDIT_MAX_EVENTS = 0
        try:
            result = self.inspect()
        finally:
            preflight_module._AUDIT_MAX_EVENTS = original
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

    def test_invalid_utf8_audit_text_blocks_preflight_without_sql_crash(self):
        self.db.execute(
            "INSERT INTO audit VALUES(1,CAST(x'80' AS TEXT),?,?)",
            ("0" * 64, "f" * 64),
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("audit chain" in item for item in result.blockers))

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

    def test_unapproved_persistent_view_is_blocked(self):
        self.db.execute("CREATE VIEW injected_view AS SELECT 'shadow' AS value")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any(
            "indexes, triggers, or views" in item
            for item in result.blockers
        ))

    def test_unapproved_trigger_is_blocked(self):
        self.db.execute(
            "CREATE TRIGGER injected AFTER INSERT ON fills BEGIN SELECT 1; END"
        )
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any("indexes, triggers, or views" in item for item in result.blockers))


    def test_malformed_foreign_key_target_is_reported_without_sql_crash(self):
        self.db.execute("DROP TABLE holdings")
        # SQLite reports a foreign-key mismatch (rather than an empty result)
        # when the referenced parent key is not UNIQUE/PRIMARY KEY.
        self.db.execute("CREATE TABLE missing_markets(market_id TEXT)")
        self.db.execute(
            "CREATE TABLE holdings(market_id TEXT PRIMARY KEY "
            "REFERENCES missing_markets(market_id), quantity TEXT NOT NULL)"
        )
        self.db.execute("INSERT INTO holdings VALUES('unknown-market','1')")
        result = self.inspect()
        self.assertFalse(result.eligible)
        self.assertTrue(any(
            "foreign_key_check could not be completed" in item
            for item in result.blockers
        ))

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
