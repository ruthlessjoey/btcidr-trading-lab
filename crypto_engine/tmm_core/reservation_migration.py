"""Copy-only, fail-closed v1 -> reservation-v2 schema enablement.

The source database is never modified. A verified byte-for-byte backup and a
separate migrated working copy are created. Existing holdings are not converted
into reservations and no SELL authority is created by this operation.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .reservation_migration_preflight import (
    MigrationPreflight,
    classify_reservation_schema,
    inspect_v1_migration_eligibility,
)
from .reservation_schema_v2 import ensure_reservation_schema_v2


_V1_TABLES = (
    "metadata","account","markets","holdings","batches",
    "fills","audit","outbox",
)
_V2_TABLES = (
    "reservations","reservation_allocations","reservation_outbox",
)
_CHUNK_SIZE = 1024 * 1024


class ReservationMigrationError(RuntimeError):
    """Unsafe copy, blocked preflight or failed schema enablement."""


class ReservationMigrationBlocked(ReservationMigrationError):
    """The source database did not satisfy the exact-v1 migration preflight."""

    def __init__(self, blockers: tuple[str, ...]):
        self.blockers = blockers
        super().__init__("migration preflight blocked: " + "; ".join(blockers))


@dataclass(frozen=True)
class ReservationMigrationCopyResult:
    source_path: str
    backup_path: str
    output_path: str
    source_sha256: str
    backup_sha256: str
    output_sha256: str
    schema_class: str
    original_table_sha256: tuple[tuple[str,str], ...]
    new_reservation_tables_empty: bool


def _absolute_regular_source(path: str | os.PathLike[str]) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ReservationMigrationError("source path must be absolute")
    if candidate.is_symlink() or not candidate.exists() or not candidate.is_file():
        raise ReservationMigrationError("source must be an existing regular non-symlink file")
    return candidate.resolve(strict=True)


def _new_destination(path: str | os.PathLike[str]) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ReservationMigrationError("destination paths must be absolute")
    if candidate.exists() or candidate.is_symlink():
        raise ReservationMigrationError("backup/output destination must not already exist")
    parent = candidate.parent
    if not parent.exists() or not parent.is_dir():
        raise ReservationMigrationError("destination parent directory must already exist")
    return parent.resolve(strict=True) / candidate.name


def _reject_sidecars(path: Path) -> None:
    for suffix in ("-wal","-shm","-journal"):
        if Path(str(path) + suffix).exists():
            raise ReservationMigrationError("SQLite sidecar files exist; close/checkpoint the database first")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(_CHUNK_SIZE)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _copy_exclusive(source: Path, destination: Path, *, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(destination,flags,mode)
    try:
        with os.fdopen(fd,"wb") as target, source.open("rb") as original:
            while True:
                block = original.read(_CHUNK_SIZE)
                if not block:
                    break
                target.write(block)
            target.flush()
            os.fsync(target.fileno())
        directory_fd = os.open(destination.parent,os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        finally:
            raise


def _readonly_uri(path: Path) -> str:
    return "file:" + quote(str(path),safe="/") + "?mode=ro"


def _open_readonly(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(_readonly_uri(path),uri=True,timeout=5)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA trusted_schema=OFF")
    return db


def _snapshot_v1_tables(db: sqlite3.Connection) -> tuple[tuple[str,str], ...]:
    snapshot = []
    for table in _V1_TABLES:
        digest = hashlib.sha256()
        rows = db.execute(f"SELECT * FROM main.{table} ORDER BY rowid")
        for row in rows:
            encoded = json.dumps(
                list(row),ensure_ascii=False,separators=(",",":")
            ).encode("utf-8")
            digest.update(len(encoded).to_bytes(8,"big"))
            digest.update(encoded)
        snapshot.append((table,digest.hexdigest()))
    return tuple(snapshot)


def _preflight_and_snapshot(path: Path) -> tuple[MigrationPreflight,tuple[tuple[str,str], ...]]:
    db = _open_readonly(path)
    try:
        if db.execute("PRAGMA journal_mode").fetchone() != ("delete",):
            raise ReservationMigrationError("source SQLite journal mode must be DELETE")
        db.execute("BEGIN")
        result = inspect_v1_migration_eligibility(db)
        snapshot = _snapshot_v1_tables(db)
        db.rollback()
        return result,snapshot
    finally:
        db.close()


def _verify_migrated_copy(
    path: Path,
    expected_snapshot: tuple[tuple[str,str], ...],
) -> None:
    db = _open_readonly(path)
    try:
        db.execute("BEGIN")
        if classify_reservation_schema(db) != "V2_CURRENT_EXACT":
            raise ReservationMigrationError("migrated copy is not the exact current v2 schema")
        if _snapshot_v1_tables(db) != expected_snapshot:
            raise ReservationMigrationError("original v1 table contents changed during schema enablement")
        for table in _V2_TABLES:
            if db.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone() != (0,):
                raise ReservationMigrationError("migration unexpectedly created reservation authority")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ReservationMigrationError("migrated copy integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ReservationMigrationError("migrated copy foreign-key check failed")
        db.rollback()
    finally:
        db.close()


def create_v2_migrated_copy(
    source_path: str | os.PathLike[str],
    backup_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
) -> ReservationMigrationCopyResult:
    """Create a verified byte-for-byte backup and a separate current-v2 copy.

    This function never changes source_path. Both destinations must be new
    absolute paths in existing directories. The backup is byte-for-byte and
    made read-only after verification. The output copy contains only the three
    empty reservation v2 tables; existing holdings are not reserved.
    """
    source = _absolute_regular_source(source_path)
    backup = _new_destination(backup_path)
    output = _new_destination(output_path)
    if len({str(source),str(backup),str(output)}) != 3:
        raise ReservationMigrationError("source, backup and output paths must be distinct")
    if os.path.samefile(source,backup) if backup.exists() else False:
        raise ReservationMigrationError("backup path aliases source")
    _reject_sidecars(source)

    source_hash_before = _sha256_file(source)
    preflight,snapshot = _preflight_and_snapshot(source)
    if not preflight.eligible:
        raise ReservationMigrationBlocked(preflight.blockers)
    if _sha256_file(source) != source_hash_before:
        raise ReservationMigrationError("source changed during read-only preflight")

    backup_created = False
    output_created = False
    try:
        _copy_exclusive(source,backup,mode=0o600)
        backup_created = True
        backup_hash = _sha256_file(backup)
        if backup_hash != source_hash_before or _sha256_file(source) != source_hash_before:
            raise ReservationMigrationError("source/backup byte hash mismatch")

        _copy_exclusive(backup,output,mode=0o600)
        output_created = True
        if _sha256_file(output) != backup_hash:
            raise ReservationMigrationError("working copy does not match verified backup")

        db = sqlite3.connect(output,timeout=5,isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA ignore_check_constraints=OFF")
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=FULL")
            if db.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise ReservationMigrationError("working copy could not enter DELETE journal mode")
            db.execute("BEGIN IMMEDIATE")
            db.execute("PRAGMA query_only=ON")
            locked_preflight = inspect_v1_migration_eligibility(db)
            if not locked_preflight.eligible:
                raise ReservationMigrationBlocked(locked_preflight.blockers)
            db.execute("PRAGMA query_only=OFF")
            ensure_reservation_schema_v2(db)
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ReservationMigrationError("working copy integrity check failed before commit")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ReservationMigrationError("working copy foreign-key check failed before commit")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        _verify_migrated_copy(output,snapshot)
        if _sha256_file(source) != source_hash_before or _sha256_file(backup) != backup_hash:
            raise ReservationMigrationError("source or backup changed during schema enablement")
        os.chmod(backup,0o400)
        os.chmod(output,0o600)
        return ReservationMigrationCopyResult(
            source_path=str(source),backup_path=str(backup),output_path=str(output),
            source_sha256=source_hash_before,backup_sha256=backup_hash,
            output_sha256=_sha256_file(output),schema_class="V2_CURRENT_EXACT",
            original_table_sha256=snapshot,new_reservation_tables_empty=True,
        )
    except Exception:
        if output_created:
            output.unlink(missing_ok=True)
        if backup_created and _sha256_file(backup) != source_hash_before:
            backup.unlink(missing_ok=True)
        raise
