"""Verify a hash-chained append-only experiment trial registry."""
from __future__ import annotations
import hashlib
import json
import re
from collections.abc import Mapping

_ZERO = "0" * 64
_HASH = re.compile(r"^[0-9a-f]{64}$")
_KEYS = {"seq", "event", "payload", "previous_hash", "record_hash"}


class TrialRegistryError(ValueError):
    """Invalid or tampered trial registry."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TrialRegistryError("duplicate JSON object key")
        result[key] = value
    return result


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise TrialRegistryError("registry event is not canonical JSON") from exc


def verify_trial_registry(raw: bytes) -> dict:
    """Verify exact JSONL bytes and count all started trials, including failures."""
    if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\n"):
        raise TrialRegistryError("registry must be non-empty UTF-8 JSONL ending with newline")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TrialRegistryError("registry must be strict UTF-8") from exc
    previous = _ZERO
    started = {}
    trial_strategies = {}
    finished = set()
    counts = {}
    event_count = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            raise TrialRegistryError(f"blank registry line at {line_number}")
        try:
            record = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise TrialRegistryError(f"invalid JSON at line {line_number}") from exc
        if not isinstance(record, Mapping) or set(record) != _KEYS:
            raise TrialRegistryError(f"record {line_number} schema is invalid")
        seq = record["seq"]
        if isinstance(seq, bool) or not isinstance(seq, int) or seq != event_count + 1:
            raise TrialRegistryError("registry sequence must be contiguous from 1")
        if record["previous_hash"] != previous:
            raise TrialRegistryError(f"record {line_number} previous hash mismatch")
        digest = record["record_hash"]
        if not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise TrialRegistryError(f"record {line_number} hash is invalid")
        core = {key: record[key] for key in ("seq", "event", "payload", "previous_hash")}
        if hashlib.sha256(_canonical(core)).hexdigest() != digest:
            raise TrialRegistryError(f"record {line_number} hash verification failed")
        payload = record["payload"]
        if not isinstance(payload, Mapping):
            raise TrialRegistryError(f"record {line_number} payload must be an object")
        if record["event"] == "TRIAL_STARTED":
            if set(payload) != {"trial_id", "research_family", "strategy_id", "config_sha256"}:
                raise TrialRegistryError("TRIAL_STARTED payload schema is invalid")
            trial_id, family, strategy, config_hash = (
                payload["trial_id"], payload["research_family"],
                payload["strategy_id"], payload["config_sha256"],
            )
            for value, field in ((trial_id, "trial_id"), (family, "research_family"), (strategy, "strategy_id")):
                if not isinstance(value, str) or not value.strip() or len(value) > 128:
                    raise TrialRegistryError(f"{field} must be a bounded non-empty string")
            if not isinstance(config_hash, str) or not _HASH.fullmatch(config_hash):
                raise TrialRegistryError("config_sha256 must be lowercase SHA-256")
            if trial_id in started:
                raise TrialRegistryError("trial_id may only be started once")
            started[trial_id] = family
            trial_strategies.setdefault(family, []).append(strategy)
            counts[family] = counts.get(family, 0) + 1
        elif record["event"] == "TRIAL_FINISHED":
            if set(payload) != {"trial_id", "status", "result_sha256"}:
                raise TrialRegistryError("TRIAL_FINISHED payload schema is invalid")
            trial_id, status, result_hash = payload["trial_id"], payload["status"], payload["result_sha256"]
            if not isinstance(trial_id, str) or trial_id not in started:
                raise TrialRegistryError("TRIAL_FINISHED references unknown trial")
            if trial_id in finished:
                raise TrialRegistryError("trial may only be finished once")
            if not isinstance(status, str) or status not in {"COMPLETED", "FAILED", "ABANDONED"}:
                raise TrialRegistryError("trial finish status is invalid")
            if result_hash is not None and (not isinstance(result_hash, str) or not _HASH.fullmatch(result_hash)):
                raise TrialRegistryError("result_sha256 must be null or lowercase SHA-256")
            if status == "COMPLETED" and result_hash is None:
                raise TrialRegistryError("completed trial requires result SHA-256")
            finished.add(trial_id)
        else:
            raise TrialRegistryError("unknown trial registry event")
        previous = digest
        event_count += 1
    return {
        "registry_sha256": hashlib.sha256(raw).hexdigest(),
        "event_count": event_count,
        "trial_counts": counts,
        "trial_strategies": trial_strategies,
        "final_chain_hash": previous,
    }
