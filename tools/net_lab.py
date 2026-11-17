"""Disabled broad network scanner. No network access is performed by this module."""
import sys


def main():
    print("Network lab disabled: only explicitly approved market-data routes may be contacted.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
