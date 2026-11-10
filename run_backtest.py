"""run_backtest.py - Step 2: research-only backtest on the pinned, verified dataset (READ-ONLY).

Usage: python3 run_backtest.py --datasets-root DIR [--prev-results DIR] [--crosscheck FILE] [--out out]
"""
import argparse
import json
import os
import sys

from research.pipeline import run_backtest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="backtest_config.json")
    ap.add_argument("--datasets-root", required=True)
    ap.add_argument("--prev-results", default=None, help="folder holding earlier test_evaluations/")
    ap.add_argument("--crosscheck", default=None)
    ap.add_argument("--out", default="out")
    ap.add_argument("--allow-reeval", action="store_true", help="repeat the test window (labelled)")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--prepare-reservation", action="store_true", help="prepare a holdout reservation without evaluating TEST")
    modes.add_argument("--require-committed-reservation", action="store_true", help="evaluate TEST only with the exact persistent reservation")
    a = ap.parse_args(argv)
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    return run_backtest(cfg, a.datasets_root, a.out, a.prev_results, a.crosscheck, a.allow_reeval,
                        os.environ.get("GITHUB_RUN_ID", "local"), os.environ.get("GITHUB_SHA"),
                        prepare_reservation=a.prepare_reservation,
                        require_committed_reservation=a.require_committed_reservation,
                        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
                        workflow_ref=os.environ.get("GITHUB_WORKFLOW_REF", "local"),
                        repository=os.environ.get("GITHUB_REPOSITORY", "local/repository"))


if __name__ == "__main__":
    sys.exit(main())
