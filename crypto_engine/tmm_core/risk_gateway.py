"""Trusted account boundary for multi-market paper-risk proposals.

This service is deliberately offline. It accepts proposals, reads inventory from
an injected authoritative ledger, persists the resulting risk journal, and
requires an independent audit anchor before returning an authorization.
Strategy agents must receive this facade only, never the guard, ledger, store,
reset verifier, or broker/order interfaces.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from .session_risk import SessionLossGuard, SessionRiskError


class RiskGatewayError(RuntimeError):
    """Fail-closed account-risk gateway error."""


class InventoryLedger(Protocol):
    def snapshot_holdings(self, account_id: str) -> Mapping[str, object]:
        """Return authoritative base-asset quantities keyed by stable market ID."""

    def snapshot_equity(self, account_id: str) -> object:
        """Return authoritative account equity in the configured account currency."""


class ResetAuthorizer(Protocol):
    def verify_reset(self, request: Mapping[str, str]) -> bool:
        """Verify owner authorization outside the strategy-agent trust boundary."""


class AuditAnchor(Protocol):
    def verify(self, account_id: str, head_hash: str) -> bool:
        """Verify the persisted journal head against an independently held anchor."""

    def publish(self, account_id: str, head_hash: str) -> bool:
        """Durably publish the new journal head outside the local writable boundary."""


class RiskStateStore(Protocol):
    def load(self, account_id: str) -> Mapping[str, object] | None: ...
    def save_atomic(self, account_id: str, snapshot: Mapping[str, object]) -> None: ...


class SQLiteRiskStateStore:
    """Local transactional snapshot store; external anchoring remains mandatory."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS risk_state ("
                "account_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, head_hash TEXT NOT NULL)"
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise RiskGatewayError("cannot restrict risk-state database permissions") from exc

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def load(self, account_id: str) -> Mapping[str, object] | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT snapshot_json FROM risk_state WHERE account_id=?", (account_id,)
            ).fetchone()
            if row is None:
                return None
            try:
                value = json.loads(row[0])
            except (TypeError, ValueError) as exc:
                raise RiskGatewayError("stored risk snapshot is malformed") from exc
            if not isinstance(value, dict):
                raise RiskGatewayError("stored risk snapshot must be an object")
            return value

    def save_atomic(self, account_id: str, snapshot: Mapping[str, object]) -> None:
        if not account_id:
            raise RiskGatewayError("account_id is required")
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        state = snapshot.get("state")
        head_hash = state.get("head_hash") if isinstance(state, Mapping) else None
        if not isinstance(head_hash, str) or len(head_hash) != 64:
            raise RiskGatewayError("snapshot has no valid journal head")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO risk_state(account_id,snapshot_json,head_hash) VALUES(?,?,?) "
                "ON CONFLICT(account_id) DO UPDATE SET "
                "snapshot_json=excluded.snapshot_json, head_hash=excluded.head_hash",
                (account_id, encoded, head_hash),
            )
            db.execute("COMMIT")
        try:
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise RiskGatewayError("cannot preserve restrictive risk-state permissions") from exc


class RiskGateway:
    """Only proposal/reset facade intended to be exposed to strategy agents."""

    def __init__(self, *, account_id: str, guard: SessionLossGuard,
                 ledger: InventoryLedger, store: RiskStateStore,
                 anchor: AuditAnchor, reset_authorizer: ResetAuthorizer) -> None:
        if not isinstance(account_id, str) or not account_id.strip():
            raise RiskGatewayError("account_id is required")
        self._account_id = account_id
        self._guard = guard
        self._ledger = ledger
        self._store = store
        self._anchor = anchor
        self._reset_authorizer = reset_authorizer
        self._lock = threading.RLock()
        self._failed = False

    @classmethod
    def create_new(cls, *, account_id: str, guard: SessionLossGuard,
                   ledger: InventoryLedger, store: RiskStateStore,
                   anchor: AuditAnchor, reset_authorizer: ResetAuthorizer) -> "RiskGateway":
        gateway = cls(account_id=account_id, guard=guard, ledger=ledger, store=store,
                      anchor=anchor, reset_authorizer=reset_authorizer)
        gateway._commit()
        return gateway

    @classmethod
    def restore(cls, *, account_id: str, ledger: InventoryLedger,
                store: RiskStateStore, anchor: AuditAnchor,
                reset_authorizer: ResetAuthorizer) -> "RiskGateway":
        snapshot = store.load(account_id)
        if snapshot is None:
            raise RiskGatewayError("no persisted risk state; account startup is refused")
        state = snapshot.get("state")
        head_hash = state.get("head_hash") if isinstance(state, Mapping) else None
        if not isinstance(head_hash, str) or not anchor.verify(account_id, head_hash):
            raise RiskGatewayError("external audit anchor verification failed; startup refused")
        try:
            guard = SessionLossGuard.restore(snapshot)
        except SessionRiskError as exc:
            raise RiskGatewayError("risk journal recovery failed; startup refused") from exc
        return cls(account_id=account_id, guard=guard, ledger=ledger, store=store,
                   anchor=anchor, reset_authorizer=reset_authorizer)

    def _require_healthy(self) -> None:
        if self._failed:
            raise RiskGatewayError("risk gateway is fail-closed after a persistence/anchor failure")

    def _commit(self) -> None:
        snapshot = self._guard.snapshot()
        state = snapshot.get("state")
        head_hash = state.get("head_hash") if isinstance(state, Mapping) else None
        try:
            self._store.save_atomic(self._account_id, snapshot)
            if not isinstance(head_hash, str) or not self._anchor.publish(self._account_id, head_hash):
                raise RiskGatewayError("external audit anchor publish failed")
        except Exception as exc:
            self._failed = True
            if isinstance(exc, RiskGatewayError):
                raise
            raise RiskGatewayError("risk-state persistence failed; gateway locked") from exc

    def propose(self, *, proposals: Mapping[str, object], timestamp: int) -> dict[str, object]:
        """Authorize proposals using ledger-owned holdings; caller cannot supply inventory."""
        with self._lock:
            self._require_healthy()
            try:
                equity = self._ledger.snapshot_equity(self._account_id)
                self._guard.observe_equity(equity=equity, timestamp=timestamp)
                holdings = self._ledger.snapshot_holdings(self._account_id)
                permitted = self._guard.authorize_proposals(
                    proposals=proposals, holdings=holdings, timestamp=timestamp
                )
                self._commit()
                return {"account_id": self._account_id, "permitted_deltas": permitted,
                        "risk_halted": self._guard.is_halted}
            except Exception:
                # A proposal error is not itself a storage failure. _commit marks
                # the gateway unhealthy when persistence or anchoring fails.
                raise

    def settle_sell(self, *, market_id: str, authorized_quantity: object,
                    filled_quantity: object, timestamp: int) -> None:
        with self._lock:
            self._require_healthy()
            self._guard.settle_sell(market_id=market_id, authorized_quantity=authorized_quantity,
                                    filled_quantity=filled_quantity, timestamp=timestamp)
            self._commit()

    def reset(self, *, new_session_id: str, opening_equity: object, timestamp: int,
              actor: str, reason: str, approval_ref: str) -> None:
        with self._lock:
            self._require_healthy()
            request = {"account_id": self._account_id, "current_session_id": self._guard.session_id,
                       "new_session_id": new_session_id, "actor": actor, "reason": reason,
                       "approval_ref": approval_ref}
            try:
                approved = self._reset_authorizer.verify_reset(request)
            except Exception as exc:
                raise RiskGatewayError("reset authorization service failed; reset refused") from exc
            if approved is not True:
                raise RiskGatewayError("owner reset authorization was not verified")
            self._guard.reset(new_session_id=new_session_id, opening_equity=opening_equity,
                              timestamp=timestamp, actor=actor, reason=reason,
                              approval_ref=approval_ref)
            self._commit()

    @property
    def is_halted(self) -> bool:
        with self._lock:
            self._require_healthy()
            return self._guard.is_halted
