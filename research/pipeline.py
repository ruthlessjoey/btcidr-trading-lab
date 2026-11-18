"""research/pipeline.py - Step 2 end to end: load the pinned verified dataset, check it, split it,
select the moving-average period on train + validation, freeze it, evaluate the test window once.

READ-ONLY research. No orders, no keys, no network (the cross-check is a separate step).
"""
import csv
import json
import os
from datetime import datetime, timezone

from research import dataset, engine, selection, splits as splits_mod, strategy
from research.backtest_report import build_markdown
from research.engine import EngineError, Rules

SEGMENTS = (("train", "TRAIN (in-sample; used to screen candidates)"),
            ("validation", "VALIDATION (used to pick among eligible candidates)"),
            ("test", "TEST (final; evaluated once)"))


def utc_day(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_fetched(text):
    return int(datetime.strptime(text.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")
               .replace(tzinfo=timezone.utc).timestamp())


def remap_splits(splits, original, reduced):
    """Same calendar boundaries on a series with some candles removed."""
    times = [c.time for c in reduced]

    def idx(t):
        return next(i for i, x in enumerate(times) if x >= t)
    return {k: (idx(original[a].time), idx(original[b].time) if b < len(original) else len(reduced))
            for k, (a, b) in splits.items()}


def load_pinned(cfg, datasets_root):
    market_name = f"{cfg['provider']}_{cfg['symbol']}_{cfg['timeframe']}"
    path = os.path.join(datasets_root, market_name, cfg["dataset_version"] + ".manifest.json")
    manifest, candles = dataset.load_verified(path, expect={
        "provider": cfg["provider"], "symbol": cfg["symbol"],
        "quote_asset": cfg["quote_asset"], "timeframe": cfg["timeframe"]})
    engine.check_series(candles, manifest["timeframe_seconds"])
    engine.assert_completed(candles, parse_fetched(manifest["fetched_utc"]), manifest["timeframe_seconds"])
    return manifest, candles


def evaluate_frozen(candles, n, splits, rules, include_test=False):
    """The frozen choice on the train and validation segments under every cost scenario, with
    benchmarks. The TEST numbers come only from selection.evaluate_test, never from here."""
    selection_candles = candles[:splits["validation"][1]]
    sig = strategy.ma_trend(n)(selection_candles)
    out = {}
    for seg, (a, b) in splits.items():
        if seg == "test":
            continue
        out[seg] = {}
        for costs in selection.COST_GRID:
            out[seg][costs.name] = {
                "strategy": engine.metrics(engine.simulate(selection_candles, sig, a, b, costs, rules)),
                "buy_and_hold": engine.metrics(engine.buy_and_hold(candles, a, b, costs, rules)),
                "cash": engine.metrics(engine.cash_only(candles, a, b, costs, rules))}
    return out


def write_logs(candles, n, splits, out_dir, rules, include_test):
    """BASE-cost trade/order/equity logs for TRAIN + VALIDATION only; never resimulate TEST."""
    costs = selection.SELECTION_COSTS
    selection_candles = candles[:splits["validation"][1]]
    sig = strategy.ma_trend(n)(selection_candles)
    with open(os.path.join(out_dir, "trades.csv"), "w", newline="", encoding="utf-8") as ft, \
            open(os.path.join(out_dir, "orders.csv"), "w", newline="", encoding="utf-8") as fo, \
            open(os.path.join(out_dir, "equity.csv"), "w", newline="", encoding="utf-8") as fe:
        wt, wo, we = csv.writer(ft, lineterminator="\n"), csv.writer(fo, lineterminator="\n"), csv.writer(fe, lineterminator="\n")
        wt.writerow(["segment", "entry_date", "entry_price", "exit_date", "exit_price", "qty", "fees", "pnl", "ret"])
        wo.writerow(["segment", "date", "side", "status", "ref_open", "fill", "qty", "fee", "reason"])
        we.writerow(["segment", "date", "strategy_equity", "buy_and_hold_equity"])
        for seg, (a, b) in splits.items():
            # TEST is evaluated exactly once by selection.evaluate_test. Re-simulating it
            # here just to produce CSV logs would be a second holdout evaluation.
            if seg == "test":
                continue
            run = engine.simulate(selection_candles, sig, a, b, costs, rules)
            bh = engine.buy_and_hold(candles, a, b, costs, rules)
            for t in run["trades"]:
                wt.writerow([seg, utc_day(t["entry_time"]), t["entry_price"], utc_day(t["exit_time"]),
                             t["exit_price"], t["qty"], t["fees"], t["pnl"], t["ret"]])
            for o in run["orders"]:
                wo.writerow([seg, utc_day(o["time"]), o["side"], o["status"], o.get("ref_open", ""),
                             o.get("fill", ""), o.get("qty", ""), o.get("fee", ""), o.get("reason", "")])
            for t, e1, e2 in zip(run["times"], run["equity"], bh["equity"]):
                we.writerow([seg, utc_day(t), e1, e2])


def sensitivity(candles, splits, flagged_dates, rules, original_selection):
    """Rerun TRAIN + VALIDATION selection with flagged candles removed; never inspect TEST signals."""
    drop = {c.time for c in candles if utc_day(c.time) in flagged_dates}
    if not drop:
        return None
    reduced = [c for c in candles if c.time not in drop]
    engine.check_series(reduced, skipped_times=drop)
    sp2 = remap_splits(splits, candles, reduced)
    sel2 = selection.select(reduced, sp2)
    return {"removed": sorted(utc_day(t) for t in drop), "selection": sel2,
            "selected_n_changed": sel2["selected_n"] != original_selection["selected_n"]}


def run_backtest(cfg, datasets_root, out_dir="out", prev_results_root=None, crosscheck_path=None,
                 allow_reeval=False, run_id="local", code_rev=None, prepare_reservation=False,
                 require_committed_reservation=False, run_attempt=None, workflow_ref=None, repository=None):
    rules = Rules()
    os.makedirs(out_dir, exist_ok=True)
    result = {"status": "FAILED", "error": None, "run_id": run_id}
    try:
        manifest, candles = load_pinned(cfg, datasets_root)
        splits = splits_mod.make_splits(len(candles), warmup=cfg.get("warmup", 200))
        for n in selection.CANDIDATES:                      # look-ahead guard on the real series
            strategy.assert_causal(strategy.ma_trend(n), candles[:splits["validation"][1]])
    except (dataset.DatasetError, EngineError, OSError, KeyError) as e:
        result["error"] = f"{type(e).__name__}: {e}"
        return finish(result, out_dir)
    ds = {"version_id": manifest["version_id"], "sha256": manifest["csv_sha256"],
          "rows": manifest["row_count"], "first_open_utc": manifest["first_open_utc"],
          "last_open_utc": manifest["last_open_utc"], "market": manifest["market"]}
    sel = selection.select(candles, splits)
    expected = cfg.get("expected_selected_n")
    if expected is not None and sel["selected_n"] != expected:
        result["error"] = (f"the selection now gives {sel['selected_n']}, but the choice recorded before "
                           f"the final run was {expected}; the test window was NOT evaluated")
        return finish(result, out_dir)
    frozen = selection.freeze(sel, splits, ds, candles, rules, code_rev=code_rev)
    with open(os.path.join(out_dir, "frozen_choice.json"), "w", encoding="utf-8") as f:
        json.dump(frozen, f, indent=2)                      # written BEFORE the test is evaluated
    registry = os.path.join(prev_results_root, "test_evaluations") if prev_results_root else None
    if prepare_reservation:
        if sel["selected_n"] is None:
            result.update(status="RESERVATION_PREPARED", reservation={"status": "not_required",
                                                                         "reason": "no candidate passed the training screen"})
            return finish(result, out_dir)
        if not cfg.get("evaluate_test", False):
            result.update(status="RESERVATION_PREPARED", reservation={"status": "not_required", "reason": "evaluate_test is false"})
            return finish(result, out_dir)
        try:
            reservation = selection.prepare_test_reservation(
                frozen, os.path.join(out_dir, "test_evaluations"), run_id,
                run_attempt, workflow_ref, repository)
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
            return finish(result, out_dir)
        result.update(status="RESERVATION_PREPARED", reservation=reservation or {"status": "not_required"})
        return finish(result, out_dir)
    if cfg.get("evaluate_test", False) and sel["selected_n"] is not None:
        if not require_committed_reservation:
            result["error"] = ("TEST evaluation requires --require-committed-reservation; "
                               "prepare and persist the exact reservation first")
            return finish(result, out_dir)
        if not registry:
            result["error"] = ("holdout evaluation requires prev_results_root so the persistent "
                               "test registry and exclusive reservation are shared across runs")
            return finish(result, out_dir)
        try:
            reservation_context = None
            if require_committed_reservation:
                reservation_context = {"run_id": run_id, "run_attempt": run_attempt,
                                       "workflow_ref": workflow_ref, "repository": repository}
            test = selection.evaluate_test(candles, frozen, splits, registry_dir=registry,
                                           out_registry_dir=os.path.join(out_dir, "test_evaluations"),
                                           allow_reeval=allow_reeval, run_id=run_id,
                                           committed_reservation=reservation_context)
        except Exception as e:
            # Preserve the failure report and non-zero exit while evaluate_test keeps any
            # post-start reservation in place for manual recovery.
            result["error"] = f"{type(e).__name__}: {e}"
            return finish(result, out_dir)
    else:
        if cfg.get("evaluate_test", False):
            test = {"status": "skipped", "reason": "no candidate passed the training screen, so the "
                                                   "test window was not computed or looked at"}
        else:
            test = {"status": "skipped", "reason": "dry run: the config says evaluate_test is false, so the "
                                                   "test window was not computed or looked at"}
    try:
        n = sel["selected_n"]
        shown = evaluate_frozen(candles, n, splits, rules) if n is not None else None
        if n is not None:
            write_logs(candles, n, splits, out_dir, rules, test["status"] in ("evaluated", "already_evaluated"))
        cross = None
        if crosscheck_path and os.path.exists(crosscheck_path):
            with open(crosscheck_path, encoding="utf-8") as f:
                cross = json.load(f)
        sens = sensitivity(candles, splits, cfg.get("flagged_dates", []), rules, sel) if cfg.get("flagged_dates") else None
        result.update(status="OK", dataset=ds, splits={k: {"start": utc_day(candles[a].time),
                                                         "end": utc_day(candles[b - 1].time),
                                                         "bars": b - a, "start_index": a, "end_index": b}
                                                     for k, (a, b) in splits.items()},
                      selection=sel, frozen=frozen, test=test, shown=shown, crosscheck=cross,
                      sensitivity=sens, rules=rules.__dict__, expected_selected_n=expected,
                      cost_grid=[{"name": c.name, "fee": c.fee, "slip": c.slip} for c in selection.COST_GRID])
    except Exception as e:
        # TEST may already be durably evaluated. Never leave the earlier preparation
        # report in place claiming TEST was not evaluated after a post-evaluation error.
        post_status = "POST_EVALUATION_FAILED" if test.get("status") == "evaluated" else "POST_PROCESSING_FAILED"
        result.update(status=post_status,
                      error=f"{type(e).__name__}: {e}", dataset=ds,
                      selection=sel, frozen=frozen, test=test)
        return finish(result, out_dir)
    return finish(result, out_dir)


def finish(result, out_dir):
    text = build_markdown(result)
    with open(os.path.join(out_dir, "backtest_report.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "backtest_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    return 0 if result["status"] in ("OK", "RESERVATION_PREPARED") else 1
