"""markets/providers/normalize.py - shared, provider-neutral normalization for adapter output.

Rules, applied to every adapter:
  - Rows become canonical markets.candles.Candle objects. Invalid OHLC or misaligned rows are bad_payload.
  - A candle still forming at now_s (open + interval > now_s) is excluded and counted. Only the newest row may be
    forming. A forming row that is followed by a completed row is bad_payload.
  - Rows with identical content and the same open time are deduplicated and counted.
  - Rows with the same open time but different content are conflicting_duplicate. The run refuses.
  - Rows outside [start_s, end_s] are trimmed and counted.
  - Output is sorted by open time. Missing intervals are never filled here.
"""
from markets import candles as mc
from markets.providers.errors import ProviderError


def chunk_windows(start_s, end_s, timeframe_s, max_candles):
    """Splits the inclusive range [start_s, end_s] into windows of at most max_candles grid slots each."""
    if max_candles is None or max_candles < 1:
        raise ValueError("max_candles must be a positive integer")
    windows = []
    cursor = start_s
    while cursor <= end_s:
        chunk_end = min(cursor + (max_candles - 1) * timeframe_s, end_s)
        windows.append((cursor, chunk_end))
        cursor = chunk_end + timeframe_s
    return windows


def normalize_rows(rows, start_s, end_s, now_s, timeframe_s, provider_name):
    """Returns (candles tuple, stats dict). Raises ProviderError for any unusable row set."""
    by_time = {}
    duplicates_removed = 0
    for raw in rows:
        try:
            candle = mc.Candle(raw[0], raw[1], raw[2], raw[3], raw[4], raw[5])
            mc.check_alignment(candle, timeframe_s)
        except mc.CandleError as e:
            raise ProviderError("bad_payload", provider_name, f"invalid candle at {raw[0]}: {e}")
        previous = by_time.get(candle.open_time_s)
        if previous is None:
            by_time[candle.open_time_s] = candle
        elif previous == candle:
            duplicates_removed += 1
        else:
            raise ProviderError("conflicting_duplicate", provider_name,
                                f"two different candles share open time {candle.open_time_s}; refusing")

    ordered = [by_time[t] for t in sorted(by_time)]
    forming = [c for c in ordered if c.open_time_s + timeframe_s > now_s]
    if len(forming) > 1:
        raise ProviderError("bad_payload", provider_name, f"{len(forming)} candles are still forming; at most one")
    if forming:
        if ordered[-1] is not forming[0]:
            raise ProviderError("bad_payload", provider_name, "a forming candle is followed by completed candles")
        ordered = ordered[:-1]
    forming_dropped = 1 if forming else 0

    kept = [c for c in ordered if start_s <= c.open_time_s <= end_s]
    out_of_window = len(ordered) - len(kept)
    return tuple(kept), {"forming_dropped": forming_dropped, "duplicates_removed": duplicates_removed,
                         "out_of_window_dropped": out_of_window}
