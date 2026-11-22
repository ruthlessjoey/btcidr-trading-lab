"""Static offline tests for the legacy candle runner's exact source boundary.

Do not import run.py here: it imports the protected validator.py module.
"""
import ast
import json
import os
import re
import subprocess
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_STATIC_ONLY_SOURCES = frozenset({
    "research/pipeline.py",
    "run.py",
    ".github/workflows/research-data.yml",
    ".github/workflows/research-backtest.yml",
    ".github/workflows/q08-offline-tests.yml",
})


def _verified_git_head_sha():
    """Bind static Git-blob reads to the exact commit GitHub Actions checked out."""
    expected = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        raise RuntimeError("GITHUB_SHA is unavailable or invalid")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    actual = result.stdout.strip()
    if actual != expected:
        raise RuntimeError("checked-out HEAD does not match GITHUB_SHA")
    return expected


def git_source_text(path):
    """Read only an allowlisted blob from the exact GitHub Actions commit."""
    if path not in _STATIC_ONLY_SOURCES:
        raise ValueError("source path is not approved for static inspection")
    verified_sha = _verified_git_head_sha()
    result = subprocess.run(
        ["git", "show", verified_sha + ":" + path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout



class PipelineContainmentTests(unittest.TestCase):
    def test_crosscheck_authorization_is_empty_immutable_and_wired_statically(self):
        crosscheck_path = os.path.join(ROOT, "research", "crosscheck.py")
        with open(crosscheck_path, encoding="utf-8") as f:
            crosscheck_tree = ast.parse(f.read(), filename=crosscheck_path)
        authorization = [
            node for node in crosscheck_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "AUTHORIZED_CROSSCHECK_PROVIDERS"
                    for target in node.targets)
        ]
        self.assertEqual(len(authorization), 1)
        value = authorization[0].value
        self.assertIsInstance(value, ast.Call)
        self.assertIsInstance(value.func, ast.Name)
        self.assertEqual(value.func.id, "frozenset")
        self.assertEqual(value.args, [])
        self.assertEqual(value.keywords, [])

        # Inspect the pipeline as text only. Do not import it: its dependency
        # chain reaches the protected research engine/validator boundary.
        pipeline_path = os.path.join(ROOT, "research", "pipeline.py")
        pipeline_tree = ast.parse(
            git_source_text("research/pipeline.py"), filename="research/pipeline.py"
        )
        wiring = [
            node for node in pipeline_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "AUTHORIZED_CROSSCHECK_PROVIDERS"
                    for target in node.targets)
        ]
        self.assertEqual(len(wiring), 1)
        wired_value = wiring[0].value
        self.assertIsInstance(wired_value, ast.Attribute)
        self.assertEqual(wired_value.attr, "AUTHORIZED_CROSSCHECK_PROVIDERS")
        self.assertIsInstance(wired_value.value, ast.Name)
        self.assertEqual(wired_value.value.id, "crosscheck")

        # The owner-authorization gate must run before split creation. Inspect
        # syntax only; do not import or execute the pipeline.
        run_backtest = next(
            node for node in pipeline_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_backtest"
        )
        gate_calls = [
            node for node in ast.walk(run_backtest)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "load_required_crosscheck"
        ]
        split_calls = [
            node for node in ast.walk(run_backtest)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "splits_mod"
            and node.func.attr == "make_splits"
        ]
        self.assertEqual(len(gate_calls), 1)
        self.assertEqual(len(split_calls), 1)
        self.assertLess(gate_calls[0].lineno, split_calls[0].lineno)

    def test_default_config_contains_only_exact_tokocrypto_source(self):
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["sources"], [{
            "name": "tokocrypto-mbx",
            "style": "binance_style",
            "base_url": "https://www.tokocrypto.site",
        }])
        self.assertEqual(cfg["live_providers"], ["tokocrypto"])

    def test_run_pipeline_rejects_any_other_source_configuration_before_io(self):
        source = git_source_text("run.py")
        guard = 'if cfg.get("sources") != [{"name": "tokocrypto-mbx"'
        self.assertIn(guard, source)
        self.assertLess(source.index(guard), source.index('os.makedirs(out_dir, exist_ok=True)'))
        self.assertLess(source.index(guard), source.index('for source_cfg in cfg["sources"]'))

    def test_undocumented_server_time_route_is_not_in_the_transport_allowlist(self):
        with open(os.path.join(ROOT, "fetcher.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('APPROVED_PATHS = {"/api/v3/klines"}', source)
        self.assertIn("Tokocrypto server-time route is unverified; no network request was made", source)

    def test_market_data_check_remains_blocked_without_protected_validator_access(self):
        with open(os.path.join(ROOT, ".github", "workflows", "market-data-check.yml"),
                  encoding="utf-8") as f:
            workflow = f.read()
        self.assertIn("blocked pending protected validator review", workflow)
        self.assertIn("live_check.py imports protected validator.py/report.py", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("python3 live_check.py", workflow)
        self.assertIn("No checkout, test, protected file access, network request, or exchange call occurred.", workflow)

    def test_research_data_workflow_executes_only_the_offline_step1_entrypoint(self):
        with open(os.path.join(ROOT, ".github", "workflows", "research-data.yml"),
                  encoding="utf-8") as f:
            workflow = f.read()
        self.assertIn("python3 fetch_history.py", workflow)
        self.assertIn("python3 -m unittest discover -s tests -p 'test_pipeline.py' -v", workflow)
        self.assertNotIn("python3 run.py", workflow)
        self.assertNotIn("python3 live_check.py", workflow)
        self.assertIn("no network request is made", workflow)

    def test_research_workflows_do_not_checkout_protected_engine_sources(self):
        for name in ("research-data.yml", "research-backtest.yml"):
            path = ".github/workflows/" + name
            workflow = git_source_text(path)
            sparse = workflow.split("sparse-checkout: |", 1)[1].split("\n\n", 1)[0]
            self.assertNotIn("/run.py", sparse)
            self.assertNotIn("/research/pipeline.py", sparse)
            self.assertIn("/research/backtest_report.py", sparse)

    def test_static_source_helper_rejects_unapproved_paths(self):
        with self.assertRaises(ValueError):
            git_source_text("validator.py")


    def test_static_source_helper_rejects_unapproved_paths_before_git_access(self):
        with patch.object(subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "not approved"):
                git_source_text("validator.py")
        run.assert_not_called()

    def test_static_source_allowlist_is_exact_and_never_executes_source(self):
        expected = frozenset({
            "research/pipeline.py",
            "run.py",
            ".github/workflows/research-data.yml",
            ".github/workflows/research-backtest.yml",
            ".github/workflows/q08-offline-tests.yml",
        })
        self.assertEqual(_STATIC_ONLY_SOURCES, expected)

        forbidden_roots = {"P1", "signal", "markets", "validator.py", "report.py"}
        for path in _STATIC_ONLY_SOURCES:
            self.assertNotIn(path.split("/", 1)[0], forbidden_roots, path)

        # This helper may read exact allowlisted blobs as text for ast.parse; it
        # must never evaluate, import, compile, or execute the returned source.
        with open(__file__, encoding="utf-8") as source_file:
            helper_tree = ast.parse(source_file.read())
        helper = next(
            node for node in helper_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "git_source_text"
        )
        forbidden_calls = {"exec", "eval", "compile", "__import__", "import_module", "run_module"}
        for node in ast.walk(helper):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else ""
                )
                self.assertNotIn(name, forbidden_calls, name)

    def test_static_source_helper_rejects_head_mismatch_before_git_show(self):
        expected = "0" * 40
        actual = "1" * 40
        with patch.dict(os.environ, {"GITHUB_SHA": expected}), patch.object(
                subprocess, "run", return_value=type("Result", (), {"stdout": actual + "\\n"})()
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "does not match GITHUB_SHA"):
                git_source_text("run.py")
        run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_protected_pipeline_dependency_is_recorded_without_importing_it(self):
        tree = ast.parse(
            git_source_text("research/pipeline.py"), filename="research/pipeline.py"
        )
        imports_engine = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "research"
            and any(alias.name == "engine" for alias in node.names)
            for node in ast.walk(tree)
        )
        self.assertTrue(imports_engine, "protected research.engine dependency must remain explicit")

    def test_all_three_offline_workflows_exclude_protected_engine_entrypoints(self):
        for path in (
            ".github/workflows/q08-offline-tests.yml",
            ".github/workflows/research-data.yml",
            ".github/workflows/research-backtest.yml",
        ):
            workflow = git_source_text(path)
            sparse = workflow.split("sparse-checkout: |", 1)[1].split("\n\n", 1)[0]
            for forbidden in (
                "/run.py", "/research/pipeline.py", "/validator.py", "/report.py",
                "/P1/", "/signal/data/", "/markets/risk/",
            ):
                with self.subTest(path=path, forbidden=forbidden):
                    self.assertNotIn(forbidden, sparse)
            if path == ".github/workflows/q08-offline-tests.yml":
                # test_history.py statically verifies this module's unprotected import closure.
                self.assertIn("/tests/test_research_gates.py", sparse)
                self.assertIn("python3 -m unittest discover -s tests -p 'test_research_gates.py' -v", workflow)

    def test_run_pipeline_is_read_only_and_no_legacy_open_v1_style_is_constructible(self):
        source = git_source_text("run.py")
        self.assertIn("assert_read_only(cfg)", source)
        self.assertIn("only supports mode 'read_only'", source)
        with open(os.path.join(ROOT, "fetcher.py"), encoding="utf-8") as f:
            fetcher_source = f.read()
        self.assertIn('if self.style != "binance_style":', fetcher_source)
        self.assertIn("symbol metadata routes are not approved", fetcher_source)


    def test_log_writer_never_replays_the_test_window(self):
        # Static-only inspection: importing research.pipeline reaches the protected
        # research.dataset / research.engine / validator.py dependency chain.
        tree = ast.parse(
            git_source_text("research/pipeline.py"),
            filename="research/pipeline.py",
        )
        writer = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "write_logs"
        )
        self.assertNotIn("include_test", {arg.arg for arg in writer.args.args})

        loops = [
            node for node in ast.walk(writer)
            if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Attribute)
            and isinstance(node.iter.func.value, ast.Name)
            and node.iter.func.value.id == "splits"
            and node.iter.func.attr == "items"
        ]
        self.assertEqual(len(loops), 1)
        loop = loops[0]
        guard = loop.body[0]
        self.assertIsInstance(guard, ast.If)
        self.assertIsInstance(guard.test, ast.Compare)
        self.assertIsInstance(guard.test.left, ast.Name)
        self.assertEqual(guard.test.left.id, "seg")
        self.assertEqual(len(guard.test.ops), 1)
        self.assertIsInstance(guard.test.ops[0], ast.Eq)
        self.assertEqual(len(guard.test.comparators), 1)
        self.assertIsInstance(guard.test.comparators[0], ast.Constant)
        self.assertEqual(guard.test.comparators[0].value, "test")
        self.assertEqual(len(guard.body), 1)
        self.assertIsInstance(guard.body[0], ast.Continue)
        self.assertEqual(guard.orelse, [])

        simulator_calls = [
            node for node in ast.walk(loop)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "engine"
            and node.func.attr in {"simulate", "buy_and_hold"}
        ]
        self.assertTrue(simulator_calls)
        self.assertTrue(all(node.lineno > guard.lineno for node in simulator_calls))

        run_backtest = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_backtest"
        )
        write_calls = [
            node for node in ast.walk(run_backtest)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "write_logs"
        ]
        self.assertEqual(len(write_calls), 1)
        self.assertEqual(len(write_calls[0].args), 5)
        self.assertEqual(write_calls[0].keywords, [])

        test_evaluations = [
            node for node in ast.walk(run_backtest)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "selection"
            and node.func.attr == "evaluate_test"
        ]
        self.assertEqual(len(test_evaluations), 1)



if __name__ == "__main__":
    unittest.main()
