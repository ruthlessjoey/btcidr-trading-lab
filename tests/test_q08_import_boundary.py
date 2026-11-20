"""Static import-closure guard for the deliberately restricted Q0.8 test workflow.

This test parses source text only. It does not import project modules, execute project
code, run subprocesses, or contact a network endpoint.
"""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "q08-offline-tests.yml"

# These are exactly the Python modules imported by the selected test suite.
SOURCE_FILES = {
    "fetcher": "fetcher.py",
    "providers": "providers.py",
    "probe": "probe.py",
    "research.crosscheck": "research/crosscheck.py",
}
TEST_FILES = (
    "tests/test_fetcher.py",
    "tests/test_probe.py",
    "tests/test_sanitization.py",
    "tests/test_q08_import_boundary.py",
)
PACKAGE_INIT = "research/__init__.py"
# test_probe launches this standalone disabled script. Include it in the audited
# runtime closure even though it is not imported as a Python module.
EXECUTED_SCRIPTS = ("tools/net_lab.py",)
WORKFLOW_CHECKOUT = {
    "fetcher.py",
    "providers.py",
    "probe.py",
    "tools/net_lab.py",
    "research/__init__.py",
    "research/crosscheck.py",
    *TEST_FILES,
    "tests/test_q08_import_boundary.py",
    ".github/workflows/q08-offline-tests.yml",
}
FORBIDDEN_IMPORT_ROOTS = {
    "P1", "signal", "markets", "validator", "report", "run", "live_check",
    "research.engine", "research.pipeline", "research.dataset",
    "research.selection", "research.splits", "research.strategy",
}


def _source_imports(path):
    """Extract direct imports and reject dynamic/relative imports."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
    edges = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            edges.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise AssertionError(f"{path}: relative import is not permitted")
            module = node.module or ""
            if module == "research":
                edges.update("research." + alias.name for alias in node.names)
            elif module:
                edges.add(module)
        elif isinstance(node, ast.Call):
            func = node.func
            if ((isinstance(func, ast.Name) and func.id in {"__import__", "eval", "exec"})
                or (isinstance(func, ast.Attribute) and func.attr == "import_module")):
                raise AssertionError(f"{path}: dynamic import/evaluation is not permitted")
    return edges


def _local_edges(path):
    edges = _source_imports(path)
    local_roots = set(SOURCE_FILES)
    result = set()
    for edge in edges:
        if edge in SOURCE_FILES:
            result.add(edge)
        elif edge.startswith("research."):
            if edge in SOURCE_FILES:
                result.add(edge)
            else:
                raise AssertionError(f"{path}: unapproved local research import {edge}")
        elif edge.split(".", 1)[0] in local_roots:
            raise AssertionError(f"{path}: unapproved local import {edge}")
        if edge in FORBIDDEN_IMPORT_ROOTS or any(
            edge == root or edge.startswith(root + ".")
            for root in FORBIDDEN_IMPORT_ROOTS
        ):
            raise AssertionError(f"{path}: protected/forbidden import {edge}")
    return result


def _resolve_closure(path, seen=None):
    seen = set() if seen is None else seen
    if path in seen:
        return seen
    seen.add(path)
    for module in _local_edges(path):
        if module.startswith("research."):
            _resolve_closure(PACKAGE_INIT, seen)
        child = SOURCE_FILES[module]
        _resolve_closure(child, seen)
    return seen


class Q08ImportBoundaryTests(unittest.TestCase):
    def test_selected_test_modules_have_only_the_approved_local_import_closure(self):
        for test_path in TEST_FILES:
            with self.subTest(test=test_path):
                closure = _resolve_closure(test_path)
                self.assertLessEqual(closure, set(TEST_FILES) | set(SOURCE_FILES.values()))
                for path in closure:
                    _source_imports(path)

    def test_disabled_subprocess_script_is_static_and_unprotected(self):
        path = EXECUTED_SCRIPTS[0]
        edges = _source_imports(path)
        self.assertFalse(any(
            edge in FORBIDDEN_IMPORT_ROOTS or any(
                edge == root or edge.startswith(root + ".")
                for root in FORBIDDEN_IMPORT_ROOTS
            ) for edge in edges
        ))
        test_source = (ROOT / "tests/test_probe.py").read_text(encoding="utf-8")
        self.assertIn("tools/net_lab.py", test_source)
        self.assertIn("Network lab disabled", (ROOT / path).read_text(encoding="utf-8"))

    def test_workflow_sparse_checkout_matches_exact_approved_file_set(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        match = re.search(r"(?ms)^          sparse-checkout: \|\n((?:^            .*\n)+)", source)
        self.assertIsNotNone(match, "sparse-checkout allowlist is missing or malformed")
        actual = {line.strip()[1:] for line in match.group(1).splitlines() if line.strip()}
        self.assertEqual(actual, WORKFLOW_CHECKOUT)
        for forbidden in (
            "/P1/", "/signal/", "/markets/risk/", "/validator.py", "/report.py",
            "/run.py", "/live_check.py", "/research/engine.py", "/research/pipeline.py",
            "/research/history.py", "/tests/test_history.py", "/tests/test_pipeline.py",
            "/tests/test_live_check.py", "/tests/test_research_gates.py",
        ):
            self.assertNotIn(forbidden, source)

    def test_workflow_runs_only_exact_selected_test_modules(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        commands = re.findall(
            r"python3 -m unittest discover -s tests -p '([^']+)' -v", source
        )
        self.assertEqual(commands, [
            "test_q08_import_boundary.py",
            "test_fetcher.py",
            "test_probe.py",
            "test_sanitization.py",
        ])
        self.assertIn("contents: read", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn('"$REVIEW_HEAD_SHA" != "$ACTUAL_HEAD_SHA"', source)


if __name__ == "__main__":
    unittest.main()
