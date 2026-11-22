"""Legacy live provider checker disabled.

The old entrypoint imported protected validator.py/report.py and iterated providers
that are not currently authorized. It must remain inert until an independently reviewed
unprotected reporting/validation boundary is available.
"""
import sys

BLOCK_REASON = (
    "Legacy provider checker disabled: protected validator/report import boundary "
    "and unapproved provider/endpoint routes."
)


def run_live_check(*args, **kwargs):
    raise SystemExit(BLOCK_REASON)


def main():
    print(BLOCK_REASON, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
