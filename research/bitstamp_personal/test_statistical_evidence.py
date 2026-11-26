import unittest
from statistical_evidence import StatisticalEvidenceError,_ppf,deflated_sharpe_probability,paired_moving_block_bootstrap_lower_bound

class StatisticalEvidenceTests(unittest.TestCase):
 def test_inverse_normal_quantiles(self):
  self.assertAlmostEqual(_ppf(.5),0,places=7);self.assertAlmostEqual(_ppf(.975),1.95996398,places=6);self.assertAlmostEqual(_ppf(.025),-1.95996398,places=6)
 def test_dsr_uses_registered_trial_count_and_candidate(self):
  a=[.001+(i%7)*.0001 for i in range(200)];b=[.0001+((i*3)%11)*.0001 for i in range(200)]
  r=deflated_sharpe_probability(a,[a,b],registered_trial_count=14)
  self.assertEqual(r["registered_trial_count"],14);self.assertEqual(r["completed_trial_series_count"],2);self.assertTrue(0<=r["deflated_sharpe_probability"]<=1)
 def test_more_trials_raise_expected_max_threshold(self):
  a=[.001+(i%7)*.0001 for i in range(200)];b=[.0001+((i*3)%11)*.0001 for i in range(200)]
  x=deflated_sharpe_probability(a,[a,b],registered_trial_count=2);y=deflated_sharpe_probability(a,[a,b],registered_trial_count=14)
  self.assertGreaterEqual(y["expected_max_sharpe_threshold_per_period"],x["expected_max_sharpe_threshold_per_period"])
 def test_dsr_rejects_missing_candidate_and_bad_lengths(self):
  a=[.001+(i%3)*.0001 for i in range(50)];b=[.002+(i%3)*.0001 for i in range(50)]
  with self.assertRaisesRegex(StatisticalEvidenceError,"included"):deflated_sharpe_probability(a,[b,b],registered_trial_count=2)
  with self.assertRaisesRegex(StatisticalEvidenceError,"equal observation"):deflated_sharpe_probability(a,[a,b[:-1]],registered_trial_count=2)
 def test_dsr_rejects_zero_variance(self):
  a=[.001]*50
  with self.assertRaisesRegex(StatisticalEvidenceError,"non-zero"):deflated_sharpe_probability(a,[a,a],registered_trial_count=2)
 def test_bootstrap_is_deterministic_and_positive(self):
  a=[.002+(i%5)*.0001 for i in range(200)];b=[.0001+(i%5)*.00005 for i in range(200)]
  x=paired_moving_block_bootstrap_lower_bound(a,b,seed=17);y=paired_moving_block_bootstrap_lower_bound(a,b,seed=17)
  self.assertEqual(x,y);self.assertGreater(x["bootstrap_excess_ci_lower"],0)
 def test_bootstrap_negative_edge_is_negative(self):
  a=[.0001+(i%5)*.00001 for i in range(200)];b=[.002+(i%5)*.0001 for i in range(200)]
  self.assertLess(paired_moving_block_bootstrap_lower_bound(a,b,seed=4)["bootstrap_excess_ci_lower"],0)
 def test_bootstrap_rejects_invalid_lengths_and_parameters(self):
  a=[.001+(i%5)*.0001 for i in range(100)]
  with self.assertRaisesRegex(StatisticalEvidenceError,"equal length"):paired_moving_block_bootstrap_lower_bound(a,a[:-1])
  for kw in ({"block_length":0},{"replicates":999},{"confidence_level":1.0},{"seed":-1}):
   with self.subTest(kw=kw),self.assertRaises(StatisticalEvidenceError):paired_moving_block_bootstrap_lower_bound(a,a,**kw)
 def test_rejects_boolean_nan_infinite_and_less_than_minus_one(self):
  good=[.001+(i%5)*.0001 for i in range(100)]
  for bad in (True,float("nan"),float("inf"),-1.1):
   x=list(good);x[0]=bad
   with self.subTest(bad=bad),self.assertRaises(StatisticalEvidenceError):paired_moving_block_bootstrap_lower_bound(x,good)
if __name__=="__main__":unittest.main()
