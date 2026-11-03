"""markets/providers/symbols.py - explicit provider symbol tables.

Keys are canonical listing identities (S2 Listing.canonical). Values are the exact provider symbols.
A listing that is not in a table is unsupported. Symbols are never derived by string replacement: some
exchanges list the same asset under a different code, so the table is the only source.
"""

BINANCE_VISION = {
    "crypto:binance-spot:BTC-USDT": "BTCUSDT",
}

KRAKEN = {
    "crypto:kraken-spot:BTC-USD": "XBTUSD",     # Kraken lists bitcoin as XBT
}
