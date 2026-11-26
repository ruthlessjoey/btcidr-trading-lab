"""Deterministic statistical evidence primitives for frozen OOS research folds."""
from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from decimal import Decimal
from statistics import NormalDist

MINIMUM_RETURN_OBSERVATIONS = 30
BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_LOWER_QUANTILE = 0.025
BLOCK_BARS = 24
_EULER_MASCHERONI = 0.5772156649015329


class StatisticalEvidenceError(ValueError):
    """Invalid return series or statistical evidence inputs."""


def _numeric_series(values: object, name: str, *, minimum: int) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise StatisticalEvidenceError(f"{name} must be a numeric sequence")
    if len(values) < minimum:
        raise StatisticalEvidenceError(f"{name} requires at least {minimum} observations")
    result = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise StatisticalEvidenceError(f"{name}[{index}] must be numeric, not boolean")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise StatisticalEvidenceError(f"{name}[{index}] must be finite") from exc
        if not math.isfinite(number) or number <= -1:
            raise StatisticalEvidenceError(f"{name}[{index}] must be finite and greater than -1")
        result.append(number)
    return result


def non_overlapping_24bar_returns(equity_curve: Sequence[object]) -> list[float]:
    """Convert positive equity marks to non-overlapping 24-bar simple returns.

    The first equity mark is the segment's starting mark. Incomplete trailing
    blocks are ignored. Observations are non-overlapping to reduce (not remove)
    hourly serial dependence in the DSR input.
    """
    if isinstance(equity_curve, (str, bytes)) or not isinstance(equity_curve, Sequence):
        raise StatisticalEvidenceError("equity_curve must be a numeric sequence")
    if len(equity_curve) < BLOCK_BARS + 1:
        raise StatisticalEvidenceError(
            f"equity_curve requires at least {BLOCK_BARS + 1} marks"
        )
    marks = []
    for index, value in enumerate(equity_curve):
        if isinstance(value, bool):
            raise StatisticalEvidenceError(f"equity_curve[{index}] cannot be boolean")
        try:
            mark = float(Decimal(str(value)))
        except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
            raise StatisticalEvidenceError(f"equity_curve[{index}] must be numeric") from exc
        if not math.isfinite(mark) or mark <= 0:
            raise StatisticalEvidenceError("equity marks must be finite and strictly positive")
        marks.append(mark)
    returns = [
        marks[index + BLOCK_BARS] / marks[index] - 1.0
        for index in range(0, len(marks) - BLOCK_BARS, BLOCK_BARS)
    ]
    if len(returns) < MINIMUM_RETURN_OBSERVATIONS:
        raise StatisticalEvidenceError(
            f"at least {MINIMUM_RETURN_OBSERVATIONS} complete non-overlapping 24-bar returns are required"
        )
    return returns


def deflated_sharpe_probability(
    returns: Sequence[object], *, registered_trial_count: int
) -> float:
    """Estimate DSR from non-overlapping periodic returns and all registered trials.

    Uses the probabilistic-Sharpe finite-sample variance approximation and the
    expected maximum Sharpe under a Gaussian null across N registered trials.
    This approximation assumes sufficiently independent observations; callers
    should use non-overlapping 24-bar returns and interpret it with the paired
    block-bootstrap result and independent statistical review.
    """
    series = _numeric_series(returns, "returns", minimum=MINIMUM_RETURN_OBSERVATIONS)
    if (isinstance(registered_trial_count, bool)
            or not isinstance(registered_trial_count, int)
            or registered_trial_count < 2):
        raise StatisticalEvidenceError("registered_trial_count must be an integer >= 2")
    n = len(series)
    mean = math.fsum(series) / n
    centered = [value - mean for value in series]
    second = math.fsum(value * value for value in centered) / n
    if second == 0:
        return 0.5
    std = math.sqrt(second)
    sharpe = mean / std
    third = math.fsum(value ** 3 for value in centered) / n
    fourth = math.fsum(value ** 4 for value in centered) / n
    skew = third / (second ** 1.5)
    kurtosis = fourth / (second ** 2)
    variance_sharpe = (
        1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe
    ) / (n - 1)
    if not math.isfinite(variance_sharpe) or variance_sharpe <= 0:
        raise StatisticalEvidenceError("Sharpe variance approximation is not positive and finite")
    standard_error = math.sqrt(variance_sharpe)
    normal = NormalDist()
    p1 = 1.0 - 1.0 / registered_trial_count
    p2 = 1.0 - 1.0 / (registered_trial_count * math.e)
    expected_max_z = (
        (1.0 - _EULER_MASCHERONI) * normal.inv_cdf(p1)
        + _EULER_MASCHERONI * normal.inv_cdf(p2)
    )
    benchmark = standard_error * expected_max_z
    probability = normal.cdf((sharpe - benchmark) / standard_error)
    return min(1.0, max(0.0, probability))


def paired_block_bootstrap_excess_lower_bound(
    strategy_returns: Sequence[object],
    baseline_returns: Sequence[object],
    *,
    dataset_sha256: str,
    fold_id: str,
) -> float:
    """Return deterministic 95% paired circular block-bootstrap lower bound.

    Resampling uses fixed 10,000 replications and circular blocks of length
    ceil(n**(1/3)). The seed is derived from the immutable dataset hash and fold
    identifier, so reruns are reproducible. The lower 2.5th percentile is used.
    """
    strategy = _numeric_series(
        strategy_returns, "strategy_returns", minimum=MINIMUM_RETURN_OBSERVATIONS
    )
    baseline = _numeric_series(
        baseline_returns, "baseline_returns", minimum=MINIMUM_RETURN_OBSERVATIONS
    )
    if len(strategy) != len(baseline):
        raise StatisticalEvidenceError("paired return series must have equal lengths")
    if (not isinstance(dataset_sha256, str)
            or len(dataset_sha256) != 64
            or any(char not in "0123456789abcdef" for char in dataset_sha256)):
        raise StatisticalEvidenceError("dataset_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(fold_id, str) or not fold_id.strip() or len(fold_id) > 128:
        raise StatisticalEvidenceError("fold_id must be a non-empty string up to 128 characters")

    differences = [left - right for left, right in zip(strategy, baseline)]
    n = len(differences)
    block_size = max(2, math.ceil(n ** (1.0 / 3.0)))
    seed_material = f"{dataset_sha256}:{fold_id}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n)
            take = min(block_size, n - len(sample))
            sample.extend(differences[(start + offset) % n] for offset in range(take))
        means.append(math.fsum(sample) / n)
    means.sort()
    index = math.floor(BOOTSTRAP_LOWER_QUANTILE * (BOOTSTRAP_RESAMPLES - 1))
    return means[index]
