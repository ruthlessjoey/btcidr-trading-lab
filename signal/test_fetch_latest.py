"""Offline tests for signal/fetch_latest.py. No network: every request goes through a fake opener.
Run from the repository root with:
    python3 -B -m unittest discover -s signal -p "test_*.py" -v
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import btc_signal as bs
import fetch_latest as fl
from test_btc_signal import candles_from_closes, wave, write_dataset

BASE_URL = "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=40"


class FakeResp:
    def __init__(self, body, status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_opener(body, status=200, raises=None):
    calls = []

    def op(req, timeout):
        calls.append(req.full_url)
        if raises is not None:
            raise raises
        return FakeResp(body, status)
    op.calls = calls
    return op


def kline_body(candles, drop=(), duplicate=None, bad_close=None):
    rows = []
    for i, c in enumerate(candles):
        if i in drop:
            continue
        open_ms = c.time * 1000
        close_ms = open_ms + bs.STEP * 1000 - 1
        if i == bad_close:
            close_ms += 5
        row = [open_ms, str(c.open), str(c.high), str(c.low), str(c.close), str(c.volume),
               close_ms, "0", 0, "0", "0", "0"]
        rows.append(row)
        if i == duplicate:
            rows.append(row)
    return json.dumps(rows).encode("utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="btc_fetch_test_")
        # 71 synthetic daily candles. History = first 60. Fetch covers index 40 to 70.
        self.cs = candles_from_closes([wave(i, 100, 0.5) for i in range(71)])
        self.history_manifest, _ = write_dataset(self.tmp, self.cs[:60],
                                                 version="v20260101T000000Z_hist0000")
        # Candle 70 is still forming at fetch_s, so 40..69 are completed.
        self.fetch_s = self.cs[70].time + 10
        self.out = os.path.join(self.tmp, "out")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, body, opener=None, fetch_s=None):
        op = opener if opener is not None else fake_opener(body)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = fl.main(["--history-manifest", self.history_manifest, "--out-dir", self.out],
                         opener=op, now=self.fetch_s if fetch_s is None else fetch_s)
        return rc, op

    def written(self):
        folder = os.path.join(self.out, fl.DATASET_NAME)
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


class UrlTests(unittest.TestCase):
    def test_url_is_the_exact_documented_endpoint(self):
        self.assertEqual(fl.build_url(), BASE_URL)

    def test_limit_bounds(self):
        with self.assertRaises(fl.FetchError):
            fl.build_url(0)
        with self.assertRaises(fl.FetchError):
            fl.build_url(fl.MAX_LIMIT + 1)


class HappyPathTests(Base):
    def test_one_request_and_verified_snapshot_written(self):
        rc, op = self.run_main(kline_body(self.cs[40:71]))
        self.assertEqual(rc, 0)
        self.assertEqual(op.calls, [BASE_URL])                 # exactly one request
        self.assertEqual(len(self.written()), 2)               # csv + manifest, nothing else
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        m, candles = bs.load_verified(man)                      # the loader accepts it
        self.assertEqual(len(candles), 30)                      # indices 40..69 only
        self.assertEqual(m["forming_excluded"], 1)
        self.assertEqual(candles[-1].time, self.cs[69].time)

    def test_forming_candle_is_excluded_not_used(self):
        self.run_main(kline_body(self.cs[40:71]))
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        with open(man, encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["last_open_unix"], self.cs[69].time)
        self.assertNotEqual(m["last_open_unix"], self.cs[70].time)

    def test_manifest_keeps_source_and_proxy_disclaimer(self):
        self.run_main(kline_body(self.cs[40:71]))
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        with open(man, encoding="utf-8") as f:
            m = json.load(f)
        self.assertIn("NOT Tokocrypto execution prices", m["price_basis_warning"])
        self.assertEqual(m["source"]["host"], "https://data-api.binance.vision")
        self.assertEqual(m["market"]["provider"], "binance-vision")
        names = {g["name"]: g["status"] for g in m["gate_checks"]}
        self.assertEqual(names["history_overlap"], "PASS")
        self.assertEqual(names["completed_only"], "PASS")

    def test_price_spike_warning_is_kept(self):
        closes = [wave(i, 100, 0.5) for i in range(71)]
        closes[65] = closes[64] * 1.4                          # a 40% move, not in history
        cs = candles_from_closes(closes)
        body = kline_body(cs[40:71])
        self.run_main(body, fetch_s=cs[70].time + 10)
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        with open(man, encoding="utf-8") as f:
            m = json.load(f)
        spike = [g for g in m["gate_checks"] if g["name"] == "validator_price_spikes"][0]
        self.assertEqual(spike["status"], "WARN")

    def test_refuses_to_overwrite_existing_snapshot(self):
        rc1, _ = self.run_main(kline_body(self.cs[40:71]))
        rc2, _ = self.run_main(kline_body(self.cs[40:71]))
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 2)
        self.assertEqual(len(self.written()), 2)


class RefusalTests(Base):
    def assert_refused_and_empty(self, rc, op=None):
        self.assertEqual(rc, 2)
        self.assertEqual(self.written(), [])                   # nothing written on failure

    def test_network_failure_no_fallback(self):
        rc, _ = self.run_main(b"", opener=fake_opener(b"", raises=OSError("offline")))
        self.assert_refused_and_empty(rc)

    def test_non_200_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71]), opener=fake_opener(b"", status=451))
        self.assert_refused_and_empty(rc)

    def test_malformed_json_refused(self):
        rc, _ = self.run_main(b"<html>not json</html>")
        self.assert_refused_and_empty(rc)

    def test_empty_list_refused(self):
        rc, _ = self.run_main(b"[]")
        self.assert_refused_and_empty(rc)

    def test_missing_candle_in_response_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71], drop=(20,)))
        self.assert_refused_and_empty(rc)

    def test_duplicate_row_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71], duplicate=5))
        self.assert_refused_and_empty(rc)

    def test_wrong_close_time_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71], bad_close=3))
        self.assert_refused_and_empty(rc)

    def test_two_forming_candles_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71]), fetch_s=self.cs[69].time + 10)
        self.assert_refused_and_empty(rc)

    def test_overlap_mismatch_refused(self):
        changed = list(self.cs[40:71])
        h = changed[15]                                        # candle 55, inside history
        changed[15] = bs.Candle(h.time, h.open, h.high, h.low, h.close, h.volume + 1.0)
        rc, _ = self.run_main(kline_body(changed))
        self.assert_refused_and_empty(rc)

    def test_committed_candle_missing_from_fetch_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71], drop=(10,)))   # candle 50 dropped
        self.assert_refused_and_empty(rc)

    def test_fetch_not_reaching_history_end_refused(self):
        rc, _ = self.run_main(kline_body(self.cs[30:55]), fetch_s=self.cs[55].time + 10)
        self.assert_refused_and_empty(rc)

    def test_stale_newest_candle_refused_no_fallback(self):
        rc, _ = self.run_main(kline_body(self.cs[40:71]), fetch_s=self.cs[70].time + 4 * 86400)
        self.assert_refused_and_empty(rc)

    def test_too_few_overlapping_candles_refused(self):
        short_history, _ = write_dataset(self.tmp, self.cs[:45],
                                         version="v20260101T000000Z_short000")
        with contextlib.redirect_stdout(io.StringIO()):
            rc = fl.main(["--history-manifest", short_history, "--out-dir", self.out],
                         opener=fake_opener(kline_body(self.cs[40:71])), now=self.fetch_s)
        self.assert_refused_and_empty(rc)


class PinAndSignalTests(Base):
    def test_snapshot_passes_only_with_its_independent_pin(self):
        self.run_main(kline_body(self.cs[40:71]))
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        with open(man, encoding="utf-8") as f:
            m = json.load(f)
        pins = {"status": "t", "pins": {fl.DATASET_NAME: [
            {"version_id": m["version_id"], "csv_sha256": m["csv_sha256"]}]}}
        bs.load_verified(man, pins=pins)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(man, pins={"status": "t", "pins": {}})

    def test_tampered_snapshot_refused_by_independent_pin(self):
        self.run_main(kline_body(self.cs[40:71]))
        man = os.path.join(self.out, fl.DATASET_NAME, self.written()[1])
        csv_path = man[:-len(".manifest.json")] + ".csv"
        with open(man, encoding="utf-8") as f:
            m = json.load(f)
        pins = {"status": "t", "pins": {fl.DATASET_NAME: [
            {"version_id": m["version_id"], "csv_sha256": m["csv_sha256"]}]}}
        with open(csv_path, "rb") as f:
            data = f.read()
        with open(csv_path, "wb") as f:
            f.write(data.replace(b"1000.0", b"1001.0", 1))
        m["csv_sha256"] = bs.sha256_file(csv_path)              # attacker fixes the manifest
        with open(man, "w", encoding="utf-8") as f:
            json.dump(m, f)
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(man, pins=pins)
        self.assertIn("INDEPENDENT pin", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
