import copy, unittest
from promotion_gate import PromotionEvidenceError,evaluate_promotion_gate
H="a"*64
def folds():
 return [{"fold_id":f"f{i}","test_start":i*100,"test_end":i*100+80,"dataset_sha256":H,"trial_registry_sha256":"e"*64,"cost_model_sha256":"c"*64,"strategy_config_sha256":"d"*64,"return_valuation":"REALIZED_NET_AFTER_COSTS_TERMINAL_FLAT","terminal_position_status":"FLAT","registered_trial_count":2,"strategy_net_return":.08,"buy_hold_net_return":.02,"two_x_cost_net_return":.04,"max_drawdown":.1,"profit_factor":1.5,"closed_trade_count":8,"observations":30,"deflated_sharpe_probability":.97,"bootstrap_excess_ci_lower":.005} for i in range(5)]
class GateTests(unittest.TestCase):
 def test_pass_means_review_only(self):
  r=evaluate_promotion_gate(folds()); self.assertTrue(all(r["checks"].values())); self.assertEqual(r["profitability_status"],"NOT_VERIFIED")
 def test_minimum_folds(self):
  with self.assertRaisesRegex(PromotionEvidenceError,"at least 5"): evaluate_promotion_gate(folds()[:4])
 def test_negative_mean_return(self):
  x=folds()
  for r in x:r["strategy_net_return"]=-.01;r["two_x_cost_net_return"]=-.03
  self.assertFalse(evaluate_promotion_gate(x)["checks"]["positive_mean_net_return"])
 def test_same_cost_benchmark(self):
  x=folds()
  for r in x:r["buy_hold_net_return"]=.09
  z=evaluate_promotion_gate(x); self.assertFalse(z["checks"]["positive_mean_excess_vs_same_cost_buy_hold"])
 def test_cost_stress(self):
  x=folds()
  for r in x:r["two_x_cost_net_return"]=-.001
  self.assertFalse(evaluate_promotion_gate(x)["checks"]["positive_mean_net_return_at_2x_cost"])
 def test_2x_cannot_improve_return(self):
  x=folds();x[0]["two_x_cost_net_return"]=.09
  with self.assertRaisesRegex(PromotionEvidenceError,"cannot exceed"):evaluate_promotion_gate(x)
 def test_drawdown_pf_dsr_bootstrap_thresholds(self):
  for key,value,check in [("max_drawdown",.21,"every_fold_drawdown_at_most_20pct"),("profit_factor",1.19,"every_fold_profit_factor_at_least_1_20"),("deflated_sharpe_probability",.94,"every_fold_dsr_probability_at_least_0_95"),("bootstrap_excess_ci_lower",0,"every_fold_paired_bootstrap_lower_bound_positive")]:
   x=folds();x[0][key]=value;self.assertFalse(evaluate_promotion_gate(x)["checks"][check])
 def test_aggregate_trade_and_observation_floors(self):
  x=folds()
  for r in x:r["closed_trade_count"]=5;r["observations"]=19
  z=evaluate_promotion_gate(x);self.assertFalse(z["checks"]["at_least_30_closed_trades"]);self.assertFalse(z["checks"]["at_least_100_observations"])
 def test_duplicate_ids_overlap_hash_and_trial_mismatch(self):
  x=folds();x[1]["fold_id"]=x[0]["fold_id"]
  with self.assertRaisesRegex(PromotionEvidenceError,"unique"):evaluate_promotion_gate(x)
  x=folds();x[1]["test_start"]=70
  with self.assertRaisesRegex(PromotionEvidenceError,"non-overlapping"):evaluate_promotion_gate(x)
  x=folds();x[1]["dataset_sha256"]="b"*64
  with self.assertRaisesRegex(PromotionEvidenceError,"same dataset"):evaluate_promotion_gate(x)
  x=folds();x[1]["registered_trial_count"]=3
  with self.assertRaisesRegex(PromotionEvidenceError,"same complete"):evaluate_promotion_gate(x)
 def test_schema_digest_and_invalid_metrics_fail_closed(self):
  x=folds();del x[0]["profit_factor"]
  with self.assertRaises(PromotionEvidenceError):evaluate_promotion_gate(x)
  x=folds();x[0]["unexpected"]=1
  with self.assertRaises(PromotionEvidenceError):evaluate_promotion_gate(x)
  for value in (True,float("nan"),float("inf"),"0.1"):
   x=folds();x[0]["strategy_net_return"]=value
   with self.assertRaises(PromotionEvidenceError):evaluate_promotion_gate(x)
  x=folds();x[0]["dataset_sha256"]="bad"
  with self.assertRaisesRegex(PromotionEvidenceError,"SHA-256"):evaluate_promotion_gate(x)
 def test_cost_and_strategy_hashes_must_match_across_folds(self):
  x=folds();x[1]["cost_model_sha256"]="e"*64
  with self.assertRaisesRegex(PromotionEvidenceError,"cost-model hash"):evaluate_promotion_gate(x)
  x=folds();x[1]["strategy_config_sha256"]="f"*64
  with self.assertRaisesRegex(PromotionEvidenceError,"strategy-config hash"):evaluate_promotion_gate(x)
 def test_unrealized_or_open_terminal_returns_are_rejected(self):
  x=folds();x[0]["return_valuation"]="MARK_TO_MARKET"
  with self.assertRaisesRegex(PromotionEvidenceError,"realized after costs"):evaluate_promotion_gate(x)
  x=folds();x[0]["terminal_position_status"]="OPEN"
  with self.assertRaisesRegex(PromotionEvidenceError,"must end flat"):evaluate_promotion_gate(x)
 def test_boolean_counts_empty_range_and_input_immutability(self):
  x=folds();x[0]["closed_trade_count"]=True
  with self.assertRaises(PromotionEvidenceError):evaluate_promotion_gate(x)
  x=folds();x[0]["test_end"]=x[0]["test_start"]
  with self.assertRaises(PromotionEvidenceError):evaluate_promotion_gate(x)
  x=folds();before=copy.deepcopy(x);evaluate_promotion_gate(x);self.assertEqual(x,before)


    def test_trial_registry_hash_must_match_across_folds(self):
        rows = valid_folds()
        rows[1]["trial_registry_sha256"] = "f" * 64
        with self.assertRaisesRegex(PromotionEvidenceError, "trial-registry hash"):
            evaluate_promotion_gate(rows)



if __name__=="__main__":unittest.main()
