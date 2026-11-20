"""Offline regressions for the Step 1 fail-closed gate and dataset-source reporting.

These tests import only standard-library-only, unprotected research helpers. They do
not import protected validator.py or invoke network code.
"""
import ast
import json
import os
import unittest
import tempfile

from research.history import run_step1
from research.backtest_report import build_markdown, dataset_source_label

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
        # These are the approved modules selected by q08-offline-tests.yml and
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
            "research/__init__.py": set(),
            "research/history.py": set(),
            "research/backtest_report.py": set(),
            "research/crosscheck.py": {"fetcher"},
        }
        # Protected roots and separately protected modules stay outside this offline test closure.
        forbidden_roots = {"P1", "signal", "markets", "validator", "report", "__relative_import__"}
        forbidden_research = ()
        for path, expected in expected_local_edges.items():
            with self.subTest(path=path):
                edges = source_import_edges(path)
                local = {
                    edge for edge in edges
                    if edge.split(".", 1)[0] in {"fetcher", "providers", "probe", "research", "validator", "report"}
                }
                self.assertEqual(local, expected)
                self.assertFalse(
                    any(edge.split(".", 1)[0] in forbidden_roots
                        or any(edge == prefix or edge.startswith(prefix + ".")
                               for prefix in forbidden_research)
                        for edge in edges),
                    f"{path} imports a protected module or uses a relative import",
                )

    def test_offline_workflow_excludes_protected_import_closure(self):
        with open(os.path.join(ROOT, ".github", "workflows", "q08-offline-tests.yml"),
                  encoding="utf-8") as f:
            workflow = f.read()
        forbidden = (
            "/validator.py", "/report.py", "/P1/", "/signal/", "/markets/",
            "/research/pipeline.py", "/research/engine.py", "/research/dataset.py",
            "/research/selection.py", "/research/splits.py", "/research/strategy.py",
            "/tests/test_research_gates.py",
            "test_research_gates.py",
        )
        for path in forbidden:
            with self.subTest(path=path):
                self.assertNotIn(path, workflow)
        self.assertIn("test_history.py", workflow)
        self.assertNotIn("python3 -m unittest discover -s tests -p 'test_research_gates.py'", workflow)

    def test_backtest_report_uses_the_preserved_dataset_source_label(self):
        market = {"provider": "tokocrypto", "pair_label": "BTC/USDT"}
        self.assertEqual(dataset_source_label({"dataset": {"market": market}}),
                         "tokocrypto BTC/USDT")
        self.assertEqual(dataset_source_label({"dataset": {"market": {}}}),
                         "unverified dataset source")
        rendered = build_markdown({
            "run_id": "source-label-regression",
            "status": "STOPPED",
            "error": "market identity gate closed",
            "dataset": {"market": market},
        })
        self.assertIn("recorded dataset source is tokocrypto BTC/USDT", rendered)
        self.assertNotIn("market is Binance", rendered)
        with open(os.path.join(ROOT, "research", "backtest_report.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("vs Binance ", source)

    def test_research_config_names_only_the_approved_provider_and_host(self):
        with open(os.path.join(ROOT, "research_config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["provider"], "tokocrypto")
        self.assertEqual(cfg["host"], "https://www.tokocrypto.site")
        self.assertEqual(cfg["symbol"], "BTCUSDT")

    def test_static_source_asserts_history_gate_fails_without_symbol_metadata_authorization(self):
        with open(os.path.join(ROOT, "research", "history.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn('"name": "market_identity", "status": "FAIL"', source)
        self.assertIn('"network_requests": 0', source)
        self.assertIn('"backtest_allowed": False', source)
        self.assertIn("route is undocumented", source)
        self.assertIn("Configuration alone is insufficient", source)

    def test_step1_entrypoint_behaviorally_fails_closed_without_network_or_dataset(self):
        calls = []

        def forbidden_opener(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("fail-closed Step 1 must not contact the network")

        cfg = {
            "mode": "read_only", "provider": "tokocrypto",
            "host": "https://www.tokocrypto.site", "symbol": "BTCUSDT",
            "base_asset": "BTC", "quote_asset": "USDT", "timeframe": "1h",
        }
        with tempfile.TemporaryDirectory() as out_dir:
            status = run_step1(cfg, out_dir=out_dir, opener=forbidden_opener,
                               local_now=1_700_000_000)
            self.assertEqual(status, 1)
            with open(os.path.join(out_dir, "dataset_report.json"), encoding="utf-8") as f:
                report = json.load(f)
            self.assertEqual(report["gate"], "FAIL")
            self.assertEqual(report["checks"][0]["status"], "FAIL")
            self.assertEqual(report["network_requests"], 0)
            self.assertIsNone(report["dataset"])
            self.assertFalse(report["backtest_allowed"])
            self.assertEqual(sorted(os.listdir(out_dir)), ["dataset_report.json", "dataset_report.md"])
        self.assertEqual(calls, [])

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
