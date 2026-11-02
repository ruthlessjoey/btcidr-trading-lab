"""markets/identity.py - market-neutral identity for instruments and listings (S2.1).

Standard library only. Deterministic. No network, no orders, no credentials.

Two distinct, immutable, validated concepts:

  Instrument  what is traded, independent of where it is traded.
              canonical: "<asset_class>:<BASE>-<QUOTE>"             e.g. "crypto:BTC-USDT"
  Listing     an instrument traded at a venue as a market type.
              canonical: "<asset_class>:<venue>-<market_type>:<BASE>-<QUOTE>"
                                                                    e.g. "crypto:binance-spot:BTC-USDT"

Legacy P1 form, accepted and reproduced exactly (crypto listings only):
              "<venue>-<market_type>:<BASE>-<QUOTE>"                e.g. "binance-spot:BTC-USDT"

Field rules are explicit per asset class; nothing is inferred from another asset class:
  crypto  base and quote: 1-15 characters of A-Z or 0-9, with at least one letter.
  equity  base: ticker of 1-5 letters A-Z (no dots or digits). quote: 3-letter currency code.
  fx      base and quote: 3-letter currency codes.
  venue   lowercase letters and digits, joined by single hyphens, at most 40 characters.
  market_type per asset class: crypto spot/perp/future/option; equity cash; fx spot.

Not done here: alias rewriting. Non-canonical input is rejected, never silently corrected.

LEGACY FORM LIMITATION. The legacy form "<venue>-<market_type>:<BASE>-<QUOTE>" carries no asset class.
It is interpreted as crypto ONLY by the explicit function parse_legacy_crypto_listing(). The generic
parse_listing() refuses legacy-form IDs, so an ambiguous ID such as "nasdaq-spot:AAPL-USD" can never be
silently read as a crypto listing. Equity and FX listings must use the canonical form.

VENUE / MARKET-TYPE SPLIT. In both the canonical and legacy forms, the venue-and-market head is split at
its LAST hyphen. The final segment is the market type; everything before it is the venue, which may
itself contain hyphens. Examples:
    binance-spot          venue "binance",     market type "spot"
    binance-us-spot       venue "binance-us",  market type "spot"
    binance-spot-perp     venue "binance-spot", market type "perp"   (a venue may contain a market-type
                                                                      word; the last segment still decides)
Market types never contain hyphens, so the split is always deterministic.
"""
import json
import re
from dataclasses import dataclass

ASSET_CLASSES = ("crypto", "equity", "fx")
MARKET_TYPES = {
    "crypto": ("spot", "perp", "future", "option"),
    "equity": ("cash",),
    "fx": ("spot",),
}
LEGACY_ASSET_CLASS = "crypto"
MAX_VENUE_LENGTH = 40


class IdentityError(ValueError):
    """An instrument or listing identity is invalid. Nothing is coerced or aliased."""


_VENUE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_CRYPTO_SYMBOL = re.compile(r"[A-Z0-9]{1,15}")
_EQUITY_TICKER = re.compile(r"[A-Z]{1,5}")
_CURRENCY = re.compile(r"[A-Z]{3}")
_PAIR = re.compile(r"([A-Z0-9]+)-([A-Z0-9]+)")


def _text(name, value):
    if not isinstance(value, str):
        raise IdentityError(f"{name} must be text, not {type(value).__name__}")
    return value


def _validate_asset_class(asset_class):
    _text("asset class", asset_class)
    if asset_class not in ASSET_CLASSES:
        raise IdentityError(f"unknown asset class {asset_class!r}; expected one of {ASSET_CLASSES}")


def _validate_symbols(asset_class, base, quote):
    _text("base", base)
    _text("quote", quote)
    if asset_class == "crypto":
        for role, value in (("base", base), ("quote", quote)):
            if not _CRYPTO_SYMBOL.fullmatch(value) or not any("A" <= ch <= "Z" for ch in value):
                raise IdentityError(f"crypto {role} {value!r} must be 1-15 characters of A-Z or 0-9 "
                                    "with at least one letter")
    elif asset_class == "equity":
        if not _EQUITY_TICKER.fullmatch(base):
            raise IdentityError(f"equity ticker {base!r} must be 1-5 letters A-Z (no dots or digits)")
        if not _CURRENCY.fullmatch(quote):
            raise IdentityError(f"equity quote {quote!r} must be a 3-letter currency code")
    else:  # fx
        for role, value in (("base", base), ("quote", quote)):
            if not _CURRENCY.fullmatch(value):
                raise IdentityError(f"fx {role} {value!r} must be a 3-letter currency code")
    if base == quote:
        raise IdentityError("base and quote must differ")


def _validate_venue(venue):
    _text("venue", venue)
    if len(venue) > MAX_VENUE_LENGTH or not _VENUE.fullmatch(venue):
        raise IdentityError(f"venue {venue!r} must be lowercase letters and digits joined by single "
                            f"hyphens, at most {MAX_VENUE_LENGTH} characters")


def _validate_market_type(asset_class, market_type):
    _text("market type", market_type)
    allowed = MARKET_TYPES[asset_class]
    if market_type not in allowed:
        raise IdentityError(f"market type {market_type!r} is not valid for {asset_class}; "
                            f"expected one of {allowed}")


def _exact_keys(data, keys, what):
    if not isinstance(data, dict):
        raise IdentityError(f"{what} must be a JSON object")
    if set(data) != set(keys):
        raise IdentityError(f"{what} must have exactly the keys {sorted(keys)}")
    return data


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Instrument:
    """What is traded, independent of venue. Equal instruments compare equal everywhere."""

    asset_class: str
    base: str
    quote: str

    def __post_init__(self):
        _validate_asset_class(self.asset_class)
        _validate_symbols(self.asset_class, self.base, self.quote)

    @property
    def canonical(self):
        return f"{self.asset_class}:{self.base}-{self.quote}"

    def to_dict(self):
        return {"asset_class": self.asset_class, "base": self.base, "quote": self.quote}

    def to_json(self):
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data):
        return cls(**_exact_keys(data, ("asset_class", "base", "quote"), "instrument"))


@dataclass(frozen=True)
class Listing:
    """An instrument traded at one venue as one market type."""

    instrument: Instrument
    venue: str
    market_type: str

    def __post_init__(self):
        if not isinstance(self.instrument, Instrument):
            raise IdentityError("a listing needs an Instrument")
        _validate_venue(self.venue)
        _validate_market_type(self.instrument.asset_class, self.market_type)

    @property
    def canonical(self):
        i = self.instrument
        return f"{i.asset_class}:{self.venue}-{self.market_type}:{i.base}-{i.quote}"

    def to_legacy(self):
        """The P1 form. Exists only for crypto listings; other asset classes have no legacy form."""
        i = self.instrument
        if i.asset_class != LEGACY_ASSET_CLASS:
            raise IdentityError(f"the legacy form exists only for {LEGACY_ASSET_CLASS} listings")
        return f"{self.venue}-{self.market_type}:{i.base}-{i.quote}"

    def to_dict(self):
        i = self.instrument
        return {"asset_class": i.asset_class, "base": i.base, "market_type": self.market_type,
                "quote": i.quote, "venue": self.venue}

    def to_json(self):
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, data):
        d = _exact_keys(data, ("asset_class", "base", "market_type", "quote", "venue"), "listing")
        return cls(Instrument(d["asset_class"], d["base"], d["quote"]), d["venue"], d["market_type"])


def _instrument_from_pair(asset_class, pair):
    _validate_asset_class(asset_class)
    _text("pair", pair)
    m = _PAIR.fullmatch(pair)
    if not m:
        raise IdentityError(f"pair {pair!r} must look like '<BASE>-<QUOTE>'")
    return Instrument(asset_class, m.group(1), m.group(2))


def parse_instrument(text):
    """Parses '<asset_class>:<BASE>-<QUOTE>' and refuses anything not in exact canonical form."""
    _text("instrument", text)
    parts = text.split(":")
    if len(parts) != 2:
        raise IdentityError("instrument must look like '<asset_class>:<BASE>-<QUOTE>'")
    instrument = _instrument_from_pair(parts[0], parts[1])
    if instrument.canonical != text:
        raise IdentityError(f"instrument {text!r} is not in canonical form")
    return instrument


def _split_head(head):
    """Splits 'venue-market_type' at the LAST hyphen. Market types have no hyphens, so the final
    segment is always the market type, and everything before it is the venue."""
    _text("venue-and-market head", head)
    if "-" not in head:
        raise IdentityError(f"{head!r} must be '<venue>-<market_type>' with a hyphen between them")
    venue, market_type = head.rsplit("-", 1)
    return venue, market_type


def parse_listing(text):
    """Parses the CANONICAL listing form only: '<asset_class>:<venue>-<market_type>:<BASE>-<QUOTE>'.

    Example: 'crypto:binance-us-spot:BTC-USD' -> venue 'binance-us', market type 'spot'.

    Legacy IDs ('binance-spot:BTC-USDT') are REFUSED here. The legacy form has no asset class, so it
    cannot be parsed safely by a generic parser. Use parse_legacy_crypto_listing() for legacy crypto IDs.
    The input must reproduce exactly from the parsed fields, or it is refused.
    """
    _text("listing", text)
    parts = text.split(":")
    if len(parts) == 2:
        raise IdentityError(f"{text!r} is in the legacy form, which has no asset class; use "
                            "parse_legacy_crypto_listing() for legacy crypto IDs")
    if len(parts) != 3:
        raise IdentityError("canonical listing must look like '<asset_class>:<venue>-<market_type>:<BASE>-<QUOTE>'")
    asset_class, head, pair = parts
    venue, market_type = _split_head(head)
    listing = Listing(_instrument_from_pair(asset_class, pair), venue, market_type)
    if listing.canonical != text:
        raise IdentityError(f"listing {text!r} is not in canonical form")
    return listing


def parse_legacy_crypto_listing(text):
    """Parses the P1 legacy form '<venue>-<market_type>:<BASE>-<QUOTE>' as a CRYPTO listing.

    This is the only place that assigns the crypto asset class to a legacy ID, and it is explicit by name.
    Example: 'binance-us-spot:BTC-USD' -> crypto listing, venue 'binance-us', market type 'spot'.
    The input must reproduce exactly through Listing.to_legacy(), or it is refused.
    """
    _text("legacy listing", text)
    parts = text.split(":")
    if len(parts) != 2:
        raise IdentityError("legacy listing must look like '<venue>-<market_type>:<BASE>-<QUOTE>'")
    head, pair = parts
    venue, market_type = _split_head(head)
    listing = Listing(_instrument_from_pair(LEGACY_ASSET_CLASS, pair), venue, market_type)
    if listing.to_legacy() != text:
        raise IdentityError(f"legacy listing {text!r} is not in exact legacy form")
    return listing
