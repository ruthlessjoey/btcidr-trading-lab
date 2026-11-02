"""Offline tests for markets/identity.py. No network, no repository data. Run from the repository root:
    python3 -B -m unittest discover -s markets -p "test_*.py"
"""
import json
import unittest

from markets import identity as mi


class InstrumentTests(unittest.TestCase):
    def test_equality_and_hash_are_venue_free(self):
        a = mi.Instrument("crypto", "BTC", "USDT")
        b = mi.Instrument("crypto", "BTC", "USDT")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, mi.Instrument("crypto", "BTC", "USD"))
        self.assertNotEqual(a, mi.Instrument("equity", "BTC", "USD"))

    def test_canonical_form_for_each_asset_class(self):
        self.assertEqual(mi.Instrument("crypto", "BTC", "USDT").canonical, "crypto:BTC-USDT")
        self.assertEqual(mi.Instrument("equity", "AAPL", "USD").canonical, "equity:AAPL-USD")
        self.assertEqual(mi.Instrument("fx", "EUR", "USD").canonical, "fx:EUR-USD")

    def test_parse_round_trip(self):
        for text in ("crypto:BTC-USDT", "crypto:1INCH-USDT", "equity:AAPL-USD", "fx:EUR-USD"):
            with self.subTest(text=text):
                self.assertEqual(mi.parse_instrument(text).canonical, text)

    def test_dict_and_json_round_trip(self):
        inst = mi.Instrument("fx", "EUR", "USD")
        self.assertEqual(mi.Instrument.from_dict(inst.to_dict()), inst)
        self.assertEqual(inst.to_json(), '{"asset_class":"fx","base":"EUR","quote":"USD"}')

    def test_invalid_instruments_are_refused(self):
        bad = [
            ("stock", "AAPL", "USD"),          # unknown asset class
            ("Crypto", "BTC", "USDT"),         # case matters
            ("", "BTC", "USDT"),
            ("crypto", "btc", "USDT"),         # lowercase
            ("crypto", "BTC", ""),             # empty quote
            ("crypto", "BTC", "USD-T"),        # hyphen inside a token
            ("crypto", "BTC", "BTC"),          # base equals quote
            ("crypto", "BT C", "USDT"),        # space
            ("crypto", "-", "USDT"),
            ("equity", "AAPL", "USDT"),        # equity quote must be a 3-letter currency
            ("equity", "BRK.B", "USD"),        # dotted ticker
            ("equity", "AAPL1", "USD"),        # digit in equity ticker
            ("equity", "TOOLONGX", "USD"),     # ticker over 5 letters
            ("fx", "EURUSD", "USD"),           # fx base not 3 letters
            ("fx", "EUR", "usd"),              # lowercase currency
            ("fx", "EUR", "US"),
            ("crypto", None, "USDT"),          # non-text
            (None, "BTC", "USDT"),
            ("crypto", 5, "USDT"),
        ]
        for asset_class, base, quote in bad:
            with self.subTest(args=(asset_class, base, quote)):
                with self.assertRaises(mi.IdentityError):
                    mi.Instrument(asset_class, base, quote)

    def test_parse_refuses_non_canonical_text(self):
        for text in (" crypto:BTC-USDT", "crypto:BTC-USDT ", "crypto:btc-usdt", "crypto/BTC-USDT",
                     "crypto:BTC-USDT:x", "crypto:BTC", "BTC-USDT", "", "crypto:BTC_USDT"):
            with self.subTest(text=text):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_instrument(text)

    def test_from_dict_requires_exact_keys(self):
        with self.assertRaises(mi.IdentityError):
            mi.Instrument.from_dict({"asset_class": "fx", "base": "EUR"})
        with self.assertRaises(mi.IdentityError):
            mi.Instrument.from_dict({"asset_class": "fx", "base": "EUR", "quote": "USD", "x": 1})
        with self.assertRaises(mi.IdentityError):
            mi.Instrument.from_dict(["fx", "EUR", "USD"])


class ListingTests(unittest.TestCase):
    def test_listing_canonical_form(self):
        listing = mi.Listing(mi.Instrument("crypto", "BTC", "USDT"), "binance", "spot")
        self.assertEqual(listing.canonical, "crypto:binance-spot:BTC-USDT")

    def test_same_instrument_different_venues_share_instrument_but_not_listing(self):
        inst = mi.Instrument("crypto", "BTC", "USDT")
        a = mi.Listing(inst, "binance", "spot")
        b = mi.Listing(inst, "kraken", "spot")
        self.assertEqual(a.instrument, b.instrument)
        self.assertNotEqual(a, b)

    def test_valid_market_types_per_asset_class(self):
        cases = [("crypto", "spot"), ("crypto", "perp"), ("crypto", "future"), ("crypto", "option"),
                 ("equity", "cash"), ("fx", "spot")]
        for asset_class, market_type in cases:
            with self.subTest(asset_class=asset_class, market_type=market_type):
                inst = mi.Instrument(asset_class, "AAPL" if asset_class == "equity" else "EUR",
                                     "USD")
                mi.Listing(inst, "nasdaq" if asset_class == "equity" else "binance", market_type)

    def test_invalid_listings_are_refused(self):
        btc = mi.Instrument("crypto", "BTC", "USDT")
        aapl = mi.Instrument("equity", "AAPL", "USD")
        cases = [
            (btc, "Binance", "spot"),          # uppercase venue
            (btc, "binance_us", "spot"),       # underscore
            (btc, "-binance", "spot"),
            (btc, "binance--us", "spot"),      # double hyphen
            (btc, "binance spot", "spot"),
            (btc, "", "spot"),
            (btc, "x" * 41, "spot"),           # too long
            (btc, "binance", "margin"),        # unknown market type
            (btc, "binance", "cash"),          # cash is equity-only
            (aapl, "nasdaq", "spot"),          # spot is not an equity market type
            (aapl, "nasdaq", "perp"),
            (btc, "binance", None),
            ("BTC-USDT", "binance", "spot"),   # not an Instrument
        ]
        for inst, venue, market_type in cases:
            with self.subTest(venue=venue, market_type=market_type):
                with self.assertRaises(mi.IdentityError):
                    mi.Listing(inst, venue, market_type)

    def test_listing_json_is_deterministic(self):
        listing = mi.Listing(mi.Instrument("crypto", "BTC", "USDT"), "binance", "spot")
        expected = ('{"asset_class":"crypto","base":"BTC","market_type":"spot",'
                    '"quote":"USDT","venue":"binance"}')
        self.assertEqual(listing.to_json(), expected)
        self.assertEqual(listing.to_json(), mi.Listing.from_dict(listing.to_dict()).to_json())
        self.assertEqual(mi.Listing.from_dict(listing.to_dict()), listing)

    def test_listing_from_dict_round_trip(self):
        listing = mi.Listing(mi.Instrument("equity", "AAPL", "USD"), "nasdaq", "cash")
        self.assertEqual(mi.Listing.from_dict(listing.to_dict()), listing)

    def test_listing_from_dict_refuses_missing_keys(self):
        full = mi.Listing(mi.Instrument("crypto", "BTC", "USDT"), "binance", "spot").to_dict()
        for key in full:
            data = dict(full)
            del data[key]
            with self.subTest(missing=key):
                with self.assertRaises(mi.IdentityError):
                    mi.Listing.from_dict(data)

    def test_listing_from_dict_refuses_unexpected_keys(self):
        data = mi.Listing(mi.Instrument("crypto", "BTC", "USDT"), "binance", "spot").to_dict()
        data["extra"] = 1
        with self.assertRaises(mi.IdentityError):
            mi.Listing.from_dict(data)

    def test_listing_from_dict_refuses_non_object(self):
        for value in (["crypto", "binance", "spot"], "crypto:binance-spot:BTC-USDT", None):
            with self.subTest(value=value):
                with self.assertRaises(mi.IdentityError):
                    mi.Listing.from_dict(value)

    def test_listing_from_dict_still_validates_fields(self):
        data = {"asset_class": "equity", "base": "AAPL", "market_type": "spot",
                "quote": "USD", "venue": "nasdaq"}                 # spot is not an equity market type
        with self.assertRaises(mi.IdentityError):
            mi.Listing.from_dict(data)


class CanonicalParserTests(unittest.TestCase):
    def test_canonical_parse_round_trip(self):
        listing = mi.parse_listing("crypto:binance-spot:BTC-USDT")
        self.assertEqual(listing.canonical, "crypto:binance-spot:BTC-USDT")
        self.assertEqual(listing.instrument, mi.Instrument("crypto", "BTC", "USDT"))

    def test_generic_parser_refuses_legacy_ids(self):
        for text in ("binance-spot:BTC-USDT", "binance-us-spot:BTC-USD"):
            with self.subTest(text=text):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_listing(text)

    def test_generic_parser_refuses_ambiguous_legacy_ids_for_non_crypto(self):
        # The legacy form carries no asset class. The generic parser must not read these as crypto.
        for text in ("nasdaq-spot:AAPL-USD", "oanda-spot:EUR-USD", "nasdaq-cash:AAPL-USD"):
            with self.subTest(text=text):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_listing(text)

    def test_canonical_parser_refuses_bad_or_non_canonical_input(self):
        for text in ("stock:binance-spot:BTC-USDT", "Crypto:binance-spot:BTC-USDT",
                     "crypto:binance-spot:BTC-USDT:x", "crypto:binance:spot:BTC-USDT",
                     "crypto:Binance-spot:BTC-USDT", "crypto:binance-spot:btc-usdt",
                     " crypto:binance-spot:BTC-USDT", "crypto:binance-spot:BTC-USDT ",
                     "crypto:binance-margin:BTC-USDT", "equity:nasdaq-spot:AAPL-USD", ""):
            with self.subTest(text=text):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_listing(text)

    def test_parse_rejects_non_text(self):
        for value in (None, 5, b"crypto:binance-spot:BTC-USDT"):
            with self.subTest(value=value):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_listing(value)
                with self.assertRaises(mi.IdentityError):
                    mi.parse_instrument(value)


class LegacyCrypto(unittest.TestCase):
    """P1's legacy form, parsed ONLY by the explicit parse_legacy_crypto_listing(). P1 is not imported."""

    def test_explicit_legacy_crypto_parse_and_round_trip(self):
        listing = mi.parse_legacy_crypto_listing("binance-spot:BTC-USDT")
        self.assertEqual(listing.instrument, mi.Instrument("crypto", "BTC", "USDT"))
        self.assertEqual(listing.venue, "binance")
        self.assertEqual(listing.market_type, "spot")
        self.assertEqual(listing.to_legacy(), "binance-spot:BTC-USDT")

    def test_legacy_and_canonical_forms_describe_the_same_listing(self):
        legacy = mi.parse_legacy_crypto_listing("binance-spot:BTC-USDT")
        canonical = mi.parse_listing("crypto:binance-spot:BTC-USDT")
        self.assertEqual(legacy, canonical)
        self.assertEqual(canonical.canonical, "crypto:binance-spot:BTC-USDT")

    def test_venue_with_hyphen_is_split_at_last_hyphen(self):
        # 'binance-us-spot': the final segment before ':' is the market type ('spot');
        # the preceding segments form the venue ('binance-us').
        listing = mi.parse_legacy_crypto_listing("binance-us-spot:BTC-USD")
        self.assertEqual(listing.venue, "binance-us")
        self.assertEqual(listing.market_type, "spot")
        self.assertEqual(listing.to_legacy(), "binance-us-spot:BTC-USD")

    def test_venue_containing_a_market_type_word_is_still_split_at_last_hyphen(self):
        # 'binance-spot-perp': the venue is 'binance-spot', the market type is 'perp'.
        listing = mi.parse_legacy_crypto_listing("binance-spot-perp:BTC-USDT")
        self.assertEqual(listing.venue, "binance-spot")
        self.assertEqual(listing.market_type, "perp")
        self.assertEqual(listing.to_legacy(), "binance-spot-perp:BTC-USDT")

    def test_all_legacy_crypto_market_types_round_trip(self):
        for text in ("binance-perp:BTC-USDT", "binance-future:BTC-USDT", "deribit-option:BTC-USD"):
            with self.subTest(text=text):
                self.assertEqual(mi.parse_legacy_crypto_listing(text).to_legacy(), text)

    def test_explicit_legacy_parse_refuses_market_types_that_are_not_crypto(self):
        with self.assertRaises(mi.IdentityError):
            mi.parse_legacy_crypto_listing("nasdaq-cash:AAPL-USD")   # 'cash' is not a crypto market type

    def test_explicit_legacy_parse_refuses_malformed_ids(self):
        for text in ("binance-spot:btc-usdt",        # lowercase symbols
                     "Binance-spot:BTC-USDT",        # uppercase venue
                     "binance:BTC-USDT",             # no market type
                     "binance-spot:BTC-USDT:x",      # too many parts
                     "crypto:binance-spot:BTC-USDT", # canonical form, not legacy
                     " binance-spot:BTC-USDT",       # leading space
                     "binance-spot:BTCUSDT",         # no separator in pair
                     "binance-margin:BTC-USDT",      # unknown market type
                     "binance-spot:BTC-USDT ",       # trailing space
                     "",
                     "binance-spot"):                # no pair at all
            with self.subTest(text=text):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_legacy_crypto_listing(text)

    def test_explicit_legacy_parse_rejects_non_text(self):
        for value in (None, 5, b"binance-spot:BTC-USDT"):
            with self.subTest(value=value):
                with self.assertRaises(mi.IdentityError):
                    mi.parse_legacy_crypto_listing(value)

    def test_legacy_serialization_refused_for_non_crypto(self):
        # The legacy form cannot represent a non-crypto listing, so serialization is refused.
        with self.assertRaises(mi.IdentityError):
            mi.Listing(mi.Instrument("equity", "AAPL", "USD"), "nasdaq", "cash").to_legacy()
        with self.assertRaises(mi.IdentityError):
            mi.Listing(mi.Instrument("fx", "EUR", "USD"), "oanda", "spot").to_legacy()


class DeterminismTests(unittest.TestCase):
    def test_repeated_serialization_is_identical(self):
        listing = mi.parse_listing("crypto:binance-spot:BTC-USDT")
        outputs = {listing.to_json() for _ in range(5)}
        self.assertEqual(len(outputs), 1)

    def test_json_round_trip_is_stable(self):
        listing = mi.parse_listing("crypto:binance-spot:BTC-USDT")
        again = mi.Listing.from_dict(json.loads(listing.to_json()))
        self.assertEqual(again.to_json(), listing.to_json())


if __name__ == "__main__":
    unittest.main()
