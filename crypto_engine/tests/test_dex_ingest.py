import unittest
from datetime import datetime, timezone

from tmm_core.dex_ingest import (
    DexIngestError, SOL_MINT, aggregate_transaction_costs,
    parse_trade_batch, parse_trade_record,
)


def row(**overrides):
    value = {
        "block_time": "2026-10-15T00:00:00", "ts": 1792022400,
        "event_ts": 1792022400, "slot": 457030039, "idx": 106, "seq": 0,
        "venue": "curve", "venue_code": "c", "failed": False,
        "mint": "TokenMint111", "pool": None, "migration_pool": None,
        "wallet": "Wallet111", "side": "buy", "sol_lamports": 100000000,
        "token_amount": 1000000, "quote_mint": SOL_MINT,
        "quote_amount": 100000000, "r1": 63210724936.0,
        "r2": 509249029358694.0, "r3": 33210724936.0,
        "pool_base_mint": None, "pool_quote_mint": None,
        "fee_lamports": 1005001, "tip_lamports": 0,
        "compute_units": 68444, "multi_hop": False, "error": None, "epoch": 1057,
    }
    value.update(overrides)
    return value


class DexIngestTests(unittest.TestCase):
    def test_parse_landed_curve_row(self):
        trade = parse_trade_record(row())
        self.assertEqual(trade.venue, "curve")
        self.assertEqual(trade.token_identity_status, "MINT_PRESENT")
        self.assertEqual(trade.token_amount, 1000000)

    def test_parse_landed_pumpswap_migration_pool(self):
        trade = parse_trade_record(row(
            venue="pumpswap", venue_code="a", pool="Pool111",
            migration_pool=True, pool_base_mint="TokenMint111", pool_quote_mint=SOL_MINT,
        ))
        self.assertEqual(trade.venue, "pumpswap")
        self.assertTrue(trade.migration_pool)

    def test_parse_failed_attempt_keeps_fee_but_no_fill(self):
        trade = parse_trade_record(row(
            failed=True, event_ts=None, sol_lamports=None, token_amount=None,
            quote_mint=None, quote_amount=None, r1=None, r2=None, r3=None,
            error="InstructionError(1, Custom(6001))", tip_lamports=None, compute_units=None,
        ))
        self.assertTrue(trade.failed)
        self.assertEqual(trade.fee_lamports, 1005001)
        self.assertIsNone(trade.token_amount)

    def test_token_quoted_curve_does_not_claim_sol_amount(self):
        trade = parse_trade_record(row(
            sol_lamports=None, quote_mint="OtherToken111", quote_amount=92744223642,
        ))
        self.assertIsNone(trade.sol_lamports)
        self.assertEqual(trade.quote_mint, "OtherToken111")

    def test_missing_multi_hop_mint_remains_unresolved(self):
        trade = parse_trade_record(row(
            venue="pumpswap", venue_code="a", pool="Pool111", mint=None,
            multi_hop=True, pool_base_mint=None, pool_quote_mint=SOL_MINT,
        ))
        self.assertEqual(trade.token_identity_status, "UNRESOLVED_MULTI_HOP_MINT")

    def test_wallet_is_not_retained(self):
        self.assertFalse(hasattr(parse_trade_record(row()), "wallet"))

    def test_native_parquet_datetime_is_accepted(self):
        trade = parse_trade_record(row(block_time=datetime(2026, 10, 15, tzinfo=timezone.utc)))
        self.assertTrue(trade.block_time.endswith("+00:00"))

    def test_large_float64_reserves_are_flagged(self):
        self.assertTrue(parse_trade_record(row(r2=float(1 << 60))).reserve_precision_warning)

    def test_rejects_unknown_or_missing_schema_fields(self):
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(extra="not-allowed"))
        missing = row()
        del missing["epoch"]
        with self.assertRaises(DexIngestError):
            parse_trade_record(missing)

    def test_rejects_boolean_as_integer(self):
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(slot=True))

    def test_rejects_uint64_overflow_and_negative_amount(self):
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(token_amount=1 << 64))
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(quote_amount=-1))

    def test_rejects_timestamp_mismatch_and_non_utc(self):
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(ts=1792022401))
        with self.assertRaises(DexIngestError):
            parse_trade_record(row(block_time="2026-10-15T07:00:00+07:00"))

    def test_rejects_invalid_venue_side_and_reserves(self):
        for change in ({"venue": "unknown"}, {"side": "hold"}, {"r1": float("nan")}):
            with self.subTest(change=change), self.assertRaises(DexIngestError):
                parse_trade_record(row(**change))

    def test_rejects_landed_missing_amounts_or_quote(self):
        for change in ({"token_amount": None}, {"quote_amount": 0}, {"quote_mint": None}):
            with self.subTest(change=change), self.assertRaises(DexIngestError):
                parse_trade_record(row(**change))

    def test_rejects_failed_rows_with_amounts_or_without_error(self):
        for change in (
            {"failed": True, "error": "failure"},
            {"failed": True, "token_amount": None, "quote_amount": None,
             "sol_lamports": None, "r1": None, "r2": None, "r3": None},
        ):
            with self.subTest(change=change), self.assertRaises(DexIngestError):
                parse_trade_record(row(**change))

    def test_batch_rejects_duplicate_or_out_of_order_execution_key(self):
        with self.assertRaises(DexIngestError):
            parse_trade_batch([row(), row()])
        with self.assertRaises(DexIngestError):
            parse_trade_batch([row(idx=108), row()])

    def test_batch_accepts_multiple_rows_in_one_transaction(self):
        trades = parse_trade_batch([
            row(), row(seq=1, token_amount=2000000, quote_amount=200000000),
        ])
        costs = aggregate_transaction_costs(trades)
        self.assertEqual(len(costs), 1)
        self.assertEqual(costs[0]["row_count"], 2)
        self.assertEqual(costs[0]["fee_lamports"], 1005001)

    def test_transaction_fee_counted_once_and_conflicts_rejected(self):
        trades = parse_trade_batch([row(), row(idx=108, fee_lamports=2000)])
        costs = aggregate_transaction_costs(trades)
        self.assertEqual(sum(x["fee_lamports"] for x in costs), 1007001)
        conflicted = parse_trade_batch([row(), row(seq=1, fee_lamports=1005002)])
        with self.assertRaises(DexIngestError):
            aggregate_transaction_costs(conflicted)


if __name__ == "__main__":
    unittest.main()
