"""Offline tests for the Step 1 data gate.

EVERY PRICE HERE IS SYNTHETIC. This fake exchange only exercises our code paths.
Passing these tests says nothing about Binance; only a real run can show that.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fetcher import Candle  # noqa: E402
from research import dataset, history  # noqa: E402

NO_SLEEP = lambda s: None  # noqa: E731
DAY = 86400


def ts(y, m, d, h=0, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=timezone.utc).timestamp())


NOW = ts(2026, 10, 27, 9, 50)
LISTING = ts(2017, 8, 17)
CFG = {"mode": "read_only", "provider": "binance-vision", "host": "https://h.test",
       "symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT", "timeframe": "1d",
       "fetch_from_utc_date": "2017-01-01", "require_first_candle_on_or_before": "2017-09-30",
       "min_rows": 3000, "page_limit": 1000, "max_pages": 30, "max_spike_pct": 25,
       "http_timeout_seconds": 5, "http_retries": 1}


def px(t):
    return 20000.0 + ((t // DAY) % 50) * 10


def fake(now=NOW, listing=LISTING, quote="USDT", status="TRADING", gap=(), cap=None,
         dup_before=False, conflict=False, offset=0, revise=None):
    calls = []

    def opener(url, timeout):
        u = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(u.query)
        calls.append(u.path)
        if u.path == "/api/v3/exchangeInfo":
            return 200, json.dumps({"symbols": [{"symbol": "BTCUSDT", "status": status,
                                                 "baseAsset": "BTC", "quoteAsset": quote,
                                                 "isSpotTradingAllowed": True}]}).encode()
        if u.path == "/api/v3/time":
            return 200, json.dumps({"serverTime": now * 1000}).encode()
        if u.path == "/api/v3/klines":
            start, end = int(q["startTime"][0]) // 1000, int(q["endTime"][0]) // 1000
            lim = min(int(q["limit"][0]), cap or 10 ** 9)
            first = max(start, listing)
            first = -(-first // DAY) * DAY
            times = [t + offset for t in range(first, end + 1, DAY) if t not in gap][:lim]
            rows = []
            if dup_before and start > listing:
                times = [start - DAY] + times
            for t in times:
                c = (revise or {}).get(t, px(t) + 10)
                rows.append([t * 1000, str(px(t)), str(px(t) + 50), str(px(t) - 50), str(c),
                             "100.0", (t + DAY) * 1000 - 1, "1", 1, "1", "1", "0"])
            if conflict and rows:
                bad = list(rows[-1])
                bad[4] = str(float(bad[4]) + 5)
                rows.append(bad)
            return 200, json.dumps(rows).encode()
        return 404, b""
    opener.calls = calls
    return opener


def run(opener, cfg=CFG, previous_root=None, now=NOW):
    out = tempfile.mkdtemp()
    code = history.run_step1(cfg, out, opener, NO_SLEEP, now, previous_root)
    with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
        md = f.read()
    return code, data, md, out


def status(data, name):
    return next(c["status"] for c in data["checks"] if c["name"] == name)


class GateTests(unittest.TestCase):
    def tearDown(self):
        for d in getattr(self, "dirs", []):
            shutil.rmtree(d, ignore_errors=True)

    def go(self, *a, **k):
        r = run(*a, **k)
        self.dirs = getattr(self, "dirs", []) + [r[3]]
        return r

    def test_good_dataset_passes_and_is_written_and_reloadable(self):
        code, data, md, out = self.go(fake())
        self.assertEqual(code, 0)
        self.assertEqual(data["gate"], "PASS")
        self.assertEqual(len(data["pages"]), 4)                     # 3359 rows / 1000 per page
        self.assertEqual(data["coverage"]["first_open_utc"], "2017-08-17")
        self.assertEqual(data["coverage"]["last_open_utc"], "2026-10-26")   # 10-27 still forming
        self.assertEqual(data["coverage"]["forming_excluded"], 1)
        self.assertEqual(data["coverage"]["missing"], 0)
        self.assertEqual(data["coverage"]["rows"], data["coverage"]["expected_rows"])
        self.assertTrue(data["backtest_allowed"])
        manifest = os.path.join(out, "datasets", "binance-vision_BTCUSDT_1d", data["dataset"]["manifest"])
        m, candles = dataset.load_verified(manifest, expect={"quote_asset": "USDT", "symbol": "BTCUSDT"})
        self.assertEqual(len(candles), data["coverage"]["rows"])
        self.assertEqual(m["csv_sha256"], data["dataset"]["sha256"])
        self.assertIn("NOT Tokocrypto", m["price_basis_warning"])
        self.assertIn("GATE: ✅ PASS", md)
        self.assertIn("not** Tokocrypto", md)

    def test_short_history_fails_reports_actual_start_and_writes_nothing(self):
        code, data, md, out = self.go(fake(listing=ts(2019, 1, 1)))
        self.assertEqual(code, 1)
        self.assertEqual(data["gate"], "FAIL")
        self.assertEqual(status(data, "history_depth"), "FAIL")
        self.assertEqual(data["coverage"]["first_open_utc"], "2019-01-01")
        self.assertFalse(data["backtest_allowed"])
        self.assertFalse(os.path.exists(os.path.join(out, "datasets")))
        self.assertIn("2019-01-01", md)
        self.assertIn("must not run", md)

    def test_missing_day_fails(self):
        code, data, md, out = self.go(fake(gap={ts(2021, 5, 5)}))
        self.assertEqual(code, 1)
        self.assertEqual(status(data, "missing_days"), "FAIL")
        self.assertIn("2021-05-05", md)
        self.assertFalse(os.path.exists(os.path.join(out, "datasets")))

    def test_page_overlap_is_caught_as_pagination_and_duplicate_failure(self):
        code, data, md, out = self.go(fake(dup_before=True))
        self.assertEqual(code, 1)
        self.assertEqual(status(data, "pagination"), "FAIL")
        self.assertEqual(status(data, "duplicates"), "FAIL")

    def test_conflicting_duplicate_fails(self):
        code, data, md, out = self.go(fake(conflict=True))
        self.assertEqual(code, 1)
        self.assertEqual(data["coverage"]["conflicting_duplicates"], len(data["pages"]))   # one injected per page
        self.assertEqual(status(data, "duplicates"), "FAIL")

    def test_wrong_quote_asset_fails_before_any_candles_are_requested(self):
        op = fake(quote="BUSD")
        code, data, md, out = self.go(op)
        self.assertEqual(code, 1)
        self.assertEqual(status(data, "market_identity"), "FAIL")
        self.assertNotIn("/api/v3/klines", op.calls)

    def test_symbol_not_trading_fails(self):
        code, data, md, out = self.go(fake(status="BREAK"))
        self.assertEqual(status(data, "market_identity"), "FAIL")

    def test_off_grid_timestamps_fail(self):
        code, data, md, out = self.go(fake(offset=1800))
        self.assertEqual(status(data, "timestamp_grid"), "FAIL")
        self.assertEqual(code, 1)

    def test_server_that_returns_fewer_rows_than_asked_cannot_pass(self):
        # A silent 500-row cap would stop the pager early: must not look like a pass.
        code, data, md, out = self.go(fake(cap=500))
        self.assertEqual(code, 1)
        self.assertEqual(data["gate"], "FAIL")

    def test_network_block_reports_failure_and_no_data(self):
        def blocked(url, timeout):
            return 451, b"unavailable"
        code, data, md, out = self.go(blocked)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 451", md)
        self.assertIsNone(data["coverage"])
        self.assertFalse(os.path.exists(os.path.join(out, "datasets")))

    def test_refuses_non_read_only(self):
        for mode in ("live", "paper", None):
            with self.assertRaises(SystemExit):
                history.run_step1(dict(CFG, mode=mode), tempfile.gettempdir(), fake(), NO_SLEEP, NOW)


class VersioningTests(unittest.TestCase):
    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def go(self, *a, **k):
        r = run(*a, **k)
        self.dirs.append(r[3])
        return r

    def test_second_fetch_is_a_new_version_and_old_one_is_untouched(self):
        _, d1, _, out1 = self.go(fake())
        before = open(os.path.join(out1, "datasets", "binance-vision_BTCUSDT_1d",
                                   d1["dataset"]["csv"]), "rb").read()
        code, d2, md2, out2 = self.go(fake(now=NOW + 3 * DAY), previous_root=os.path.join(out1, "datasets"),
                                      now=NOW + 3 * DAY)
        self.assertEqual(code, 0)
        self.assertNotEqual(d1["dataset"]["version_id"], d2["dataset"]["version_id"])
        cmp_ = d2["previous"]["compare"]
        self.assertEqual((cmp_["changed"], cmp_["only_in_old"]), (0, 0))
        self.assertEqual(cmp_["added_in_new"], 3)
        after = open(os.path.join(out1, "datasets", "binance-vision_BTCUSDT_1d",
                                  d1["dataset"]["csv"]), "rb").read()
        self.assertEqual(before, after)

    def test_revised_history_is_detected_and_fails(self):
        _, d1, _, out1 = self.go(fake())
        code, d2, md, out2 = self.go(fake(revise={ts(2020, 3, 12): 1.0 + px(ts(2020, 3, 12))}),
                                     previous_root=os.path.join(out1, "datasets"))
        self.assertEqual(status(d2, "previous_version"), "FAIL")
        self.assertEqual(d2["previous"]["compare"]["changed"], 1)
        self.assertEqual(code, 1)

    def test_tampered_previous_version_fails_reverification(self):
        _, d1, _, out1 = self.go(fake())
        p = os.path.join(out1, "datasets", "binance-vision_BTCUSDT_1d", d1["dataset"]["csv"])
        with open(p, "a", encoding="utf-8") as f:
            f.write("tampered\n")
        code, d2, md, out2 = self.go(fake(), previous_root=os.path.join(out1, "datasets"))
        self.assertEqual(code, 1)
        self.assertIn("FAILED re-verification", md)

    def test_never_overwrites_an_existing_version(self):
        market = {"provider": "p", "symbol": "S", "timeframe": "1d", "quote_asset": "Q"}
        cs = [Candle(i * DAY, 1, 2, 0.5, 1.5, 3) for i in range(3)]
        root = tempfile.mkdtemp()
        self.dirs.append(root)
        dataset.write_version(root, market, cs, NOW)
        with self.assertRaises(dataset.DatasetError):
            dataset.write_version(root, market, cs, NOW)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.market = {"provider": "p", "symbol": "BTCUSDT", "timeframe": "1d", "quote_asset": "USDT"}

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, candles):
        return dataset.write_version(self.root, self.market, candles, NOW)[1]

    def good(self, n=5):
        return [Candle(i * DAY, 10.0, 12.0, 9.0, 11.0, 5.0) for i in range(n)]

    def test_roundtrip(self):
        m, c = dataset.load_verified(self.write(self.good()), expect=self.market)
        self.assertEqual(c, self.good())

    def test_usd_dataset_cannot_load_as_usdt(self):
        path = self.write(self.good())
        with self.assertRaises(dataset.DatasetError) as ctx:
            dataset.load_verified(path, expect={"quote_asset": "USD"})
        self.assertIn("never mixed", str(ctx.exception))

    def test_changed_file_is_rejected_by_hash(self):
        path = self.write(self.good())
        csv_path = path.replace(".manifest.json", ".csv")
        text = open(csv_path, encoding="utf-8").read().replace("11.0", "12.0", 1)
        open(csv_path, "w", encoding="utf-8").write(text)
        with self.assertRaises(dataset.DatasetError) as ctx:
            dataset.load_verified(path)
        self.assertIn("hash", str(ctx.exception))

    def test_gap_duplicate_and_unsorted_are_rejected_even_with_a_valid_hash(self):
        g = self.good()
        for bad, word in ((g[:2] + g[3:], "consecutive"), (g[:3] + [g[2]] + g[3:], "consecutive"),
                          ([g[1], g[0]] + g[2:], "consecutive")):
            with self.assertRaises(dataset.DatasetError) as ctx:
                dataset.load_verified(self.write(bad))
            self.assertIn(word, str(ctx.exception))
            shutil.rmtree(self.root)
            self.root = tempfile.mkdtemp()

    def test_impossible_prices_rejected(self):
        bad = self.good() + [Candle(5 * DAY, 10.0, 8.0, 9.0, 11.0, 5.0)]      # high below low
        with self.assertRaises(dataset.DatasetError):
            dataset.load_verified(self.write(bad))


class SafetyTests(unittest.TestCase):
    FORBIDDEN = ["/order", "/account", "/withdraw", "listenkey", "x-mbx-apikey", "signature",
                 "hmac", "api_key", "apikey", "secret", "password"]

    def test_step1_files_have_no_trading_or_credential_code(self):
        files = ["fetch_history.py"] + [os.path.join("research", n) for n in
                                        sorted(os.listdir(os.path.join(ROOT, "research"))) if n.endswith(".py")]
        for name in files:
            text = open(os.path.join(ROOT, name), encoding="utf-8").read().lower()
            for word in self.FORBIDDEN:
                self.assertNotIn(word, text, f"{name} contains {word!r}")

    def test_only_public_market_paths(self):
        text = open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8").read()
        for p in ("/api/v3/exchangeInfo", "/api/v3/klines", "/api/v3/time"):
            self.assertIn(p, text)


if __name__ == "__main__":
    unittest.main()
