"""Permanently disabled broad network scanner.

Exit code 2 means the scanner is blocked by policy, not that it should be retried.
This module performs no network access.
"""
import sys


def main():
    print("Network lab disabled: only explicitly approved market-data routes may be contacted.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
