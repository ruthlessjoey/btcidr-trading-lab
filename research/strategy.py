"""research/strategy.py - the baseline strategy and the look-ahead guard.

A strategy is a function: list of candles -> list of 0/1 signals (one per candle).
signals[i] may use candles[0..i] only. assert_causal() proves that for a given series.
"""
from fetcher import Candle
from research.engine import EngineError


def ma_trend(n):
    """Long when the completed candle's close is above the simple average of the last n closes
    (that candle included); otherwise flat. Needs n candles before it can say 'long'."""
    if n < 2:
        raise ValueError("moving-average period must be at least 2")

    def signals(candles):
        out, running = [], 0.0
        for i, c in enumerate(candles):
            running += c.close
            if i >= n:
                running -= candles[i - n].close
            out.append(1 if i >= n - 1 and c.close > running / n else 0)
        return out
    signals.n = n
    return signals


def assert_causal(strategy, candles, points=None, tail=3):
    """Look-ahead guard. For each checked bar k:
      1. the signal computed on candles[:k+1] must equal the signal computed on the full series;
      2. rewriting every FUTURE candle with absurd prices must not change signals[:k+1].
    Raises EngineError if either fails. `points` defaults to a deterministic spread of bars."""
    n = len(candles)
    full = strategy(candles)
    if len(full) != n:
        raise EngineError("strategy returned the wrong number of signals")
    ks = points if points is not None else sorted(set(
        list(range(n - tail, n)) + [round(j * (n - 1) / 59) for j in range(60)]))
    for k in ks:
        if not 0 <= k < n:
            continue
        cut = strategy(candles[:k + 1])
        if cut[k] != full[k] or cut[:k + 1] != full[:k + 1]:
            raise EngineError(f"look-ahead bias: signals up to bar {k} change when later "
                              f"candles are removed")
        wild = candles[:k + 1] + [Candle(c.time, 1e9, 2e9, 1.0, 1.5e9 if j % 2 else 2.0, 1.0)
                                  for j, c in enumerate(candles[k + 1:])]
        if strategy(wild)[:k + 1] != full[:k + 1]:
            raise EngineError(f"look-ahead bias: signals up to bar {k} change when later "
                              f"candles are rewritten")
    return True
