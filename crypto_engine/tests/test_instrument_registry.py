import unittest
from dataclasses import replace

from tmm_core.instrument_registry import (
    InstrumentRegistryError, InstrumentVersion, evaluate_market_lifecycle,
    validate_instrument_registry,
)


class InstrumentRegistryTests(unittest.TestCase):
    NOW = 1_800_000_000
    HASH = "b" * 64

    def record(self, **kwargs):
        base = dict(
            market_id="solana:pool-address-1", venue_id="raydium",
            market_type="DEX_POOL", base_asset_id="solana:mint-1",
            quote_asset_id="solana:wrapped-sol", base_symbol="MEME",
            quote_symbol="WSOL", effective_from=self.NOW - 1000,
            effective_to=None, source_id="synthetic-registry",
            source_sha256=self.HASH, source_timestamp=self.NOW - 30,
            observed_at=self.NOW - 20, status="ACTIVE",
            sell_side_available=True, reactivation_confirmed=None,
        )
        base.update(kwargs)
        return InstrumentVersion(**base)

    def test_active_market_with_confirmed_exit_path_allows_market_eligibility(self):
        result = evaluate_market_lifecycle(records=[self.record()],
                                           market_id="solana:pool-address-1",
                                           decision_time=self.NOW)
        self.assertTrue(result["market_eligible_for_new_entries"])
        self.assertTrue(result["sell_side_market_available"])
        self.assertFalse(result["order_authorized"])

    def test_active_market_without_sell_path_blocks_new_entries(self):
        result = evaluate_market_lifecycle(records=[self.record(sell_side_available=False)],
                                           market_id="solana:pool-address-1",
                                           decision_time=self.NOW)
        self.assertFalse(result["market_eligible_for_new_entries"])
        self.assertIn("EXIT_PATH_NOT_CONFIRMED", result["reasons"])

    def test_halted_and_delisting_markets_block_entries_but_can_allow_exit_path(self):
        for status in ("HALTED", "DELISTING_ANNOUNCED"):
            result = evaluate_market_lifecycle(records=[self.record(status=status)],
                                               market_id="solana:pool-address-1",
                                               decision_time=self.NOW)
            self.assertFalse(result["market_eligible_for_new_entries"])
            self.assertTrue(result["sell_side_market_available"])

    def test_delisted_migrating_and_unknown_markets_block_entries_and_exit_path(self):
        for status in ("DELISTED", "MIGRATION_PENDING", "UNKNOWN"):
            result = evaluate_market_lifecycle(records=[self.record(status=status)],
                                               market_id="solana:pool-address-1",
                                               decision_time=self.NOW)
            self.assertFalse(result["market_eligible_for_new_entries"])
            self.assertFalse(result["sell_side_market_available"])
            if status == "DELISTED":
                self.assertEqual(result["delisted_position_resolution"], "UNRESOLVED")

    def test_reactivation_requires_explicit_confirmation(self):
        halted = self.record(status="HALTED", effective_to=self.NOW - 100,
                             sell_side_available=False)
        active = self.record(effective_from=self.NOW - 50, reactivation_confirmed=None)
        result = evaluate_market_lifecycle(records=[halted, active],
                                           market_id="solana:pool-address-1",
                                           decision_time=self.NOW)
        self.assertFalse(result["market_eligible_for_new_entries"])
        self.assertIn("REACTIVATION_NOT_CONFIRMED", result["reasons"])
        confirmed = replace(active, reactivation_confirmed=True)
        result = evaluate_market_lifecycle(records=[halted, confirmed],
                                           market_id="solana:pool-address-1",
                                           decision_time=self.NOW)
        self.assertTrue(result["market_eligible_for_new_entries"])

    def test_stale_metadata_fails_closed(self):
        result = evaluate_market_lifecycle(
            records=[self.record(source_timestamp=self.NOW - 10000,
                                 observed_at=self.NOW - 9990)],
            market_id="solana:pool-address-1", decision_time=self.NOW,
            max_metadata_age_seconds=100,
        )
        self.assertFalse(result["market_eligible_for_new_entries"])
        self.assertIn("STALE_MARKET_METADATA", result["reasons"])

    def test_stale_market_metadata_blocks_exit_availability_too(self):
        result = evaluate_market_lifecycle(
            records=[self.record(status="HALTED", source_timestamp=self.NOW - 10000,
                                 observed_at=self.NOW - 9990)],
            market_id="solana:pool-address-1", decision_time=self.NOW,
            max_metadata_age_seconds=100,
        )
        self.assertFalse(result["market_eligible_for_new_entries"])
        self.assertFalse(result["sell_side_market_available"])

    def test_overlapping_versions_and_future_metadata_are_rejected(self):
        first = self.record(effective_to=self.NOW - 10)
        second = self.record(effective_from=self.NOW - 20)
        with self.assertRaises(InstrumentRegistryError):
            validate_instrument_registry(records=[first, second], decision_time=self.NOW)
        with self.assertRaises(InstrumentRegistryError):
            validate_instrument_registry(records=[self.record(source_timestamp=self.NOW + 1)],
                                         decision_time=self.NOW)

    def test_registry_rejects_bad_identity_hash_and_status(self):
        for record in (self.record(market_id=""), self.record(source_sha256="bad"),
                       self.record(status="TRADING")):
            with self.subTest(record=record), self.assertRaises(InstrumentRegistryError):
                validate_instrument_registry(records=[record], decision_time=self.NOW)


if __name__ == "__main__":
    unittest.main()
