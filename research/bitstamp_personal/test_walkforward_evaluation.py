import hashlib
import json
import unittest
from decimal import Decimal

from walkforward_evaluation import (
    RESEARCH_FAMILY, WalkForwardEvaluationError, canonical_dataset_sha256,
    evaluate_five_fold_strategy,
)
from trial_registry import verify_trial_registry
from dataset_manifest import verify_dataset_manifest


def trial_registry():
    lines = [
        '{"event":"TRIAL_STARTED","payload":{"config_sha256":"19754128395ac4f102c189419600c200ad39cc3257658e4855bac20191e5012f","research_family":"BITSTAMP_PERSONAL_SPOT_V2","strategy_id":"SMA20_50_LONG_ONLY","trial_id":"BITSTAMP_V2_SMA20_50_LONG_ONLY"},"previous_hash":"0000000000000000000000000000000000000000000000000000000000000000","record_hash":"726b28a3c72e7e7a2569e26653e6ef9bd87ca7c1401c3a810e81d54d66baf3f4","seq":1}',
        '{"event":"TRIAL_STARTED","payload":{"config_sha256":"a409c684088f65388511d018933b542a120cb424d77c7fc26eba482b3f018612","research_family":"BITSTAMP_PERSONAL_SPOT_V2","strategy_id":"RSI14_MEAN_REVERSION_LONG_ONLY","trial_id":"BITSTAMP_V2_RSI14_MEAN_REVERSION_LONG_ONLY"},"previous_hash":"726b28a3c72e7e7a2569e26653e6ef9bd87ca7c1401c3a810e81d54d66baf3f4","record_hash":"8c6bf55aca81224db38deac1840131f1b0af76f32cf0de0f3471ad56ebccbcc3","seq":2}',
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def synthetic_dataset():
    rows=[]
    previous=Decimal("100")
    for index in range(24840):
        phase=index%40
        close=Decimal("100")-Decimal(phase)*Decimal("0.4") if phase<20 else Decimal("92")+Decimal(phase-20)*Decimal("0.4")
        op=previous;high=max(op,close)+Decimal("0.5");low=min(op,close)-Decimal("0.5")
        opened=1704067200+index*3600
        rows.append({"open_timestamp":opened,"timestamp":opened+3600,"open":str(op),
          "high":str(high),"low":str(low),"close":str(close),"volume":"10000"})
        previous=close
    raw=json.dumps(rows,sort_keys=True,separators=(",",":")).encode()
    return {"market_symbol":"dogeusd","pair":"DOGE/USD","step_seconds":3600,
      "row_count":24840,"first_open_timestamp":1704067200,"last_close_timestamp":1793491200,
      "gap_count":0,"gaps":[],"coverage_status":"CONTIGUOUS",
      "dataset_sha256":hashlib.sha256(raw).hexdigest(),"raw_page_sha256":"b"*64,
      "page_count":25,"candles":rows}


class WalkForwardEvaluationTests(unittest.TestCase):
    def test_builds_five_gate_ready_folds_and_same_cost_baseline(self):
        dataset=synthetic_dataset()
        result=evaluate_five_fold_strategy(
            dataset["candles"],market_symbol=dataset["market_symbol"],
            strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
            trial_registry_bytes=trial_registry(),dataset_manifest=dataset,
        )
        self.assertEqual(len(result["folds"]), 5)
        self.assertEqual(result["registered_trial_count"], 2)
        self.assertEqual(result["costs"]["fee_bps_per_side"], "16")
        self.assertEqual(result["costs"]["half_spread_bps_per_side"], "15")
        self.assertEqual(result["costs"]["slippage_bps_per_side"], "20")
        self.assertEqual(result["dataset_sha256"], verify_dataset_manifest(dataset)["manifest_sha256"])
        self.assertEqual(result["raw_page_sha256"], dataset["raw_page_sha256"])
        self.assertEqual(result["trial_registry_sha256"], verify_trial_registry(trial_registry())["registry_sha256"])
        self.assertEqual(result["profitability_status"], "NOT_VERIFIED")
        for fold in result["folds"]:
            self.assertEqual(fold["observations"], 31)
            self.assertEqual(fold["registered_trial_count"], 2)
            self.assertEqual(fold["trial_registry_sha256"], result["trial_registry_sha256"])
            self.assertTrue(0 <= fold["max_drawdown"] < 1)
            self.assertTrue(0 <= fold["deflated_sharpe_probability"] <= 1)

    def test_costs_and_dataset_identity_are_frozen_by_market_symbol(self):
        dataset=synthetic_dataset()
        digest=canonical_dataset_sha256("btcusd",dataset["candles"])
        self.assertEqual(len(digest),64)
        self.assertNotEqual(digest,canonical_dataset_sha256("ethusd",dataset["candles"]))
        with self.assertRaisesRegex(WalkForwardEvaluationError, "frozen V2 universe"):
            canonical_dataset_sha256("not-a-market",dataset["candles"])
        with self.assertRaisesRegex(WalkForwardEvaluationError,"completeness validation"):
            bad=dict(dataset);bad["gap_count"]=1
            evaluate_five_fold_strategy(dataset["candles"],market_symbol="dogeusd",
              strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",trial_registry_bytes=trial_registry(),dataset_manifest=bad)
        changed=list(dataset["candles"]);changed[0]=dict(changed[0],close="999")
        with self.assertRaisesRegex(WalkForwardEvaluationError,"do not match verified dataset manifest"):
            evaluate_five_fold_strategy(changed,market_symbol="dogeusd",
              strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",trial_registry_bytes=trial_registry(),dataset_manifest=dataset)

    def test_strategy_must_be_present_in_verified_trial_registry(self):
        # Two registered SMA attempts meet the minimum trial count, but RSI
        # must still be rejected because it is absent from the verified registry.
        import hashlib, json
        events = []
        previous = "0" * 64
        for seq, trial_id in enumerate(("SMA_TRIAL_ONE", "SMA_TRIAL_TWO"), 1):
            payload = {
                "config_sha256": ("a" if seq == 1 else "b") * 64,
                "research_family": "BITSTAMP_PERSONAL_SPOT_V2",
                "strategy_id": "SMA20_50_LONG_ONLY",
                "trial_id": trial_id,
            }
            core = {
                "seq": seq, "event": "TRIAL_STARTED",
                "payload": payload, "previous_hash": previous,
            }
            record_hash = hashlib.sha256(
                json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            events.append(json.dumps(
                {**core, "record_hash": record_hash},
                sort_keys=True, separators=(",", ":"),
            ))
            previous = record_hash
        raw = ("\n".join(events) + "\n").encode()
        dataset=synthetic_dataset()
        with self.assertRaisesRegex(WalkForwardEvaluationError, "missing from the verified trial registry"):
            evaluate_five_fold_strategy(
                dataset["candles"], market_symbol="dogeusd",
                strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
                trial_registry_bytes=raw, dataset_manifest=dataset,
            )

    def test_invalid_strategy_or_registry_fails_closed(self):
        dataset=synthetic_dataset()
        kwargs={"market_symbol":"dogeusd","trial_registry_bytes":trial_registry(),"dataset_manifest":dataset}
        with self.assertRaisesRegex(WalkForwardEvaluationError, "not preregistered"):
            evaluate_five_fold_strategy(dataset["candles"], strategy_id="UNREGISTERED", **kwargs)
        with self.assertRaisesRegex(WalkForwardEvaluationError, "integrity validation"):
            evaluate_five_fold_strategy(
                dataset["candles"], strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
                **{**kwargs, "trial_registry_bytes": b"tampered\n"},
            )


if __name__ == "__main__":
    unittest.main()
