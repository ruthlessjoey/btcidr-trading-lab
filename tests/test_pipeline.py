"""Static offline tests for the legacy candle runner's exact source boundary.

Do not import run.py here: it imports the protected validator.py module.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PipelineContainmentTests(unittest.TestCase):
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
