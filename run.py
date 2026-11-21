"""Legacy market-data runner disabled pending a safe unprotected validation/report boundary.

This file intentionally imports no project modules. The historical pipeline imported
protected validator.py/report.py and used endpoint routes outside current authorization.
Use only the separately reviewed, candles-only transport tests until a safe replacement
pipeline and market-identity acceptance gate are approved.
"""
import sys

BLOCK_REASON = (
    "Legacy pipeline disabled: it imports protected validation/report modules and "
    "does not implement the current candles-only, fail-closed market-identity boundary."
)


def assert_read_only(cfg):
    if not isinstance(cfg, dict) or cfg.get("mode") != "read_only":
        raise SystemExit("Refusing to run: only mode 'read_only' is permitted.")
    raise SystemExit(BLOCK_REASON)


def load_config(path="config.json"):
    raise SystemExit(BLOCK_REASON)


def run_pipeline(*args, **kwargs):
    raise SystemExit(BLOCK_REASON)


def main():
    print(BLOCK_REASON, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
