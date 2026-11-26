"""Durable fail-closed idempotency journal for offline synthetic batches.

The journal prevents a restarted process from replaying against a fresh in-memory
portfolio ledger. A runtime identity mismatch requires operator reconciliation.
It does not make the ledger and settlement callback one atomic transaction.
"""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
from pathlib import Path
from typing import Any


class BatchJournalError(RuntimeError):
    """Batch journal is unsafe, inconsistent, or requires reconciliation."""


class _ClosingConnection(sqlite3.Connection):
    """Connection context manager that also closes the handle on exit."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


class SQLiteBatchJournal:
    """SQLite-backed batch state journal; trusted simulator use only."""

    def __init__(self, path: str | os.PathLike[str], *, runtime_id: str) -> None:
        if not isinstance(runtime_id, str) or not runtime_id.strip() or len(runtime_id) > 128:
            raise BatchJournalError("runtime_id is required")
        self.path = Path(path)
        if not self.path.is_absolute():
            raise BatchJournalError("journal path must be absolute")
        self.runtime_id = runtime_id
        self._lock = threading.RLock()
        self._validate_path()
        db = self._connect(initialize=True)
        db.close()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM metadata WHERE key='runtime_id'").fetchone()
            if row is None:
                db.execute("INSERT INTO metadata(key,value) VALUES('runtime_id',?)", (runtime_id,))
            elif row[0] != runtime_id:
                db.rollback()
                raise BatchJournalError("journal belongs to another runtime; reconcile before reuse")
            db.commit()

    def claim(self, batch_id: str, request_hash: str) -> list[dict[str, Any]] | None:
        """Claim a new batch; return stored result for an identical completed replay."""
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request_hash,status,result_json FROM batches WHERE batch_id=?",
                (batch_id,),
            ).fetchone()
            if row is not None:
                old_hash, status, result_json = row
                if old_hash != request_hash:
                    db.rollback()
                    raise BatchJournalError("batch_id reused with different request content")
                if status == "COMPLETE":
                    db.commit()
                    return json.loads(result_json)
                db.rollback()
                raise BatchJournalError("batch is unresolved; trusted reconciliation required")
            db.execute(
                "INSERT INTO batches(batch_id,request_hash,status,result_json) VALUES(?,?,?,NULL)",
                (batch_id, request_hash, "PROCESSING"),
            )
            db.commit()
            return None

    def complete(self, batch_id: str, request_hash: str, results: list[dict[str, Any]]) -> None:
        encoded = json.dumps(results, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request_hash,status FROM batches WHERE batch_id=?", (batch_id,)
            ).fetchone()
            if row != (request_hash, "PROCESSING"):
                db.rollback()
                raise BatchJournalError("batch completion does not match a processing claim")
            db.execute(
                "UPDATE batches SET status='COMPLETE',result_json=? WHERE batch_id=?",
                (encoded, batch_id),
            )
            db.commit()

    def _validate_path(self) -> None:
        parent = self.path.parent
        if not parent.exists() or parent.is_symlink() or not parent.is_dir():
            raise BatchJournalError("journal parent must be an existing real directory")
        current = parent
        while current != current.parent:
            if current.is_symlink():
                raise BatchJournalError("symlinked journal path component rejected")
            current = current.parent
        if self.path.exists() or self.path.is_symlink():
            info = self.path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BatchJournalError("journal must be a regular, non-symlink, single-link file")
            if os.name == "posix":
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                    raise BatchJournalError("journal must be current-user-owned and private")
        if os.name == "posix":
            info = parent.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise BatchJournalError("journal parent must be current-user-owned and private")

    def _connect(self, initialize: bool = False) -> sqlite3.Connection:
        self._validate_path()
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None, factory=_ClosingConnection)
        os.chmod(self.path, 0o600)
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA trusted_schema=OFF")
        if initialize:
            db.execute("CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute(
                "CREATE TABLE IF NOT EXISTS batches("
                "batch_id TEXT PRIMARY KEY,request_hash TEXT NOT NULL,"
                "status TEXT NOT NULL CHECK(status IN ('PROCESSING','COMPLETE')),"
                "result_json TEXT)"
            )
        return db
