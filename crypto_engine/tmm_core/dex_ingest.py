"""Offline parser for Pump.fun/PumpSwap trade rows.

This module normalizes already-retrieved records. It performs no network or
chain access, does not identify wallets, and never authorizes or submits orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from collections.abc import Mapping, Sequence
from typing import Any

UINT64_MAX = (1 << 64) - 1
INT64_MAX = (1 << 63) - 1
INT32_MAX = (1 << 31) - 1
SOL_MINT = "So11111111111111111111111111111111111111112"

FIELDS = frozenset({
    "block_time", "ts", "event_ts", "slot", "idx", "seq", "venue",
    "venue_code", "failed", "mint", "pool", "migration_pool", "wallet",
    "side", "sol_lamports", "token_amount", "quote_mint", "quote_amount",
    "r1", "r2", "r3", "pool_base_mint", "pool_quote_mint", "fee_lamports",
    "tip_lamports", "compute_units", "multi_hop", "error", "epoch",
})


class DexIngestError(ValueError):
    """Raised when a DEX record or batch violates the versioned schema."""


def _integer(value: Any, name: str, *, optional: bool = False,
             maximum: int = INT64_MAX) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DexIngestError(f"{name} must be an integer" + (" or null" if optional else ""))
    if value < 0 or value > maximum:
        raise DexIngestError(f"{name} is outside its allowed unsigned range")
    return value


def _text(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DexIngestError(f"{name} must be a non-empty string" + (" or null" if optional else ""))
    return value


def _boolean(value: Any, name: str, *, optional: bool = False) -> bool | None:
    if value is None and optional:
        return None
    if not isinstance(value, bool):
        raise DexIngestError(f"{name} must be boolean" + (" or null" if optional else ""))
    return value


def _reserve(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DexIngestError(f"{name} must be a finite number or null")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise DexIngestError(f"{name} must be finite and nonnegative")
    return result


def _utc_second(block_time: Any, ts: int) -> str:
    if isinstance(block_time, datetime):
        parsed = block_time
    elif isinstance(block_time, str) and block_time.strip():
        try:
            parsed = datetime.fromisoformat(block_time.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DexIngestError("block_time must be an ISO-8601 timestamp") from exc
    else:
        raise DexIngestError("block_time must be an ISO-8601 string or datetime")
    if parsed.tzinfo is None:
        # The source schema declares timestamp[us, tz=UTC].
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DexIngestError("block_time must be UTC")
    if int(parsed.timestamp()) != ts:
        raise DexIngestError("block_time and ts disagree")
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class DexTrade:
    block_time: str
    ts: int
    event_ts: int | None
    slot: int
    idx: int
    seq: int
    venue: str
    venue_code: str
    failed: bool
    mint: str | None
    pool: str | None
    migration_pool: bool | None
    side: str
    sol_lamports: int | None
    token_amount: int | None
    quote_mint: str | None
    quote_amount: int | None
    r1: float | None
    r2: float | None
    r3: float | None
    pool_base_mint: str | None
    pool_quote_mint: str | None
    fee_lamports: int
    tip_lamports: int | None
    compute_units: int | None
    multi_hop: bool | None
    error: str | None
    epoch: int
    token_identity_status: str
    reserve_precision_warning: bool


def parse_trade_record(row: Mapping[str, Any]) -> DexTrade:
    """Parse one exact-schema Pump.fun/PumpSwap record without side effects."""
    if not isinstance(row, Mapping):
        raise DexIngestError("trade row must be a mapping")
    keys = set(row)
    missing, extra = FIELDS - keys, keys - FIELDS
    if missing:
        raise DexIngestError("missing fields: " + ",".join(sorted(missing)))
    if extra:
        raise DexIngestError("unexpected fields: " + ",".join(sorted(extra)))

    ts = _integer(row["ts"], "ts")
    block_time = _utc_second(row["block_time"], ts)
    event_ts = _integer(row["event_ts"], "event_ts", optional=True)
    slot = _integer(row["slot"], "slot")
    idx = _integer(row["idx"], "idx", maximum=INT32_MAX)
    seq = _integer(row["seq"], "seq", maximum=INT32_MAX)
    epoch = _integer(row["epoch"], "epoch", maximum=INT32_MAX)
    venue = _text(row["venue"], "venue")
    venue_code = _text(row["venue_code"], "venue_code")
    if venue not in {"curve", "pumpswap"}:
        raise DexIngestError("venue must be curve or pumpswap")
    failed = _boolean(row["failed"], "failed")
    side = _text(row["side"], "side")
    if side not in {"buy", "sell"}:
        raise DexIngestError("side must be buy or sell")

    mint = _text(row["mint"], "mint", optional=True)
    pool = _text(row["pool"], "pool", optional=True)
    migration_pool = _boolean(row["migration_pool"], "migration_pool", optional=True)
    _text(row["wallet"], "wallet", optional=True)  # validated, deliberately not retained
    quote_mint = _text(row["quote_mint"], "quote_mint", optional=True)
    pool_base_mint = _text(row["pool_base_mint"], "pool_base_mint", optional=True)
    pool_quote_mint = _text(row["pool_quote_mint"], "pool_quote_mint", optional=True)
    multi_hop = _boolean(row["multi_hop"], "multi_hop", optional=True)
    error = _text(row["error"], "error", optional=True)

    sol_lamports = _integer(row["sol_lamports"], "sol_lamports", optional=True)
    token_amount = _integer(row["token_amount"], "token_amount", optional=True,
                            maximum=UINT64_MAX)
    quote_amount = _integer(row["quote_amount"], "quote_amount", optional=True,
                            maximum=UINT64_MAX)
    fee_lamports = _integer(row["fee_lamports"], "fee_lamports")
    tip_lamports = _integer(row["tip_lamports"], "tip_lamports", optional=True)
    compute_units = _integer(row["compute_units"], "compute_units", optional=True)
    r1, r2, r3 = (_reserve(row[name], name) for name in ("r1", "r2", "r3"))

    if failed:
        if error is None:
            raise DexIngestError("failed rows require an error")
        if any(value is not None for value in
               (sol_lamports, token_amount, quote_amount, r1, r2, r3)):
            raise DexIngestError("failed rows cannot contain landed trade amounts or reserves")
    else:
        if error is not None:
            raise DexIngestError("landed rows cannot contain an error")
        if token_amount is None or token_amount == 0:
            raise DexIngestError("landed rows require a positive token_amount")
        if quote_amount is None or quote_amount == 0:
            raise DexIngestError("landed rows require a positive quote_amount")
        if quote_mint is None:
            raise DexIngestError("landed rows require quote_mint")
        if quote_mint == SOL_MINT and sol_lamports is None:
            raise DexIngestError("SOL-quoted landed rows require sol_lamports")
        if quote_mint != SOL_MINT and sol_lamports is not None:
            raise DexIngestError("non-SOL-quoted rows cannot claim sol_lamports")

    # A missing mint on a multi-hop leg must be resolved only from a separate,
    # point-in-time pool-event join. This parser never guesses it.
    token_identity_status = (
        "UNRESOLVED_MULTI_HOP_MINT" if mint is None and multi_hop is True
        else "MINT_PRESENT" if mint is not None else "MINT_UNAVAILABLE"
    )

    return DexTrade(
        block_time=block_time, ts=ts, event_ts=event_ts, slot=slot,
        idx=idx, seq=seq, venue=venue, venue_code=venue_code, failed=failed,
        mint=mint, pool=pool, migration_pool=migration_pool, side=side,
        sol_lamports=sol_lamports, token_amount=token_amount,
        quote_mint=quote_mint, quote_amount=quote_amount, r1=r1, r2=r2, r3=r3,
        pool_base_mint=pool_base_mint, pool_quote_mint=pool_quote_mint,
        fee_lamports=fee_lamports, tip_lamports=tip_lamports,
        compute_units=compute_units, multi_hop=multi_hop, error=error,
        epoch=epoch, token_identity_status=token_identity_status,
        reserve_precision_warning=any(
            value is not None and abs(value) > (1 << 53) for value in (r1, r2, r3)
        ),
    )


def parse_trade_batch(rows: Sequence[Mapping[str, Any]]) -> list[DexTrade]:
    """Parse a batch and reject duplicate or out-of-order block execution keys."""
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise DexIngestError("rows must be a sequence of mappings")
    parsed = [parse_trade_record(row) for row in rows]
    previous = None
    seen = set()
    for trade in parsed:
        key = (trade.slot, trade.idx, trade.seq)
        if key in seen:
            raise DexIngestError("duplicate (slot, idx, seq) execution key")
        if previous is not None and key <= previous:
            raise DexIngestError("batch is not ordered by (slot, idx, seq)")
        seen.add(key)
        previous = key
    return parsed


def aggregate_transaction_costs(trades: Sequence[DexTrade]) -> list[dict[str, int]]:
    """Count transaction-level fees/tips once, not once per trade leg or row."""
    groups: dict[tuple[int, int], list[DexTrade]] = {}
    for trade in trades:
        groups.setdefault((trade.slot, trade.idx), []).append(trade)
    result = []
    for (slot, idx), rows in sorted(groups.items()):
        for field in ("fee_lamports", "tip_lamports", "compute_units"):
            values = {getattr(row, field) for row in rows if getattr(row, field) is not None}
            if len(values) > 1:
                raise DexIngestError(f"conflicting transaction-level {field}")
        result.append({
            "slot": slot,
            "idx": idx,
            "row_count": len(rows),
            "failed_rows": sum(row.failed for row in rows),
            "landed_rows": sum(not row.failed for row in rows),
            "fee_lamports": rows[0].fee_lamports,
            "tip_lamports": next((row.tip_lamports for row in rows if row.tip_lamports is not None), 0),
            "compute_units": next((row.compute_units for row in rows if row.compute_units is not None), 0),
        })
    return result
