"""Permanently disabled legacy probe.

Exit code 2 means the diagnostic is blocked by policy, not that it should be retried.
No network request or symbol-metadata discovery is performed.
"""
import sys


def run_probe(*args, **kwargs):
    print("Probe disabled: symbol metadata routes are not approved and this diagnostic bypassed transport controls.")
    return 2


if __name__ == "__main__":
    sys.exit(run_probe())
