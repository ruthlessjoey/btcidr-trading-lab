"""Offline tests for pipeline/btc_pipeline.py. Synthetic fixtures and injected bytes only. No network.
Run from the repository root with:
    python3 -B -m unittest discover -s pipeline -p "test_*.py"
"""
import contextlib
import errno
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from unittest import mock

import btc_pipeline as bp
import btc_signal as bs
import fetch_latest as fl

DAY = 86400
T0 = 1609459200                       # 2021-01-01T00:00:00Z, daily boundary
NOW = T0 + 200 * DAY + 3600           # one hour after a daily boundary: the last slot is forming
SELL_TEXT = "SELL = bearish/exit candidate in spot research, not a short instruction."


def make_rows(now_s=NOW, limit=bp.REQUEST_LIMIT, falling=False):
    """Binance-shaped kline rows for `limit` daily slots ending with the forming slot at now's day start."""
    day_start = (now_s // DAY) * DAY
    rows = []
    for i in range(limit):
        o = day_start - (limit - 1 - i) * DAY
        if falling:
            p = 30000.0 - i * 60.0
        else:
            p = 20000.0 + i * 15 + (i % 7) * 20
        rows.append([o * 1000, f"{p}", f"{p + 5}", f"{p - 5}", f"{p + 3}", "100.5",
                     (o + DAY) * 1000 - 1, "0", "0", "0", "0", "0"])
    return rows


def run_t(now=NOW, opener=None, **kw):
    """Test helper: a run whose provenance is declared as synthetic with an explicit reference time."""
    return bp.run(now, data_source="synthetic", time_source="explicit-caller", opener=opener, **kw)


def quiet_main(out_dir, opener, extra=(), now_s=NOW):
    """Runs the CLI entry point with a fixed now, synthetic provenance and captured stdout."""
    with contextlib.redirect_stdout(io.StringIO()):
        return bp.main(["--out-dir", out_dir, "--data-source", "synthetic", *extra],
                       opener=opener, now_s=now_s)


def main_output(argv, opener=None, now_s=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = bp.main(argv, opener=opener, now_s=now_s)
    return code, buf.getvalue()


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


class Opener:
    """Records calls. Returns a canned body or raises a canned exception."""

    def __init__(self, body=b"", status=200, exc=None):
        self.body = body
        self.status = status
        self.exc = exc
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return FakeResp(self.body, self.status)


def body_of(rows):
    return json.dumps(rows).encode("utf-8")


REQUIRED_KEYS = {
    "report_type", "pipeline_version", "disclaimer", "no_trading", "now_s", "generated_utc", "provider",
    "market", "window", "pipeline_code", "candles", "gate", "signal", "explanation",
    "data_source", "data_source_note", "reference_time",
}


class HappyPathTests(unittest.TestCase):
    def test_happy_path_passes_gate_and_produces_an_s1_signal(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(r["gate"]["status"], "PASSED", r["gate"])
        self.assertIsNotNone(r["signal"])
        self.assertIn(r["signal"]["decision"], ("BUY", "SELL", "WAIT"))
        self.assertEqual(r["signal"]["rule_version"], bs.RULE_VERSION)
        self.assertEqual(r["candles"]["completed_count"], bp.REQUEST_LIMIT - 1)
        self.assertEqual(r["candles"]["forming_rows_dropped"], 1)
        self.assertEqual(r["candles"]["validation"]["coverage"], "complete")
        self.assertTrue(r["candles"]["validation"]["ok"])

    def test_exactly_one_request_on_success(self):
        op = Opener(body_of(make_rows()))
        run_t(opener=op)
        self.assertEqual(op.calls, 1)

    def test_default_limit_is_120_and_window_matches_the_response(self):
        self.assertEqual(bp.REQUEST_LIMIT, 120)
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(r["provider"]["request_limit"], 120)
        self.assertEqual(r["window"]["expected_completed_count"], 119)
        self.assertEqual(r["candles"]["first_open_utc"], r["window"]["expected_completed_start_utc"])
        self.assertEqual(r["candles"]["last_open_utc"], r["window"]["expected_completed_end_utc"])

    def test_identical_inputs_give_identical_reports(self):
        body = body_of(make_rows())
        a = run_t(opener=Opener(body))
        b = run_t(opener=Opener(body))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_market_and_provider_identity_are_recorded(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(r["market"]["canonical"], "crypto:binance-spot:BTC-USDT")
        self.assertEqual(r["market"]["listing"]["venue"], "binance")
        self.assertEqual(r["market"]["listing"]["market_type"], "spot")
        self.assertEqual(r["provider"]["name"], "binance-vision")
        self.assertEqual(r["provider"]["symbol"], "BTCUSDT")
        self.assertEqual(r["provider"]["auth"], "none (public market data)")

    def test_required_report_fields_are_present(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertTrue(REQUIRED_KEYS <= set(r), REQUIRED_KEYS - set(r))
        self.assertIn("dataset_sha256", r["candles"])
        self.assertIn("status", r["candles"]["validation"])
        self.assertIn("freshness", r["candles"])

    def test_signal_is_evaluated_only_once_on_the_validated_candles(self):
        real = bs.signal_at
        with mock.patch.object(bs, "signal_at", side_effect=real) as spy:
            run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(spy.call_count, 1)
        candles_passed = spy.call_args.args[0]
        self.assertEqual(len(candles_passed), bp.REQUEST_LIMIT - 1)


class ProvenanceTests(unittest.TestCase):
    """Fix 1: every result declares its data source and reference time. Live is never inferred or mislabeled."""

    def test_live_result_is_labeled_live_and_uses_the_real_fetch_path(self):
        body = body_of(make_rows())
        with mock.patch.object(fl, "fetch_body", return_value=body) as fb:
            r = bp.run(NOW, data_source="live", time_source="runtime-clock")
        self.assertEqual(fb.call_count, 1)
        self.assertEqual(len(fb.call_args.args), 1)            # no injected opener: the real path
        self.assertEqual(r["data_source"], "live")
        self.assertEqual(r["provider"]["network_requests_attempted"], 1)
        self.assertEqual(r["reference_time"]["source"], "runtime-clock")

    def test_replay_is_labeled_replay_never_live(self):
        r = bp.run(NOW, data_source="replay", time_source="explicit-caller",
                   opener=Opener(body_of(make_rows())))
        self.assertEqual(r["data_source"], "replay")
        self.assertEqual(r["provider"]["network_requests_attempted"], 0)
        self.assertEqual(r["reference_time"]["source"], "explicit-caller")
        md = bp.render_markdown(r)
        self.assertIn("**Data source: replay**", md)
        self.assertNotIn("Data source: live", md)

    def test_synthetic_is_labeled_synthetic_never_live(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(r["data_source"], "synthetic")
        self.assertEqual(r["provider"]["network_requests_attempted"], 0)
        md = bp.render_markdown(r)
        self.assertIn("**Data source: synthetic**", md)
        self.assertNotIn("Data source: live", md)
        self.assertIn("Not market data", r["data_source_note"])

    def test_each_source_appears_in_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            for src in ("replay", "synthetic"):
                r = bp.run(NOW, data_source=src, time_source="explicit-caller",
                           opener=Opener(body_of(make_rows())))
                targets, _ = bp.write_outputs(r, os.path.join(d, src))
                with open(targets["json"], encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["data_source"], src)
                with open(targets["md"], encoding="utf-8") as f:
                    self.assertIn(f"**Data source: {src}**", f.read())

    def test_injected_bytes_cannot_be_labeled_live(self):
        with self.assertRaises(bp.PipelineError) as cm:
            bp.run(NOW, data_source="live", time_source="explicit-caller", opener=Opener(body_of(make_rows())))
        self.assertIn("only valid for the real public endpoint", str(cm.exception))

    def test_replay_and_synthetic_cannot_use_the_network_path(self):
        with mock.patch.object(fl, "fetch_body", side_effect=AssertionError("network must not be used")):
            for src in ("replay", "synthetic"):
                with self.subTest(source=src):
                    with self.assertRaises(bp.PipelineError):
                        bp.run(NOW, data_source=src, time_source="explicit-caller")

    def test_replay_and_synthetic_require_explicit_reference_time(self):
        for src in ("replay", "synthetic"):
            with self.subTest(source=src):
                with self.assertRaises(bp.PipelineError):
                    bp.run(NOW, data_source=src, time_source="runtime-clock",
                           opener=Opener(body_of(make_rows())))

    def test_invalid_data_source_values_are_rejected(self):
        for bad in ("LIVE", "Live", "", "offline", "live ", None, 1):
            with self.subTest(value=bad):
                with self.assertRaises(bp.PipelineError):
                    bp.run(NOW, data_source=bad, time_source="explicit-caller",
                           opener=Opener(body_of(make_rows())))

    def test_invalid_time_source_values_are_rejected(self):
        for bad in ("", "clock", "Runtime-Clock", None):
            with self.subTest(value=bad):
                with self.assertRaises(bp.PipelineError):
                    bp.run(NOW, data_source="synthetic", time_source=bad,
                           opener=Opener(body_of(make_rows())))

    def test_data_source_and_time_source_are_required_keywords(self):
        with self.assertRaises(TypeError):
            bp.run(NOW, opener=Opener(body_of(make_rows())))

    def test_reference_time_is_recorded_with_its_source(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        self.assertEqual(r["reference_time"], {"now_s": NOW, "utc": bp.utc_text(NOW),
                                               "source": "explicit-caller"})

    def test_refusals_also_carry_data_source(self):
        r = bp.run(NOW, data_source="replay", time_source="explicit-caller", opener=Opener(exc=TimeoutError("t")))
        self.assertEqual(r["gate"]["status"], "REFUSED")
        self.assertEqual(r["data_source"], "replay")
        self.assertIn("**Data source: replay**", bp.render_markdown(r))

    def test_source_label_does_not_change_the_computed_result(self):
        """The source is a label only: the same bytes give the same numbers under replay and synthetic."""
        body = body_of(make_rows())
        a = bp.run(NOW, data_source="replay", time_source="explicit-caller", opener=Opener(body))
        b = bp.run(NOW, data_source="synthetic", time_source="explicit-caller", opener=Opener(body))
        for r in (a, b):
            for k in ("data_source", "data_source_note"):
                r.pop(k)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class SellMeaningTests(unittest.TestCase):
    """Fix 3: the decision explanation itself states what SELL means, not only a disclaimer elsewhere."""

    def test_sell_explanation_states_the_meaning(self):
        r = run_t(opener=Opener(body_of(make_rows(falling=True))))
        self.assertEqual(r["gate"]["status"], "PASSED", r["gate"])
        self.assertEqual(r["signal"]["decision"], "SELL")
        self.assertEqual(r["explanation"][0], SELL_TEXT)
        self.assertEqual(r["signal"]["decision_meaning"], SELL_TEXT)

    def test_markdown_states_the_sell_meaning_in_the_signal_section(self):
        r = run_t(opener=Opener(body_of(make_rows(falling=True))))
        md = bp.render_markdown(r)
        self.assertIn(f"- Meaning: {SELL_TEXT}", md)

    def test_each_decision_states_its_own_meaning(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        decision = r["signal"]["decision"]
        self.assertEqual(r["explanation"][0], bp.DECISION_MEANING[decision])
        self.assertIn(decision, r["explanation"][0])

    def test_sell_meaning_text_is_exact(self):
        self.assertEqual(bp.DECISION_MEANING["SELL"], SELL_TEXT)


class RefusalTests(unittest.TestCase):
    """Every refusal must: stop the run, record REFUSED with reasons, produce no signal, and never call S1."""

    def assertRefused(self, r, stage=None):
        self.assertEqual(r["gate"]["status"], "REFUSED")
        self.assertIsNone(r["signal"])
        self.assertTrue(r["gate"]["reasons"])
        self.assertIn("Signal NOT produced", r["explanation"][0])
        if stage is not None:
            self.assertEqual(r["gate"]["stage"], stage)

    def run_refused(self, opener, now=NOW, **kw):
        with mock.patch.object(bs, "signal_at", side_effect=AssertionError("S1 must not run")) as spy:
            r = run_t(now=now, opener=opener, **kw)
        self.assertEqual(spy.call_count, 0)
        return r

    def test_http_error_refuses(self):
        op = Opener(exc=urllib.error.HTTPError("https://x", 500, "server error", None, None))
        r = self.run_refused(op)
        self.assertRefused(r, "fetch_or_parse")
        self.assertEqual(op.calls, 1)                       # one attempt, no retry

    def test_non_200_status_refuses(self):
        r = self.run_refused(Opener(body_of(make_rows()), status=503))
        self.assertRefused(r, "fetch_or_parse")
        self.assertIn("503", r["gate"]["reasons"][0])

    def test_timeout_refuses_without_retry(self):
        op = Opener(exc=TimeoutError("timed out"))
        r = self.run_refused(op)
        self.assertRefused(r, "fetch_or_parse")
        self.assertEqual(op.calls, 1)

    def test_malformed_json_refuses(self):
        r = self.run_refused(Opener(b"<html>not json</html>"))
        self.assertRefused(r, "fetch_or_parse")

    def test_empty_list_refuses(self):
        r = self.run_refused(Opener(b"[]"))
        self.assertRefused(r, "fetch_or_parse")

    def test_duplicate_timestamp_refuses(self):
        rows = make_rows()
        rows.insert(10, list(rows[9]))                      # same open time twice
        r = self.run_refused(Opener(body_of(rows)))
        self.assertRefused(r, "fetch_or_parse")
        self.assertIn("not strictly consecutive", r["gate"]["reasons"][0])

    def test_internal_gap_refuses(self):
        rows = make_rows()
        del rows[40]                                        # a missing candle in the middle
        r = self.run_refused(Opener(body_of(rows)))
        self.assertRefused(r, "fetch_or_parse")

    def test_missing_leading_candle_is_refused_by_validation(self):
        rows = make_rows()
        del rows[0]                                         # first expected candle absent
        r = self.run_refused(Opener(body_of(rows)))
        self.assertRefused(r, "gates")
        joined = " ".join(r["gate"]["reasons"])
        self.assertIn("validation FAIL", joined)
        self.assertIn("expected_missing", joined)

    def test_forming_candle_beyond_the_last_row_refuses(self):
        rows = make_rows()
        day_start = (NOW // DAY) * DAY
        future = [(day_start + DAY) * 1000, "20100", "20110", "20090", "20105", "10",
                  (day_start + 2 * DAY) * 1000 - 1, "0", "0", "0", "0", "0"]
        rows.append(future)
        r = self.run_refused(Opener(body_of(rows)))
        self.assertRefused(r, "fetch_or_parse")
        self.assertIn("still forming", r["gate"]["reasons"][0])

    def test_stale_response_is_refused_by_the_gates(self):
        # A response built five days earlier, judged at NOW: it cannot match the expected window.
        r = self.run_refused(Opener(body_of(make_rows(now_s=NOW - 5 * DAY))))
        self.assertRefused(r, "gates")
        joined = " ".join(r["gate"]["reasons"])
        self.assertIn("stale", joined)

    def test_invalid_limit_refuses_before_any_request(self):
        op = Opener(body_of(make_rows()))
        r = self.run_refused(op, limit=1)
        self.assertRefused(r, "request")
        self.assertEqual(op.calls, 0)

    def test_refusal_report_is_still_complete_and_serializable(self):
        r = self.run_refused(Opener(exc=TimeoutError("timed out")))
        self.assertTrue(REQUIRED_KEYS <= set(r), REQUIRED_KEYS - set(r))
        json.dumps(r, sort_keys=True)


class FreshnessGateTests(unittest.TestCase):
    def test_boundary_is_inclusive(self):
        last_close = T0 + DAY
        self.assertTrue(bp.freshness_gate(last_close, last_close + bp.MAX_AGE_SECONDS)[0])
        self.assertFalse(bp.freshness_gate(last_close, last_close + bp.MAX_AGE_SECONDS + 1)[0])

    def test_close_after_fetch_time_is_refused(self):
        ok, age, reason = bp.freshness_gate(T0 + DAY, T0)
        self.assertFalse(ok)
        self.assertLess(age, 0)

    def test_stale_reason_names_staleness(self):
        ok, _, reason = bp.freshness_gate(T0, T0 + 10 * DAY)
        self.assertFalse(ok)
        self.assertIn("stale", reason)


class WindowTests(unittest.TestCase):
    def test_window_excludes_the_forming_slot(self):
        start, end = bp.window_for(NOW, 120)
        day_start = (NOW // DAY) * DAY
        self.assertEqual(end, day_start - DAY)
        self.assertEqual(start, day_start - 119 * DAY)
        self.assertEqual((end - start) // DAY + 1, 119)

    def test_window_rejects_bad_arguments(self):
        for now, limit in ((-1, 120), (True, 120), (NOW, 1), (NOW, True)):
            with self.subTest(now=now, limit=limit):
                with self.assertRaises(bp.PipelineError):
                    bp.window_for(now, limit)


class NormalizationTests(unittest.TestCase):
    def test_candles_are_canonical_markets_candles(self):
        import markets.candles as mc
        op = Opener(body_of(make_rows()))
        real = bp.to_canonical
        seen = {}

        def spy(s1):
            out = real(s1)
            seen["types"] = {type(c) for c in out}
            seen["times_are_int"] = all(isinstance(c.open_time_s, int) for c in out)
            return out

        with mock.patch.object(bp, "to_canonical", side_effect=spy):
            run_t(opener=op)
        self.assertEqual(seen["types"], {mc.Candle})
        self.assertTrue(seen["times_are_int"])

    def test_candle_without_volume_is_refused(self):
        s1 = [bs.Candle(T0, 1.0, 1.0, 1.0, 1.0, None)]
        with self.assertRaises(bp.PipelineError):
            bp.to_canonical(s1)


class DatasetHashTests(unittest.TestCase):
    def test_hash_is_deterministic(self):
        a = run_t(opener=Opener(body_of(make_rows())))["candles"]["dataset_sha256"]
        b = run_t(opener=Opener(body_of(make_rows())))["candles"]["dataset_sha256"]
        self.assertEqual(a, b)
        self.assertRegex(a, r"^[0-9a-f]{64}$")

    def test_hash_changes_when_one_price_changes(self):
        rows = make_rows()
        a = run_t(opener=Opener(body_of(rows)))["candles"]["dataset_sha256"]
        rows[5][2] = "21000.0"                              # keep OHLC consistent: raise the high ...
        rows[5][4] = "20999.5"                              # ... and move the close inside it
        b = run_t(opener=Opener(body_of(rows)))["candles"]["dataset_sha256"]
        self.assertNotEqual(a, b)


class OutputSafetyTests(unittest.TestCase):
    """Fix 2: safe output writing. A pair is written completely or not at all, and nothing pre-existing is lost."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="btc_pipeline_test_")
        self.result = run_t(opener=Opener(body_of(make_rows())))
        self.targets = bp._targets(self.result, self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def leftovers(self):
        return [n for n in os.listdir(self.dir) if n.startswith(".btc_pipeline_")]

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_clean_write_creates_both_files_and_no_temp_files(self):
        targets, warnings = bp.write_outputs(self.result, self.dir)
        self.assertTrue(os.path.isfile(targets["json"]))
        self.assertTrue(os.path.isfile(targets["md"]))
        self.assertEqual(warnings, [])
        self.assertEqual(self.leftovers(), [])

    def test_json_collision_refuses_and_preserves_the_existing_file(self):
        with open(self.targets["json"], "wb") as f:
            f.write(b"user json")
        with self.assertRaises(bp.OutputError):
            bp.write_outputs(self.result, self.dir)
        self.assertEqual(self.read(self.targets["json"]), b"user json")
        self.assertFalse(os.path.exists(self.targets["md"]))       # no half pair
        self.assertEqual(self.leftovers(), [])

    def test_markdown_collision_refuses_and_preserves_the_existing_file(self):
        with open(self.targets["md"], "wb") as f:
            f.write(b"user md")
        with self.assertRaises(bp.OutputError):
            bp.write_outputs(self.result, self.dir)
        self.assertEqual(self.read(self.targets["md"]), b"user md")
        self.assertFalse(os.path.exists(self.targets["json"]))     # the JSON was not written first
        self.assertEqual(self.leftovers(), [])

    def test_both_collisions_refuse_and_preserve_both(self):
        for ext in ("json", "md"):
            with open(self.targets[ext], "wb") as f:
                f.write(f"user {ext}".encode())
        with self.assertRaises(bp.OutputError) as cm:
            bp.write_outputs(self.result, self.dir)
        self.assertIn("nothing was written", str(cm.exception))
        self.assertEqual(self.read(self.targets["json"]), b"user json")
        self.assertEqual(self.read(self.targets["md"]), b"user md")

    def test_temp_write_failure_leaves_no_partial_pair_and_no_temp_files(self):
        real = bp._write_temp
        calls = {"n": 0}

        def flaky(out_dir, text):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full (simulated)")
            return real(out_dir, text)

        with mock.patch.object(bp, "_write_temp", side_effect=flaky):
            with self.assertRaises(bp.OutputError) as cm:
                bp.write_outputs(self.result, self.dir)
        self.assertIn("disk full", str(cm.exception))
        self.assertFalse(os.path.exists(self.targets["json"]))
        self.assertFalse(os.path.exists(self.targets["md"]))
        self.assertEqual(self.leftovers(), [])

    def test_finalization_failure_rolls_back_the_first_output(self):
        real_link = os.link
        calls = {"n": 0}

        def flaky_link(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("link refused (simulated)")
            return real_link(src, dst, *a, **kw)

        with mock.patch("btc_pipeline.os.link", side_effect=flaky_link):
            with self.assertRaises(bp.OutputError) as cm:
                bp.write_outputs(self.result, self.dir)
        self.assertIn("any partial files from this run were removed", str(cm.exception))
        self.assertFalse(os.path.exists(self.targets["json"]))     # rolled back
        self.assertFalse(os.path.exists(self.targets["md"]))
        self.assertEqual(self.leftovers(), [])

    def test_rollback_failure_names_the_leftover_file(self):
        real_link = os.link
        real_unlink = os.unlink
        calls = {"n": 0}

        def flaky_link(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("link refused (simulated)")
            return real_link(src, dst, *a, **kw)

        def stuck_unlink(path, *a, **kw):
            if path == self.targets["json"]:
                raise PermissionError("locked (simulated)")
            return real_unlink(path, *a, **kw)

        with mock.patch("btc_pipeline.os.link", side_effect=flaky_link), \
                mock.patch("btc_pipeline.os.unlink", side_effect=stuck_unlink):
            with self.assertRaises(bp.OutputError) as cm:
                bp.write_outputs(self.result, self.dir)
        self.assertIn("need manual cleanup", str(cm.exception))
        self.assertIn(self.targets["json"], str(cm.exception))

    def test_existing_unrelated_files_are_never_touched(self):
        other = os.path.join(self.dir, "notes.txt")
        with open(other, "wb") as f:
            f.write(b"keep me")
        real_link = os.link
        calls = {"n": 0}

        def flaky_link(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("link refused (simulated)")
            return real_link(src, dst, *a, **kw)

        with mock.patch("btc_pipeline.os.link", side_effect=flaky_link):
            with self.assertRaises(bp.OutputError):
                bp.write_outputs(self.result, self.dir)
        self.assertEqual(self.read(other), b"keep me")
        bp.write_outputs(self.result, self.dir)                    # a clean run afterwards still works
        self.assertEqual(self.read(other), b"keep me")

    def test_repeated_run_with_same_timestamp_is_refused_and_first_pair_intact(self):
        bp.write_outputs(self.result, self.dir)
        before = (self.read(self.targets["json"]), self.read(self.targets["md"]))
        with self.assertRaises(bp.OutputError):
            bp.write_outputs(self.result, self.dir)
        after = (self.read(self.targets["json"]), self.read(self.targets["md"]))
        self.assertEqual(before, after)
        self.assertEqual(self.leftovers(), [])

    def test_repeated_run_with_a_new_timestamp_writes_a_new_pair(self):
        bp.write_outputs(self.result, self.dir)
        later = run_t(now=NOW + DAY, opener=Opener(body_of(make_rows(now_s=NOW + DAY))))
        targets, _ = bp.write_outputs(later, self.dir)
        self.assertNotEqual(targets["json"], self.targets["json"])
        self.assertTrue(os.path.isfile(targets["json"]) and os.path.isfile(targets["md"]))

    def test_outputs_have_normal_file_permissions(self):
        targets, _ = bp.write_outputs(self.result, self.dir)
        self.assertEqual(os.stat(targets["json"]).st_mode & 0o777, 0o644)

    def test_output_directory_that_cannot_be_created_is_a_clean_error(self):
        blocker = os.path.join(self.dir, "afile")
        with open(blocker, "wb") as f:
            f.write(b"x")
        with self.assertRaises(bp.OutputError):
            bp.write_outputs(self.result, os.path.join(blocker, "sub"))

    def test_rollback_never_deletes_a_user_file_that_replaced_our_output(self):
        """A file put at our path during the run must survive a rollback. Only our own inode may be removed."""
        real_link = os.link
        calls = {"n": 0}

        def replacing_link(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return real_link(src, dst, *a, **kw)           # the JSON is ours
            # During the second link, someone replaces the JSON with their own file, then the link fails.
            os.unlink(self.targets["json"])
            with open(self.targets["json"], "wb") as f:
                f.write(b"user replaced it")
            raise OSError("link refused (simulated)")

        with mock.patch("btc_pipeline.os.link", side_effect=replacing_link):
            with self.assertRaises(bp.OutputError) as cm:
                bp.write_outputs(self.result, self.dir)
        self.assertEqual(self.read(self.targets["json"]), b"user replaced it")   # not deleted
        self.assertIn("left in place, not deleted", str(cm.exception))
        self.assertIn("need manual cleanup", str(cm.exception))
        self.assertFalse(os.path.exists(self.targets["md"]))

    def test_hard_link_unsupported_is_reported_clearly_and_writes_nothing(self):
        with mock.patch("btc_pipeline.os.link", side_effect=OSError(errno.EPERM, "Operation not permitted")):
            with self.assertRaises(bp.OutputError) as cm:
                bp.write_outputs(self.result, self.dir)
        self.assertIn("may not support hard links", str(cm.exception))
        self.assertFalse(os.path.exists(self.targets["json"]))
        self.assertFalse(os.path.exists(self.targets["md"]))
        self.assertEqual(self.leftovers(), [])

    def test_temp_cleanup_failure_after_success_is_a_warning_and_the_pair_is_complete(self):
        real_unlink = os.unlink

        def stuck_temp_unlink(path, *a, **kw):
            if os.path.basename(path).startswith(".btc_pipeline_"):
                raise PermissionError("locked (simulated)")
            return real_unlink(path, *a, **kw)

        with mock.patch("btc_pipeline.os.unlink", side_effect=stuck_temp_unlink):
            targets, warnings = bp.write_outputs(self.result, self.dir)
        self.assertTrue(os.path.isfile(targets["json"]) and os.path.isfile(targets["md"]))
        self.assertEqual(len(warnings), 2)
        self.assertTrue(all("could not be removed" in w for w in warnings))

    def test_failed_run_never_returns_a_success_value(self):
        """A failure must raise. There is no path that returns targets after a failed finalization."""
        real_link = os.link
        calls = {"n": 0}

        def flaky(src, dst, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("link refused (simulated)")
            return real_link(src, dst, *a, **kw)

        with mock.patch("btc_pipeline.os.link", side_effect=flaky):
            with self.assertRaises(bp.OutputError):
                bp.write_outputs(self.result, self.dir)


class ReportIntegrityTests(unittest.TestCase):
    """Fix/Task 3: the JSON and the Markdown written from the same run must agree on every key fact."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="btc_pipeline_integrity_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def written_pair(self, r):
        targets, _ = bp.write_outputs(r, self.dir)
        with open(targets["json"], encoding="utf-8") as f:
            j = json.load(f)
        with open(targets["md"], encoding="utf-8") as f:
            md = f.read()
        return j, md

    def assert_agree(self, j, md):
        # Data source and reference time
        self.assertIn(f"**Data source: {j['data_source']}**", md)
        self.assertIn(j["data_source_note"], md)
        self.assertIn(f"Reference time: {j['reference_time']['utc']} (source: {j['reference_time']['source']})", md)
        # Market and provider
        self.assertIn(f"Market: `{j['market']['canonical']}`", md)
        self.assertIn(f"{j['provider']['host']}{j['provider']['path']}", md)
        self.assertIn(f"network requests attempted {j['provider']['network_requests_attempted']}", md)
        # Gate and refusal reasons
        self.assertIn(f"**Gate: {j['gate']['status']}**", md)
        for reason in j["gate"]["reasons"]:
            self.assertIn(reason, md)
        # Dataset fingerprint and validation outcome
        if j["candles"] and "dataset_sha256" in j["candles"]:
            self.assertIn(f"`{j['candles']['dataset_sha256']}`", md)
            v = j["candles"]["validation"]
            self.assertIn(f"Validation: {v['status']} (ok={v['ok']}, coverage={v['coverage']})", md)
        # Signal and meaning
        if j["signal"] is None:
            self.assertIn("NOT PRODUCED (gate refused).", md)
            self.assertNotIn("- Decision:", md)
            self.assertEqual(j["gate"]["status"], "REFUSED")
        else:
            self.assertEqual(j["gate"]["status"], "PASSED")
            self.assertIn(f"- Decision: **{j['signal']['decision']}**", md)
            self.assertIn(f"- Meaning: {j['signal']['decision_meaning']}", md)
            self.assertNotIn("NOT PRODUCED", md)
        # A refusal must never present itself as a pass
        if j["gate"]["status"] == "REFUSED":
            self.assertNotIn("**Gate: PASSED**", md)
            self.assertIsNone(j["signal"])

    def test_passed_synthetic_run_pair_agrees(self):
        r = run_t(opener=Opener(body_of(make_rows())))
        j, md = self.written_pair(r)
        self.assertEqual(j["gate"]["status"], "PASSED")
        self.assert_agree(j, md)

    def test_passed_replay_run_pair_agrees(self):
        r = bp.run(NOW, data_source="replay", time_source="explicit-caller",
                   opener=Opener(body_of(make_rows(falling=True))))
        j, md = self.written_pair(r)
        self.assertEqual(j["signal"]["decision"], "SELL")
        self.assert_agree(j, md)
        self.assertIn(bp.DECISION_MEANING["SELL"], md)

    def test_refused_timeout_pair_agrees_and_shows_no_signal(self):
        r = run_t(opener=Opener(exc=TimeoutError("timed out (simulated)")))
        j, md = self.written_pair(r)
        self.assertIsNone(j["signal"])
        self.assert_agree(j, md)

    def test_refused_stale_pair_agrees_and_lists_the_reason(self):
        r = run_t(opener=Opener(body_of(make_rows(now_s=NOW - 5 * DAY))))
        j, md = self.written_pair(r)
        self.assertEqual(j["gate"]["status"], "REFUSED")
        self.assertTrue(any("stale" in x for x in j["gate"]["reasons"]))
        self.assert_agree(j, md)

    def test_refused_validation_pair_agrees_and_lists_the_failure(self):
        rows = make_rows()
        del rows[0]
        r = run_t(opener=Opener(body_of(rows)))
        j, md = self.written_pair(r)
        self.assertEqual(j["gate"]["stage"], "gates")
        self.assert_agree(j, md)

    def test_live_refusal_pair_carries_live_provenance(self):
        with mock.patch.object(fl, "fetch_body", side_effect=fl.FetchError("request failed, nothing written: denied")):
            r = bp.run(NOW, data_source="live", time_source="runtime-clock")
        j, md = self.written_pair(r)
        self.assertEqual(j["data_source"], "live")
        self.assertEqual(j["provider"]["network_requests_attempted"], 1)
        self.assert_agree(j, md)
        self.assertIn("**Data source: live**", md)


class RenderTests(unittest.TestCase):
    def test_markdown_renders_success_and_refusal(self):
        ok = bp.render_markdown(run_t(opener=Opener(body_of(make_rows()))))
        self.assertIn("Gate: PASSED", ok)
        self.assertIn("Decision:", ok)
        refused = bp.render_markdown(run_t(opener=Opener(exc=TimeoutError("t"))))
        self.assertIn("Gate: REFUSED", refused)
        self.assertIn("NOT PRODUCED", refused)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="btc_pipeline_main_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_main_writes_json_and_markdown_and_returns_zero_on_pass(self):
        code = quiet_main(self.dir, opener=Opener(body_of(make_rows())))
        self.assertEqual(code, 0)
        names = sorted(os.listdir(self.dir))
        self.assertEqual(len(names), 2)
        with open(os.path.join(self.dir, [n for n in names if n.endswith(".json")][0]), encoding="utf-8") as f:
            report = json.load(f)
        self.assertEqual(report["gate"]["status"], "PASSED")
        self.assertEqual(report["data_source"], "synthetic")

    def test_main_returns_two_on_refusal(self):
        code = quiet_main(self.dir, opener=Opener(exc=TimeoutError("t")))
        self.assertEqual(code, 2)

    def test_main_repeated_run_is_a_clean_output_error_not_a_traceback(self):
        quiet_main(self.dir, opener=Opener(body_of(make_rows())))
        code, out = main_output(["--out-dir", self.dir, "--data-source", "synthetic"],
                                opener=Opener(body_of(make_rows())), now_s=NOW)
        self.assertEqual(code, bp.EXIT_OUTPUT_ERROR)
        self.assertIn("output error", out)
        self.assertIn("already exist", out)

    def test_main_collision_exit_code_and_message(self):
        with open(os.path.join(self.dir, f"btc_pipeline_{self._stamp()}.md"), "wb") as f:
            f.write(b"user md")
        code, out = main_output(["--out-dir", self.dir, "--data-source", "synthetic"],
                                opener=Opener(body_of(make_rows())), now_s=NOW)
        self.assertEqual(code, 3)
        self.assertIn("output error", out)

    def _stamp(self):
        import time
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(NOW))

    def test_main_requires_an_explicit_data_source(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                bp.main(["--out-dir", self.dir], opener=Opener(body_of(make_rows())), now_s=NOW)

    def test_main_invalid_provenance_writes_nothing_and_returns_one(self):
        code, out = main_output(["--out-dir", self.dir, "--data-source", "replay"], now_s=NOW)
        self.assertEqual(code, bp.EXIT_INVALID)
        self.assertIn("invalid run", out)
        self.assertEqual(os.listdir(self.dir), [])

    def test_main_live_without_injected_bytes_uses_the_fetch_path(self):
        with mock.patch.object(fl, "fetch_body", return_value=body_of(make_rows())) as fb:
            code, out = main_output(["--out-dir", self.dir, "--data-source", "live"], now_s=NOW)
        self.assertEqual(fb.call_count, 1)
        self.assertEqual(code, 0)
        self.assertIn("data source: live", out)

    def test_main_records_explicit_now_as_explicit_caller(self):
        code, _ = main_output(["--out-dir", self.dir, "--data-source", "synthetic", "--now", str(NOW)],
                              opener=Opener(body_of(make_rows())))
        self.assertEqual(code, 0)
        json_name = [n for n in os.listdir(self.dir) if n.endswith(".json")][0]
        with open(os.path.join(self.dir, json_name), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["reference_time"]["source"], "explicit-caller")


class BoundaryTests(unittest.TestCase):
    def test_pipeline_module_has_no_third_party_or_account_imports(self):
        import ast
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "btc_pipeline.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        allowed = {"argparse", "errno", "hashlib", "json", "os", "sys", "tempfile", "time", "btc_signal",
                   "fetch_latest", "markets", "urllib", "unittest"}
        self.assertTrue(names <= allowed, names - allowed)


if __name__ == "__main__":
    unittest.main()
