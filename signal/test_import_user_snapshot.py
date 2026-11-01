"""Offline tests for signal/import_user_snapshot.py. No network, no repository data.
Run from the repository root with:
    python3 -B -m unittest discover -s signal -p "test_*.py" -v
"""
import ast
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest

import btc_signal as bs
import fetch_latest as fl
import import_user_snapshot as ius
from test_btc_signal import candles_from_closes, wave, write_dataset
from test_fetch_latest import kline_body

HERE = os.path.dirname(os.path.abspath(__file__))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="btc_import_test_")
        self.cs = candles_from_closes([wave(i, 100, 0.5) for i in range(71)])
        self.history_manifest, self.history_csv = write_dataset(
            self.tmp, self.cs[:60], version="v20260101T000000Z_hist0000")
        # Download happens 10 s after candle 70 opens, so candle 70 is forming and 40..69 complete.
        self.download_s = self.cs[70].time + 10
        self.download_text = bs.utc_text(self.download_s)
        self.raw_path = os.path.join(self.tmp, "user.json")
        self.out = os.path.join(self.tmp, "out")
        self.write_raw(kline_body(self.cs[40:71]))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_raw(self, body):
        with open(self.raw_path, "wb") as f:
            f.write(body)

    def run_import(self, download_text=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return ius.main(["--user-json", self.raw_path,
                             "--history-csv", self.history_csv,
                             "--history-manifest", self.history_manifest,
                             "--download-utc", download_text or self.download_text],
                            out_dir=self.out)

    def files(self):
        folder = os.path.join(self.out, fl.DATASET_NAME)
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def manifest_path(self):
        return os.path.join(self.out, fl.DATASET_NAME,
                            [f for f in self.files() if f.endswith(".manifest.json")][0])


class CombinedSnapshotTests(Base):
    def test_combined_snapshot_has_history_plus_new_completed_candles(self):
        self.assertEqual(self.run_import(), 0)
        m, candles = bs.load_verified(self.manifest_path())
        self.assertEqual(len(candles), 70)                       # 60 history + 10 new (60..69)
        self.assertEqual(candles[-1].time, self.cs[69].time)     # forming candle 70 excluded
        self.assertEqual(candles, self.cs[:70])

    def test_historical_bytes_are_preserved_exactly(self):
        self.run_import()
        with open(self.history_csv, "rb") as f:
            hist = f.read()
        csv_name = [f for f in self.files() if f.endswith(".csv")][0]
        with open(os.path.join(self.out, fl.DATASET_NAME, csv_name), "rb") as f:
            combined = f.read()
        self.assertTrue(combined.startswith(hist.rstrip(b"\n")))

    def test_provenance_is_kept_separate_and_labelled(self):
        self.run_import()
        with open(self.manifest_path(), encoding="utf-8") as f:
            m = json.load(f)
        prov = m["provenance"]
        self.assertEqual(prov["label"], "USER-SUPPLIED / PROVISIONAL")
        self.assertIn("NOT AUTHENTICATED", prov["authenticity"])
        self.assertEqual(prov["historical_rows"]["rows"], 60)
        self.assertEqual(prov["user_supplied_rows"]["rows"], 10)
        self.assertIn("no independent pin", prov["historical_rows"]["source"])
        self.assertEqual(prov["download_utc_user_stated"], self.download_text + " UTC")

    def test_raw_user_response_is_stored_byte_exact(self):
        self.run_import()
        raw_name = [f for f in self.files() if f.endswith(".raw-user-supplied.json")][0]
        with open(os.path.join(self.out, fl.DATASET_NAME, raw_name), "rb") as f:
            stored = f.read()
        with open(self.raw_path, "rb") as f:
            self.assertEqual(stored, f.read())

    def test_overlap_is_checked_against_user_file(self):
        self.run_import()
        with open(self.manifest_path(), encoding="utf-8") as f:
            m = json.load(f)
        self.assertEqual(m["provenance"]["overlap_checked_against_user_file"], 20)
        names = {g["name"]: g["status"] for g in m["gate_checks"]}
        self.assertEqual(names["history_overlap"], "PASS")
        self.assertEqual(names["completed_only"], "PASS")


class RefusalTests(Base):
    def assert_refused_and_nothing_written(self, rc):
        self.assertEqual(rc, 2)
        self.assertEqual(self.files(), [])

    def test_overlap_mismatch_refused(self):
        changed = list(self.cs[40:71])
        h = changed[15]                                          # candle 55, inside history
        changed[15] = bs.Candle(h.time, h.open, h.high, h.low, h.close, h.volume + 1.0)
        self.write_raw(kline_body(changed))
        self.assert_refused_and_nothing_written(self.run_import())

    def test_stale_download_refused(self):
        late = bs.utc_text(self.cs[70].time + 4 * 86400)
        self.assert_refused_and_nothing_written(self.run_import(download_text=late))

    def test_download_before_last_candle_closed_refused(self):
        early = bs.utc_text(self.cs[69].time + 10)               # candle 69 still forming
        self.assert_refused_and_nothing_written(self.run_import(download_text=early))

    def test_no_new_candles_refused(self):
        self.write_raw(kline_body(self.cs[40:60]))               # only history candles
        self.assert_refused_and_nothing_written(self.run_import())

    def test_malformed_download_time_refused(self):
        self.assert_refused_and_nothing_written(self.run_import(download_text="2026/11/01 08:45"))

    def test_malformed_user_json_refused(self):
        self.write_raw(b"<html>not json</html>")
        self.assert_refused_and_nothing_written(self.run_import())

    def test_never_overwrites_existing_snapshot(self):
        self.assertEqual(self.run_import(), 0)
        self.assertEqual(self.run_import(), 2)
        self.assertEqual(len(self.files()), 3)                   # csv, manifest, raw


class ReportProvenanceTests(Base):
    def test_report_shows_user_supplied_provisional_label(self):
        self.run_import()
        r = bs.build_report(self.manifest_path(), now_ts=self.download_s + 3600)
        self.assertEqual(r["provenance"]["label"], "USER-SUPPLIED / PROVISIONAL")
        md = bs.render_markdown(r)
        self.assertIn("USER-SUPPLIED / PROVISIONAL", md)
        self.assertIn("NOT AUTHENTICATED", md)
        self.assertFalse(r["stale"])

    def test_report_without_provenance_still_renders(self):
        mpath, _ = write_dataset(self.tmp, self.cs[:60], version="v20260102T000000Z_plain000")
        md = bs.render_markdown(bs.build_report(mpath, now_ts=self.cs[59].time + bs.STEP + 3600))
        self.assertIn("none recorded", md)


class BoundaryTests(unittest.TestCase):
    def test_importer_makes_no_network_import(self):
        path = os.path.join(HERE, "import_user_snapshot.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        for banned in ("urllib", "socket", "http", "requests", "ccxt", "subprocess"):
            self.assertNotIn(banned, names)


if __name__ == "__main__":
    unittest.main()
