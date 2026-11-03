"""markets/strategies/btc_s1.py - the S1 BTC daily trend rule set as a provider-neutral strategy (M5).

This is a compatibility adapter. It does not copy S1's thresholds or formulas. It converts canonical candles to S1
candles and calls the committed S1 function signal_at, unchanged. So its decisions cannot drift from S1's.

Mapping: S1 BUY -> BUY, S1 SELL -> SELL, S1 WAIT -> HOLD.

Scope, exact and pinned:
  - canonical listing: crypto:binance-spot:BTC-USDT only (S1 was developed and validated on Binance daily BTC-USDT);
  - interval: 86400 seconds only;
  - rule version: btc-rules-v1 only. Import refuses if the committed S1 reports any other rule version.
Requests outside that scope are refused by the engine with INVALID before signal_at is called.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_SIGNAL = os.path.join(_ROOT, "signal")
for _p in (_ROOT, _SIGNAL):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import btc_signal as bs  # noqa: E402  committed S1 engine, unchanged

from markets.strategies import contract as C  # noqa: E402

PINNED_RULE_VERSION = "btc-rules-v1"
PINNED_LISTING = "crypto:binance-spot:BTC-USDT"
PINNED_INTERVAL_S = 86400

if bs.RULE_VERSION != PINNED_RULE_VERSION or bs.STEP != PINNED_INTERVAL_S:
    raise C.StrategyError(f"committed S1 is {bs.RULE_VERSION!r} at {bs.STEP}s; this adapter is pinned to "
                          f"{PINNED_RULE_VERSION!r} at {PINNED_INTERVAL_S}s")

_MAPPING = {
    "BUY": ("S1_BUY_RULES_MET", C.BUY),
    "SELL": ("S1_SELL_RULES_MET", C.SELL),
    "WAIT": ("S1_NO_RULE_MET", C.HOLD),
}


class BtcS1DailyTrend(C.Strategy):
    strategy_id = "s1-btc-daily-trend"
    version = PINNED_RULE_VERSION
    description = "S1 BTC daily trend rules (SMA20/SMA50 with close and RSI14 filters), unchanged."
    asset_classes = ("crypto",)
    market_types = ("spot",)
    base_assets = ("BTC",)
    quote_assets = ("USDT",)
    canonical_listings = (PINNED_LISTING,)
    intervals_s = (PINNED_INTERVAL_S,)
    CONFIG_SCHEMA = {}                      # S1's thresholds are frozen in S1; nothing here can change them
    reason_codes = tuple(code for code, _ in _MAPPING.values())

    def required_history(self, config):
        return bs.SMA_SLOW

    def evaluate(self, config, candles):
        s1 = [bs.Candle(c.open_time_s, c.open, c.high, c.low, c.close, c.volume) for c in candles]
        result = bs.signal_at(s1, len(s1) - 1)
        if result["rule_version"] != PINNED_RULE_VERSION:
            raise C.StrategyError(f"S1 returned rule version {result['rule_version']!r}, not {PINNED_RULE_VERSION!r}")
        code, decision = _MAPPING[result["decision"]]
        return {
            "decision": decision,
            "reason_codes": [code],
            "reasons": list(result["reasons"]),
            "indicators": dict(result["values"]),
        }
