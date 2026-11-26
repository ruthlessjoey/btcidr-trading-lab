"""Fail-closed OOS promotion screen; never places orders or proves future returns."""
from __future__ import annotations
import math, re
from collections.abc import Mapping, Sequence

MINIMUM_FOLDS=5
MINIMUM_FOLD_RATIO=0.60
MAXIMUM_DRAWDOWN=0.20
MINIMUM_PROFIT_FACTOR=1.20
MINIMUM_CLOSED_TRADES=30
MINIMUM_OBSERVATIONS=100
MINIMUM_DSR=0.95
FIELDS=frozenset({"fold_id","test_start","test_end","dataset_sha256","cost_model_sha256","strategy_config_sha256","return_valuation","terminal_position_status","registered_trial_count","strategy_net_return","buy_hold_net_return","two_x_cost_net_return","max_drawdown","profit_factor","closed_trade_count","observations","deflated_sharpe_probability","bootstrap_excess_ci_lower"})

class PromotionEvidenceError(ValueError):
    """Evidence is missing, malformed or internally inconsistent."""

def _number(v, name):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)):
        raise PromotionEvidenceError(f"{name} must be a finite number")
    return float(v)

def _count(v,name):
    if isinstance(v,bool) or not isinstance(v,int) or v<0:
        raise PromotionEvidenceError(f"{name} must be a nonnegative integer")
    return v

def _fold(f,i):
    if not isinstance(f,Mapping) or set(f)!=FIELDS:
        raise PromotionEvidenceError(f"fold[{i}] must contain exactly the required fields")
    name=f["fold_id"]
    if not isinstance(name,str) or not name.strip() or len(name)>128:
        raise PromotionEvidenceError(f"fold[{i}].fold_id is invalid")
    start=_count(f["test_start"],f"fold[{i}].test_start")
    end=_count(f["test_end"],f"fold[{i}].test_end")
    if end<=start: raise PromotionEvidenceError(f"fold[{i}] test range must be non-empty")
    digest=f["dataset_sha256"]
    if not isinstance(digest,str) or re.fullmatch(r"[0-9a-f]{64}",digest) is None:
        raise PromotionEvidenceError(f"fold[{i}].dataset_sha256 must be lowercase SHA-256")
    cost_hash=f["cost_model_sha256"]
    config_hash=f["strategy_config_sha256"]
    for label,value in (("cost_model_sha256",cost_hash),("strategy_config_sha256",config_hash)):
        if not isinstance(value,str) or re.fullmatch(r"[0-9a-f]{64}",value) is None:
            raise PromotionEvidenceError(f"fold[{i}].{label} must be lowercase SHA-256")
    if f["return_valuation"]!="REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT":
        raise PromotionEvidenceError(f"fold[{i}] returns must be realized after costs with terminal liquidation")
    if f["terminal_position_status"]!="FLAT":
        raise PromotionEvidenceError(f"fold[{i}] strategy and benchmark must end flat")
    trials=_count(f["registered_trial_count"],f"fold[{i}].registered_trial_count")
    if trials<2: raise PromotionEvidenceError("registered_trial_count must include all preregistered candidates")
    r={"fold_id":name,"test_start":start,"test_end":end,"dataset_sha256":digest,"cost_model_sha256":cost_hash,"strategy_config_sha256":config_hash,"return_valuation":f["return_valuation"],"terminal_position_status":f["terminal_position_status"],"registered_trial_count":trials}
    for k in ("strategy_net_return","buy_hold_net_return","two_x_cost_net_return","max_drawdown","profit_factor","deflated_sharpe_probability","bootstrap_excess_ci_lower"):
        r[k]=_number(f[k],f"fold[{i}].{k}")
    for k in ("closed_trade_count","observations"): r[k]=_count(f[k],f"fold[{i}].{k}")
    for k in ("strategy_net_return","buy_hold_net_return","two_x_cost_net_return"):
        if r[k]<=-1: raise PromotionEvidenceError(f"fold[{i}].{k} must exceed -100%")
    if not 0<=r["max_drawdown"]<1: raise PromotionEvidenceError(f"fold[{i}].max_drawdown must be in [0,1)")
    if r["profit_factor"]<0: raise PromotionEvidenceError(f"fold[{i}].profit_factor cannot be negative")
    if not 0<=r["deflated_sharpe_probability"]<=1: raise PromotionEvidenceError(f"fold[{i}].deflated_sharpe_probability must be in [0,1]")
    if r["two_x_cost_net_return"]>r["strategy_net_return"]:
        raise PromotionEvidenceError(f"fold[{i}] 2x-cost return cannot exceed base-cost return")
    return r

def evaluate_promotion_gate(folds: Sequence[Mapping[str,object]]) -> dict:
    """Screen half-open candle-index OOS folds; returns and drawdown are fractions.

    Caller-supplied DSR/bootstrap, costs, dataset provenance, embargo and untouched
    status are not independently verified here. Passing only permits human review.
    """
    if isinstance(folds,(str,bytes)) or not isinstance(folds,Sequence):
        raise PromotionEvidenceError("folds must be a sequence")
    if len(folds)<MINIMUM_FOLDS: raise PromotionEvidenceError("at least 5 distinct OOS folds are required")
    rows=[_fold(f,i) for i,f in enumerate(folds)]
    seen=set(); digest=rows[0]["dataset_sha256"]; cost_hash=rows[0]["cost_model_sha256"]; config_hash=rows[0]["strategy_config_sha256"]; trials=rows[0]["registered_trial_count"]; end=-1
    for r in rows:
        if r["fold_id"] in seen: raise PromotionEvidenceError("fold_id values must be unique")
        seen.add(r["fold_id"])
        if r["test_start"]<end: raise PromotionEvidenceError("OOS test ranges must be chronological and non-overlapping")
        end=r["test_end"]
        if r["dataset_sha256"]!=digest: raise PromotionEvidenceError("all folds must bind to the same dataset SHA-256")
        if r["cost_model_sha256"]!=cost_hash: raise PromotionEvidenceError("all folds must use the same frozen cost-model hash")
        if r["strategy_config_sha256"]!=config_hash: raise PromotionEvidenceError("all folds must use the same frozen strategy-config hash")
        if r["registered_trial_count"]!=trials: raise PromotionEvidenceError("all folds must use the same complete registered-trial count")
    n=len(rows)
    positive=sum(r["strategy_net_return"]>0 for r in rows)/n
    beat=sum(r["strategy_net_return"]>r["buy_hold_net_return"] for r in rows)/n
    stress=sum(r["two_x_cost_net_return"]>0 for r in rows)/n
    mean=lambda k: math.fsum(r[k] for r in rows)/n
    checks={
      "at_least_five_distinct_oos_folds":n>=5,
      "positive_net_return_in_at_least_60pct_folds":positive>=.60,
      "beats_same_cost_buy_hold_in_at_least_60pct_folds":beat>=.60,
      "positive_mean_net_return":mean("strategy_net_return")>0,
      "positive_mean_excess_vs_same_cost_buy_hold":mean("strategy_net_return")-mean("buy_hold_net_return")>0,
      "positive_net_return_in_at_least_60pct_folds_at_2x_cost":stress>=.60,
      "positive_mean_net_return_at_2x_cost":mean("two_x_cost_net_return")>0,
      "every_fold_drawdown_at_most_20pct":max(r["max_drawdown"] for r in rows)<=.20,
      "every_fold_profit_factor_at_least_1_20":min(r["profit_factor"] for r in rows)>=1.20,
      "every_fold_dsr_probability_at_least_0_95":min(r["deflated_sharpe_probability"] for r in rows)>=.95,
      "every_fold_paired_bootstrap_lower_bound_positive":min(r["bootstrap_excess_ci_lower"] for r in rows)>0,
      "at_least_30_closed_trades":sum(r["closed_trade_count"] for r in rows)>=30,
      "at_least_100_observations":sum(r["observations"] for r in rows)>=100,
    }
    return {
      "status":"ELIGIBLE_FOR_INDEPENDENT_HUMAN_REVIEW_NOT_PROVEN_PROFITABLE" if all(checks.values()) else "REJECT_OR_RESEARCH_MORE",
      "profitability_status":"NOT_VERIFIED","fold_count":n,"positive_fold_ratio":positive,
      "same_cost_buy_hold_beat_fold_ratio":beat,"two_x_cost_positive_fold_ratio":stress,
      "mean_strategy_net_return":mean("strategy_net_return"),
      "mean_excess_vs_same_cost_buy_hold":mean("strategy_net_return")-mean("buy_hold_net_return"),
      "mean_two_x_cost_net_return":mean("two_x_cost_net_return"),
      "worst_fold_max_drawdown":max(r["max_drawdown"] for r in rows),
      "minimum_fold_profit_factor":min(r["profit_factor"] for r in rows),
      "minimum_fold_dsr_probability":min(r["deflated_sharpe_probability"] for r in rows),
      "minimum_fold_bootstrap_excess_ci_lower":min(r["bootstrap_excess_ci_lower"] for r in rows),
      "total_closed_trades":sum(r["closed_trade_count"] for r in rows),
      "total_observations":sum(r["observations"] for r in rows),
      "dataset_sha256":digest,"cost_model_sha256":cost_hash,"strategy_config_sha256":config_hash,"registered_trial_count":trials,"checks":checks,
      "frozen_thresholds":{"minimum_folds":5,"minimum_fold_ratio":.60,"maximum_drawdown":.20,"minimum_profit_factor":1.20,"minimum_closed_trades":30,"minimum_observations":100,"minimum_dsr_probability":.95},
      "limitations":["Dataset hash must cover exact source bytes and preprocessing.","Untouched, embargoed OOS status requires independent proof.","Returns must include fees, spread, slippage, partial/rejected fills and stated impact.","2x-cost replay must use identical signals and data, changing only costs.","DSR, trial registry and paired block-bootstrap require independent reproduction.","A pass only permits human review; it never enables PAPER/LIVE or proves future profit."]
    }
