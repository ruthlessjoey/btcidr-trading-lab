"""Offline tests for the deliberately disabled legacy probe."""
import os
import subprocess
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

    def test_probe_has_no_legacy_symbol_metadata_or_http_client(self):
        with open(os.path.join(ROOT, "probe.py"), encoding="utf-8") as f:
            source = f.read()
        self.assertIn("Probe disabled", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("exchangeInfo", source)
        self.assertNotIn("open/v1", source)

    def test_probe_exit_two_is_a_policy_block_not_a_retry_signal(self):
        path = os.path.join(ROOT, "probe.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("Permanently disabled legacy probe", source)
        self.assertIn("Exit code 2 means the diagnostic is blocked by policy", source)
        self.assertIn("not that it should be retried", source)
        self.assertEqual(probe.run_probe(), 2)

    def test_network_lab_exit_two_is_a_policy_block_not_a_retry_signal(self):
        path = os.path.join(ROOT, "tools", "net_lab.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("Permanently disabled broad network scanner", source)
        self.assertIn("Exit code 2 means the scanner is blocked by policy", source)
        self.assertIn("not that it should be retried", source)
        result = subprocess.run(
            [sys.executable, path], cwd=ROOT, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Network lab disabled", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
