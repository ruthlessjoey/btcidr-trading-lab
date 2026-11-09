"""run_crosscheck.py - compare flagged Binance candles with Coinbase/Bitstamp (READ-ONLY).

Usage: python3 run_crosscheck.py --datasets-root DIR [--out out]
Always exits 0 when it could write a report; a disagreement is a finding, not a crash.
"""
import argparse
import json
import sys

from research import crosscheck
from research.pipeline import load_pinned


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="backtest_config.json")
    ap.add_argument("--datasets-root", required=True)
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    manifest, candles = load_pinned(cfg, a.datasets_root)
    crosscheck.run_crosscheck(manifest, candles, cfg.get("flagged_dates", []), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
