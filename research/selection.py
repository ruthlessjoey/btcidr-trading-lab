"""research/selection.py - choose the moving-average period from TRAIN + VALIDATION only,
freeze the choice, and allow the TEST period to be evaluated exactly once.

All cost and rule numbers are ASSUMPTIONS, not verified exchange terms.
"""
import hashlib
import json
import os

from research import engine, splits as split_tools, strategy
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


def _validated_candidates(candidates):
    try:
        periods = tuple(candidates)
    except TypeError:
        raise engine.EngineError("candidates must be an iterable of integer periods")
    if not periods or any(type(n) is not int or n < 2 for n in periods):
        raise engine.EngineError("candidates must contain positive integer periods of at least 2")
    if len(set(periods)) != len(periods):
        raise engine.EngineError("candidate periods must be unique")
    return periods


def select(candles, splits, candidates=CANDIDATES, costs=SELECTION_COSTS, rules=Rules()):
    """Uses identical, fully warmed training bars for every candidate."""
    splits = split_tools.validate_splits(len(candles), splits)
    periods = _validated_candidates(candidates)
    if splits["train"][0] < max(periods):
        raise engine.EngineError("training split must start after the longest candidate lookback")
    rows = []
    for n in periods:
        sig = strategy.ma_trend(n)(candles)
        tr = engine.metrics(engine.simulate(candles, sig, *splits["train"], costs, rules))
        va = engine.metrics(engine.simulate(candles, sig, *splits["validation"], costs, rules))
        rows.append({"n": n, "train": tr, "validation": va,
                     "eligible": tr["total_return"] > 0,
                     "score": va["total_return"] / max(va["max_drawdown"], DD_FLOOR)})
    ok = [r for r in rows if r["eligible"]]
    chosen = max(ok, key=lambda r: (r["score"], -r["validation"]["closed_trades"], r["n"]))["n"] if ok else None
    return {"rows": rows, "selected_n": chosen}


def _selection_rule_text(periods, training_start):
    if periods == CANDIDATES and training_start == 200:
        return RULE_TEXT
    candidate_text = ", ".join(str(period) for period in periods)
    return (
        "Pre-registered before any test result was computed. "
        f"Candidates: {candidate_text}. Costs for selection: the BASE scenario. "
        f"Training evaluation starts at index {training_start}, after the longest candidate "
        "lookback, and all candidates are scored on identical bars. A candidate is eligible "
        "only if its training total return is above zero. Validation chooses the highest score "
        "= total return / max(max drawdown, 5%). Ties: fewer validation trades, then the larger "
        "period. If no candidate is eligible, nothing is selected and the test period is not "
        "evaluated. The test period is never used to choose anything."
    )


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _candles_sha256(candles):
    """Stable content fingerprint for the exact candle sequence used by a frozen evaluation."""
    rows = [[c.time, repr(c.open), repr(c.high), repr(c.low), repr(c.close), repr(c.volume)]
            for c in candles]
    return hashlib.sha256(_canon(rows).encode()).hexdigest()


def _verify_frozen_inputs(candles, frozen, splits):
    if not isinstance(frozen, dict):
        raise engine.EngineError("frozen record must be an object")
    periods = _validated_candidates(frozen.get("candidates"))
    selected = frozen.get("selected_n")
    if selected is not None and (type(selected) is not int or selected not in periods):
        raise engine.EngineError("frozen selected period is not one of its candidates")
    expected = frozen.get("splits")
    if not isinstance(expected, dict) or set(expected) != {"train", "validation", "test"}:
        raise engine.EngineError("frozen record has invalid split metadata")
    if not isinstance(splits, dict) or set(splits) != set(expected):
        raise engine.EngineError("evaluation split windows differ from the frozen record")
    frozen_ranges = {}
    for name, item in expected.items():
        if not isinstance(item, dict):
            raise engine.EngineError(f"frozen {name} split metadata is invalid")
        start, end = item.get("start_index"), item.get("end_index")
        supplied = splits[name]
        if (not isinstance(supplied, (tuple, list)) or len(supplied) != 2
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(candles)
                or tuple(supplied) != (start, end)):
            raise engine.EngineError(f"{name} split window differs from the frozen record")
        first_ts, last_ts = item.get("first_open_unix"), item.get("last_open_unix")
        if (type(first_ts) is not int or first_ts < 0
                or type(last_ts) is not int or last_ts < 0):
            raise engine.EngineError(f"{name} frozen candle timestamps must be non-negative integers")
        if candles[start].time != first_ts or candles[end - 1].time != last_ts:
            raise engine.EngineError(f"{name} candle boundaries differ from the frozen record")
        frozen_ranges[name] = (start, end)
    split_tools.validate_splits(len(candles), frozen_ranges)
    if frozen_ranges["train"][0] < max(periods):
        raise engine.EngineError("frozen training split does not cover the longest candidate lookback")
    if _candles_sha256(candles) != frozen.get("candles_sha256"):
        raise engine.EngineError("candle content differs from the dataset frozen before test evaluation")


def freeze(selection, splits, dataset, candles, rules=Rules(), costs=SELECTION_COSTS, code_rev=None):
    """The record that fixes the choice before the test is looked at."""
    splits = split_tools.validate_splits(len(candles), splits)
    if not isinstance(selection, dict) or not isinstance(selection.get("rows"), list):
        raise engine.EngineError("selection result must contain a rows list")
    periods = _validated_candidates([r.get("n") for r in selection["rows"] if isinstance(r, dict)])
    if len(periods) != len(selection["rows"]):
        raise engine.EngineError("selection rows are malformed")
    if splits["train"][0] < max(periods):
        raise engine.EngineError("training split must start after the longest candidate lookback")
    selected = selection.get("selected_n")
    if selected is not None and (type(selected) is not int or selected not in periods):
        raise engine.EngineError("selected period is not one of the evaluated candidates")
    _validated_dataset_sha256(dataset)
    body = {"selected_n": selected, "candidates": list(periods),
            "rule_text": _selection_rule_text(periods, splits["train"][0]), "selection_costs": costs.name,
            "splits": {k: {"start_index": a, "end_index": b,
                           "first_open_unix": candles[a].time, "last_open_unix": candles[b - 1].time}
                       for k, (a, b) in splits.items()},
            "dataset": dataset, "candles_sha256": _candles_sha256(candles),
            "rules_assumed": rules.__dict__, "code_revision": code_rev,
            "scores": [{"n": r["n"], "eligible": r["eligible"], "score": r["score"],
                        "train_return": r["train"]["total_return"],
                        "validation_return": r["validation"]["total_return"]} for r in selection["rows"]]}
    body["frozen_hash"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    return body


def _validated_dataset_sha256(dataset):
    """Return a safe, canonical dataset SHA-256 for registry keys."""
    if not isinstance(dataset, dict):
        raise engine.EngineError("frozen dataset metadata must be an object")
    digest = dataset.get("sha256")
    if (not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)):
        raise engine.EngineError("frozen dataset sha256 must be 64 lowercase hexadecimal characters")
    return digest


def verify_frozen(frozen):
    if not isinstance(frozen, dict):
        raise engine.EngineError("frozen record must be an object")
    _validated_dataset_sha256(frozen.get("dataset"))
    expected_hash = frozen.get("frozen_hash")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise engine.EngineError("frozen record has no valid integrity hash")
    body = {k: v for k, v in frozen.items() if k != "frozen_hash"}
    try:
        actual_hash = hashlib.sha256(_canon(body).encode()).hexdigest()
    except (TypeError, ValueError):
        raise engine.EngineError("frozen record contains non-canonical data")
    if actual_hash != expected_hash:
        raise engine.EngineError("frozen choice was altered after it was frozen")


def test_key(frozen):
    digest = _validated_dataset_sha256(frozen.get("dataset") if isinstance(frozen, dict) else None)
    frozen_hash = frozen.get("frozen_hash")
    if (not isinstance(frozen_hash, str) or len(frozen_hash) != 64
            or any(ch not in "0123456789abcdef" for ch in frozen_hash)):
        raise engine.EngineError("frozen hash must be 64 lowercase hexadecimal characters")
    return f"{digest[:12]}_{frozen_hash[:12]}"


def _load_test_record(path, frozen):
    """Load and minimally authenticate a completed record for this exact frozen choice."""
    if os.path.islink(path) or not os.path.isfile(path):
        raise engine.EngineError("existing test registry record must be a regular, non-symlink file")
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError) as exc:
        raise engine.EngineError(f"existing test registry record is unreadable: {type(exc).__name__}")
    if (not isinstance(record, dict) or record.get("status") != "evaluated"
            or record.get("key") != test_key(frozen)
            or record.get("frozen_hash") != frozen["frozen_hash"]
            or not isinstance(record.get("results"), dict)):
        raise engine.EngineError("existing test registry record is malformed or belongs to another frozen choice")
    return record


def find_prior_test(registry_dir, frozen, out_registry_dir=None):
    """Find a completed evaluation in either the prior registry or this run's output registry."""
    paths = []
    for directory in (registry_dir, out_registry_dir):
        if directory:
            path = os.path.join(directory, test_key(frozen) + ".json")
            if path not in paths:
                paths.append(path)
    records = []
    for path in paths:
        # lexists also detects dangling symlinks; exists() follows them and returns False.
        if os.path.lexists(path):
            records.append(_load_test_record(path, frozen))
    if not records:
        return None
    first = records[0]
    first_digest = hashlib.sha256(_canon(first).encode()).hexdigest()
    if any(hashlib.sha256(_canon(item).encode()).hexdigest() != first_digest for item in records[1:]):
        raise engine.EngineError("conflicting completed test records exist across registry directories")
    return first


def _publish_record(directory, final_path, record):
    """Publish without clobbering: hard-link a fully written temp file to the final name."""
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix=".holdout-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(temporary, final_path)
        except FileExistsError:
            raise engine.EngineError("test evaluation record already exists; refusing to overwrite it")
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def evaluate_test(candles, frozen, splits, registry_dir=None, out_registry_dir=None,
                  allow_reeval=False, run_id=None, cost_grid=COST_GRID, rules=Rules()):
    """Evaluate a frozen holdout once, using an exclusive persistent reservation.

    A hard process termination leaves the reservation in place and blocks retries until
    an operator verifies whether a result was published. This deliberately fails closed.
    """
    verify_frozen(frozen)
    _verify_frozen_inputs(candles, frozen, splits)
    if run_id is not None and (not isinstance(run_id, str) or not run_id or len(run_id) > 128):
        raise engine.EngineError("run_id must be a non-empty string of at most 128 characters")
    if frozen["selected_n"] is None:
        return {"status": "not_evaluated", "reason": "no candidate passed the training screen"}

    store_dir = out_registry_dir or registry_dir
    reservation_dir = registry_dir or store_dir
    if not store_dir or not reservation_dir:
        raise engine.EngineError("a persistent registry directory is required for holdout evaluation")
    os.makedirs(store_dir, exist_ok=True)
    os.makedirs(reservation_dir, exist_ok=True)

    # Fast path permits recovery of a completed publication if the process stopped
    # after publishing the record but before removing its reservation.
    prior = find_prior_test(registry_dir, frozen, out_registry_dir)
    if prior and not allow_reeval:
        return {"status": "already_evaluated", "prior": prior,
                "reason": "the test window was already evaluated for this frozen choice; "
                          "a second look is refused"}
    if prior and allow_reeval and run_id is None:
        raise engine.EngineError("run_id is required for an explicitly labelled re-evaluation")

    key = test_key(frozen)
    reservation = os.path.join(reservation_dir, key + ".pending")
    output_reservation = os.path.join(store_dir, key + ".pending")
    try:
        lock_fd = os.open(reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise engine.EngineError(
            "a holdout evaluation is already in progress or has an interrupted reservation"
        )

    output_lock_fd = None
    same_reservation_dir = os.path.samefile(store_dir, reservation_dir)
    if not same_reservation_dir:
        try:
            output_lock_fd = os.open(output_reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            os.close(lock_fd)
            os.unlink(reservation)
            raise engine.EngineError(
                "an output reservation already exists; refusing to repeat the holdout evaluation"
            )

    published = False
    calculation_started = False
    try:
        lock_record = {"key": key, "frozen_hash": frozen["frozen_hash"],
                       "run_id": run_id, "status": "in_progress"}
        with os.fdopen(lock_fd, "w", encoding="utf-8") as lock_file:
            json.dump(lock_record, lock_file)
            lock_file.flush()
            os.fsync(lock_file.fileno())
        if output_lock_fd is not None:
            with os.fdopen(output_lock_fd, "w", encoding="utf-8") as lock_file:
                json.dump(lock_record, lock_file)
                lock_file.flush()
                os.fsync(lock_file.fileno())

        # Recheck while holding the exclusive reservation. This closes the race
        # where two callers both observed no prior record before either acquired it.
        prior = find_prior_test(registry_dir, frozen, out_registry_dir)
        if prior and not allow_reeval:
            return {"status": "already_evaluated", "prior": prior,
                    "reason": "the test window was already evaluated for this frozen choice; "
                              "a second look is refused"}
        if prior and allow_reeval and run_id is None:
            raise engine.EngineError("run_id is required for an explicitly labelled re-evaluation")

        calculation_started = True
        sig = strategy.ma_trend(frozen["selected_n"])(candles)
        a, b = splits["test"]
        results = {}
        for costs in cost_grid:
            results[costs.name] = {
                "strategy": engine.metrics(engine.simulate(candles, sig, a, b, costs, rules)),
                "buy_and_hold": engine.metrics(engine.buy_and_hold(candles, a, b, costs, rules)),
                "cash": engine.metrics(engine.cash_only(candles, a, b, costs, rules))}
        record = {"status": "evaluated", "key": key, "run_id": run_id,
                  "evaluation_number": 2 if prior else 1, "re_evaluation": bool(prior),
                  "frozen_hash": frozen["frozen_hash"], "results": results}

        if prior:
            # Never interpolate caller-controlled run_id into a path.
            suffix = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:12]
            final_name = key + f"_reeval_{suffix}.json"
            record["evaluation_number"] = 2
            record["re_evaluation"] = True
        else:
            final_name = key + ".json"

        # Publish to the run output (which the workflow preserves) and mirror into
        # the shared registry so another caller in this workspace sees the result.
        _publish_record(store_dir, os.path.join(store_dir, final_name), record)
        if registry_dir and not os.path.samefile(registry_dir, store_dir):
            _publish_record(registry_dir, os.path.join(registry_dir, final_name), record)
        published = True
        return record
    finally:
        # Ordinary exceptions release the reservation. A hard kill leaves it behind,
        # forcing deliberate manual recovery rather than silently repeating the test.
        if published or not calculation_started:
            for pending_path in {reservation, output_reservation}:
                try:
                    os.unlink(pending_path)
                except FileNotFoundError:
                    pass
