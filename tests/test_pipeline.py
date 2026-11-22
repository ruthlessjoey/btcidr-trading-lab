"""Static offline tests for the legacy candle runner's exact source boundary.

Do not import run.py here: it imports the protected validator.py module.
"""
import ast
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
        with open(pipeline_path, encoding="utf-8") as f:
            pipeline_tree = ast.parse(f.read(), filename=pipeline_path)
        # Production wiring must not expose a mutable module-level alias.
        pipeline_aliases = [
            node for node in pipeline_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "AUTHORIZED_CROSSCHECK_PROVIDERS"
                    for target in node.targets)
        ]
        self.assertEqual(pipeline_aliases, [])

        # The production loader must pass a fresh, empty immutable allowlist.
        loader = next(
            node for node in pipeline_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "load_required_crosscheck"
        )
        loader_calls = [
            node for node in ast.walk(loader)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "validate_crosscheck_artifact"
        ]
        self.assertEqual(len(loader_calls), 1)
        self.assertGreaterEqual(len(loader_calls[0].args), 4)
        empty_allowlist = loader_calls[0].args[3]
        self.assertIsInstance(empty_allowlist, ast.Call)
        self.assertIsInstance(empty_allowlist.func, ast.Name)
        self.assertEqual(empty_allowlist.func.id, "frozenset")
        self.assertEqual(empty_allowlist.args, [])
        self.assertEqual(empty_allowlist.keywords, [])

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
        with open(os.path.join(ROOT, "run.py"), encoding="utf-8") as f:
            source = f.read()
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

    def test_run_pipeline_is_read_only_and_no_legacy_open_v1_style_is_constructible(self):
        with open(os.path.join(ROOT, "run.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("assert_read_only(cfg)", source)
        self.assertIn("only supports mode 'read_only'", source)
        with open(os.path.join(ROOT, "fetcher.py"), encoding="utf-8") as f:
            fetcher_source = f.read()
        self.assertIn('if self.style != "binance_style":', fetcher_source)
        self.assertIn("symbol metadata routes are not approved", fetcher_source)


if __name__ == "__main__":
    unittest.main()
