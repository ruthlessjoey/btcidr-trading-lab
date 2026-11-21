"""Static-only tests for legacy entrypoint isolation.

This module parses source/configuration text only. It does not import project modules,
execute legacy entrypoints, contact the network, or inspect protected files.
"""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = {"P1", "signal", "markets", "validator", "report", "research"}


def imports_from(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise AssertionError(f"{path} contains a relative import")
            if node.module:
                found.add(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if ((isinstance(func, ast.Name) and func.id in {"__import__", "eval", "exec"})
                or (isinstance(func, ast.Attribute) and func.attr == "import_module")):
                raise AssertionError(f"{path} contains dynamic import/evaluation")
    return found


class LegacyEntryPointIsolationTests(unittest.TestCase):
    def test_legacy_entrypoints_do_not_import_protected_modules_or_network_clients(self):
        for path in ("run.py", "live_check.py", "probe.py", "tools/net_lab.py"):
            with self.subTest(path=path):
                imports = imports_from(path)
                for item in imports:
                    self.assertNotIn(item.split(".", 1)[0], FORBIDDEN_IMPORT_ROOTS)
                self.assertNotIn("urllib", imports)
                self.assertNotIn("requests", imports)
                self.assertNotIn("socket", imports)

    def test_legacy_entrypoints_are_explicitly_disabled(self):
        for path in ("run.py", "live_check.py", "probe.py", "tools/net_lab.py"):
            with self.subTest(path=path):
                self.assertIn("disabled", (ROOT / path).read_text(encoding="utf-8").lower())

    def test_configuration_contains_only_the_approved_provider_and_host(self):
        text = (ROOT / "config.json").read_text(encoding="utf-8")
        cfg = json.loads(text)
        self.assertEqual(cfg["mode"], "read_only")
        self.assertEqual(cfg["sources"], [{
            "name": "tokocrypto-mbx", "style": "binance_style",
            "base_url": "https://www.tokocrypto.site",
        }])
        self.assertEqual(cfg["live_providers"], ["tokocrypto"])
        self.assertNotIn("tokocrypto.com", text)

    def test_market_data_workflow_remains_blocked_without_protected_access(self):
        source = (ROOT / ".github/workflows/market-data-check.yml").read_text(encoding="utf-8")
        self.assertIn("blocked pending safe live-check boundary", source)
        self.assertNotIn("actions/checkout", source)
        self.assertNotIn("python3 live_check.py", source)


if __name__ == "__main__":
    unittest.main()
