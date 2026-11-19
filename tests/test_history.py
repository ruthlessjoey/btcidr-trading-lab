"""Static offline tests for the Step 1 fail-closed gate.

These tests deliberately avoid importing protected validator.py or invoking network code.
They parse source text with Python's AST; they never import the Step 1 entrypoint.
"""
import ast
import json
import os
import unittest

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


class HistoryContainmentTests(unittest.TestCase):
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
