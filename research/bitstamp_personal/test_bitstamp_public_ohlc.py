import json
import unittest
from urllib.parse import urlsplit

from bitstamp_public_ohlc import (
    BASE, BitstampDataError, _normalize_candle, _validate_url,
    fetch_json, fetch_spot_history, fetch_spot_markets,
)


class FakeResponse:
    status = 200

    def __init__(self, body, content_type="application/json"):
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def open(self, request, timeout=20):
        self.urls.append(request.full_url)
        if not self.responses:
            raise AssertionError("unexpected additional request")
        return self.responses.pop(0)


def candle(ts, *, open_="100", high="102", low="99", close="101", volume="10"):
    return {
        "timestamp": str(ts), "open": open_, "high": high,
        "low": low, "close": close, "volume": volume,
    }


def spot_market(symbol="btcusd", name="BTC/USD", base="BTC", quote="USD",
                trading="Enabled", matching="Enabled"):
    return {
        "market_symbol": symbol,
        "market_type": "SPOT",
        "name": name,
        "base_currency": base,
        "counter_currency": quote,
        "trading": trading,
        "matching": matching,
    }


class BitstampPublicOhlcTests(unittest.TestCase):
    def test_exact_host_and_endpoint_allowlist(self):
        self.assertEqual(_validate_url(BASE + "/markets/"), {"kind": "markets"})
        url = BASE + "/ohlc/btcusd/?step=3600&limit=1000&end=10&exclude_current_candle=true"
        self.assertEqual(_validate_url(url)["market_symbol"], "btcusd")
        for bad in (
            "http://www.bitstamp.net/api/v2/markets/",
            "https://api.bitstamp.net/api/v2/markets/",
            "https://www.bitstamp.com/api/v2/markets/",
            "https://www.bitstamp.net.evil.example/api/v2/markets/",
            "https://www.bitstamp.net/api/v2/private/",
            BASE + "/ohlc/btcusd/?step=60&limit=1000&end=10&exclude_current_candle=true",
            BASE + "/ohlc/btcusd/?step=3600&limit=1001&end=10&exclude_current_candle=true",
            BASE + "/ohlc/btcusd/?step=3600&limit=1000&end=10&exclude_current_candle=false",
            BASE + "/ohlc/btcusd/?step=3600&step=3600&limit=1000&end=10&exclude_current_candle=true",
        ):
            with self.subTest(url=bad), self.assertRaises(BitstampDataError):
                _validate_url(bad)

    def test_strict_json_rejects_duplicate_keys(self):
        opener = FakeOpener([FakeResponse('{"x":1,"x":2}')])
        with self.assertRaisesRegex(BitstampDataError, "duplicate JSON key"):
            fetch_json(BASE + "/markets/", opener=opener)

    def test_response_size_is_bounded(self):
        opener = FakeOpener([FakeResponse(b" " * (4 * 1024 * 1024 + 1))])
        with self.assertRaisesRegex(BitstampDataError, "oversized"):
            fetch_json(BASE + "/markets/", opener=opener)

    def test_market_list_filters_to_spot_and_valid_symbols(self):
        payload = [
            spot_market(),
            {"market_symbol": "btcusd-perp", "market_type": "FUTURES", "name": "BTC/USD Perpetual"},
            {"market_symbol": "../evil", "market_type": "SPOT", "name": "invalid"},
        ]
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        markets, digest = fetch_spot_markets(opener=opener)
        self.assertEqual(list(markets), ["btcusd"])
        self.assertEqual(markets["btcusd"]["market_type"], "SPOT")
        self.assertEqual(len(digest), 64)

    def test_market_list_rejects_duplicate_spot_symbols(self):
        payload = [
            spot_market(),
            spot_market(),
        ]
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        with self.assertRaisesRegex(BitstampDataError, "duplicate SPOT market"):
            fetch_spot_markets(opener=opener)

    def test_market_list_excludes_disabled_trading_or_matching(self):
        payload = [
            spot_market("btcusd"),
            spot_market("ethusd", "ETH/USD", "ETH", "USD", trading="Disabled"),
            spot_market("xrpusd", "XRP/USD", "XRP", "USD", matching="Disabled"),
        ]
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        markets, _ = fetch_spot_markets(opener=opener)
        self.assertEqual(list(markets), ["btcusd"])

    def test_market_list_rejects_inconsistent_market_identity(self):
        payload = [spot_market("btcusd", "ETH/USD", "BTC", "USD")]
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        with self.assertRaisesRegex(BitstampDataError, "identity do not agree"):
            fetch_spot_markets(opener=opener)

    def test_market_list_rejects_incomplete_identity_metadata(self):
        payload = [spot_market()]
        payload[0]["counter_currency"] = None
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        with self.assertRaisesRegex(BitstampDataError, "metadata is incomplete"):
            fetch_spot_markets(opener=opener)

    def test_candle_validation_rejects_bad_prices_and_volume(self):
        for row in (
            candle(3600, open_="0"),
            candle(3600, high="100", close="101"),
            candle(3600, low="102"),
            candle(3600, volume="-1"),
            candle(3601),
            {"timestamp": 3600.5, "open": "100", "high": "102", "low": "99", "close": "101", "volume": "10"},
            {"timestamp": "3600", "open": 100.5, "high": "102", "low": "99", "close": "101", "volume": "10"},
        ):
            with self.subTest(row=row), self.assertRaises(BitstampDataError):
                _normalize_candle(row, step=3600)

    def test_backward_pagination_returns_sorted_contiguous_closed_candles(self):
        first = {"data": {"pair": "BTC/USD", "ohlc": [candle(3 * 3600), candle(4 * 3600)]}}
        second = {"data": {"pair": "BTC/USD", "ohlc": [
            candle(0), candle(1 * 3600), candle(2 * 3600)
        ]}}
        opener = FakeOpener([FakeResponse(json.dumps(first)), FakeResponse(json.dumps(second))])
        dataset = fetch_spot_history(
            "btcusd", start_timestamp=0, end_timestamp=5 * 3600,
            opener=opener, sleep=lambda _: None,
        )
        self.assertEqual(dataset["row_count"], 5)
        self.assertEqual(dataset["coverage_status"], "CONTIGUOUS")
        self.assertEqual(dataset["gap_count"], 0)
        self.assertEqual(
            [row["open_timestamp"] for row in dataset["candles"]],
            [0, 3600, 7200, 10800, 14400],
        )
        self.assertEqual(dataset["last_close_timestamp"], 5 * 3600)
        self.assertEqual(dataset["page_count"], 2)
        self.assertEqual(len(dataset["dataset_sha256"]), 64)
        self.assertEqual(len(opener.urls), 2)
        self.assertTrue(all(urlsplit(url).hostname == "www.bitstamp.net" for url in opener.urls))

    def test_gap_is_reported_and_backtest_must_be_blocked(self):
        payload = {"data": {"pair": "BTC/USD", "ohlc": [candle(3600), candle(3 * 3600)]}}
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        dataset = fetch_spot_history(
            "btcusd", start_timestamp=3600, end_timestamp=4 * 3600,
            opener=opener, sleep=lambda _: None,
        )
        self.assertEqual(dataset["gap_count"], 1)
        self.assertEqual(dataset["coverage_status"], "GAPS_DETECTED_BACKTEST_BLOCKED")

    def test_backward_pagination_stops_after_crossing_start_boundary(self):
        recent = {
            "data": {"pair": "BTC/USD", "ohlc": [candle(3 * 3600), candle(4 * 3600)]}
        }
        older = {
            "data": {"pair": "BTC/USD", "ohlc": [candle(0), candle(3600)]}
        }
        opener = FakeOpener([FakeResponse(json.dumps(recent)), FakeResponse(json.dumps(older))])
        dataset = fetch_spot_history(
            "btcusd", start_timestamp=2 * 3600, end_timestamp=5 * 3600,
            opener=opener, sleep=lambda _: None,
        )
        self.assertEqual(dataset["page_count"], 2)
        self.assertEqual(dataset["row_count"], 2)
        self.assertEqual(dataset["gap_count"], 1)
        self.assertEqual(dataset["gaps"][0]["gap_type"], "LEADING")
        self.assertEqual(dataset["gaps"][0]["missing_hours"], 1)
        self.assertEqual(dataset["coverage_status"], "GAPS_DETECTED_BACKTEST_BLOCKED")

    def test_missing_range_boundaries_are_reported_as_gaps(self):
        first = {
            "data": {"pair": "BTC/USD", "ohlc": [candle(2 * 3600), candle(3 * 3600)]}
        }
        empty = {"data": {"pair": "BTC/USD", "ohlc": []}}
        opener = FakeOpener([FakeResponse(json.dumps(first)), FakeResponse(json.dumps(empty))])
        dataset = fetch_spot_history(
            "btcusd", start_timestamp=3600, end_timestamp=5 * 3600,
            opener=opener, sleep=lambda _: None,
        )
        self.assertEqual(dataset["gap_count"], 2)
        self.assertEqual(dataset["coverage_status"], "GAPS_DETECTED_BACKTEST_BLOCKED")
        self.assertEqual([gap["gap_type"] for gap in dataset["gaps"]], ["LEADING", "TRAILING"])
        self.assertEqual([gap["missing_hours"] for gap in dataset["gaps"]], [1, 1])

    def test_market_identity_must_remain_stable_across_pages(self):
        first = {"data": {"pair": "BTC/USD", "ohlc": [candle(3600), candle(7200)]}}
        second = {"data": {"pair": "ETH/USD", "ohlc": [candle(0)]}}
        opener = FakeOpener([FakeResponse(json.dumps(first)), FakeResponse(json.dumps(second))])
        with self.assertRaisesRegex(BitstampDataError, "identity changed between pages"):
            fetch_spot_history(
                "btcusd", start_timestamp=0, end_timestamp=3 * 3600,
                opener=opener, sleep=lambda _: None,
            )

    def test_requested_range_must_align_to_hourly_boundaries(self):
        opener = FakeOpener([])
        with self.assertRaisesRegex(BitstampDataError, "align to exact 1-hour"):
            fetch_spot_history(
                "btcusd", start_timestamp=1, end_timestamp=2 * 3600,
                opener=opener, sleep=lambda _: None,
            )
        self.assertEqual(opener.urls, [])

    def test_missing_market_identity_fails_closed(self):
        payload = {"data": {"ohlc": [candle(3600)]}}
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        with self.assertRaisesRegex(BitstampDataError, "market identity"):
            fetch_spot_history(
                "btcusd", start_timestamp=0, end_timestamp=2 * 3600,
                opener=opener, sleep=lambda _: None,
            )

    def test_empty_history_fails_closed(self):
        opener = FakeOpener([FakeResponse(json.dumps({"data": {"pair": "BTC/USD", "ohlc": []}}))])
        with self.assertRaisesRegex(BitstampDataError, "no closed OHLC"):
            fetch_spot_history(
                "btcusd", start_timestamp=0, end_timestamp=2 * 3600,
                opener=opener, sleep=lambda _: None,
            )

    def test_page_limit_is_enforced(self):
        rows = [candle((index + 1) * 3600) for index in range(1000)]
        payload = {"data": {"pair": "BTC/USD", "ohlc": rows}}
        opener = FakeOpener([FakeResponse(json.dumps(payload))])
        with self.assertRaisesRegex(BitstampDataError, "page limit"):
            fetch_spot_history(
                "btcusd", start_timestamp=0, end_timestamp=1002 * 3600,
                opener=opener, sleep=lambda _: None, max_pages=1,
            )


if __name__ == "__main__":
    unittest.main()
