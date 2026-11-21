"""Disabled broad network scanner. This module must never perform network requests."""
import sys


def main():
    print(
        "Network lab disabled: external endpoints are restricted to the approved "
        "Tokocrypto public candle route.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
