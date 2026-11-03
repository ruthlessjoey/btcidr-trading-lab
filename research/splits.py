"""research/splits.py - chronological train / validation / test windows (bar index ranges)."""
from research.engine import EngineError


def make_splits(n, train=0.6, val=0.2, warmup=200):
    """[start, end) bar ranges. Split points come from the row count alone, never from prices.
    Train evaluation starts at `warmup` for EVERY candidate so all candidates are scored on the
    same bars. Earlier candles are used only to warm the moving averages up."""
    n_train, n_val = int(n * train), int(n * val)
    if not 0 < warmup < n_train or n_val < 1 or n - n_train - n_val < 1:
        raise EngineError("series too short for the requested split")
    return {"train": (warmup, n_train), "validation": (n_train, n_train + n_val),
            "test": (n_train + n_val, n)}
