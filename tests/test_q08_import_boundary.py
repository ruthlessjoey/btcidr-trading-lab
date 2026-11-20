"""Static AST import-boundary guard for the exact offline Q0.8 test surface."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "q08-offline-tests.yml"
SOURCE_FILES = {"fetcher": "fetcher.py", "providers": "providers.py", "probe": "probe.py"}
TEST_FILES = (
    "tests/test_fetcher.py", "tests/test_live_check.py", "tests/test_probe.py",
    "tests/test_sanitization.py", "tests/test_pipeline.py", "tests/test_q08_import_boundary.py",
)
WORKFLOW_CHECKOUT = {
    "CLAUDE.md", "PROJECT_HANDOFF.MD", "config.json", "fetcher.py", "providers.py",
    "probe.py", "run.py", "live_check.py", "tools/net_lab.py", *TEST_FILES,
    ".github/workflows/market-data-check.yml", ".github/workflows/q08-offline-tests.yml",
}
FORBIDDEN_IMPORT_ROOTS = {
    "P1", "signal", "markets", "validator", "report", "run", "live_check", "research",
}


def _source_imports(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
    edges = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise AssertionError(f"{path}: relative import is not permitted")
            if node.module:
                edges.add(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if ((isinstance(func, ast.Name) and func.id in {"__import__", "eval", "exec"})
                or (isinstance(func, ast.Attribute) and func.attr == "import_module")):
                raise AssertionError(f"{path}: dynamic import/evaluation is not permitted")
    return edges


def _local_edges(path):
    result = set()
    for edge in _source_imports(path):
        if edge in SOURCE_FILES:
            result.add(edge)
        elif edge.split(".", 1)[0] in SOURCE_FILES:
            raise AssertionError(f"{path}: unapproved local import {edge}")
        if edge.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
            raise AssertionError(f"{path}: protected/forbidden import {edge}")
    return result


def _resolve_closure(path, seen=None):
    seen = set() if seen is None else seen
    if path in seen:
        return seen
    seen.add(path)
    for module in _local_edges(path):
        _resolve_closure(SOURCE_FILES[module], seen)
    return seen


class Q08ImportBoundaryTests(unittest.TestCase):
    def test_selected_test_modules_have_only_the_approved_local_import_closure(self):
        expected = {
            "tests/test_fetcher.py": {"fetcher"},
            "tests/test_live_check.py": {"providers", "fetcher"},
            "tests/test_probe.py": {"probe"},
            "tests/test_sanitization.py": {"fetcher", "providers"},
            "tests/test_pipeline.py": set(),
            "tests/test_q08_import_boundary.py": set(),
        }
        for test_path, allowed in expected.items():
            with self.subTest(test=test_path):
                closure = _resolve_closure(test_path)
                self.assertLessEqual(closure, set(TEST_FILES) | set(SOURCE_FILES.values()))
                for path in closure:
                    self.assertFalse(any(
                        edge.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS
                        for edge in _source_imports(path)
                    ), f"{path} imports a protected dependency")
                self.assertEqual({
                    edge for edge in _source_imports(test_path)
                    if edge.split(".", 1)[0] in SOURCE_FILES
                }, allowed)

    def test_fetcher_is_the_only_selected_module_with_an_http_client(self):
        network_client_roots = {
            "requests", "httpx", "aiohttp", "socket", "urllib3", "httpx",
        }
        forbidden_exact = {"urllib.request", "http.client"}
        for path in ("providers.py", "probe.py", "run.py", "live_check.py", "tools/net_lab.py"):
            with self.subTest(path=path):
                imports = _source_imports(path)
                self.assertFalse(any(
                    edge.split(".", 1)[0] in network_client_roots
                    or edge in forbidden_exact
                    for edge in imports
                ), f"{path} must not own a network client; use fetcher.py only")

    def test_disabled_subprocess_script_has_no_network_or_protected_imports(self):
        path = "tools/net_lab.py"
        edges = _source_imports(path)
        self.assertFalse(any(edge.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS for edge in edges))
        test_source = (ROOT / "tests/test_probe.py").read_text(encoding="utf-8")
        self.assertIn("tools/net_lab.py", test_source)
        self.assertIn("Network lab disabled", (ROOT / path).read_text(encoding="utf-8"))

    def test_workflow_sparse_checkout_matches_exact_approved_file_set(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        match = re.search(r"(?m)^          sparse-checkout: \|\n((?:^            [^\n]*\n)+)", source)
        self.assertIsNotNone(match, "sparse-checkout allowlist is missing or malformed")
        actual = {line.strip()[1:] for line in match.group(1).splitlines() if line.strip()}
        self.assertEqual(actual, WORKFLOW_CHECKOUT)
        for forbidden in (
            "/P1/", "/signal/", "/markets/risk/", "/validator.py", "/report.py",
            "/research/engine.py", "/research/pipeline.py", "/tests/test_history.py",
            "/tests/test_research_gates.py",
        ):
            self.assertNotIn(forbidden, source)

    def test_repository_guidance_matches_current_candles_only_boundary(self):
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(
            "unauthenticated HTTPS GET candles from "
            "`https://www.tokocrypto.site/api/v3/klines` for `BTCUSDT`",
            claude,
        )
        self.assertNotIn("server-time/candles access", claude)

        handoff = (ROOT / "PROJECT_HANDOFF.MD").read_text(encoding="utf-8")
        self.assertIn("Superseding Tokocrypto public-market-data boundary", handoff)
        self.assertIn("server-time (`/api/v3/time`)", handoff)
        self.assertIn("any `www.tokocrypto.com` API endpoint are **not authorized**", handoff)
        self.assertIn("any `www.tokocrypto.com` API endpoint are **not authorized**", handoff)

    def test_workflow_runs_only_exact_approved_offline_modules(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        commands = re.findall(r"python3 -m unittest discover -s tests -p '([^']+)' -v", source)
        self.assertEqual(commands, [
            "test_q08_import_boundary.py", "test_fetcher.py", "test_live_check.py",
            "test_probe.py", "test_sanitization.py", "test_pipeline.py",
        ])
        self.assertIn("contents: read", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn('"$REVIEW_HEAD_SHA" != "$ACTUAL_HEAD_SHA"', source)


if __name__ == "__main__":
    unittest.main()
