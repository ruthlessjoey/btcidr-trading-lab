"""markets/providers/binance_vision.py - Binance public market-data adapter (daily klines only in M4a).

Endpoint and terms were checked against the official 'Market Data Only URLs' FAQ: public market data only, no
authentication. That page states no terms of use and no rate limits, so terms_source says so.
Row layout (Binance klines): [open_time_ms, open, high, low, close, volume, close_time_ms, ...].
"""
import json
import urllib.parse

from markets.providers import MarketDataProvider, ProviderInfo
from markets.providers import symbols
from markets.providers.errors import ProviderError


class BinanceVision(MarketDataProvider):
    info = ProviderInfo(
        name="binance-vision",
        venue="binance",
        docs_url="https://developers.binance.com/en/docs/products/spot/faqs/market_data_only",
        terms_source="Binance 'Market Data Only URLs' FAQ: public market data, no authentication. The page states "
                     "no terms of use and no rate limits (unverified beyond that page).",
    )
    SYMBOLS = symbols.BINANCE_VISION
    INTERVALS = {86400: "1d"}
    MAX_CANDLES_PER_REQUEST = 1000
    BASE_URL = "https://data-api.binance.vision/api/v3/klines"

    def build_url(self, symbol, timeframe_s, start_s, end_s):
        query = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": self.INTERVALS[timeframe_s],
            "startTime": start_s * 1000,
            "endTime": end_s * 1000 + timeframe_s * 1000 - 1,   # inclusive of the candle opening at end_s
            "limit": self.MAX_CANDLES_PER_REQUEST,
        })
        return f"{self.BASE_URL}?{query}"

    def parse_chunk(self, body, timeframe_s):
        name = self.info.name
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise ProviderError("bad_payload", name, f"response is not JSON: {e}")
        if not isinstance(data, list):
            raise ProviderError("bad_payload", name, f"response is not a list of candles: {str(data)[:120]}")
        rows = []
        for index, row in enumerate(data):
            if not isinstance(row, list) or len(row) < 7:
                raise ProviderError("bad_payload", name, f"row {index} has an unexpected shape")
            open_ms = row[0]
            if isinstance(open_ms, bool) or not isinstance(open_ms, int) or open_ms % 1000:
                raise ProviderError("bad_payload", name, f"row {index} open time is not whole seconds")
            open_s = open_ms // 1000
            if row[6] != (open_s + timeframe_s) * 1000 - 1:
                raise ProviderError("bad_payload", name, f"row {index} close time does not match its interval")
            try:
                o, h, lo, c, v = (float(row[k]) for k in (1, 2, 3, 4, 5))
            except (TypeError, ValueError, OverflowError):
                raise ProviderError("bad_payload", name, f"row {index} has a non-numeric price or volume")
            rows.append((open_s, o, h, lo, c, v))
        return rows
