"""Offline tests for the Step 1 fail-closed gate.

The approved import closure includes only research.history, which uses the standard
library. These tests combine AST-only source-boundary checks with an isolated temporary
directory behavior test. They never import fetch_history.py or protected modules and
never make network requests.
"""
import ast
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from research import history

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def source_imports(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "__import__") or (
                isinstance(func, ast.Attribute) and func.attr == "import_module"
            ):
                raise AssertionError(f"{path} contains a dynamic import")
    return modules



def source_import_edges(path):
    """Return normalized source import edges without importing the target module."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    edges = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            if node.level:
                # Do not silently ignore relative edges: none are needed by this
                # approved import closure, so fail closed if one appears.
                edges.add("__relative_import__")
            elif node.module == "research":
                edges.update("research." + alias.name for alias in node.names)
            else:
                edges.add(module)
        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "__import__") or (
                isinstance(func, ast.Attribute) and func.attr == "import_module"
            ):
                raise AssertionError(f"{path} contains a dynamic import")
    return edges


class HistoryContainmentTests(unittest.TestCase):
    def test_q08_workflow_test_import_closure_stays_outside_protected_modules(self):
        # These are the exact selected test modules in q08-offline-tests.yml,
        # research-data.yml, and research-backtest.yml. Resolve only source imports; do not import or execute them.
        expected_local_edges = {
            "tests/test_fetcher.py": {"fetcher"},
            "tests/test_live_check.py": {"providers", "fetcher"},
            "tests/test_history.py": {"research.history"},
            "tests/test_probe.py": {"probe"},
            "tests/test_pipeline.py": set(),
            "tests/test_research_gates.py": {"research.crosscheck", "research.backtest_report"},
            "tests/test_sanitization.py": {"fetcher", "providers", "research.crosscheck"},
            "fetch_history.py": {"research.history"},
            "fetcher.py": set(),
            "providers.py": {"fetcher"},
            "probe.py": set(),
            "research/history.py": set(),
            "research/crosscheck.py": {"fetcher"},
        }
        forbidden_roots = {
            "P1", "signal", "markets", "validator", "report", "__relative_import__",
        }
        forbidden_research = ("research.engine", "research.pipeline")
        for path, expected in expected_local_edges.items():
            with self.subTest(path=path):
                edges = source_import_edges(path)
                local = {
                    edge for edge in edges
                    if edge.split(".", 1)[0] in {"fetcher", "providers", "probe", "research"}
                }
                self.assertEqual(local, expected)
                self.assertFalse(
                    any(edge.split(".", 1)[0] in forbidden_roots
                        or any(edge == prefix or edge.startswith(prefix + ".")
                               for prefix in forbidden_research)
                        for edge in edges),
                    f"{path} imports a protected module or uses a relative import",
                )

    def test_run_entrypoint_source_guard_precedes_filesystem_and_source_iteration(self):
        # run.py imports protected validator/report modules, so inspect its AST only.
        path = os.path.join(ROOT, "run.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename="run.py")
        run_pipeline = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline"
        )
        body = run_pipeline.body

        def call_index(function_name, owner=None):
            for index, statement in enumerate(body):
                for node in ast.walk(statement):
                    if not isinstance(node, ast.Call):
                        continue
                    if owner is None and isinstance(node.func, ast.Name) and node.func.id == function_name:
                        return index
                    if (owner is not None and isinstance(node.func, ast.Attribute)
                            and node.func.attr == function_name
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == owner):
                        return index
            self.fail(f"run_pipeline does not call {owner + '.' if owner else ''}{function_name}")

        readonly_index = call_index("assert_read_only")
        mkdir_index = call_index("makedirs", "os")
        source_loop_index = next(
            index for index, statement in enumerate(body)
            if isinstance(statement, ast.For)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "source_cfg"
            and ast.unparse(statement.iter) == "cfg['sources']"
        )
        source_guard_index = next(
            index for index, statement in enumerate(body)
            if isinstance(statement, ast.If)
            and any(
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "source configuration is not the exact approved Tokocrypto endpoint" in node.value
                for node in ast.walk(statement)
            )
        )
        guard = body[source_guard_index]
        guard_expression = ast.unparse(guard.test)
        self.assertIn("cfg.get('sources')", guard_expression)
        self.assertIn("tokocrypto-mbx", guard_expression)
        self.assertLess(readonly_index, source_guard_index)
        self.assertLess(source_guard_index, mkdir_index)
        self.assertLess(source_guard_index, source_loop_index)

    def test_step1_behavior_fails_closed_without_network_or_dataset(self):
        cfg = {
            "mode": "read_only",
            "provider": "tokocrypto",
            "host": "https://www.tokocrypto.site",
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "timeframe": "1h",
        }
        calls = []

        def forbidden_opener(url, timeout):
            calls.append((url, timeout))
            raise AssertionError("Step 1 must not make a network request")

        with tempfile.TemporaryDirectory() as out:
            with redirect_stdout(io.StringIO()):
                status = history.run_step1(
                    cfg, out_dir=out, opener=forbidden_opener,
                    sleep=lambda seconds: None, local_now=1_700_000_000,
                )
            self.assertEqual(status, 1)
            self.assertEqual(calls, [])
            self.assertEqual(set(os.listdir(out)), {"dataset_report.json", "dataset_report.md"})
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                report = json.load(f)
            self.assertEqual(report["gate"], "FAIL")
            self.assertEqual(report["network_requests"], 0)
            self.assertIsNone(report["dataset"])
            self.assertFalse(report["backtest_allowed"])
            self.assertIn("Market identity is unverified", report["stop_reason"])

    def test_research_config_names_only_the_approved_provider_and_host(self):
        with open(os.path.join(ROOT, "research_config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["provider"], "tokocrypto")
        self.assertEqual(cfg["host"], "https://www.tokocrypto.site")
        self.assertEqual(cfg["symbol"], "BTCUSDT")

    def test_history_gate_fails_without_symbol_metadata_authorization(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"name": "market_identity", "status": "FAIL"', source)
        self.assertIn('"network_requests": 0', source)
        self.assertIn('"backtest_allowed": False', source)
        self.assertIn("route is undocumented", source)
        self.assertIn("Configuration alone is insufficient", source)

    def test_history_module_has_only_standard_library_imports(self):
        self.assertEqual(
            source_imports("research/history.py"),
            {"json", "os", "time", "datetime"},
        )

    def test_step1_entrypoint_has_an_exact_unprotected_import_closure(self):
        self.assertEqual(
            source_imports("fetch_history.py"),
            {"argparse", "json", "sys", "research.history"},
        )
        source_imports("fetch_history.py")  # also rejects dynamic imports

    def test_only_exact_tokocrypto_scope_is_accepted_as_configuration(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        for literal in (
            'provider == "tokocrypto"',
            'host == "https://www.tokocrypto.site"',
            'symbol == "BTCUSDT"',
            'base_asset == "BTC"',
            'quote_asset == "USDT"',
        ):
            self.assertIn(literal, source)


if __name__ == "__main__":
    unittest.main()
