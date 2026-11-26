"""research/toy.py - SYNTHETIC TOY candles for testing the engine. NOT MARKET DATA.

Never used by a real run: the pipeline only accepts a dataset whose manifest names the
expected exchange, and these datasets are labelled provider 'SYNTHETIC-TOY'.
"""
import random

from fetcher import Candle

TOY_LABEL = "SYNTHETIC TOY DATA - NOT MARKET DATA"
TOY_PROVIDER = "SYNTHETIC-TOY"
DAY = 86400
START = 1_500_000_000 - (1_500_000_000 % DAY)      # an arbitrary UTC midnight


def toy_candles(n=1000, seed=7):
    """Seeded random walk with alternating up/down drift regimes (deterministic)."""
    rng = random.Random(seed)
    price, out = 100.0, []
    for i in range(n):
        drift = 0.004 if (i // 120) % 2 == 0 else -0.004
        o = price
        c = max(1.0, o * (1 + drift + rng.uniform(-0.02, 0.02)))
        hi = max(o, c) * (1 + rng.uniform(0, 0.01))
        lo = min(o, c) * (1 - rng.uniform(0, 0.01))
        out.append(Candle(START + i * DAY, round(o, 4), round(hi, 4), round(lo, 4),
                          round(c, 4), round(rng.uniform(10, 50), 3)))
        price = c
    return out


def straight_line(n, start_price=100.0, step=1.0):
    """open = previous close, close = open + step. Easy to verify by hand."""
    out = []
    for i in range(n):
        o = start_price + i * step
        c = o + step
        out.append(Candle(START + i * DAY, o, max(o, c) + 0.5, min(o, c) - 0.5, c, 10.0))
    return out
