"""Pure preflight validation for synthetic SELL reservation allocations.

This module is not an authorization boundary or a durable ledger. A trusted
settlement transaction must reload reservations, revalidate versions and
remaining quantities, persist allocations, and update reservation consumption
atomically. Never accept reservation state supplied by a strategy agent.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Mapping, Sequence


class ReservationAllocationError(ValueError):
    """Invalid or inconsistent SELL reservation allocation input."""


def _quantity(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ReservationAllocationError(f"{field} must be a finite decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReservationAllocationError(
            f"{field} must be a finite decimal"
        ) from exc
    if not number.is_finite():
        raise ReservationAllocationError(f"{field} must be finite")
    parts = number.as_tuple()
    if len(parts.digits) > 38 or parts.exponent < -18 or number.adjusted() > 38:
        raise ReservationAllocationError(f"{field} exceeds supported decimal precision")
    return number


def _required_text(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReservationAllocationError(f"{key} is required")
    return value


def validate_sell_allocations(
    *,
    account_id: str,
    fills: Sequence[Mapping[str, object]],
    reservations: Sequence[Mapping[str, object]],
    allocations: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Validate exact per-fill allocations against a trusted reservation snapshot.

    The caller must invoke this while holding the authoritative settlement
    transaction and must persist the returned rows in that same transaction.
    A result from this function alone does not reserve or consume inventory.
    """
    if not isinstance(account_id, str) or not account_id.strip():
        raise ReservationAllocationError("account_id is required")
    for name, values in (("fills", fills), ("reservations", reservations),
                         ("allocations", allocations)):
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise ReservationAllocationError(f"{name} must be a sequence")

    fill_by_id: dict[str, dict[str, object]] = {}
    for raw in fills:
        if not isinstance(raw, Mapping):
            raise ReservationAllocationError("each fill must be a mapping")
        fill_id = _required_text(raw, "fill_id")
        if fill_id in fill_by_id:
            raise ReservationAllocationError("fill IDs must be unique")
        side = raw.get("side")
        if side not in ("BUY", "SELL"):
            raise ReservationAllocationError("fill side must be BUY or SELL")
        market_id = _required_text(raw, "market_id")
        quantity = _quantity(raw.get("quantity"), "fill quantity")
        if quantity <= 0:
            raise ReservationAllocationError("fill quantity must be positive")
        fill_by_id[fill_id] = {
            "side": side, "market_id": market_id, "quantity": quantity
        }

    reservation_by_id: dict[str, dict[str, object]] = {}
    for raw in reservations:
        if not isinstance(raw, Mapping):
            raise ReservationAllocationError("each reservation must be a mapping")
        reservation_id = _required_text(raw, "reservation_id")
        if reservation_id in reservation_by_id:
            raise ReservationAllocationError("reservation IDs must be unique")
        owner = _required_text(raw, "account_id")
        market_id = _required_text(raw, "market_id")
        version = raw.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ReservationAllocationError("reservation version must be a positive integer")
        authorized = _quantity(raw.get("authorized_quantity"), "authorized_quantity")
        consumed = _quantity(raw.get("consumed_quantity", "0"), "consumed_quantity")
        if authorized <= 0 or consumed < 0 or consumed > authorized:
            raise ReservationAllocationError("invalid reservation quantity state")
        reservation_by_id[reservation_id] = {
            "account_id": owner, "market_id": market_id, "version": version,
            "remaining": authorized - consumed,
        }

    normalized: list[dict[str, object]] = []
    allocation_ids: set[str] = set()
    allocated_by_fill: dict[str, Decimal] = {}
    allocated_by_reservation: dict[str, Decimal] = {}
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        for raw in allocations:
            if not isinstance(raw, Mapping):
                raise ReservationAllocationError("each allocation must be a mapping")
            allocation_id = _required_text(raw, "allocation_id")
            if allocation_id in allocation_ids:
                raise ReservationAllocationError("allocation IDs must be unique")
            allocation_ids.add(allocation_id)
            fill_id = _required_text(raw, "fill_id")
            reservation_id = _required_text(raw, "reservation_id")
            if fill_id not in fill_by_id:
                raise ReservationAllocationError("allocation references unknown fill")
            if reservation_id not in reservation_by_id:
                raise ReservationAllocationError("allocation references unknown reservation")
            fill = fill_by_id[fill_id]
            reservation = reservation_by_id[reservation_id]
            if fill["side"] != "SELL":
                raise ReservationAllocationError("BUY fills cannot consume SELL reservations")
            if reservation["account_id"] != account_id:
                raise ReservationAllocationError("cross-account reservation allocation rejected")
            if reservation["market_id"] != fill["market_id"]:
                raise ReservationAllocationError("cross-market reservation allocation rejected")
            version = raw.get("reservation_version")
            if isinstance(version, bool) or not isinstance(version, int):
                raise ReservationAllocationError("reservation_version must be an integer")
            if version != reservation["version"]:
                raise ReservationAllocationError("stale reservation version")
            quantity = _quantity(raw.get("allocated_quantity"), "allocated_quantity")
            if quantity <= 0:
                raise ReservationAllocationError("allocated_quantity must be positive")
            allocated_by_fill[fill_id] = allocated_by_fill.get(fill_id, Decimal("0")) + quantity
            allocated_by_reservation[reservation_id] = (
                allocated_by_reservation.get(reservation_id, Decimal("0")) + quantity
            )
            normalized.append({
                "allocation_id": allocation_id,
                "fill_id": fill_id,
                "reservation_id": reservation_id,
                "account_id": account_id,
                "market_id": str(fill["market_id"]),
                "allocated_quantity": format(quantity, "f"),
                "reservation_version": version,
            })

        with localcontext() as decimal_context:
        decimal_context.prec = 80
        for fill_id, fill in fill_by_id.items():
                allocated = allocated_by_fill.get(fill_id, Decimal("0"))
                if fill["side"] == "SELL" and allocated != fill["quantity"]:
                    raise ReservationAllocationError(
                        "SELL allocations must equal each fill quantity exactly"
                    )
                if fill["side"] == "BUY" and allocated != 0:
                    raise ReservationAllocationError("BUY fills cannot have allocations")

            for reservation_id, allocated in allocated_by_reservation.items():
                if allocated > reservation_by_id[reservation_id]["remaining"]:
                    raise ReservationAllocationError("reservation over-consumption rejected")

    return sorted(normalized, key=lambda row: str(row["allocation_id"]))
