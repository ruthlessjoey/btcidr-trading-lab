"""Offline tests for the Step 1 fail-closed gate.

Runtime tests invoke only the standard-library-only gate with synthetic configuration
and forbidden network callbacks. AST tests avoid protected validator.py entirely.
"""
import ast
import json
import os
import tempfile
import unittest

from research.history import _gate_status, run_step1

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
        # These are the exact six modules selected by q08-offline-tests.yml and
        # research-data.yml. Resolve only source imports; do not import or execute them.
        expected_local_edges = {
            "tests/test_fetcher.py": {"fetcher"},
            "tests/test_live_check.py": {"providers", "fetcher"},
            "tests/test_history.py": {"research.history"},
            "tests/test_probe.py": {"probe"},
            "tests/test_pipeline.py": set(),
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
        self.assertIn('backtest_allowed = gate == "PASS" and dataset is not None', source)
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


class HistoryRuntimeGateTests(unittest.TestCase):
    def test_gate_status_requires_nonempty_all_pass_checks(self):
        self.assertEqual(_gate_status([]), "FAIL")
        self.assertEqual(_gate_status([{"status": "PASS"}]), "PASS")
        self.assertEqual(_gate_status([{"status": "FAIL"}]), "FAIL")
        self.assertEqual(
            _gate_status([{"status": "PASS"}, {"status": "FAIL"}]),
            "FAIL",
        )

    def run_and_assert_fail_closed(self, cfg, expected_reason):
        calls = []

        def forbidden_opener(*args, **kwargs):
            calls.append(("opener", args, kwargs))
            raise AssertionError("the Step 1 gate must not make a network request")

        def forbidden_sleep(*args, **kwargs):
            calls.append(("sleep", args, kwargs))
            raise AssertionError("the Step 1 gate must not wait for a network retry")

        with tempfile.TemporaryDirectory() as out:
            code = run_step1(
                cfg, out_dir=out, opener=forbidden_opener,
                sleep=forbidden_sleep, local_now=1_700_000_000,
            )
            with open(os.path.join(out, "dataset_report.json"), encoding="utf-8") as f:
                report = json.load(f)
            with open(os.path.join(out, "dataset_report.md"), encoding="utf-8") as f:
                markdown = f.read()

            self.assertEqual(code, 1)
            self.assertEqual(report["gate"], "FAIL")
            self.assertIsNone(report["dataset"])
            self.assertFalse(report["backtest_allowed"])
            self.assertEqual(report["network_requests"], 0)
            self.assertEqual(report["http_log"], [])
            self.assertEqual(len(report["checks"]), 1)
            self.assertEqual(report["checks"][0]["name"], "market_identity")
            self.assertEqual(report["checks"][0]["status"], "FAIL")
            self.assertEqual(report["checks"][0]["detail"], report["stop_reason"])
            self.assertIn(expected_reason, report["stop_reason"])
            self.assertIn("**GATE: FAIL**", markdown)
            self.assertEqual(set(os.listdir(out)), {"dataset_report.json", "dataset_report.md"})
            self.assertEqual(calls, [])

    def test_exact_approved_config_still_fails_without_market_identity_proof(self):
        self.run_and_assert_fail_closed({
            "mode": "read_only",
            "provider": "tokocrypto",
            "host": "https://www.tokocrypto.site",
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "timeframe": "1d",
        }, "Market identity is unverified")

    def test_unapproved_config_fails_without_network_or_dataset_output(self):
        self.run_and_assert_fail_closed({
            "mode": "read_only",
            "provider": "unapproved-test-provider",
            "host": None,
            "symbol": None,
            "base_asset": None,
            "quote_asset": None,
        }, "outside the exact approved read-only Tokocrypto BTC/USDT scope")


if __name__ == "__main__":
    unittest.main()
