import json,unittest
from experiment_registry import TrialRegistryError,parse_trial_registry
P="TEST_V1";M=("btcusd","ethusd");S=("SMA","RSI")
def row(m,s,event="REGISTERED"):
 return {"trial_id":f"{P}:{m}:{s}","market_symbol":m,"strategy_id":s,"preregistration_id":P,"event":event,"registered_date":"2026-11-27"}
def raw(rows):return ("\n".join(json.dumps(x) for x in rows)+"\n").encode()
class RegistryTests(unittest.TestCase):
 def test_complete_universe_hash_and_count(self):
  x=[row(m,s) for m in M for s in S];r=parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P);self.assertEqual(r["registered_trial_count"],4);self.assertEqual(len(r["registry_sha256"]),64)
 def test_append_terminal_event_keeps_registered_count(self):
  x=[row(m,s) for m in M for s in S]+[row("btcusd","SMA","FAILED")];r=parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P);self.assertEqual(r["registered_trial_count"],4);self.assertEqual(r["trial_statuses"][f"{P}:btcusd:SMA"],"FAILED")
 def test_missing_unknown_and_duplicate_registration_fail(self):
  x=[row(m,s) for m in M for s in S]
  with self.assertRaisesRegex(TrialRegistryError,"universe mismatch"):parse_trial_registry(raw(x[:-1]),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
  x[-1]=row("solusd","SMA")
  with self.assertRaises(TrialRegistryError):parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
  x=[row(m,s) for m in M for s in S]+[row("btcusd","SMA")]
  with self.assertRaisesRegex(TrialRegistryError,"duplicate REGISTERED"):parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
 def test_event_order_and_terminal_state_are_immutable(self):
  x=[row(m,s) for m in M for s in S];x.insert(0,row("btcusd","SMA","FAILED"))
  with self.assertRaisesRegex(TrialRegistryError,"precedes REGISTERED"):parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
  x=[row(m,s) for m in M for s in S]+[row("btcusd","SMA","FAILED"),row("btcusd","SMA","COMPLETED")]
  with self.assertRaisesRegex(TrialRegistryError,"terminal trial"):parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
 def test_duplicate_json_keys_bad_date_event_blank_and_utf8_fail(self):
  with self.assertRaisesRegex(TrialRegistryError,"duplicate JSON key"):parse_trial_registry(b'{"a":1,"a":2}\n',expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
  for change in ({"registered_date":"bad"},{"event":"NOPE"}):
   x=[row(m,s) for m in M for s in S];x[0].update(change)
   with self.assertRaises(TrialRegistryError):parse_trial_registry(raw(x),expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
  for value in (b"\n",b"\xff"):
   with self.assertRaises(TrialRegistryError):parse_trial_registry(value,expected_market_symbols=M,expected_strategies=S,preregistration_id=P)
if __name__=="__main__":unittest.main()
