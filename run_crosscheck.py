"""Cross-check entry point intentionally disabled pending approved independent sources.

Coinbase and Bitstamp are excluded. This command performs no network requests.
Exit status 2 is the shared CLI convention for disabled or approval-blocked commands.
"""
import sys


def main(argv=None):
    print("Cross-check blocked: no independent comparison provider is currently authorized.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
