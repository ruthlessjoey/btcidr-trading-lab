"""Offline tests for providers.py and live_check.py.

EVERYTHING HERE IS A SYNTHETIC FAKE EXCHANGE used only to test our code paths.
These prices are not market data, and passing these tests does not show that any
real exchange works. Only a real run of the workflow can show that.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import live_check  # noqa: E402
import providers  # noqa: E402
from fetcher import ApiError  # noqa: E402

NO_SLEEP = lambda s: None  # noqa: E731
NOW = 1_700_003_700          # 1h candles end exactly on multiples of 3600 before this
CFG = {"mode": "read_only", "timeframe": "1h", "lookback_days": 2, "max_missing_ratio": 0.02,
       "max_spike_pct": 10, "http_timeout_seconds": 5, "http_retries": 1, "min_verified": 1,
       "live_providers": ["kraken", "coinbase", "binance-vision", "tokocrypto"]}


def grid(start, end, step=3600):
    first = -(-start // step) * step
    return list(range(first, end + 1, step))


def px(t):
    return 1000.0 + (t // 3600) % 7


def fake(now, blocked=(), drop=()):
    """Fake hosts with each exchange's own layout. blocked hosts answer 451."""
    def opener(url, timeout):
        u = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(u.query)
        if u.hostname in blocked:
            return 451, b"unavailable"
        if u.path == "/0/public/Time":
            return 200, json.dumps({"error": [], "result": {"unixtime": now}}).encode()
        if u.path == "/0/public/OHLC":
            ts = [t for t in grid(int(q["since"][0]), now) if t not in drop]
            rows = [[t, str(px(t)), str(px(t) + 2), str(px(t) - 2), str(px(t) + 1),
                     "1000", "3.5", 10] for t in ts]
            return 200, json.dumps({"error": [], "result": {"XXBTZUSD": rows,
                                                           "last": ts[-1]}}).encode()
        if u.path == "/time":
            return 200, json.dumps({"iso": "x", "epoch": now + 0.355}).encode()
        if u.path.endswith("/candles"):
            g = int(q["granularity"][0])
            lo = int(__import__("datetime").datetime.strptime(q["start"][0], "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=__import__("datetime").timezone.utc).timestamp())
            hi = int(__import__("datetime").datetime.strptime(q["end"][0], "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=__import__("datetime").timezone.utc).timestamp())
            assert (hi - lo) // g < 300, "more than 300 candles requested"
            ts = [t for t in grid(lo, hi, g) if t not in drop]
            rows = [[t, px(t) - 2, px(t) + 2, px(t), px(t) + 1, 3.5] for t in reversed(ts)]
            return 200, json.dumps(rows).encode()
        if u.path == "/api/v3/time":
            return 200, json.dumps({"serverTime": now * 1000}).encode()
        if u.path == "/api/v3/klines":
            lo, hi = int(q["startTime"][0]) // 1000, int(q["endTime"][0]) // 1000
            ts = [t for t in grid(lo, hi) if t not in drop][:int(q["limit"][0])]
            rows = [[t * 1000, str(px(t)), str(px(t) + 2), str(px(t) - 2), str(px(t) + 1), "3.5",
                     t * 1000 + 3_599_999, "9", 5] for t in ts]
            return 200, json.dumps(rows).encode()
        return 404, b"nope"
    return opener


def run(cfg, opener):
    with tempfile.TemporaryDirectory() as out:
        code = live_check.run_live_check(cfg, out, opener, NO_SLEEP, NOW)
        with open(os.path.join(out, "providers.json"), encoding="utf-8") as f:
            data = json.load(f)
        with open(os.path.join(out, "providers.md"), encoding="utf-8") as f:
            md = f.read()
        files = sorted(os.listdir(out))
    return code, data, md, files


class AdapterTests(unittest.TestCase):
    def http(self, opener):
        return providers.Http(5, 1, opener, NO_SLEEP)

    def test_kraken_maps_fields_and_drops_nothing_itself(self):
        c = providers.Kraken().candles("1h", NOW - 7200, NOW, self.http(fake(NOW)))
        self.assertEqual((c[0].open, c[0].high, c[0].low, c[0].close, c[0].volume),
                         (px(c[0].time), px(c[0].time) + 2, px(c[0].time) - 2, px(c[0].time) + 1, 3.5))

    def test_coinbase_maps_low_high_open_close_and_sorts_oldest_first(self):
        c = providers.Coinbase().candles("1h", NOW - 7200, NOW, self.http(fake(NOW)))
        self.assertEqual([x.time for x in c], sorted(x.time for x in c))
        self.assertEqual((c[0].open, c[0].high, c[0].low, c[0].close),
                         (px(c[0].time), px(c[0].time) + 2, px(c[0].time) - 2, px(c[0].time) + 1))

    def test_coinbase_paginates_in_chunks_under_300(self):
        h = self.http(fake(NOW))
        c = providers.Coinbase().candles("1h", NOW - 20 * 86400, NOW, h)
        self.assertGreater(h.requests, 1)
        self.assertEqual(len(c), len({x.time for x in c}))        # joined pages have no repeats

    def test_kraken_refuses_range_beyond_720_candles(self):
        with self.assertRaises(ValueError):
            providers.Kraken().candles("1h", NOW - 40 * 86400, NOW, self.http(fake(NOW)))

    def test_kraken_error_list_is_an_error(self):
        op = lambda url, t: (200, json.dumps({"error": ["EQuery:Unknown asset pair"]}).encode())  # noqa: E731
        with self.assertRaises(ApiError) as ctx:
            providers.Kraken().candles("1h", NOW - 7200, NOW, self.http(op))
        self.assertIn("Unknown asset pair", str(ctx.exception))

    def test_coinbase_non_list_is_an_error(self):
        op = lambda url, t: (200, json.dumps({"message": "NotFound"}).encode())  # noqa: E731
        with self.assertRaises(ApiError):
            providers.Coinbase().candles("1h", NOW - 7200, NOW, self.http(op))

    def test_http_log_records_real_status(self):
        h = self.http(fake(NOW, blocked={"api.kraken.com"}))
        with self.assertRaises(ApiError):
            providers.Kraken().server_time(h)
        self.assertEqual(h.log, [("/0/public/Time", "HTTP 451")])

    def test_unknown_provider_and_timeframe(self):
        with self.assertRaises(ValueError):
            providers.build("nope")
        with self.assertRaises(ValueError):
            providers.Coinbase().candles("4h", 0, 10, self.http(fake(NOW)))


class LiveCheckTests(unittest.TestCase):
    def test_all_providers_verified(self):
        code, data, md, files = run(CFG, fake(NOW))
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual([r["verdict"] for r in data["providers"]], ["VERIFIED"] * 4)
        self.assertIn("candles_kraken.csv", files)
        self.assertIn("HTTP evidence", md)
        self.assertEqual(data["cross_check"]["spread_pct"], 0.0)

    def test_one_blocked_provider_does_not_break_the_others(self):
        code, data, md, files = run(CFG, fake(NOW, blocked={"www.tokocrypto.site"}))
        by = {r["provider"]: r for r in data["providers"]}
        self.assertEqual(by["tokocrypto"]["verdict"], "BLOCKED FROM RUNNER")
        self.assertIn("HTTP 451", by["tokocrypto"]["detail"])
        self.assertEqual(by["kraken"]["verdict"], "VERIFIED")
        self.assertEqual(data["status"], "PASS")
        self.assertNotIn("candles_tokocrypto.csv", files)
        self.assertIn("BLOCKED FROM RUNNER", md)

    def test_everything_blocked_is_FAIL_and_shows_no_prices(self):
        hosts = {"api.kraken.com", "api.exchange.coinbase.com", "data-api.binance.vision",
                 "www.tokocrypto.site"}
        code, data, md, files = run(CFG, fake(NOW, blocked=hosts))
        self.assertEqual(code, 1)
        self.assertEqual(data["status"], "FAIL")
        self.assertEqual(files, ["providers.json", "providers.md"])
        self.assertIn("Nothing is made up", md)

    def test_validation_failure_is_not_hidden(self):
        # Kraken drops 40% of the hours: validator must FAIL it, not warn.
        drop = {t for t in grid(NOW - 2 * 86400, NOW) if (t // 3600) % 5 < 2}
        cfg = dict(CFG, live_providers=["kraken"])
        code, data, md, files = run(cfg, fake(NOW, drop=drop))
        r = data["providers"][0]
        self.assertEqual(r["verdict"], "FAILED")
        self.assertEqual(r["validation"], "FAIL")
        self.assertEqual(data["status"], "FAIL")
        self.assertEqual(code, 1)

    def test_stale_data_fails(self):
        def stale(url, timeout):
            status, body = fake(NOW)(url, timeout)
            if url.endswith("/0/public/Time") or "unixtime" in body.decode():
                return 200, json.dumps({"error": [], "result": {"unixtime": NOW + 10 * 3600}}).encode()
            return status, body
        code, data, md, files = run(dict(CFG, live_providers=["kraken"]), stale)
        names = {c["name"]: c["status"] for c in data["providers"][0]["checks"]}
        self.assertEqual(names["freshness"], "FAIL")
        self.assertEqual(data["status"], "FAIL")

    def test_refuses_non_read_only(self):
        for mode in ("live", "paper", None):
            with self.assertRaises(SystemExit):
                live_check.run_live_check(dict(CFG, mode=mode), tempfile.gettempdir(), fake(NOW))


class SafetyTests(unittest.TestCase):
    FORBIDDEN = ["/orders", "/order", "/account", "/withdraw", "listenkey", "x-mbx-apikey",
                 "signature", "hmac", "api_key", "apikey", "secret", "password"]

    def test_new_modules_have_no_trading_or_credential_code(self):
        for name in ("providers.py", "live_check.py"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                text = f.read().lower()
            for word in self.FORBIDDEN:
                self.assertNotIn(word, text, f"{name} contains {word!r}")

    def test_provider_paths_are_only_public_market_data(self):
        with open(os.path.join(ROOT, "providers.py"), encoding="utf-8") as f:
            text = f.read()
        for allowed in ("/0/public/Time", "/0/public/OHLC", "/time", "/candles"):
            self.assertIn(allowed, text)


if __name__ == "__main__":
    unittest.main()
