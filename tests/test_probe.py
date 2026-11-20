"""Offline tests for the deliberately disabled legacy probe."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import probe  # noqa: E402


class DisabledProbeTests(unittest.TestCase):
    def test_probe_refuses_to_run_without_network_access(self):
        def forbidden_network(*args, **kwargs):
            raise AssertionError("disabled probe must not make a network request")
        self.assertEqual(probe.run_probe(opener=forbidden_network), 2)

    def test_all_disabled_cli_entrypoints_document_shared_exit_code(self):
        for path in ("probe.py", "run_crosscheck.py", os.path.join("tools", "net_lab.py")):
            with self.subTest(path=path):
                with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                    source = f.read()
                self.assertIn("Exit status 2 is the shared CLI convention", source)
                self.assertIn("return 2", source)

    def test_probe_has_no_legacy_symbol_metadata_or_http_client(self):
        with open(os.path.join(ROOT, "probe.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("Probe disabled", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("exchangeInfo", source)
        self.assertNotIn("open/v1", source)


if __name__ == "__main__":
    unittest.main()
