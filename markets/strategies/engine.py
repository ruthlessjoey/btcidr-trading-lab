"""markets/strategies/engine.py - evaluates one strategy on one data report (M5).

evaluate_report(strategy, listing, report, config) is the only entry point. It takes the dict that
markets.data_pipeline.fetch_market_data returns. It never fetches, never reads a clock, and never names a provider:
the provider appears only as provenance text copied from the report.

Decision mapping (the engine owns it; strategies cannot change it):

    report status          decision   reason code           notes
    ---------------------  ---------  --------------------  --------------------------------------------------
    listing or interval    INVALID    UNSUPPORTED_*         strategy does not declare it; no evaluation
    listing mismatch       INVALID    LISTING_MISMATCH      listing passed in != report listing
    REFUSED                INVALID    DATA_REFUSED          provider error or validation/integrity failure kept
    PARTIAL                NO_DATA    DATA_INCOMPLETE       missing expected slots; nothing is filled
    UNAVAILABLE            NO_DATA    DATA_UNAVAILABLE      no usable candles for the window
    COMPLETE, short        NO_DATA    INSUFFICIENT_HISTORY  fewer candles than required_history
    COMPLETE               BUY/SELL/  strategy's own codes  the only path that calls strategy.evaluate
                           HOLD

No strategy evaluation happens on any path except COMPLETE with enough history. The provider error, if any, stays in
provenance.provider_error, whatever the top-level decision.
"""
from markets.strategies import contract as C
from markets.strategies.decision import StrategyDecision, config_fingerprint


def _provenance(report):
    candles = report.get("candles") or {}
    freshness = report.get("freshness") or {}
    error = report.get("error")
    return {
        "data_status": report["status"],
        "data_stage": report["stage"],
        "data_source": report["data_source"],
        "provider": report["provider"]["name"],
        "provider_venue": report["provider"]["venue"],
        "pipeline_version": report["pipeline_version"],
        "time_source": report["reference_time"]["source"],
        "freshness_state": freshness.get("state"),
        "dataset_sha256": candles.get("dataset_sha256"),
        "raw_sha256": candles.get("raw_sha256"),
        "provider_error": None if error is None else {k: error[k] for k in sorted(error)},
    }


def evaluate_report(strategy, listing, report, config=None):
    """Returns one StrategyDecision. Raises StrategyConfigError for a bad configuration (a caller error), and
    StrategyError if the strategy returns something outside its contract. Every data outcome is a decision."""
    cfg = strategy.normalize_config(config)
    fingerprint = config_fingerprint(strategy.strategy_id, strategy.version, cfg)
    timeframe_s = report["timeframe_s"]
    now_s = report["reference_time"]["now_s"]
    prov = _provenance(report)

    def make(decision, codes, reasons, indicators=None, ref_open=None, ref_close=None):
        allowed = set(strategy.reason_codes) | set(C.ENGINE_REASON_CODES)
        bad = [c for c in codes if c not in allowed]
        if bad:
            raise C.StrategyError(f"{strategy.strategy_id} attached undeclared reason code(s) {bad}")
        return StrategyDecision(
            strategy_id=strategy.strategy_id, strategy_version=strategy.version, listing=listing.canonical,
            timeframe_s=timeframe_s, evaluation_now_s=now_s, reference_open_s=ref_open,
            reference_close_s=ref_close, decision=decision, reason_codes=tuple(codes), reasons=tuple(reasons),
            indicators=indicators or {}, provenance=prov, config=cfg, config_fingerprint=fingerprint)

    # 1. Compatibility: the request itself, before any data is judged.
    problems = strategy.compatibility_problems(listing, timeframe_s)
    if problems:
        codes = list(dict.fromkeys(code for code, _ in problems))   # each code once; every reason is kept
        return make(C.INVALID, codes, [text for _, text in problems])

    if report["listing"]["canonical"] != listing.canonical:
        return make(C.INVALID, ["LISTING_MISMATCH"],
                    [f"report describes {report['listing']['canonical']!r}, not {listing.canonical!r}"])

    # 2. Data status: only COMPLETE data reaches the strategy.
    status = report["status"]
    if status == "REFUSED":
        return make(C.INVALID, ["DATA_REFUSED"], [f"data refused at stage {report['stage']}"] + list(report["reasons"]))
    if status == "PARTIAL":
        return make(C.NO_DATA, ["DATA_INCOMPLETE"], ["data is partial: expected slots are missing; nothing filled"]
                    + list(report["reasons"]))
    if status == "UNAVAILABLE":
        return make(C.NO_DATA, ["DATA_UNAVAILABLE"], ["no usable candles for the requested window"]
                    + list(report["reasons"]))
    if status != "COMPLETE":
        raise C.StrategyError(f"unknown data status {status!r}")

    candles = report.get("canonical_candles")
    if candles is None:
        return make(C.INVALID, ["INPUT_MISSING"], ["report is COMPLETE but carries no canonical candles"])

    # 3. History, then the strategy itself.
    need = strategy.required_history(cfg)
    if len(candles) < need:
        return make(C.NO_DATA, ["INSUFFICIENT_HISTORY"],
                    [f"need {need} completed candles, have {len(candles)}"])

    ref_open = candles[-1].open_time_s
    ref_close = ref_open + timeframe_s
    raw = strategy.evaluate(cfg, tuple(candles))
    if not isinstance(raw, dict) or set(raw) != {"decision", "reason_codes", "reasons", "indicators"}:
        raise C.StrategyError(f"{strategy.strategy_id} returned a result outside the contract")
    if raw["decision"] not in C.STRATEGY_DECISIONS:
        raise C.StrategyError(f"{strategy.strategy_id} returned {raw['decision']!r}; strategies may return only "
                              f"{', '.join(C.STRATEGY_DECISIONS)}")
    return make(raw["decision"], raw["reason_codes"], raw["reasons"], raw["indicators"], ref_open, ref_close)
