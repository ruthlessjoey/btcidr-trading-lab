import hashlib
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tmm_core.reservation_migration import (
    ReservationMigrationBlocked,
    ReservationMigrationError,
    create_v2_migrated_copy,
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


def create_clean_v1(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(DDL)
    db.execute("INSERT INTO metadata VALUES('schema_version','1')")
    db.execute("INSERT INTO account VALUES(1,'paper-research','USDT','1000')")
    db.execute("INSERT INTO markets VALUES('BTC/USDT','BTC','USDT')")
    db.execute("INSERT INTO batches VALUES('b-complete','request-hash','COMPLETE',10,'{}')")
    db.commit()
    db.close()


class ReservationMigrationCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite3"
        self.backup = self.root / "source.backup.sqlite3"
        self.output = self.root / "source.v2.sqlite3"
        create_clean_v1(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_byte_verified_backup_and_separate_v2_copy(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        result = create_v2_migrated_copy(self.source,self.backup,self.output)
        after = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertEqual(result.source_sha256,before)
        self.assertEqual(result.backup_sha256,before)
        self.assertEqual(hashlib.sha256(self.backup.read_bytes()).hexdigest(),before)
        self.assertNotEqual(result.output_sha256,before)
        self.assertEqual(result.schema_class,"V2_CURRENT_EXACT")
        self.assertTrue(result.new_reservation_tables_empty)
        self.assertTrue(self.output.is_file())
        self.assertTrue(self.backup.is_file())
        self.assertEqual(stat.S_IMODE(self.backup.stat().st_mode),0o400)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode),0o600)
        self.assertEqual(len(result.original_table_sha256),8)

    def test_unresolved_source_is_blocked_before_any_copy_is_created(self):
        with sqlite3.connect(self.source) as db:
            db.execute(
                "INSERT INTO batches VALUES('b-processing','request-hash','PROCESSING',20,'{}')"
            )
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(ReservationMigrationBlocked):
            create_v2_migrated_copy(self.source,self.backup,self.output)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),before)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.output.exists())


    def test_source_metadata_change_during_preflight_blocks_copy(self):
        import tmm_core.reservation_migration as migration
        original = migration._preflight_and_snapshot
        def change_source(path):
            result = original(path)
            info = path.stat()
            os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns + 1_000_000))
            return result
        with mock.patch(
            "tmm_core.reservation_migration._preflight_and_snapshot",
            side_effect=change_source,
        ):
            with self.assertRaisesRegex(ReservationMigrationError,"source file identity changed"):
                create_v2_migrated_copy(self.source,self.backup,self.output)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.output.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.backup.write_bytes(b"owner-data")
        with self.assertRaisesRegex(ReservationMigrationError,"must not already exist"):
            create_v2_migrated_copy(self.source,self.backup,self.output)
        self.assertEqual(self.backup.read_bytes(),b"owner-data")
        self.assertFalse(self.output.exists())

    def test_sqlite_sidecar_blocks_copy(self):
        sidecar = Path(str(self.source) + "-wal")
        sidecar.write_bytes(b"active-wal")
        with self.assertRaisesRegex(ReservationMigrationError,"sidecar files exist"):
            create_v2_migrated_copy(self.source,self.backup,self.output)
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.output.exists())

    def test_symlink_source_is_rejected(self):
        link = self.root / "source-link.sqlite3"
        try:
            link.symlink_to(self.source)
        except (OSError,NotImplementedError):
            self.skipTest("symlinks are unavailable in this environment")
        with self.assertRaisesRegex(ReservationMigrationError,"regular non-symlink"):
            create_v2_migrated_copy(link,self.backup,self.output)

    def test_failed_schema_enablement_rolls_back_and_keeps_verified_backup(self):
        def partial_then_fail(db):
            db.execute("CREATE TABLE partial_write(value TEXT)")
            raise RuntimeError("synthetic migration interruption")
        with mock.patch(
            "tmm_core.reservation_migration.ensure_reservation_schema_v2",
            side_effect=partial_then_fail,
        ):
            with self.assertRaisesRegex(RuntimeError,"synthetic migration interruption"):
                create_v2_migrated_copy(self.source,self.backup,self.output)
        self.assertTrue(self.backup.is_file())
        self.assertEqual(
            hashlib.sha256(self.backup.read_bytes()).hexdigest(),
            hashlib.sha256(self.source.read_bytes()).hexdigest(),
        )
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
