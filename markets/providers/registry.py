"""markets/providers/registry.py - explicit provider registry (M4b).

Selection is by name, supplied by the caller. Nothing is chosen automatically, and a failed provider is never replaced
by another one. Adding a provider means adding one entry here, with its own adapter module.
"""
from markets.providers.binance_vision import BinanceVision
from markets.providers.kraken import Kraken

PROVIDERS = {
    BinanceVision.info.name: BinanceVision,
    Kraken.info.name: Kraken,
}


class UnknownProviderError(ValueError):
    """The requested provider name is not in the registry. Raised before any adapter or transport is used."""


def provider_names():
    return tuple(sorted(PROVIDERS))


def select_provider(name):
    """Returns a new adapter instance for exactly this name. Matching is exact; no normalization, no defaults."""
    if not isinstance(name, str) or name not in PROVIDERS:
        raise UnknownProviderError(f"no provider named {name!r}; registered providers: {', '.join(provider_names())}")
    return PROVIDERS[name]()
