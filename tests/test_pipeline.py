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
