"""research/splits.py - chronological train / validation / test windows (bar index ranges)."""
import math

from research.engine import EngineError


_SPLIT_NAMES = ("train", "validation", "test")


def validate_splits(n, splits):
    """Validate complete, contiguous, chronological [start, end) windows."""
    if type(n) is not int or n < 1:
        raise EngineError("candle count must be a positive integer")
    if not isinstance(splits, dict) or set(splits) != set(_SPLIT_NAMES):
        raise EngineError("splits must contain exactly train, validation and test")
    normalized = {}
    for name in _SPLIT_NAMES:
        bounds = splits[name]
        if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2
                or type(bounds[0]) is not int or type(bounds[1]) is not int):
            raise EngineError(f"{name} split bounds must be two integer indices")
        start, end = bounds
        if not 0 <= start < end <= n:
            raise EngineError(f"{name} split bounds are outside the candle sequence")
        normalized[name] = (start, end)
    train, validation, test = (normalized[name] for name in _SPLIT_NAMES)
    if train[0] == 0:
        raise EngineError("training split must reserve at least one warm-up candle")
    if train[1] != validation[0] or validation[1] != test[0]:
        raise EngineError("train, validation and test splits must be contiguous without gaps or overlap")
    if test[1] != n:
        raise EngineError("test split must end at the final candle")
    return normalized


def make_splits(n, train=0.6, val=0.2, warmup=200):
    """Build chronological [start, end) windows using row count only.

    Training evaluation starts after the warm-up candles so all candidates
    are scored on identical bars. Earlier candles are used only for warm-up.
    """
    if type(n) is not int or n < 1:
        raise EngineError("series length must be a positive integer")
    if (isinstance(train, bool) or not isinstance(train, (int, float))
            or not math.isfinite(train) or not 0 < train < 1):
        raise EngineError("training fraction must be finite and between zero and one")
    if (isinstance(val, bool) or not isinstance(val, (int, float))
            or not math.isfinite(val) or not 0 < val < 1):
        raise EngineError("validation fraction must be finite and between zero and one")
    if train + val >= 1:
        raise EngineError("training and validation fractions must leave a non-empty test window")
    if type(warmup) is not int or warmup < 1:
        raise EngineError("warmup must be a positive integer")
    n_train, n_val = int(n * train), int(n * val)
    if not warmup < n_train or n_val < 1 or n - n_train - n_val < 1:
        raise EngineError("series too short for the requested split")
    return validate_splits(n, {
        "train": (warmup, n_train),
        "validation": (n_train, n_train + n_val),
        "test": (n_train + n_val, n),
    })
