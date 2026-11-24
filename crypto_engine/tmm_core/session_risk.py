"""Thread-safe, fail-closed session loss guard for shared spot portfolios.

This module authorizes target deltas; it does not submit or route orders. Persist
snapshots in the application's trusted durable store and restore before accepting
new strategy proposals. The hash-chained audit journal detects accidental edits;
it is not a substitute for externally anchored tamper-proof storage.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from decimal import Decimal

from .portfolio import PortfolioError, _d

D = Decimal
_ZERO_HASH = "0" * 64


class SessionRiskError(ValueError):
    """Raised when session risk state or a proposal is invalid."""


class SessionLossGuard:
    """Serializes risk decisions and reserves exits across concurrent proposals."""

    SNAPSHOT_VERSION = 1

    def __init__(self, *, session_id: str, opening_equity: object,
                 max_session_loss: object | None, started_at: int) -> None:
        if not isinstance(session_id, str) or not session_id.strip():
            raise SessionRiskError("session_id must be a non-empty string")
        try:
            equity = _d(opening_equity, "opening_equity")
            limit = None if max_session_loss is None else _d(max_session_loss, "max_session_loss")
        except PortfolioError as exc:
            raise SessionRiskError(str(exc)) from exc
        if equity <= 0:
            raise SessionRiskError("opening_equity must be positive")
        if limit is not None and not D("0") < limit < D("1"):
            raise SessionRiskError("max_session_loss must be strictly between zero and one")
        if isinstance(started_at, bool) or not isinstance(started_at, int) or started_at < 0:
            raise SessionRiskError("started_at must be a nonnegative UTC epoch second")
        self._lock = threading.RLock()
        self.session_id = session_id
        self.opening_equity = equity
        self.max_session_loss = limit
        self.started_at = started_at
        self.last_timestamp = started_at
        self.last_equity = equity
        self.halted = False
        self.halt_timestamp: int | None = None
        self.halt_reason: str | None = None
        self._reserved_sells: dict[str, Decimal] = {}
        self._events: list[dict[str, object]] = []
        self._head_hash = _ZERO_HASH
        self._append("SESSION_STARTED", started_at, {
            "opening_equity": str(equity),
            "max_session_loss": None if limit is None else str(limit),
        })

    @property
    def is_halted(self) -> bool:
        with self._lock:
            return self.halted

    def _timestamp(self, timestamp: int) -> None:
        if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < self.last_timestamp:
            raise SessionRiskError("timestamps must be nonnegative and monotonically nondecreasing")

    def _append(self, event_type: str, timestamp: int, payload: dict[str, object]) -> None:
        body = {
            "sequence": len(self._events) + 1,
            "session_id": self.session_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "payload": payload,
            "previous_hash": self._head_hash,
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        self._events.append({**body, "event_hash": digest})
        self._head_hash = digest

    def _latch(self, *, timestamp: int, reason: str, measured_loss: Decimal | None = None) -> None:
        if self.halted:
            return
        self.halted = True
        self.halt_timestamp = timestamp
        self.halt_reason = reason
        payload: dict[str, object] = {"reason": reason}
        if measured_loss is not None:
            payload["measured_loss_fraction"] = str(measured_loss)
        self._append("SESSION_HALT", timestamp, payload)

    def observe_equity(self, *, equity: object, timestamp: int) -> dict[str, object]:
        """Update marked account equity and latch at the configured loss threshold."""
        with self._lock:
            self._timestamp(timestamp)
            try:
                marked = _d(equity, "equity")
            except PortfolioError as exc:
                raise SessionRiskError(str(exc)) from exc
            if marked < 0:
                raise SessionRiskError("equity cannot be negative")
            loss = max(D("0"), (self.opening_equity - marked) / self.opening_equity)
            if not self.halted and self.max_session_loss is not None and loss >= self.max_session_loss:
                self._latch(timestamp=timestamp, reason="SESSION_LOSS_LIMIT", measured_loss=loss)
            self.last_equity = marked
            self.last_timestamp = timestamp
            self._append("EQUITY_OBSERVED", timestamp, {
                "equity": str(marked), "loss_fraction": str(loss), "halted": self.halted,
            })
            return {"halted": self.halted, "loss_fraction": loss,
                    "halt_timestamp": self.halt_timestamp, "halt_reason": self.halt_reason}

    def force_halt(self, *, timestamp: int, reason: str) -> None:
        """Latch another deterministic risk stop, such as portfolio drawdown."""
        with self._lock:
            self._timestamp(timestamp)
            if not isinstance(reason, str) or not reason.strip():
                raise SessionRiskError("halt reason must be a non-empty string")
            if self.halted:
                self._append("HALT_REASSERTED", timestamp, {"reason": reason})
            else:
                self._latch(timestamp=timestamp, reason=reason)
            self.last_timestamp = timestamp

    def authorize_proposals(self, *, proposals: Mapping[str, object],
                            holdings: Mapping[str, object], timestamp: int) -> dict[str, Decimal]:
        """Authorize signed deltas, reserve exits, and prevent shorts/double sells.

        Positive deltas are BUY exposure; negative deltas are SELL exits. After
        any latched stop all BUYs are rejected. SELLs are capped at actual
        inventory less outstanding concurrent sell reservations.
        """
        with self._lock:
            self._timestamp(timestamp)
            if not isinstance(proposals, Mapping) or not isinstance(holdings, Mapping):
                raise SessionRiskError("proposals and holdings must be mappings")
            if not proposals or set(proposals) != set(holdings):
                raise SessionRiskError("proposal and holding market sets must match and be non-empty")
            if any(not isinstance(key, str) or not key for key in proposals):
                raise SessionRiskError("market IDs must be non-empty strings")
            permitted: dict[str, Decimal] = {}
            rejected: dict[str, str] = {}
            normalized_holdings: dict[str, Decimal] = {}
            for market_id in sorted(proposals):
                if not isinstance(market_id, str) or not market_id:
                    raise SessionRiskError("market IDs must be non-empty strings")
                try:
                    delta = _d(proposals[market_id], f"{market_id}.proposal")
                    held = _d(holdings[market_id], f"{market_id}.holding")
                except PortfolioError as exc:
                    raise SessionRiskError(str(exc)) from exc
                if held < 0:
                    raise SessionRiskError(f"{market_id}: negative holdings violate spot long-only policy")
                normalized_holdings[market_id] = held
                if delta > 0 and self.halted:
                    permitted[market_id] = D("0")
                    rejected[market_id] = "SESSION_RISK_HALT_BLOCKS_BUY"
                elif delta < 0:
                    reserved = self._reserved_sells.get(market_id, D("0"))
                    available = max(D("0"), held - reserved)
                    allowed = min(-delta, available)
                    permitted[market_id] = -allowed
                    if allowed < -delta:
                        rejected[market_id] = "SELL_CAPPED_TO_UNRESERVED_HELD_QUANTITY"
                    if allowed:
                        self._reserved_sells[market_id] = reserved + allowed
                else:
                    permitted[market_id] = delta
            self.last_timestamp = timestamp
            self._append("PROPOSALS_AUTHORIZED", timestamp, {
                "halted": self.halted,
                "holdings": {k: str(v) for k, v in normalized_holdings.items()},
                "reserved_sells": {k: str(v) for k, v in sorted(self._reserved_sells.items())},
                "proposed_deltas": {k: str(_d(proposals[k], f"{k}.proposal")) for k in sorted(proposals)},
                "permitted_deltas": {k: str(v) for k, v in permitted.items()},
                "rejections": rejected,
            })
            return permitted

    def settle_sell(self, *, market_id: str, authorized_quantity: object,
                    filled_quantity: object, timestamp: int) -> None:
        """Release an exit reservation after fill or rejection is definitively known."""
        with self._lock:
            self._timestamp(timestamp)
            if not isinstance(market_id, str) or not market_id:
                raise SessionRiskError("market_id must be a non-empty string")
            try:
                authorized = _d(authorized_quantity, "authorized_quantity")
                filled = _d(filled_quantity, "filled_quantity")
            except PortfolioError as exc:
                raise SessionRiskError(str(exc)) from exc
            reserved = self._reserved_sells.get(market_id, D("0"))
            if authorized <= 0 or filled < 0 or filled > authorized or authorized > reserved:
                raise SessionRiskError("sell settlement exceeds a valid outstanding reservation")
            remaining = reserved - authorized
            if remaining:
                self._reserved_sells[market_id] = remaining
            else:
                self._reserved_sells.pop(market_id, None)
            self.last_timestamp = timestamp
            self._append("SELL_SETTLED", timestamp, {
                "market_id": market_id, "authorized_quantity": str(authorized),
                "filled_quantity": str(filled), "released_quantity": str(authorized - filled),
                "remaining_reserved": str(remaining),
            })

    def reset(self, *, new_session_id: str, opening_equity: object, timestamp: int,
              actor: str, reason: str, approval_ref: str) -> None:
        """Explicitly start a new session; reset requires audit metadata and no pending exits."""
        with self._lock:
            self._timestamp(timestamp)
            if not self.halted:
                raise SessionRiskError("session reset is allowed only after a latched stop")
            if any(value > 0 for value in self._reserved_sells.values()):
                raise SessionRiskError("cannot reset while sell reservations are unresolved")
            for field, value in (("new_session_id", new_session_id), ("actor", actor),
                                 ("reason", reason), ("approval_ref", approval_ref)):
                if not isinstance(value, str) or not value.strip():
                    raise SessionRiskError(f"{field} is required for an audited reset")
            try:
                equity = _d(opening_equity, "opening_equity")
            except PortfolioError as exc:
                raise SessionRiskError(str(exc)) from exc
            if equity <= 0:
                raise SessionRiskError("new opening_equity must be positive")
            if new_session_id == self.session_id:
                raise SessionRiskError("new session_id must differ from the halted session")
            old_session = self.session_id
            self.session_id = new_session_id
            self.opening_equity = equity
            self.started_at = timestamp
            self.last_timestamp = timestamp
            self.last_equity = equity
            self.halted = False
            self.halt_timestamp = None
            self.halt_reason = None
            self._append("SESSION_RESET", timestamp, {
                "previous_session_id": old_session, "opening_equity": str(equity),
                "actor": actor, "reason": reason, "approval_ref": approval_ref,
            })

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-serializable recovery snapshot."""
        with self._lock:
            state = {
                "session_id": self.session_id, "opening_equity": str(self.opening_equity),
                "max_session_loss": None if self.max_session_loss is None else str(self.max_session_loss),
                "started_at": self.started_at, "last_timestamp": self.last_timestamp,
                "last_equity": str(self.last_equity), "halted": self.halted,
                "halt_timestamp": self.halt_timestamp, "halt_reason": self.halt_reason,
                "reserved_sells": {k: str(v) for k, v in sorted(self._reserved_sells.items())},
                "head_hash": self._head_hash,
            }
            return {"snapshot_version": self.SNAPSHOT_VERSION, "state": state,
                    "events": [dict(event) for event in self._events]}

    @classmethod
    def restore(cls, snapshot: Mapping[str, object]) -> "SessionLossGuard":
        """Restore only a structurally valid snapshot with an intact event hash chain."""
        if not isinstance(snapshot, Mapping) or snapshot.get("snapshot_version") != cls.SNAPSHOT_VERSION:
            raise SessionRiskError("unsupported or malformed session risk snapshot")
        state = snapshot.get("state")
        events = snapshot.get("events")
        if not isinstance(state, Mapping) or not isinstance(events, list):
            raise SessionRiskError("snapshot state/events are missing")
        try:
            guard = cls(session_id=state["session_id"], opening_equity=state["opening_equity"],
                        max_session_loss=state["max_session_loss"], started_at=state["started_at"])
            expected_previous = _ZERO_HASH
            for index, event in enumerate(events, start=1):
                if not isinstance(event, Mapping):
                    raise SessionRiskError("audit event is malformed")
                body = {k: event[k] for k in (
                    "sequence", "session_id", "event_type", "timestamp", "payload", "previous_hash")}
                if body["sequence"] != index or body["previous_hash"] != expected_previous:
                    raise SessionRiskError("audit event sequence/hash linkage is invalid")
                encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
                digest = hashlib.sha256(encoded).hexdigest()
                if event.get("event_hash") != digest:
                    raise SessionRiskError("audit event hash verification failed")
                expected_previous = digest
                guard._events.append(dict(event))
            guard._head_hash = expected_previous
            guard.last_timestamp = state["last_timestamp"]
            guard.last_equity = _d(state["last_equity"], "last_equity")
            guard.halted = state["halted"]
            guard.halt_timestamp = state["halt_timestamp"]
            guard.halt_reason = state["halt_reason"]
            reservations = state["reserved_sells"]
            if not isinstance(reservations, Mapping):
                raise SessionRiskError("snapshot sell reservations are malformed")
            guard._reserved_sells = {k: _d(v, f"{k}.reserved_sell") for k, v in reservations.items()}
            if any(not isinstance(k, str) or not k or v <= 0 for k, v in guard._reserved_sells.items()):
                raise SessionRiskError("snapshot sell reservations are invalid")
            if (not isinstance(guard.halted, bool) or
                    (guard.halted and (guard.halt_timestamp is None or not guard.halt_reason)) or
                    (not guard.halted and (guard.halt_timestamp is not None or guard.halt_reason is not None))):
                raise SessionRiskError("snapshot halt state is inconsistent")
            if state["head_hash"] != guard._head_hash:
                raise SessionRiskError("snapshot head hash does not match audit journal")

            # Reconstruct security-critical state from the verified journal so a
            # modified snapshot flag cannot silently clear a recorded halt.
            if not guard._events or guard._events[0]["event_type"] != "SESSION_STARTED":
                raise SessionRiskError("audit journal has no valid session-start event")
            first = guard._events[0]
            first_payload = first["payload"]
            if not isinstance(first_payload, Mapping):
                raise SessionRiskError("session-start payload is malformed")
            active_session = first["session_id"]
            derived_opening = _d(first_payload["opening_equity"], "journal.opening_equity")
            derived_limit_raw = first_payload["max_session_loss"]
            derived_limit = None if derived_limit_raw is None else _d(derived_limit_raw, "journal.max_session_loss")
            derived_started = first["timestamp"]
            derived_halted = False
            derived_halt_timestamp = None
            derived_halt_reason = None
            derived_last_equity = derived_opening
            derived_reserved: dict[str, Decimal] = {}
            previous_timestamp = derived_started
            for event in guard._events[1:]:
                event_type = event["event_type"]
                event_timestamp = event["timestamp"]
                payload = event["payload"]
                if (isinstance(event_timestamp, bool) or not isinstance(event_timestamp, int)
                        or event_timestamp < previous_timestamp or not isinstance(payload, Mapping)):
                    raise SessionRiskError("audit event timestamp/payload is invalid")
                previous_timestamp = event_timestamp
                if event_type == "SESSION_RESET":
                    if (not derived_halted or payload.get("previous_session_id") != active_session
                            or event["session_id"] == active_session):
                        raise SessionRiskError("session reset event is inconsistent with halt state")
                    active_session = event["session_id"]
                    derived_opening = _d(payload["opening_equity"], "journal.reset_equity")
                    derived_started = event_timestamp
                    derived_last_equity = derived_opening
                    derived_halted = False
                    derived_halt_timestamp = None
                    derived_halt_reason = None
                    derived_reserved = {}
                    continue
                if event["session_id"] != active_session:
                    raise SessionRiskError("audit event session identity is inconsistent")
                if event_type == "SESSION_HALT":
                    if derived_halted:
                        raise SessionRiskError("duplicate session halt event")
                    derived_halted = True
                    derived_halt_timestamp = event_timestamp
                    derived_halt_reason = payload.get("reason")
                elif event_type == "EQUITY_OBSERVED":
                    derived_last_equity = _d(payload["equity"], "journal.equity")
                elif event_type == "PROPOSALS_AUTHORIZED":
                    raw_reserved = payload.get("reserved_sells")
                    if not isinstance(raw_reserved, Mapping):
                        raise SessionRiskError("proposal audit reservation data is malformed")
                    derived_reserved = {k: _d(v, f"journal.reserved.{k}") for k, v in raw_reserved.items()}
                elif event_type == "SELL_SETTLED":
                    market = payload["market_id"]
                    remaining = _d(payload["remaining_reserved"], "journal.remaining_reserved")
                    if remaining > 0:
                        derived_reserved[market] = remaining
                    else:
                        derived_reserved.pop(market, None)
                elif event_type not in ("PROPOSALS_AUTHORIZED", "SELL_SETTLED", "HALT_REASSERTED"):
                    raise SessionRiskError("unknown audit event type")
            if (active_session != state["session_id"]
                    or derived_opening != _d(state["opening_equity"], "snapshot.opening_equity")
                    or derived_limit != (None if state["max_session_loss"] is None
                                         else _d(state["max_session_loss"], "snapshot.max_session_loss"))
                    or derived_started != state["started_at"]
                    or previous_timestamp != state["last_timestamp"]
                    or derived_last_equity != guard.last_equity
                    or derived_halted != guard.halted
                    or derived_halt_timestamp != guard.halt_timestamp
                    or derived_halt_reason != guard.halt_reason
                    or derived_reserved != guard._reserved_sells):
                raise SessionRiskError("snapshot state does not match verified audit journal")
            if guard.last_timestamp < guard.started_at or guard.last_equity < 0:
                raise SessionRiskError("snapshot timestamp/equity is invalid")
            return guard
        except (KeyError, TypeError, ValueError, PortfolioError) as exc:
            if isinstance(exc, SessionRiskError):
                raise
            raise SessionRiskError("snapshot fields are invalid") from exc
