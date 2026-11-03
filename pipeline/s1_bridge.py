"""pipeline/s1_bridge.py - runs the committed S1 BTC rule set on canonical daily candles.

Only for BTC daily listings, because the S1 rules are the BTC rule set (rule version btc-rules-v1). The caller
decides when to pass this as signal_fn. This module does not change S1: it converts canonical candles to S1
candles at the boundary and calls the unchanged signal_at.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SIGNAL = os.path.join(_ROOT, "signal")
for _p in (_ROOT, _SIGNAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import btc_signal as bs  # noqa: E402  committed S1 engine, unchanged

DECISION_MEANING = {
    "BUY": "BUY = bullish/entry candidate in spot research, not an order instruction.",
    "SELL": "SELL = bearish/exit candidate in spot research, not a short instruction.",
    "WAIT": "WAIT = no research candidate on this basis candle; no order is implied.",
}


def s1_daily_signal(canon):
    """Returns the S1 decision for the last candle of a canonical, validated, completed daily series."""
    s1 = [bs.Candle(c.open_time_s, c.open, c.high, c.low, c.close, c.volume) for c in canon]
    result = bs.signal_at(s1, len(s1) - 1)
    return {
        "decision": result["decision"],
        "decision_meaning": DECISION_MEANING[result["decision"]],
        "rule_version": result["rule_version"],
        "basis_candle_open_utc": result["basis_candle_open_utc"],
        "basis_candle_close_utc": result["basis_candle_close_utc"],
        "values": result["values"],
        "reasons": result["reasons"],
    }
