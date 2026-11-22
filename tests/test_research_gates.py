"""Safe cross-check gate tests using only the unprotected research.crosscheck module.

The production pipeline adapts CrosscheckError to its protected engine error type,
but these tests exercise the same dataset-evidence validation without importing or
executing research.pipeline, research.engine, validator.py, or report.py.
"""
import ast
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import research.crosscheck as crosscheck
from research.crosscheck import (
    CrosscheckError, CROSSCHECK_ARTIFACT_PRODUCER, CROSSCHECK_ARTIFACT_SCHEMA,
    CONFIRMED_VERDICT, build_markdown, compare, is_confirmed_verdict,
    load_required_crosscheck, run_crosscheck, to_ts, validate_crosscheck_artifact,
)
from research.backtest_report import (
    build_markdown as build_backtest_markdown, market_source_label,
    _crosscheck_markdown_lines,
)

MANIFEST = {"version_id": "v-test", "csv_sha256": "a" * 64}
CFG = {"flagged_dates": ["2020-03-12"]}
TEST_APPROVED = frozenset({"coinbase", "bitstamp"})


class CrosscheckGateTests(unittest.TestCase):
    def write_evidence(self, directory, payload):
        path = os.path.join(directory, "crosscheck.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return path

    def comparison_source(self, agrees=True):
        agrees_by_metrics = agrees is True
        difference = 1.0 if agrees_by_metrics else 4.0
        return {
            "open_diff_pct": difference,
            "close_diff_pct": difference,
            "high_diff_pct": 1.0,
            "low_diff_pct": 1.0,
            "binance_return_pct": 5.0 if not agrees_by_metrics else 2.0,
            "other_return_pct": 1.0,
            "return_gap_pp": 1.0 if agrees_by_metrics else 4.0,
            "agrees": agrees,
        }

    def payload(self, verdict=CONFIRMED_VERDICT, providers=("coinbase", "bitstamp"),
                agreements=None):
        agreements = agreements or {}
        entry = {"date": "2020-03-12", "verdict": verdict}
        for provider in providers:
            entry[provider] = self.comparison_source(agreements.get(provider, True))
        return {
            "schema": CROSSCHECK_ARTIFACT_SCHEMA,
            "producer": CROSSCHECK_ARTIFACT_PRODUCER,
            "dataset_version": "v-test",
            "dataset_sha256": "a" * 64,
            "providers": list(providers),
            "flagged": [entry],
        }

    def test_production_crosscheck_loader_stays_disabled_even_if_module_constant_is_reassigned(self):
        original = crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS
        try:
            crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = TEST_APPROVED
            with self.assertRaisesRegex(CrosscheckError, "at least two distinct authorized providers"):
                load_required_crosscheck(CFG, MANIFEST, None)
        finally:
            crosscheck.AUTHORIZED_CROSSCHECK_PROVIDERS = original

    def test_validator_requires_two_authorized_providers(self):
        with self.assertRaisesRegex(CrosscheckError, "at least two distinct authorized providers"):
            validate_crosscheck_artifact(CFG, MANIFEST, None, frozenset({"coinbase"}))

    def test_missing_artifact_is_blocked_when_two_providers_are_authorized(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(CrosscheckError, "no artifact"):
                validate_crosscheck_artifact(
                    CFG, MANIFEST, os.path.join(d, "missing.json"), TEST_APPROVED
                )

    def test_dataset_version_and_hash_must_match(self):
        for field, value in (("dataset_version", "wrong-version"),
                             ("dataset_sha256", "b" * 64)):
            with tempfile.TemporaryDirectory() as d:
                payload = self.payload()
                payload[field] = value
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "does not match"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_artifact_requires_exact_schema_and_producer_identity(self):
        for field, value in (("schema", "twin-money-maker.crosscheck/v999"),
                             ("producer", "untrusted.producer")):
            with tempfile.TemporaryDirectory() as d:
                payload = self.payload()
                payload[field] = value
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "schema or producer"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW is not available")
    def test_symlinked_crosscheck_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            target = self.write_evidence(d, self.payload())
            path = os.path.join(d, "linked-crosscheck.json")
            os.symlink(target, path)
            with self.assertRaisesRegex(
                    CrosscheckError, "artifact is unreadable: ValueError"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_non_string_crosscheck_path_is_rejected_as_crosscheck_error(self):
        for path in ([], {}, 123, object()):
            with self.subTest(path_type=type(path).__name__):
                with self.assertRaisesRegex(
                        CrosscheckError, "path must be a non-empty string"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_symlinked_crosscheck_artifact_is_rejected_without_nofollow_flag(self):
        with tempfile.TemporaryDirectory() as d:
            target = self.write_evidence(d, self.payload())
            path = os.path.join(d, "linked-crosscheck.json")
            try:
                os.symlink(target, path)
            except (NotImplementedError, OSError):
                self.skipTest("symlink creation is not available")
            # Exercise the portable fallback even on Linux, where O_NOFOLLOW exists.
            with mock.patch.object(crosscheck.os, "O_NOFOLLOW", 0, create=True):
                with self.assertRaisesRegex(
                        CrosscheckError, "artifact is unreadable: ValueError"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_oversized_crosscheck_artifact_is_rejected_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "crosscheck.json")
            with open(path, "wb") as f:
                f.write(b" " * (crosscheck.MAX_CROSSCHECK_ARTIFACT_BYTES + 1))
            with self.assertRaisesRegex(
                    CrosscheckError, "artifact is unreadable: ValueError"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_duplicate_json_object_keys_are_rejected_at_any_depth(self):
        valid = json.dumps(self.payload())
        duplicate_cases = (
            valid.replace(
                '"schema": "twin-money-maker.crosscheck/v1"',
                '"schema": "twin-money-maker.crosscheck/v1", '
                '"schema": "twin-money-maker.crosscheck/v1"',
                1,
            ),
            valid.replace(
                '"date": "2020-03-12"',
                '"date": "2020-03-12", "date": "2020-03-12"',
                1,
            ),
        )
        for raw in duplicate_cases:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "crosscheck.json")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(raw)
                with self.assertRaisesRegex(
                        CrosscheckError, "artifact is unreadable: ValueError"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_non_standard_json_numeric_constants_are_rejected(self):
        raw = json.dumps(self.payload()).replace(
            '"dataset_version": "v-test"', '"dataset_version": NaN', 1
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "crosscheck.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(raw)
            with self.assertRaisesRegex(
                    CrosscheckError, "artifact is unreadable: ValueError"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_provider_must_be_explicitly_authorized_and_distinct(self):
        payloads = (
            self.payload(providers=("coinbase", "kraken")),
            self.payload(providers=("coinbase", "coinbase")),
            self.payload(providers=("coinbase",)),
        )
        for payload in payloads:
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(providers=payload["providers"]), self.assertRaises(CrosscheckError):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_malformed_or_duplicate_flagged_entries_are_rejected(self):
        malformed = []
        missing_list = self.payload()
        missing_list["flagged"] = None
        malformed.append(missing_list)
        non_object = self.payload()
        non_object["flagged"] = ["not-an-object"]
        malformed.append(non_object)
        duplicate_date = self.payload()
        duplicate_date["flagged"].append(dict(duplicate_date["flagged"][0]))
        malformed.append(duplicate_date)
        extra_date = self.payload()
        extra_date["flagged"].append({
            "date": "2020-03-13", "verdict": CONFIRMED_VERDICT,
            "coinbase": {"agrees": True}, "bitstamp": {"agrees": True},
        })
        malformed.append(extra_date)
        for payload in malformed:
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(payload=payload), self.assertRaises(CrosscheckError):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_each_flagged_date_requires_affirmative_evidence_from_both_providers(self):
        for agreements in (
            {"coinbase": False, "bitstamp": True},
            {"coinbase": True, "bitstamp": False},
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(agreements=agreements))
                with self.subTest(agreements=agreements), self.assertRaisesRegex(
                        CrosscheckError, "lacks affirmative agreement"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

        for agreements in (
            {"coinbase": None, "bitstamp": True},
            {"coinbase": 1, "bitstamp": True},
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(agreements=agreements))
                with self.subTest(agreements=agreements), self.assertRaisesRegex(
                        CrosscheckError, "invalid comparison evidence"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

        payload = self.payload()
        del payload["flagged"][0]["bitstamp"]
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, payload)
            with self.assertRaisesRegex(CrosscheckError, "malformed flagged entry"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_comparison_metrics_must_be_finite_and_match_the_agreement_rule(self):
        mutations = (
            ("close_diff_pct", 4.0),
            ("return_gap_pp", 4.0),
            ("low_diff_pct", 10 ** 1000),
            ("open_diff_pct", True),
        )
        for field, value in mutations:
            payload = self.payload()
            payload["flagged"][0]["coinbase"][field] = value
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "invalid comparison evidence"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

        payload = self.payload()
        raw = json.dumps(payload).replace(
            '"high_diff_pct": 1.0', '"high_diff_pct": 1e999', 1
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "crosscheck.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(raw)
            with self.assertRaisesRegex(
                    CrosscheckError, "invalid comparison evidence"):
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_return_gap_must_match_the_two_reported_daily_returns(self):
        for field, value in (
            ("binance_return_pct", 5.0),
            ("other_return_pct", -4.0),
            ("return_gap_pp", 9.0),
        ):
            payload = self.payload()
            payload["flagged"][0]["coinbase"][field] = value
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(field=field), self.assertRaisesRegex(
                        CrosscheckError, "invalid comparison evidence"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

        payload = self.payload()
        payload["flagged"][0]["coinbase"]["binance_return_pct"] = 2.0000000001
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, payload)
            self.assertEqual(
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED),
                payload,
            )

    def test_versioned_artifact_rejects_unrecognized_fields(self):
        for mutation in ("top-level", "flagged-entry"):
            payload = self.payload()
            if mutation == "top-level":
                payload["unrecognized"] = "ignored?"
            else:
                payload["flagged"][0]["unrecognized"] = "ignored?"
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, payload)
                with self.subTest(mutation=mutation), self.assertRaisesRegex(
                        CrosscheckError,
                        "unsupported fields" if mutation == "top-level" else "malformed flagged entry"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_invalid_pinned_dataset_manifest_identity_is_rejected(self):
        for manifest in (
            {"version_id": None, "csv_sha256": "a" * 64},
            {"version_id": "v-test", "csv_sha256": "not-a-sha256"},
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload())
                with self.subTest(manifest=manifest), self.assertRaisesRegex(
                        CrosscheckError, "manifest identity is invalid"):
                    validate_crosscheck_artifact(CFG, manifest, path, TEST_APPROVED)

    def test_only_exact_confirmed_verdict_is_accepted(self):
        self.assertTrue(is_confirmed_verdict(CONFIRMED_VERDICT))
        for verdict in (
            "CONFIRMED",
            "CONFIRMED_UNTRUSTED",
            "CONFIRMED-malformed",
            "CONFIRMED but not actually confirmed",
            "NOT CONFIRMED",
            "UNAVAILABLE",
            "",
            None,
            {"verdict": CONFIRMED_VERDICT},
        ):
            with self.subTest(verdict=verdict):
                self.assertFalse(is_confirmed_verdict(verdict))
        for verdict in (
            "CONFIRMED_UNTRUSTED",
            "CONFIRMED-malformed",
            "NOT CONFIRMED",
            "UNAVAILABLE",
        ):
            with tempfile.TemporaryDirectory() as d:
                path = self.write_evidence(d, self.payload(verdict=verdict))
                with self.subTest(verdict=verdict), self.assertRaisesRegex(
                        CrosscheckError, "exact confirmed verdict"):
                    validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED)

    def test_every_flagged_date_must_have_two_source_confirmation(self):
        cfg = {"flagged_dates": ["2020-03-12", "2020-03-13"]}
        with tempfile.TemporaryDirectory() as d:
            path = self.write_evidence(d, self.payload())
            with self.assertRaisesRegex(CrosscheckError, "flagged dates do not exactly match"):
                validate_crosscheck_artifact(cfg, MANIFEST, path, TEST_APPROVED)

    def test_valid_dataset_bound_two_provider_evidence_is_accepted_by_validator(self):
        with tempfile.TemporaryDirectory() as d:
            payload = self.payload()
            path = self.write_evidence(d, payload)
            self.assertEqual(
                validate_crosscheck_artifact(CFG, MANIFEST, path, TEST_APPROVED), payload
            )

    def test_comparison_never_confirms_when_either_independent_source_is_missing_or_disagrees(self):
        previous = to_ts("2020-03-11")
        target = to_ts("2020-03-12")

        def candle(timestamp, price):
            return SimpleNamespace(
                time=timestamp, open=price, high=price, low=price, close=price
            )

        binance = [candle(previous, 100), candle(target, 110)]
        coinbase = {previous: candle(previous, 100), target: candle(target, 110)}
        bitstamp = {previous: candle(previous, 100), target: candle(target, 110)}

        result = compare(binance, coinbase, {}, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], "UNAVAILABLE")

        result = compare(binance, coinbase, bitstamp, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], CONFIRMED_VERDICT)

        disagreeing = {
            previous: candle(previous, 100),
            target: candle(target, 200),
        }
        result = compare(binance, coinbase, disagreeing, ["2020-03-12"])
        self.assertEqual(result["flagged"][0]["verdict"], "NOT CONFIRMED")

    def test_disabled_crosscheck_refuses_before_injected_transport_or_filesystem_use(self):
        calls = []

        def forbidden_opener(*args, **kwargs):
            calls.append(("opener", args, kwargs))
            raise AssertionError("cross-check opener must never be called")

        def forbidden_sleep(*args, **kwargs):
            calls.append(("sleep", args, kwargs))
            raise AssertionError("cross-check sleep must never be called")

        with self.assertRaisesRegex(Exception, "independent cross-check providers are not authorized") as ctx:
            run_crosscheck(
                MANIFEST, (), ["2020-03-12"], object(),
                opener=forbidden_opener, sleep=forbidden_sleep,
                timeout="invalid", retries=-1,
            )
        self.assertEqual(type(ctx.exception).__name__, "ApiError")
        self.assertEqual(calls, [])

    def test_no_flagged_dates_does_not_require_crosscheck(self):
        self.assertIsNone(load_required_crosscheck(
            {"flagged_dates": []}, MANIFEST, None
        ))


class CrosscheckMarkdownSanitizationTests(unittest.TestCase):
    class HostileNumber:
        def __format__(self, spec):
            raise AssertionError("caller-controlled __format__ executed")

        def __str__(self):
            raise AssertionError("caller-controlled __str__ executed")

    def test_report_builder_never_formats_custom_objects_as_numbers(self):
        evil = self.HostileNumber()
        report = {
            "dataset_version": "v-test",
            "dataset_sha256": "a" * 64,
            "rule": "approved rule\n# injected heading",
            "coinbase_error": None,
            "bitstamp_error": None,
            "common_days": evil,
            "summary": {
                "median_abs_close_diff_pct": evil,
                "p95_abs_close_diff_pct": evil,
                "p99_abs_close_diff_pct": evil,
                "max_abs_close_diff_pct": evil,
                "days_over_1pct": evil,
                "days_over_2pct": 0,
                "days_over_5pct": 0,
            },
            "worst_days": [{"date": "2020-03-12", "abs_close_diff_pct": evil}],
            "flagged": [{
                "date": "2020-03-12",
                "verdict": "UNAVAILABLE\n# injected verdict",
                "table": [{
                    "date": "2020-03-12", "source": evil,
                    "open": evil, "high": evil, "low": evil, "close": evil,
                }],
                "coinbase": {
                    "open_diff_pct": evil, "close_diff_pct": evil,
                    "high_diff_pct": evil, "low_diff_pct": evil,
                    "binance_return_pct": evil, "other_return_pct": evil,
                    "return_gap_pp": evil, "agrees": evil,
                },
                "bitstamp": None,
            }],
        }
        rendered = build_markdown(report)
        self.assertIn("unavailable", rendered)
        self.assertIn("approved rule # injected heading", rendered)
        self.assertNotIn("\n# injected heading", rendered)
        self.assertNotIn("\n# injected verdict", rendered)

    def test_report_builder_formats_finite_builtin_numbers_and_rejects_non_finite_values(self):
        report = {
            "dataset_version": "v-test",
            "dataset_sha256": "a" * 64,
            "rule": "test",
            "coinbase_error": None,
            "bitstamp_error": None,
            "common_days": 2,
            "summary": {
                "median_abs_close_diff_pct": 1.25,
                "p95_abs_close_diff_pct": 2.5,
                "p99_abs_close_diff_pct": float("inf"),
                "max_abs_close_diff_pct": 3,
                "days_over_1pct": True,
                "days_over_2pct": 1,
                "days_over_5pct": 0,
            },
            "worst_days": [{"date": "2020-03-12", "abs_close_diff_pct": 1.25}],
            "flagged": [],
        }
        rendered = build_markdown(report)
        self.assertIn("| Median | 1.250% |", rendered)
        self.assertIn("| 99th percentile | unavailable% |", rendered)
        self.assertIn("| Days over 1% / 2% / 5% | unavailable / 1 / 0 |", rendered)


class BacktestReportMarketProvenanceTests(unittest.TestCase):
    def test_market_label_comes_from_the_pinned_manifest_shape(self):
        market = {
            "provider": "tokocrypto",
            "pair_label": "BTC/USDT",
            "timeframe": "1d",
            "market_type": "spot",
        }
        self.assertEqual(
            market_source_label(market), "tokocrypto BTC/USDT 1d spot"
        )

    def test_market_label_rejects_missing_or_control_character_values(self):
        self.assertEqual(
            market_source_label(None),
            "unknown (market identity unverified)",
        )
        self.assertEqual(
            market_source_label({
                "provider": "tokocrypto\n# injected",
                "pair_label": "BTC/USDT",
                "timeframe": "1d",
                "market_type": "spot",
            }),
            "unknown (market identity unverified)",
        )

    def test_flagged_comparison_uses_the_manifest_market_label(self):
        path = os.path.join(ROOT, "research", "backtest_report.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("vs {market_label}", source)
        self.assertNotIn("vs Binance", source)

    class HostileReportNumber:
        def __format__(self, spec):
            raise AssertionError("untrusted cross-check number formatter executed")

        def __float__(self):
            raise AssertionError("untrusted cross-check number conversion executed")

    def test_crosscheck_report_sanitizes_all_untrusted_text_and_numeric_fields(self):
        evil = self.HostileReportNumber()
        lines = _crosscheck_markdown_lines({
            "rule": "approved rule\n# injected rule",
            "flagged": [{
                "date": "2020-03-12\n# injected date",
                "verdict": "CONFIRMED\n# injected verdict",
                "coinbase": {
                    "other_return_pct": evil,
                    "binance_return_pct": 1.25,
                    "close_diff_pct": 0.5,
                    "low_diff_pct": float("inf"),
                },
                "bitstamp": None,
            }],
            "summary": {
                "median_abs_close_diff_pct": 1.25,
                "p99_abs_close_diff_pct": evil,
                "max_abs_close_diff_pct": float("nan"),
            },
            "coinbase_error": "provider refused\n# injected error",
        }, "tokocrypto BTC/USDT 1d spot")
        rendered = "\n".join(lines)
        self.assertIn("approved rule injected rule", rendered)
        self.assertIn("2020-03-12 injected date", rendered)
        self.assertIn("CONFIRMED injected verdict", rendered)
        self.assertIn("day return unavailable%", rendered)
        self.assertIn("close diff +0.50%", rendered)
        self.assertIn("low diff unavailable%", rendered)
        self.assertIn("99th percentile unavailable%", rendered)
        self.assertIn("max unavailable%", rendered)
        self.assertIn("provider refused injected error", rendered)
        self.assertNotIn("# injected", rendered)

    def test_report_sanitizes_stopped_run_and_manifest_metadata(self):
        report = build_backtest_markdown({
            "run_id": "run-42\n# injected run heading",
            "status": "STOPPED",
            "error": "market identity gate failed\n# injected error heading",
            "dataset": {
                "market": {
                    "provider": "tokocrypto\n# injected provider",
                    "pair_label": "BTC/USDT",
                    "timeframe": "1d",
                    "market_type": "spot",
                },
            },
        })
        self.assertIn("Run run-42 injected run heading", report)
        self.assertIn("market identity gate failed injected error heading", report)
        self.assertIn("unknown (market identity unverified)", report)
        self.assertNotIn("\n# injected", report)
        self.assertNotIn("# injected", report)

        path = os.path.join(ROOT, "research", "backtest_report.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("_safe_report_text(d.get('version_id'))", source)
        self.assertIn("_safe_report_hash(d.get('sha256'))", source)
        self.assertNotIn("d['market']['provider']", source)
        self.assertNotIn("r['error']", source)

    def test_stopped_report_uses_manifest_label_and_never_hard_codes_binance(self):
        report = build_backtest_markdown({
            "run_id": "unit-test",
            "status": "STOPPED",
            "error": "market identity gate failed",
            "dataset": {
                "market": {
                    "provider": "tokocrypto",
                    "pair_label": "BTC/USDT",
                    "timeframe": "1d",
                    "market_type": "spot",
                }
            },
        })
        self.assertIn("tokocrypto BTC/USDT 1d spot", report)
        self.assertIn("not independent proof of instrument identity", report)
        self.assertNotIn("Binance BTC/USDT", report)


class CrosscheckPipelineBoundaryTests(unittest.TestCase):
    def test_backtest_loader_passes_a_fresh_empty_authorization_set(self):
        path = os.path.join(ROOT, "research", "pipeline.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)

        assignments = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if any(isinstance(target, ast.Name)
                   and target.id == "AUTHORIZED_CROSSCHECK_PROVIDERS"
                   for target in targets):
                assignments.append(node)
        self.assertEqual(assignments, [])

        loader = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "load_required_crosscheck")
        calls = [node for node in ast.walk(loader)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "validate_crosscheck_artifact"]
        self.assertEqual(len(calls), 1)
        authorization = calls[0].args[-1]
        self.assertIsInstance(authorization, ast.Call)
        self.assertIsInstance(authorization.func, ast.Name)
        self.assertEqual(authorization.func.id, "frozenset")
        self.assertEqual(authorization.args, [])
        self.assertEqual(authorization.keywords, [])


class HistoryGateStaticTests(unittest.TestCase):
    def test_unverified_market_identity_fails_without_any_network_request(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"name": "market_identity", "status": "FAIL"', source)
        self.assertIn('"network_requests": 0', source)
        self.assertIn('"backtest_allowed": False', source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("import validator", source)


if __name__ == "__main__":
    unittest.main()
