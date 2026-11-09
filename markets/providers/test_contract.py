"""Offline tests for the provider-neutral contract. No network: every transport is a deterministic fixture,
and urllib.request.urlopen is patched to fail if anything reaches it.

Run from the repository root with:
    python3 -B -m unittest discover -s markets -p "test_*.py"
"""
import ast
import os
import unittest
import urllib.error
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in __import__("sys").path:
    __import__("sys").path.insert(0, _ROOT)

from markets import candles as mc  # noqa: E402
from markets.identity import parse_listing  # noqa: E402
from markets.providers import FetchResult, ProviderError, ProviderInfo  # noqa: E402
from markets.providers import normalize as nz  # noqa: E402
from markets.providers import synthetic as syn  # noqa: E402
from markets.providers import transport as tr  # noqa: E402
from markets.providers.binance_vision import BinanceVision  # noqa: E402
from markets.providers.kraken import Kraken  # noqa: E402

DAY = 86400
T0 = 1609459200
NOW = T0 + 200 * DAY + 3600
END = (NOW // DAY) * DAY - DAY
START = END - 118 * DAY
KRAKEN_LISTING = "crypto:kraken-spot:BTC-USD"
BINANCE_LISTING = "crypto:binance-spot:BTC-USDT"


class ErrorTests(unittest.TestCase):
    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            ProviderError("exploded", "kraken", "x")

    def test_retriable_flag_and_structured_dict(self):
        e = ProviderError("rate_limited", "kraken", "slow down", http_status=429)
        self.assertTrue(e.retriable)
        self.assertEqual(e.to_dict(), {"kind": "rate_limited", "provider": "kraken", "detail": "slow down",
                                       "http_status": 429, "retriable": True})
        self.assertFalse(ProviderError("bad_payload", "kraken", "x").retriable)

    def test_all_failure_kinds_are_known_and_only_transient_ones_are_retriable(self):
        from markets.providers.errors import KINDS, RETRIABLE_KINDS
        self.assertEqual(set(RETRIABLE_KINDS), {"rate_limited", "timeout", "unavailable"})
        for kind in KINDS:
            ProviderError(kind, "p", "d")                 # each kind constructs


class ProviderInfoTests(unittest.TestCase):
    def valid(self, **overrides):
        kw = dict(name="kraken", venue="kraken", docs_url="https://docs.example.org/x",
                  terms_source="unverified", auth="none")
        kw.update(overrides)
        return ProviderInfo(**kw)

    def test_valid_info_round_trips(self):
        self.assertEqual(self.valid().to_dict()["venue"], "kraken")

    def test_bad_name_and_venue_tokens_are_rejected(self):
        for bad in ("Kraken", "binance vision", "", "a--b", "x" * 41):
            with self.subTest(name=bad):
                with self.assertRaises(ValueError):
                    self.valid(name=bad)

    def test_only_unauthenticated_providers_are_allowed_in_m4a(self):
        with self.assertRaises(ValueError):
            self.valid(auth="api-key")

    def test_docs_must_be_https_and_terms_must_be_stated(self):
        with self.assertRaises(ValueError):
            self.valid(docs_url="http://insecure.example.org")
        with self.assertRaises(ValueError):
            self.valid(terms_source="")


class ChunkingTests(unittest.TestCase):
    def test_single_window_when_range_fits(self):
        self.assertEqual(nz.chunk_windows(START, END, DAY, 720), [(START, END)])

    def test_exactly_720_slots_is_one_window(self):
        end = START + 719 * DAY
        self.assertEqual(nz.chunk_windows(START, end, DAY, 720), [(START, end)])

    def test_721_slots_split_into_two_contiguous_windows(self):
        end = START + 720 * DAY
        windows = nz.chunk_windows(START, end, DAY, 720)
        self.assertEqual(windows, [(START, START + 719 * DAY), (START + 720 * DAY, end)])

    def test_1500_slots_give_720_720_60_without_gaps_or_overlap(self):
        end = START + 1499 * DAY
        windows = nz.chunk_windows(START, end, DAY, 720)
        self.assertEqual([(e - s) // DAY + 1 for s, e in windows], [720, 720, 60])
        for (s1, e1), (s2, _) in zip(windows, windows[1:]):
            self.assertEqual(s2, e1 + DAY)

    def test_invalid_max_candles_is_rejected(self):
        with self.assertRaises(ValueError):
            nz.chunk_windows(START, END, DAY, 0)


class NormalizeTests(unittest.TestCase):
    def row(self, t, close=20010.0):
        return (t, 20000.0, 20015.0, 19995.0, close, 100.0)

    def test_sorts_and_returns_canonical_candles(self):
        rows = [self.row(START + DAY), self.row(START)]
        candles, stats = nz.normalize_rows(rows, START, START + DAY, NOW, DAY, "p")
        self.assertIsInstance(candles[0], mc.Candle)
        self.assertEqual([c.open_time_s for c in candles], [START, START + DAY])
        self.assertEqual(stats, {"forming_dropped": 0, "duplicates_removed": 0, "out_of_window_dropped": 0})

    def test_exact_duplicates_are_removed_and_counted(self):
        rows = [self.row(START), self.row(START)]
        candles, stats = nz.normalize_rows(rows, START, START, NOW, DAY, "p")
        self.assertEqual(len(candles), 1)
        self.assertEqual(stats["duplicates_removed"], 1)

    def test_conflicting_duplicates_refuse(self):
        rows = [self.row(START, 20010.0), self.row(START, 20011.0)]
        with self.assertRaises(ProviderError) as cm:
            nz.normalize_rows(rows, START, START, NOW, DAY, "p")
        self.assertEqual(cm.exception.kind, "conflicting_duplicate")

    def test_only_one_forming_candle_is_allowed_and_it_is_dropped(self):
        forming = (END + DAY, 20000.0, 20015.0, 19995.0, 20010.0, 1.0)
        candles, stats = nz.normalize_rows([self.row(END), forming], END, END + DAY, NOW, DAY, "p")
        self.assertEqual([c.open_time_s for c in candles], [END])
        self.assertEqual(stats["forming_dropped"], 1)

    def test_two_forming_candles_are_bad_payload(self):
        f1 = (END + DAY, 20000.0, 20015.0, 19995.0, 20010.0, 1.0)
        f2 = (END + 2 * DAY, 20000.0, 20015.0, 19995.0, 20010.0, 1.0)
        with self.assertRaises(ProviderError) as cm:
            nz.normalize_rows([f1, f2], END, END + 2 * DAY, NOW, DAY, "p")
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_rows_outside_the_window_are_trimmed_and_counted(self):
        rows = [self.row(START - DAY), self.row(START), self.row(END + DAY - DAY)]
        candles, stats = nz.normalize_rows(rows, START, START, NOW, DAY, "p")
        self.assertEqual([c.open_time_s for c in candles], [START])
        self.assertEqual(stats["out_of_window_dropped"], 2)

    def test_misaligned_open_time_is_bad_payload(self):
        with self.assertRaises(ProviderError) as cm:
            nz.normalize_rows([self.row(START + 60)], START, START + DAY, NOW, DAY, "p")
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_invalid_ohlc_is_bad_payload(self):
        with self.assertRaises(ProviderError) as cm:
            nz.normalize_rows([(START, 20000.0, 19000.0, 19995.0, 20010.0, 1.0)], START, START, NOW, DAY, "p")
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_malformed_row_shapes_are_structured_bad_payload_errors(self):
        for rows in ([None], [()], [(START, 1, 2, 3, 4)], [(START, 1, 2, 3, 4, 5, 6)], ["abcdef"], [{}]):
            with self.subTest(rows=rows):
                with self.assertRaises(ProviderError) as cm:
                    nz.normalize_rows(rows, START, START, NOW, DAY, "p")
                self.assertEqual(cm.exception.kind, "bad_payload")

    def test_non_iterable_rows_are_structured_bad_payload_errors(self):
        for rows in (None, 1, True):
            with self.subTest(rows=rows):
                with self.assertRaises(ProviderError) as cm:
                    nz.normalize_rows(rows, START, START, NOW, DAY, "p")
                self.assertEqual(cm.exception.kind, "bad_payload")

    def test_numeric_conversion_errors_are_structured_bad_payload_errors(self):
        rows = [(START, 10 ** 10000, 2, 1, 1.5, 1)]
        with self.assertRaises(ProviderError) as cm:
            nz.normalize_rows(rows, START, START, NOW, DAY, "p")
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_gaps_are_never_filled(self):
        rows = [self.row(START), self.row(START + 2 * DAY)]
        candles, _ = nz.normalize_rows(rows, START, START + 2 * DAY, NOW, DAY, "p")
        self.assertEqual([c.open_time_s for c in candles], [START, START + 2 * DAY])


class AdapterNumericOverflowTests(unittest.TestCase):
    def test_binance_numeric_overflow_is_structured_bad_payload(self):
        row = [START * 1000, 10 ** 400, 10 ** 400, 1, 2, 1, (START + DAY) * 1000 - 1]
        body = __import__("json").dumps([row]).encode("utf-8")
        with self.assertRaises(ProviderError) as cm:
            BinanceVision().parse_chunk(body, DAY)
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_kraken_numeric_overflow_is_structured_bad_payload(self):
        row = [START, 10 ** 400, 10 ** 400, 1, 2, 1, 1, 1]
        body = __import__("json").dumps({"error": [], "result": {"XXBTZUSD": [row], "last": 0}}).encode("utf-8")
        with self.assertRaises(ProviderError) as cm:
            Kraken().parse_chunk(body, DAY)
        self.assertEqual(cm.exception.kind, "bad_payload")


class ListingAndIntervalTests(unittest.TestCase):
    def test_unmapped_listing_is_unsupported_even_if_derivable(self):
        k = Kraken()
        eth = parse_listing("crypto:kraken-spot:ETH-USD")
        with self.assertRaises(ProviderError) as cm:
            k.provider_symbol(eth)
        self.assertEqual(cm.exception.kind, "unsupported_listing")

    def test_other_venue_is_unsupported(self):
        with self.assertRaises(ProviderError) as cm:
            Kraken().check_request(parse_listing(BINANCE_LISTING), DAY)
        self.assertEqual(cm.exception.kind, "unsupported_listing")

    def test_unoffered_interval_is_unsupported(self):
        with self.assertRaises(ProviderError) as cm:
            Kraken().check_request(parse_listing(KRAKEN_LISTING), 3600)
        self.assertEqual(cm.exception.kind, "unsupported_interval")

    def test_supports_reports_without_raising(self):
        k = Kraken()
        self.assertTrue(k.supports(parse_listing(KRAKEN_LISTING), DAY))
        self.assertFalse(k.supports(parse_listing(BINANCE_LISTING), DAY))
        self.assertFalse(k.supports(parse_listing(KRAKEN_LISTING), 3600))

    def test_unsupported_requests_never_call_the_transport(self):
        for provider, listing, tf in ((Kraken(), BINANCE_LISTING, DAY), (Kraken(), KRAKEN_LISTING, 3600),
                                      (BinanceVision(), KRAKEN_LISTING, DAY)):
            with self.subTest(provider=provider.info.name, listing=listing, tf=tf):
                t = syn.ScriptedTransport(lambda url: b"[]")
                with self.assertRaises(ProviderError):
                    provider.fetch_candles(parse_listing(listing), tf, START, END, NOW, transport=t)
                self.assertEqual(t.urls, [])


class FetchContractTests(unittest.TestCase):
    def test_unaligned_range_is_a_caller_error(self):
        with self.assertRaises(ValueError):
            Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START + 5, END, NOW,
                                   transport=lambda u: b"")

    def test_non_bytes_transport_result_is_bad_payload(self):
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW,
                                   transport=lambda u: "not bytes")
        self.assertEqual(cm.exception.kind, "bad_payload")

    def test_transport_failure_becomes_structured_provider_error(self):
        def boom(url):
            raise tr.TransportFailure("rate_limited", "HTTP 429", 429)
        with self.assertRaises(ProviderError) as cm:
            Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW, transport=boom)
        self.assertEqual((cm.exception.kind, cm.exception.http_status), ("rate_limited", 429))
        self.assertTrue(cm.exception.retriable)

    def test_transport_failure_kind_must_be_known(self):
        with self.assertRaises(ValueError):
            tr.TransportFailure("explode", "x")

    def test_fetch_result_reports_provider_identity_and_binds_raw_bytes(self):
        rows = syn.series(START, 119, DAY)
        body = syn.kraken_body(rows)
        t = syn.ScriptedTransport(lambda url: body)
        r = Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW, transport=t)
        self.assertIsInstance(r, FetchResult)
        self.assertEqual(r.provider.name, "kraken")
        self.assertEqual(r.requests_made, 1)
        self.assertRegex(r.raw_sha256, r"^[0-9a-f]{64}$")
        # identical bytes and URL give the identical fingerprint; a changed byte changes it
        r2 = Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW,
                                    transport=syn.ScriptedTransport(lambda url: body))
        self.assertEqual(r.raw_sha256, r2.raw_sha256)
        changed = body.replace(b"20003.0", b"20003.5", 1)
        r3 = Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW,
                                    transport=syn.ScriptedTransport(lambda url: changed))
        self.assertNotEqual(r.raw_sha256, r3.raw_sha256)

    def test_empty_response_is_structured_empty(self):
        with self.assertRaises(ProviderError) as cm:
            BinanceVision().fetch_candles(parse_listing(BINANCE_LISTING), DAY, START, END, NOW,
                                          transport=lambda u: b"[]")
        self.assertEqual(cm.exception.kind, "empty")


class LiveTransportMappingTests(unittest.TestCase):
    """Every case patches urlopen. Nothing reaches the network."""

    def test_http_429_maps_to_rate_limited_with_status(self):
        err = urllib.error.HTTPError("https://x", 429, "Too Many", None, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(tr.TransportFailure) as cm:
                tr.live_transport("https://x")
        self.assertEqual((cm.exception.kind, cm.exception.status), ("rate_limited", 429))

    def test_other_http_status_maps_to_unavailable(self):
        err = urllib.error.HTTPError("https://x", 503, "Unavailable", None, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(tr.TransportFailure) as cm:
                tr.live_transport("https://x")
        self.assertEqual((cm.exception.kind, cm.exception.status), ("unavailable", 503))

    def test_timeout_maps_to_timeout(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("slow")):
            with self.assertRaises(tr.TransportFailure) as cm:
                tr.live_transport("https://x")
        self.assertEqual(cm.exception.kind, "timeout")

    def test_url_error_maps_to_unavailable(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(OSError("refused"))):
            with self.assertRaises(tr.TransportFailure) as cm:
                tr.live_transport("https://x")
        self.assertEqual(cm.exception.kind, "unavailable")


class NoNetworkTests(unittest.TestCase):
    def test_a_full_fixture_fetch_never_touches_urlopen(self):
        body = syn.kraken_body(syn.series(START, 119, DAY))
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network used")):
            r = Kraken().fetch_candles(parse_listing(KRAKEN_LISTING), DAY, START, END, NOW,
                                       transport=syn.ScriptedTransport(lambda url: body))
        self.assertEqual(len(r.candles), 119)


class BoundaryTests(unittest.TestCase):
    PROVIDER_DIR = os.path.dirname(os.path.abspath(__file__))
    FORBIDDEN_IMPORTS = ("urllib.request", "socket", "http", "ssl", "requests")
    MARKET_NAMES = ("BTC", "Binance", "binance", "Kraken", "kraken", "XBT", "USDT")

    def tree(self, name):
        with open(os.path.join(self.PROVIDER_DIR, name), encoding="utf-8") as f:
            return ast.parse(f.read())

    def imported_modules(self, tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
        return names

    def test_only_the_transport_module_may_reach_the_network(self):
        for name in ("__init__.py", "normalize.py", "errors.py", "symbols.py", "binance_vision.py", "kraken.py",
                     "synthetic.py"):
            with self.subTest(file=name):
                mods = self.imported_modules(self.tree(name))
                for bad in self.FORBIDDEN_IMPORTS:
                    self.assertFalse(any(m == bad or m.startswith(bad + ".") for m in mods), (name, mods))

    def test_shared_contract_modules_do_not_hardcode_market_or_provider_names(self):
        for name in ("__init__.py", "normalize.py", "errors.py"):
            with self.subTest(file=name):
                for node in ast.walk(self.tree(name)):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        for word in self.MARKET_NAMES:
                            self.assertNotIn(word, node.value, (name, node.value[:60]))


if __name__ == "__main__":
    unittest.main()
