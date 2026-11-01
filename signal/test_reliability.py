"""Offline tests for the reliability fixes F1 to F5. Run from the repository root with:
    python3 -B -m unittest discover -s signal -p "test_*.py" -v
Datasets are written to a temporary directory outside the repository and removed afterwards.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import btc_signal as bs
from test_btc_signal import candles_from_closes, wave, write_dataset

REPO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backtest_config.json")


def pins_for(manifest_path, version=None):
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    return {"status": "test", "pins": {m["dataset_name"]: [{
        "version_id": m["version_id"] if version is None else version,
        "csv_sha256": m["csv_sha256"]}]}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="btc_reliability_test_")
        self.cs = candles_from_closes([wave(i, 100, 0.5) for i in range(120)])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def dataset(self, **kw):
        return write_dataset(self.tmp, self.cs, **kw)[0]

    def rewrite_manifest(self, mpath, **changes):
        with open(mpath, encoding="utf-8") as f:
            m = json.load(f)
        m.update(changes)
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f)


class F1StaleDataTests(Base):
    def test_fresh_data_is_marked_current(self):
        mpath = self.dataset()
        close = self.cs[-1].time + bs.STEP
        r = bs.build_report(mpath, now_ts=close + 47 * 3600)
        self.assertFalse(r["stale"])
        self.assertEqual(r["status"], "CURRENT")
        self.assertEqual(r["stale_notice"], "")
        md = bs.render_markdown(r)
        self.assertNotIn("NOT CURRENT", md)

    def test_stale_data_is_marked_and_never_called_live(self):
        mpath = self.dataset()
        close = self.cs[-1].time + bs.STEP
        r = bs.build_report(mpath, now_ts=close + 49 * 3600)
        self.assertTrue(r["stale"])
        self.assertEqual(r["status"], "NOT CURRENT")
        self.assertIn("NOT CURRENT", r["stale_notice"])
        self.assertIn("NOT a live signal", r["stale_notice"])
        md = bs.render_markdown(r)
        self.assertIn("NOT CURRENT", md)
        self.assertIn("NOT a live signal", md)
        self.assertLess(md.index("NOT CURRENT"), md.index("Decision:"))

    def test_threshold_is_exactly_48_hours(self):
        self.assertEqual(bs.MAX_AGE_SECONDS, 172800)
        mpath = self.dataset()
        close = self.cs[-1].time + bs.STEP
        self.assertFalse(bs.build_report(mpath, now_ts=close + 172800)["stale"])
        self.assertTrue(bs.build_report(mpath, now_ts=close + 172801)["stale"])

    def test_generated_utc_in_json_and_markdown(self):
        mpath = self.dataset()
        r = bs.build_report(mpath, now_ts=self.cs[-1].time + bs.STEP + 3600)
        self.assertEqual(r["generated_utc"], bs.utc_text(self.cs[-1].time + bs.STEP + 3600) + " UTC")
        self.assertIn(r["generated_utc"], bs.render_markdown(r))
        json.dumps(r)                                    # must serialise


class F2IndependentPinTests(Base):
    def test_matching_pin_loads(self):
        mpath = self.dataset()
        m, candles = bs.load_verified(mpath, pins=pins_for(mpath))
        self.assertEqual(len(candles), 120)

    def test_manifest_and_csv_tamper_cannot_bypass_independent_pin(self):
        mpath = self.dataset()
        pins = pins_for(mpath)                           # pin records the ORIGINAL hash
        csv_path = os.path.join(self.tmp, "v20260101T000000Z_testtest.csv")
        with open(csv_path, "rb") as f:
            data = f.read()
        with open(csv_path, "wb") as f:
            f.write(data.replace(b"1000.0", b"1001.0", 1))
        # Attacker rewrites the manifest's hash and keeps the version id: the manifest agrees.
        self.rewrite_manifest(mpath, csv_sha256=bs.sha256_file(csv_path))
        # Without the independent pin the tampered pair passes (this is the gap F2 closes).
        bs.load_verified(mpath)
        # With the independent pin it must be refused.
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath, pins=pins)
        self.assertIn("INDEPENDENT pin", str(ctx.exception))

    def test_pin_for_other_version_refused(self):
        mpath = self.dataset()
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath, pins=pins_for(mpath, version="v20261027T102241Z_c11776a0"))

    def test_missing_dataset_pin_refused(self):
        mpath = self.dataset()
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath, pins={"status": "x", "pins": {}})

    def test_malformed_pin_file_refused(self):
        bad = os.path.join(self.tmp, "pins.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump({"pins": {"d": {"version_id": "v", "csv_sha256": "NOTAHASH"}}}, f)
        with self.assertRaises(bs.SignalError):
            bs.load_pins(bad)

    def test_report_states_whether_pin_was_checked(self):
        mpath = self.dataset()
        unchecked = bs.build_report(mpath, now_ts=self.cs[-1].time + bs.STEP + 3600)
        self.assertIn("NOT CHECKED", unchecked["dataset"]["independent_pin"])
        checked = bs.build_report(mpath, now_ts=self.cs[-1].time + bs.STEP + 3600,
                                  pins=pins_for(mpath))
        self.assertIn("VERIFIED", checked["dataset"]["independent_pin"])

    def test_committed_pin_file_is_well_formed_and_provisional(self):
        pins = bs.load_pins()                            # default signal/expected_pins.json
        self.assertIn("PROVISIONAL", pins["status"])
        self.assertIn("binance-vision_BTCUSDT_1d", pins["pins"])


class F3WarningTests(Base):
    def test_warn_entries_survive_into_json_and_markdown(self):
        extra = [{"name": "validator_price_spikes", "status": "WARN",
                  "detail": "1 close-to-close move(s) larger than 25%"},
                 {"name": "other_check", "status": "WARN", "detail": "example warning"}]
        mpath = self.dataset(extra_checks=extra)
        r = bs.build_report(mpath, now_ts=self.cs[-1].time + bs.STEP + 3600)
        names = {c["name"]: c for c in r["dataset_checks"]}
        self.assertEqual(names["validator_price_spikes"]["status"], "WARN")
        self.assertEqual(names["other_check"]["status"], "WARN")
        self.assertNotIn("validator_freshness", names)            # PASS entries not listed
        md = bs.render_markdown(r)
        self.assertIn("validator_price_spikes: WARN - 1 close-to-close move(s) larger than 25%", md)
        self.assertIn("other_check: WARN - example warning", md)

    def test_fail_status_stops_the_run(self):
        mpath = self.dataset(extra_checks=[{"name": "validator_ohlc_sanity", "status": "FAIL",
                                            "detail": "bad"}])
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath)
        self.assertIn("FAILED", str(ctx.exception))

    def test_unknown_gate_status_refused(self):
        mpath = self.dataset(extra_checks=[{"name": "x", "status": "MAYBE", "detail": ""}])
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)

    def test_no_warnings_says_none(self):
        mpath = self.dataset()
        md = bs.render_markdown(bs.build_report(mpath, now_ts=self.cs[-1].time + bs.STEP + 3600))
        self.assertIn("## Dataset checks (WARN and FAIL)\n- none", md)


class F4CompletedCandleTests(Base):
    def test_forming_candle_is_refused(self):
        last_open = self.cs[-1].time
        mpath = self.dataset(fetched_ts=last_open + bs.STEP - 1)      # fetched 1 s before close
        with self.assertRaises(bs.SignalError) as ctx:
            bs.load_verified(mpath)
        self.assertIn("forming candle", str(ctx.exception))

    def test_candle_closing_exactly_at_fetch_is_complete(self):
        last_open = self.cs[-1].time
        mpath = self.dataset(fetched_ts=last_open + bs.STEP)          # fetched at the close
        bs.load_verified(mpath)

    def test_missing_fetch_time_refused(self):
        mpath = self.dataset()
        self.rewrite_manifest(mpath)
        with open(mpath, encoding="utf-8") as f:
            m = json.load(f)
        del m["fetched_utc"]
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(m, f)
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)

    def test_malformed_fetch_time_refused(self):
        mpath = self.dataset()
        self.rewrite_manifest(mpath, fetched_utc="yesterday")
        with self.assertRaises(bs.SignalError):
            bs.load_verified(mpath)


class F5SameBytesTests(Base):
    def test_csv_is_opened_exactly_once(self):
        mpath = self.dataset()
        csv_name = "v20260101T000000Z_testtest.csv"
        real_open = open
        seen = []

        def spy(path, *a, **k):
            if str(path).endswith(csv_name):
                seen.append(path)
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", side_effect=spy):
            bs.load_verified(mpath)
        self.assertEqual(len(seen), 1)

    def test_hashed_bytes_are_exactly_the_parsed_bytes(self):
        mpath = self.dataset()
        recorded = []
        real_read = bs._read_once

        def record(path):
            raw = real_read(path)
            recorded.append(raw)
            return raw

        with mock.patch.object(bs, "_read_once", side_effect=record):
            m, candles = bs.load_verified(mpath)
        self.assertEqual(len(recorded), 1)
        raw = recorded[0]
        self.assertEqual(bs.hashlib.sha256(raw).hexdigest(), m["csv_sha256"])
        self.assertEqual(bs.parse_csv_bytes(raw, m["market"]), candles)

    def test_bytes_changed_after_read_do_not_affect_result(self):
        # The parser never touches the disk again: changing the file after the read cannot
        # alter the parsed result because parsing happens on the in-memory bytes.
        mpath = self.dataset()
        csv_path = os.path.join(self.tmp, "v20260101T000000Z_testtest.csv")
        real_read = bs._read_once
        original = real_read(csv_path)

        def read_then_corrupt(path):
            raw = real_read(path)
            with open(path, "wb") as f:
                f.write(b"garbage")
            return raw

        with mock.patch.object(bs, "_read_once", side_effect=read_then_corrupt):
            m, candles = bs.load_verified(mpath)
        self.assertEqual(bs.parse_csv_bytes(original, m["market"]), candles)

    def test_non_utf8_bytes_refused(self):
        with self.assertRaises(bs.SignalError):
            bs.parse_csv_bytes(b"\xff\xfe\x00", bs.EXPECTED_MARKET)


class PinnedDatasetReliabilityTests(unittest.TestCase):
    """Runs only when BTC_SIGNAL_PINNED_MANIFEST is set to a local pinned manifest. Never fetches."""

    @unittest.skipUnless(os.environ.get("BTC_SIGNAL_PINNED_MANIFEST"),
                         "set BTC_SIGNAL_PINNED_MANIFEST to a local pinned manifest to run")
    def test_pinned_dataset_passes_config_and_independent_pin(self):
        mpath = os.environ["BTC_SIGNAL_PINNED_MANIFEST"]
        with open(REPO_CONFIG, encoding="utf-8") as f:
            pinned = json.load(f)["dataset_version"]
        m, candles = bs.load_verified(mpath, expect_version=pinned, pins=bs.load_pins())
        self.assertEqual(m["version_id"], pinned)
        self.assertGreater(len(candles), 3000)


if __name__ == "__main__":
    unittest.main()
