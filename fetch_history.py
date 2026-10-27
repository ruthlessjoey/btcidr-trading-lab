"""fetch_history.py - Step 1: fetch and validate the full BTC/USDT daily history (READ-ONLY).

Usage: python3 fetch_history.py [--out out] [--previous-root DIR]
Exit 0 = gate PASS (dataset written), 1 = gate FAIL (nothing written).
"""
import argparse
import json
import sys

from research.history import run_step1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="research_config.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--previous-root", default=None,
                    help="folder holding earlier dataset versions (datasets/...)")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    return run_step1(cfg, a.out, previous_root=a.previous_root)


if __name__ == "__main__":
    sys.exit(main())
