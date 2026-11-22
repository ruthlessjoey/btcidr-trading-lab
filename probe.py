"""Disabled legacy endpoint probe. No endpoint URLs are constructed or contacted."""
import sys


def run_probe(*args, **kwargs):
    print(
        "Probe disabled: only the approved Tokocrypto public candle GET route may be used; "
        "server-time, symbol metadata, Tokocrypto .com, and other provider probes are not approved.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(run_probe())
