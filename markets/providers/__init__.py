"""markets.providers - the provider-neutral market-data contract (M4a).

Provider identity (who serves the bytes) is kept separate from canonical listing identity (what is traded).
Adapters own every provider-specific detail: URLs, symbols, response layouts, and error codes. They return
only canonical markets.candles.Candle objects. Nothing here logs in, uses keys, or places orders.

Contract:
    check_request(listing, timeframe_s)
        Raises ProviderError before any transport call when a listing or interval is not supported.
    fetch_candles(listing, timeframe_s, start_s, end_s, now_s, transport=...) -> FetchResult
        Guarantees: candles are canonical, sorted, unique, trimmed to [start_s, end_s], aligned to the interval
        grid, and exclude any candle still forming at now_s. Missing intervals are never filled. Every failure is
        a ProviderError with a kind, and never a silent partial result.
"""
import hashlib
import re
from dataclasses import dataclass

from markets.providers.errors import KINDS, RETRIABLE_KINDS, ProviderError  # noqa: F401  (re-exported)
from markets.providers.normalize import chunk_windows, normalize_rows
from markets.providers.transport import TransportFailure

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class ProviderInfo:
    """Who serves the data. Separate from the canonical listing identity."""

    name: str
    venue: str          # the S2 venue token this provider serves
    docs_url: str
    terms_source: str   # the terms page used, and what it does or does not state
    auth: str = "none"

    def __post_init__(self):
        for field_name in ("name", "venue"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or len(value) > 40 or not _TOKEN.fullmatch(value):
                raise ValueError(f"provider {field_name} {value!r} must be lowercase letters, digits and hyphens")
        if self.auth != "none":
            raise ValueError("M4a providers are public and unauthenticated only")
        if not self.docs_url.startswith("https://"):
            raise ValueError("docs_url must be an https URL")
        if not self.terms_source:
            raise ValueError("terms_source is required; state 'unverified' if the terms were not checked")

    def to_dict(self):
        return {"name": self.name, "venue": self.venue, "docs_url": self.docs_url,
                "terms_source": self.terms_source, "auth": self.auth}


@dataclass(frozen=True)
class FetchResult:
    candles: tuple
    provider: ProviderInfo
    requests_made: int
    raw_sha256: str          # binds the request URLs and the raw response bytes, in order
    forming_dropped: int
    duplicates_removed: int
    out_of_window_dropped: int

    def to_dict(self):
        return {"candles": [c.to_dict() for c in self.candles], "provider": self.provider.to_dict(),
                "requests_made": self.requests_made, "raw_sha256": self.raw_sha256,
                "forming_dropped": self.forming_dropped, "duplicates_removed": self.duplicates_removed,
                "out_of_window_dropped": self.out_of_window_dropped}


class MarketDataProvider:
    """Base class for adapters. Subclasses set `info`, `SYMBOLS`, `INTERVALS`, and `MAX_CANDLES_PER_REQUEST`,
    and implement `build_url` and `parse_chunk`. The shared algorithm lives here."""

    info = None
    SYMBOLS = {}                  # canonical listing string -> exact provider symbol (explicit, never derived)
    INTERVALS = {}                # timeframe_s -> provider interval token
    MAX_CANDLES_PER_REQUEST = None
    REQUEST_OVERLAP_CANDLES = 0   # extra candles each request reaches back before its window; duplicates are removed

    def build_url(self, symbol, timeframe_s, start_s, end_s):
        raise NotImplementedError

    def parse_chunk(self, body, timeframe_s):
        """Returns a list of (open_time_s, open, high, low, close, volume) tuples, or raises ProviderError."""
        raise NotImplementedError

    def check_page(self, rows, chunk_start_s, timeframe_s):
        """Hook for a provider-specific check of one parsed page. Raises ProviderError if the page cannot serve the
        requested window start. The default accepts every page."""
        return None

    def provider_symbol(self, listing):
        if listing.venue != self.info.venue or listing.canonical not in self.SYMBOLS:
            raise ProviderError("unsupported_listing", self.info.name,
                                f"no explicit symbol mapping for {listing.canonical}")
        return self.SYMBOLS[listing.canonical]

    def check_request(self, listing, timeframe_s):
        """Validates a request without any network access. Returns the provider symbol."""
        symbol = self.provider_symbol(listing)
        if timeframe_s not in self.INTERVALS:
            raise ProviderError("unsupported_interval", self.info.name,
                                f"interval {timeframe_s}s is not offered by this adapter")
        return symbol

    def supports(self, listing, timeframe_s):
        try:
            self.check_request(listing, timeframe_s)
        except ProviderError:
            return False
        return True

    def fetch_candles(self, listing, timeframe_s, start_s, end_s, now_s, *, transport):
        for name, value in (("timeframe_s", timeframe_s), ("start_s", start_s), ("end_s", end_s),
                            ("now_s", now_s)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if end_s < start_s:
            raise ValueError("end_s is before start_s")
        if start_s % timeframe_s or end_s % timeframe_s:
            raise ValueError("start_s and end_s must lie on the interval grid")
        symbol = self.check_request(listing, timeframe_s)     # raises before any transport call
        if not callable(transport):
            raise ValueError("a transport callable is required")

        digest = hashlib.sha256()
        rows, requests = [], 0
        windows = chunk_windows(start_s, end_s, timeframe_s,
                                self.MAX_CANDLES_PER_REQUEST - self.REQUEST_OVERLAP_CANDLES)
        for index, (chunk_start, chunk_end) in enumerate(windows, start=1):
            request_start = chunk_start - self.REQUEST_OVERLAP_CANDLES * timeframe_s
            url = self.build_url(symbol, timeframe_s, request_start, chunk_end)
            requests += 1
            try:
                body = transport(url)
            except TransportFailure as failure:
                raise ProviderError(failure.kind, self.info.name, failure.detail, failure.status) from failure
            if not isinstance(body, (bytes, bytearray)):
                raise ProviderError("bad_payload", self.info.name, "transport returned a non-bytes body")
            digest.update(url.encode("utf-8"))
            digest.update(bytes(body))
            chunk_rows = self.parse_chunk(bytes(body), timeframe_s)
            if not chunk_rows:
                raise ProviderError("empty", self.info.name,
                                    f"page {index} of {len(windows)} returned no candles; the range is incomplete")
            self.check_page(chunk_rows, chunk_start, timeframe_s)
            rows.extend(chunk_rows)

        if not rows:
            raise ProviderError("empty", self.info.name, "the provider returned no candles for the window")
        candles, stats = normalize_rows(rows, start_s, end_s, now_s, timeframe_s, self.info.name)
        return FetchResult(candles=candles, provider=self.info, requests_made=requests,
                           raw_sha256=digest.hexdigest(), **stats)
