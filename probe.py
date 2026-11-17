"""Disabled legacy probe: the previous implementation queried unapproved symbol metadata routes."""
import sys


def run_probe(*args, **kwargs):
    print("Probe disabled: symbol metadata routes are not approved and this diagnostic bypassed transport controls.")
    return 2


if __name__ == "__main__":
    sys.exit(run_probe())
