"""Point-in-time covariance-aware, long-only portfolio volatility overlay.

This is a deterministic research control, not a return forecast. Inputs must be
aligned historical returns that were available by the decision timestamp.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from .portfolio import PortfolioError, _d

D = Decimal


class RiskOverlayError(ValueError):
    """Raised when covariance inputs or risk policy are invalid."""


@dataclass(frozen=True)
class CovarianceRiskPolicy:
    max_period_volatility: Decimal | str | float
    min_observations: int = 20
    max_return_age_seconds: int = 86400


def apply_covariance_risk_overlay(*, target_weights: Mapping[str, object],
                                  returns: Mapping[str, Sequence[tuple[int, object]]],
                                  decision_time: int,
                                  policy: CovarianceRiskPolicy) -> dict[str, object]:
    """Scale long-only weights down when historical portfolio volatility exceeds a cap.

    Each return series is a chronological sequence of (UTC epoch-second, simple
    return) pairs. All markets must have identical timestamps. Volatility is per
    observation; callers must use a consistent bar frequency and set the cap in
    the same units. The function never annualizes or fills missing observations.
    """
    if isinstance(decision_time, bool) or not isinstance(decision_time, int) or decision_time < 0:
        raise RiskOverlayError("decision_time must be a nonnegative integer epoch timestamp")
    if (not isinstance(policy.min_observations, int) or isinstance(policy.min_observations, bool)
            or policy.min_observations < 2):
        raise RiskOverlayError("min_observations must be an integer of at least two")
    if (not isinstance(policy.max_return_age_seconds, int)
            or isinstance(policy.max_return_age_seconds, bool)
            or policy.max_return_age_seconds < 0):
        raise RiskOverlayError("max_return_age_seconds must be a nonnegative integer")
    try:
        max_vol = _d(policy.max_period_volatility, "max_period_volatility")
    except PortfolioError as exc:
        raise RiskOverlayError(str(exc)) from exc
    if max_vol <= 0:
        raise RiskOverlayError("max_period_volatility must be positive")
    if not isinstance(target_weights, Mapping) or not target_weights:
        raise RiskOverlayError("target_weights must be a non-empty mapping")
    if not isinstance(returns, Mapping) or set(returns) != set(target_weights):
        raise RiskOverlayError("return series must exactly cover the target market universe")

    weights: dict[str, Decimal] = {}
    for market_id, raw_weight in target_weights.items():
        if not isinstance(market_id, str) or not market_id:
            raise RiskOverlayError("market IDs must be non-empty strings")
        try:
            weight = _d(raw_weight, f"{market_id}.weight")
        except PortfolioError as exc:
            raise RiskOverlayError(str(exc)) from exc
        if weight < 0 or weight > 1:
            raise RiskOverlayError("target weights must be spot long-only values in [0, 1]")
        weights[market_id] = weight
    if sum(weights.values(), D("0")) > 1:
        raise RiskOverlayError("target gross weight cannot exceed 1")

    clean_returns: dict[str, list[Decimal]] = {}
    canonical_timestamps: tuple[int, ...] | None = None
    for market_id in sorted(weights):
        series = returns[market_id]
        if not isinstance(series, Sequence) or isinstance(series, (str, bytes)):
            raise RiskOverlayError(f"{market_id}: returns must be a timestamped sequence")
        if len(series) < policy.min_observations:
            raise RiskOverlayError(f"{market_id}: insufficient return observations")
        timestamps: list[int] = []
        values: list[Decimal] = []
        previous = None
        for index, pair in enumerate(series):
            if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)) or len(pair) != 2:
                raise RiskOverlayError(f"{market_id}: return row {index} must be (timestamp, return)")
            stamp, raw_return = pair
            if (isinstance(stamp, bool) or not isinstance(stamp, int)
                    or stamp < 0 or stamp > decision_time
                    or (previous is not None and stamp <= previous)):
                raise RiskOverlayError(f"{market_id}: return timestamps are invalid or not chronological")
            try:
                value = _d(raw_return, f"{market_id}.return[{index}]")
            except PortfolioError as exc:
                raise RiskOverlayError(str(exc)) from exc
            if value < -1:
                raise RiskOverlayError(f"{market_id}: simple return cannot be below -100%")
            timestamps.append(stamp)
            values.append(value)
            previous = stamp
        stamps = tuple(timestamps)
        if canonical_timestamps is None:
            canonical_timestamps = stamps
        elif stamps != canonical_timestamps:
            raise RiskOverlayError("all market return series must have identical timestamps")
        clean_returns[market_id] = values

    assert canonical_timestamps is not None
    if decision_time - canonical_timestamps[-1] > policy.max_return_age_seconds:
        raise RiskOverlayError("latest return observation is stale")

    count = len(canonical_timestamps)
    means = {m: sum(values, D("0")) / D(count) for m, values in clean_returns.items()}
    covariance: dict[tuple[str, str], Decimal] = {}
    market_ids = sorted(weights)
    for left in market_ids:
        for right in market_ids:
            cross = sum(((a - means[left]) * (b - means[right])
                         for a, b in zip(clean_returns[left], clean_returns[right])), D("0"))
            covariance[(left, right)] = cross / D(count - 1)

    variance = sum((weights[left] * weights[right] * covariance[(left, right)]
                    for left in market_ids for right in market_ids), D("0"))
    if variance < 0:
        raise RiskOverlayError("computed portfolio variance is negative; refusing risk scaling")
    before_vol = variance.sqrt()
    scale = D("1") if before_vol <= max_vol or before_vol == 0 else max_vol / before_vol
    adjusted = {market_id: weight * scale for market_id, weight in weights.items()}
    after_variance = variance * scale * scale
    after_vol = after_variance.sqrt()
    return {
        "weights": adjusted,
        "scale_factor": scale,
        "volatility_before": before_vol,
        "volatility_after": after_vol,
        "max_period_volatility": max_vol,
        "observations": count,
        "last_return_timestamp": canonical_timestamps[-1],
        "risk_status": "SCALED_DOWN" if scale < 1 else "WITHIN_LIMIT",
        "method": "SAMPLE_COVARIANCE_PROPORTIONAL_LONG_ONLY_SCALING",
    }
