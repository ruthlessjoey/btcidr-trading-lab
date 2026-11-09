"""markets/providers/kraken.py - Kraken public OHLC adapter (daily only in M4a, fixture-only, no live use).

Checked against Kraken's official 'Historical Data' guide: public endpoints need no authentication, OHLC returns at
most 720 candles per call, public endpoints are rate limited per IP, and the page states no license text.
Terms are therefore recorded as unverified. Kraken's documented OHLC row layout is
[time, open, high, low, close, vwap, volume, count]. That layout is asserted here and must be confirmed against
the live API before any live use.

Kraken returns the requested pair under a different result key (for example XXBTZUSD), plus a 'last' field. The
adapter requires exactly one candle list under the result, so it does not depend on the key name.
"""
import json
import urllib.parse

from markets.providers import MarketDataProvider, ProviderInfo
from markets.providers import symbols
from markets.providers.errors import ProviderError


class Kraken(MarketDataProvider):
    info = ProviderInfo(
        name="kraken",
        venue="kraken",
        docs_url="https://docs.kraken.com/exchange/guides/general/historical-data",
        terms_source="Kraken 'Historical Data' guide: public, no authentication, per-IP rate limits. The page states no "
                     "license or terms text (unverified).",
    )
    SYMBOLS = symbols.KRAKEN
    INTERVALS = {86400: 1440}     # Kraken interval parameter is in minutes
    MAX_CANDLES_PER_REQUEST = 720
    # Whether 'since' is inclusive is not stated in Kraken's docs. Each request therefore reaches one interval back,
    # so an exclusive or inclusive server both return the window start. Overlap rows are exact duplicates, removed.
    REQUEST_OVERLAP_CANDLES = 1
    BASE_URL = "https://api.kraken.com/0/public/OHLC"

    def build_url(self, symbol, timeframe_s, start_s, end_s):
        query = urllib.parse.urlencode({"pair": symbol, "interval": self.INTERVALS[timeframe_s], "since": start_s})
        return f"{self.BASE_URL}?{query}"

    def check_page(self, rows, chunk_start_s, timeframe_s):
        # Kraken's docs: a call returns up to 720 of the most recent entries, and older data cannot be retrieved
        # regardless of 'since'. A full page whose earliest candle is after the requested window start cannot contain
        # that start. The adapter cannot tell which cause applies, so the message lists both and claims neither.
        if len(rows) == self.MAX_CANDLES_PER_REQUEST:
            earliest = min(r[0] for r in rows)
            if earliest > chunk_start_s:
                raise ProviderError(
                    "history_unavailable", self.info.name,
                    "Requested window start is not available from this response. "
                    f"Requested start {chunk_start_s}; the earliest candle returned is {earliest}; the response is a "
                    f"full page of {len(rows)} entries. Possible causes: the requested window is older than Kraken's "
                    f"retrievable history (the most recent {self.MAX_CANDLES_PER_REQUEST} entries), or the listing "
                    "began after the requested start. This adapter cannot distinguish these causes; refusing rather "
                    "than guessing.")

    def parse_chunk(self, body, timeframe_s):
        name = self.info.name
        try:
            obj = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ProviderError("bad_payload", name, f"response is not JSON: {e}")
        if not isinstance(obj, dict):
            raise ProviderError("bad_payload", name, "response is not a JSON object")
        errors = obj.get("error")
        if not isinstance(errors, list):
            raise ProviderError("bad_payload", name, "response has no error list")
        if errors:
            text = "; ".join(str(e) for e in errors)
            kind = "rate_limited" if "rate limit" in text.lower() else "unavailable"
            raise ProviderError(kind, name, text)
        result = obj.get("result")
        if not isinstance(result, dict):
            raise ProviderError("bad_payload", name, "response has no result object")
        keys = [k for k in result if k != "last"]
        if len(keys) != 1 or not isinstance(result[keys[0]], list):
            raise ProviderError("bad_payload", name, f"expected exactly one candle list, got keys {list(result)[:4]}")
        raw_rows = result[keys[0]]
        if len(raw_rows) > self.MAX_CANDLES_PER_REQUEST:
            raise ProviderError("bad_payload", name,
                                f"{len(raw_rows)} candles in one response exceeds the documented "
                                f"{self.MAX_CANDLES_PER_REQUEST}")
        rows = []
        for index, row in enumerate(raw_rows):
            if not isinstance(row, list) or len(row) < 7:
                raise ProviderError("bad_payload", name, f"candle {index} has an unexpected shape")
            t = row[0]
            if isinstance(t, bool) or not isinstance(t, int):
                raise ProviderError("bad_payload", name, f"candle {index} time is not an integer")
            try:
                o, h, lo, c, v = float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[6])
            except (TypeError, ValueError, OverflowError):
                raise ProviderError("bad_payload", name, f"candle {index} has a non-numeric price or volume")
            rows.append((t, o, h, lo, c, v))
        return rows
