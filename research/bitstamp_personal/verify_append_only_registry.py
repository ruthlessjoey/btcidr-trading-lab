"""Verify trial ledger growth against a pinned genesis and Git base.

The genesis file has a pinned Git blob SHA-1. The current ledger must preserve
that exact root and the complete base-commit byte prefix; only complete
LF-delimited semantic events may be appended.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from experiment_registry import TrialRegistryError, parse_trial_registry

MAX_REGISTRY_BYTES = 1024 * 1024
GENESIS_GIT_BLOB_SHA1 = "10dbeb52941c08cda1f7b1d724b543b41dd6fdc2"
GENESIS_SHA256 = "d461f624d8b4af01ec262952574d0e62457154e89614eb3364b3444a52d7ce1d"
EXPECTED_MARKETS = (
    "btcusd", "ethusd", "xrpusd", "dogeusd", "shibusd", "pepeusd", "solusd",
)
EXPECTED_STRATEGIES = (
    "SMA20_50_LONG_ONLY", "RSI14_MEAN_REVERSION_LONG_ONLY",
)
EXPECTED_PREREGISTRATION = "BITSTAMP_PERSONAL_SPOT_RESEARCH_2026-11-27_V2_5FOLD"


class AppendOnlyRegistryError(ValueError):
    """Raised when registry history is rewritten, truncated or malformed."""


def git_blob_sha1(raw: bytes) -> str:
    """Return Git's SHA-1 object ID for a blob's exact bytes."""
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def verify_append_only_registry(
    genesis_bytes: bytes,
    base_bytes: bytes | None = None,
    head_bytes: bytes | None = None,
    *,
    expected_market_symbols=EXPECTED_MARKETS,
    expected_strategies=EXPECTED_STRATEGIES,
    preregistration_id=EXPECTED_PREREGISTRATION,
) -> dict[str, Any]:
    """Verify the pinned genesis root, base prefix and head-ledger semantics.

    The two-argument form is retained for the previous verifier API:
    (base_bytes, head_bytes). It loads the committed, SHA-1-pinned genesis
    snapshot, so older semantic regression tests remain valid.
    """
    if head_bytes is None:
        if base_bytes is None:
            raise AppendOnlyRegistryError("base and head registry values are required")
        base_bytes, head_bytes = genesis_bytes, base_bytes
        try:
            genesis_bytes = Path(__file__).with_name(
                "experiment_registry.genesis.jsonl"
            ).read_bytes()
        except OSError as exc:
            raise AppendOnlyRegistryError("pinned genesis snapshot is unavailable") from exc
    if base_bytes is None:
        raise AppendOnlyRegistryError("base registry value is required")
    if any(not isinstance(value, bytes) for value in (genesis_bytes, base_bytes, head_bytes)):
        raise AppendOnlyRegistryError("genesis, base and head registry values must be bytes")
    if any(len(value) > MAX_REGISTRY_BYTES for value in (genesis_bytes, base_bytes, head_bytes)):
        raise AppendOnlyRegistryError("trial registry exceeds the 1 MiB bound")
    if not genesis_bytes or not head_bytes:
        raise AppendOnlyRegistryError("genesis and head registries must be non-empty")
    actual_genesis_sha1 = git_blob_sha1(genesis_bytes)
    if actual_genesis_sha1 != GENESIS_GIT_BLOB_SHA1:
        raise AppendOnlyRegistryError(
            "genesis snapshot does not match the pinned Git blob SHA-1"
        )
    actual_genesis_sha256 = hashlib.sha256(genesis_bytes).hexdigest()
    if actual_genesis_sha256 != GENESIS_SHA256:
        raise AppendOnlyRegistryError(
            "genesis snapshot does not match the pinned SHA-256"
        )
    if not genesis_bytes.endswith(b"\n"):
        raise AppendOnlyRegistryError("genesis registry must end at a complete LF-delimited event")
    if base_bytes and not base_bytes.endswith(b"\n"):
        raise AppendOnlyRegistryError(
            "base registry must end at a complete LF-delimited event"
        )
    if not head_bytes.endswith(b"\n"):
        raise AppendOnlyRegistryError(
            "head registry must end at a complete LF-delimited event"
        )
    if any(b"\r" in value for value in (genesis_bytes, base_bytes, head_bytes)):
        raise AppendOnlyRegistryError("trial registry must use LF-only line endings")
    if base_bytes and not base_bytes.startswith(genesis_bytes):
        raise AppendOnlyRegistryError(
            "base registry does not preserve the pinned genesis prefix"
        )
    if not head_bytes.startswith(genesis_bytes):
        raise AppendOnlyRegistryError(
            "head registry history rewrote, reordered or truncated the pinned genesis prefix"
        )
    if not head_bytes.startswith(base_bytes):
        raise AppendOnlyRegistryError(
            "trial registry history was rewritten, reordered or truncated; "
            "head must preserve the exact base byte prefix"
        )

    appended = head_bytes[len(base_bytes):]
    if appended:
        try:
            appended_text = appended.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise AppendOnlyRegistryError("appended registry events must be UTF-8") from exc
        new_lines = appended_text.splitlines()
        if not new_lines or any(not line.strip() for line in new_lines):
            raise AppendOnlyRegistryError("appended registry segment contains an empty event")
        appended_events = len(new_lines)
    else:
        appended_events = 0

    try:
        parsed = parse_trial_registry(
            head_bytes,
            expected_market_symbols=expected_market_symbols,
            expected_strategies=expected_strategies,
            preregistration_id=preregistration_id,
        )
    except (TrialRegistryError, RecursionError, ValueError) as exc:
        raise AppendOnlyRegistryError(
            f"head trial registry semantic validation failed: {exc}"
        ) from exc

    return {
        "status": "APPEND_ONLY_VERIFIED",
        "genesis_git_blob_sha1": actual_genesis_sha1,
        "genesis_sha256": actual_genesis_sha256,
        "base_sha256": hashlib.sha256(base_bytes).hexdigest(),
        "head_sha256": hashlib.sha256(head_bytes).hexdigest(),
        "base_bytes": len(base_bytes),
        "head_bytes": len(head_bytes),
        "appended_bytes": len(appended),
        "appended_events": appended_events,
        "registered_trial_count": parsed["registered_trial_count"],
        "event_count": parsed["event_count"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("genesis_file", type=Path)
    parser.add_argument("base_file", type=Path)
    parser.add_argument("head_file", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_append_only_registry(
            args.genesis_file.read_bytes(),
            args.base_file.read_bytes(),
            args.head_file.read_bytes(),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (AppendOnlyRegistryError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
