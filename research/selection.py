"""research/selection.py - choose the moving-average period from TRAIN + VALIDATION only,
freeze the choice, and allow the TEST period to be evaluated exactly once.

All cost and rule numbers are ASSUMPTIONS, not verified exchange terms.
"""
import hashlib
import json
import os

from research import engine, strategy
from research.engine import Costs, Rules

CANDIDATES = (50, 100, 150, 200)
COST_GRID = (Costs("BASE: fee 0.40%, slippage 0.05%", 0.0040, 0.0005),
             Costs("STRESS: fee 0.40%, slippage 0.20%", 0.0040, 0.0020),
             Costs("LOW FEE: fee 0.10%, slippage 0.05%", 0.0010, 0.0005),
             Costs("LOW FEE + STRESS SLIPPAGE: fee 0.10%, slippage 0.20%", 0.0010, 0.0020))
SELECTION_COSTS = COST_GRID[0]
DD_FLOOR = 0.05

RULE_TEXT = (
    "Pre-registered before any test result was computed. Candidates: 50, 100, 150, 200 days. "
    "Costs for selection: the BASE scenario. Step 1 (training, bars from index 200 to the end of "
    "the training window, identical for all candidates): a candidate is eligible only if its "
    "training total return is above zero. Step 2 (validation): among eligible candidates choose "
    "the highest validation score = total return / max(max drawdown, 5%). Ties: fewer validation "
    "trades, then the larger period. If no candidate is eligible, nothing is selected and the test "
    "period is not evaluated. The test period is never used to choose anything.")


def select(candles, splits, candidates=CANDIDATES, costs=SELECTION_COSTS, rules=Rules()):
    """Uses bars inside the train and validation windows only (plus earlier bars for warm-up)."""
    rows = []
    for n in candidates:
        sig = strategy.ma_trend(n)(candles)
        tr = engine.metrics(engine.simulate(candles, sig, *splits["train"], costs, rules))
        va = engine.metrics(engine.simulate(candles, sig, *splits["validation"], costs, rules))
        rows.append({"n": n, "train": tr, "validation": va,
                     "eligible": tr["total_return"] > 0,
                     "score": va["total_return"] / max(va["max_drawdown"], DD_FLOOR)})
    ok = [r for r in rows if r["eligible"]]
    chosen = max(ok, key=lambda r: (r["score"], -r["validation"]["closed_trades"], r["n"]))["n"] if ok else None
    return {"rows": rows, "selected_n": chosen}


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def freeze(selection, splits, dataset, candles, rules=Rules(), costs=SELECTION_COSTS, code_rev=None):
    """The record that fixes the choice before the test is looked at."""
    body = {"selected_n": selection["selected_n"], "candidates": [r["n"] for r in selection["rows"]],
            "rule_text": RULE_TEXT, "selection_costs": costs.name,
            "splits": {k: {"start_index": a, "end_index": b,
                           "first_open_unix": candles[a].time, "last_open_unix": candles[b - 1].time}
                       for k, (a, b) in splits.items()},
            "dataset": dataset, "rules_assumed": rules.__dict__, "code_revision": code_rev,
            "scores": [{"n": r["n"], "eligible": r["eligible"], "score": r["score"],
                        "train_return": r["train"]["total_return"],
                        "validation_return": r["validation"]["total_return"]} for r in selection["rows"]]}
    body["frozen_hash"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    return body


def verify_frozen(frozen):
    body = {k: v for k, v in frozen.items() if k != "frozen_hash"}
    if hashlib.sha256(_canon(body).encode()).hexdigest() != frozen.get("frozen_hash"):
        raise engine.EngineError("frozen choice was altered after it was frozen")


def test_key(frozen):
    return f"{frozen['dataset']['sha256'][:12]}_{frozen['frozen_hash'][:12]}"


def find_prior_test(registry_dir, frozen):
    if not registry_dir:
        return None
    path = os.path.join(registry_dir, test_key(frozen) + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def evaluate_test(candles, frozen, splits, registry_dir=None, out_registry_dir=None,
                  allow_reeval=False, run_id=None, cost_grid=COST_GRID, rules=Rules()):
    """Evaluates the frozen choice on the test window ONCE. A second look at the same frozen
    choice on the same dataset is refused unless allow_reeval is set (and then it is labelled)."""
    verify_frozen(frozen)
    if frozen["selected_n"] is None:
        return {"status": "not_evaluated", "reason": "no candidate passed the training screen"}
    prior = find_prior_test(registry_dir, frozen)
    if prior and not allow_reeval:
        return {"status": "already_evaluated", "prior": prior,
                "reason": "the test window was already evaluated for this frozen choice; "
                          "a second look is refused"}
    sig = strategy.ma_trend(frozen["selected_n"])(candles)
    a, b = splits["test"]
    results = {}
    for costs in cost_grid:
        results[costs.name] = {
            "strategy": engine.metrics(engine.simulate(candles, sig, a, b, costs, rules)),
            "buy_and_hold": engine.metrics(engine.buy_and_hold(candles, a, b, costs, rules)),
            "cash": engine.metrics(engine.cash_only(candles, a, b, costs, rules))}
    record = {"status": "evaluated", "key": test_key(frozen), "run_id": run_id,
              "evaluation_number": 2 if prior else 1, "re_evaluation": bool(prior),
              "frozen_hash": frozen["frozen_hash"], "results": results}
    if out_registry_dir:
        os.makedirs(out_registry_dir, exist_ok=True)
        path = os.path.join(out_registry_dir, test_key(frozen) + ".json")
        if not os.path.exists(path):          # an existing record is never overwritten
            with open(path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
        else:
            alt = path.replace(".json", f"_reeval_{run_id or 'x'}.json")
            with open(alt, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
    return record
