import unittest
from decimal import Decimal

from walkforward_evaluation import (
    RESEARCH_FAMILY, WalkForwardEvaluationError, canonical_dataset_sha256,
    evaluate_five_fold_strategy,
)
from trial_registry import verify_trial_registry


def trial_registry():
    lines = [
        '{"event":"TRIAL_STARTED","payload":{"config_sha256":"19754128395ac4f102c189419600c200ad39cc3257658e4855bac20191e5012f","research_family":"BITSTAMP_PERSONAL_SPOT_V2","strategy_id":"SMA20_50_LONG_ONLY","trial_id":"BITSTAMP_V2_SMA20_50_LONG_ONLY"},"previous_hash":"0000000000000000000000000000000000000000000000000000000000000000","record_hash":"726b28a3c72e7e7a2569e26653e6ef9bd87ca7c1401c3a810e81d54d66baf3f4","seq":1}',
        '{"event":"TRIAL_STARTED","payload":{"config_sha256":"a409c684088f65388511d018933b542a120cb424d77c7fc26eba482b3f018612","research_family":"BITSTAMP_PERSONAL_SPOT_V2","strategy_id":"RSI14_MEAN_REVERSION_LONG_ONLY","trial_id":"BITSTAMP_V2_RSI14_MEAN_REVERSION_LONG_ONLY"},"previous_hash":"726b28a3c72e7e7a2569e26653e6ef9bd87ca7c1401c3a810e81d54d66baf3f4","record_hash":"8c6bf55aca81224db38deac1840131f1b0af76f32cf0de0f3471ad56ebccbcc3","seq":2}',
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def synthetic_candles(count):
    rows = []
    previous = Decimal("100")
    for index in range(count):
        phase = index % 40
        if phase < 20:
            close = Decimal("100") - Decimal(phase) * Decimal("0.4")
        else:
            close = Decimal("92") + Decimal(phase - 20) * Decimal("0.4")
        open_price = previous
        high = max(open_price, close) + Decimal("0.5")
        low = min(open_price, close) - Decimal("0.5")
        rows.append({
            "open": str(open_price), "high": str(high), "low": str(low),
            "close": str(close), "volume": "10000",
        })
        previous = close
    return rows


class WalkForwardEvaluationTests(unittest.TestCase):
    def test_builds_five_gate_ready_folds_and_same_cost_baseline(self):
        rows = synthetic_candles(7900)
        result = evaluate_five_fold_strategy(
            rows,
            strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
            market_symbol="dogeusd",
            trial_registry_bytes=trial_registry(),
        )
        self.assertEqual(len(result["folds"]), 5)
        self.assertEqual(result["registered_trial_count"], 2)
        self.assertEqual(result["costs"]["fee_bps_per_side"], "16")
        self.assertEqual(result["costs"]["half_spread_bps_per_side"], "15")
        self.assertEqual(result["costs"]["slippage_bps_per_side"], "20")
        self.assertEqual(result["dataset_sha256"], canonical_dataset_sha256("dogeusd", rows))
        self.assertEqual(result["trial_registry_sha256"], verify_trial_registry(trial_registry())["registry_sha256"])
        self.assertEqual(result["profitability_status"], "NOT_VERIFIED")
        for fold in result["folds"]:
            self.assertEqual(fold["observations"], 31)
            self.assertEqual(fold["registered_trial_count"], 2)
            self.assertEqual(fold["trial_registry_sha256"], result["trial_registry_sha256"])
            self.assertTrue(0 <= fold["max_drawdown"] < 1)
            self.assertTrue(0 <= fold["deflated_sharpe_probability"] <= 1)

    def test_costs_and_dataset_identity_are_frozen_by_market_symbol(self):
        rows = synthetic_candles(7900)
        digest = canonical_dataset_sha256("btcusd", rows)
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, canonical_dataset_sha256("ethusd", rows))
        with self.assertRaisesRegex(WalkForwardEvaluationError, "frozen V2 universe"):
            canonical_dataset_sha256("not-a-market", rows)
        with self.assertRaisesRegex(WalkForwardEvaluationError, "frozen V2 universe"):
            evaluate_five_fold_strategy(
                rows, market_symbol="not-a-market",
                strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
                trial_registry_bytes=trial_registry(),
            )

    def test_strategy_must_be_present_in_verified_trial_registry(self):
        # Build a valid registry containing only SMA; RSI is a known strategy
        # but must not be evaluated without a matching registered trial.
        import hashlib, json
        payload = {
            "config_sha256": "19754128395ac4f102c189419600c200ad39cc3257658e4855bac20191e5012f",
            "research_family": "BITSTAMP_PERSONAL_SPOT_V2",
            "strategy_id": "SMA20_50_LONG_ONLY",
            "trial_id": "BITSTAMP_V2_SMA20_50_LONG_ONLY",
        }
        core = {"seq": 1, "event": "TRIAL_STARTED", "payload": payload, "previous_hash": "0" * 64}
        record_hash = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        raw = (json.dumps({**core, "record_hash": record_hash}, sort_keys=True, separators=(",", ":")) + "\\n").encode()
        with self.assertRaisesRegex(WalkForwardEvaluationError, "missing from the verified trial registry"):
            evaluate_five_fold_strategy(
                synthetic_candles(7900), market_symbol="btcusd",
                strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
                trial_registry_bytes=raw,
            )

    def test_invalid_strategy_or_registry_fails_closed(self):
        rows = synthetic_candles(7900)
        kwargs = {
            "market_symbol": "btcusd",
            "trial_registry_bytes": trial_registry(),
        }
        with self.assertRaisesRegex(WalkForwardEvaluationError, "not preregistered"):
            evaluate_five_fold_strategy(rows, strategy_id="UNREGISTERED", **kwargs)
        with self.assertRaisesRegex(WalkForwardEvaluationError, "integrity validation"):
            evaluate_five_fold_strategy(
                rows, strategy_id="RSI14_MEAN_REVERSION_LONG_ONLY",
                **{**kwargs, "trial_registry_bytes": b"tampered\n"},
            )


if __name__ == "__main__":
    unittest.main()
