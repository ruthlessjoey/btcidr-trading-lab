import unittest
from decimal import Decimal

from tmm_core.offline_portfolio import (
    MarketSpec, PortfolioLedgerError, SyntheticFill, SyntheticMark,
    SyntheticPortfolioLedger,
)


class OfflinePortfolioLedgerTests(unittest.TestCase):
    def setUp(self):
        self.markets = {
            "BTC/USDT": MarketSpec("BTC/USDT", "BTC", "USDT"),
            "ETH/USDT": MarketSpec("ETH/USDT", "ETH", "USDT"),
        }
        self.ledger = SyntheticPortfolioLedger(
            account_id="synthetic-1", account_currency="USDT",
            opening_cash="1000", markets=self.markets,
        )

    def marks(self, timestamp=100):
        return {
            "BTC/USDT": SyntheticMark("BTC/USDT", "100", timestamp, "500"),
            "ETH/USDT": SyntheticMark("ETH/USDT", "10", timestamp, "500"),
        }

    def fill(self, fill_id="f1", side="BUY", quantity="2", price="100", fee="1"):
        return SyntheticFill(fill_id, "BTC/USDT", side, quantity, price, fee, 100)

    def test_buy_debits_cash_and_adds_inventory(self):
        self.assertTrue(self.ledger.apply_fill(self.fill()))
        self.assertEqual(self.ledger.snapshot_cash("synthetic-1"), "799")
        self.assertEqual(self.ledger.snapshot_holdings("synthetic-1")["BTC/USDT"], "2")

    def test_duplicate_fill_is_idempotent(self):
        self.ledger.apply_fill(self.fill())
        self.assertFalse(self.ledger.apply_fill(self.fill()))
        self.assertEqual(self.ledger.snapshot_cash("synthetic-1"), "799")

    def test_sell_credits_cash_and_reduces_inventory(self):
        self.ledger.apply_fill(self.fill())
        self.assertTrue(self.ledger.apply_fill(self.fill("f2", "SELL", "1", "110", "1")))
        self.assertEqual(self.ledger.snapshot_cash("synthetic-1"), "908")
        self.assertEqual(self.ledger.snapshot_holdings("synthetic-1")["BTC/USDT"], "1")

    def test_short_inventory_is_rejected_atomically(self):
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.apply_fill(self.fill("f1", "SELL", "1"))
        self.assertEqual(self.ledger.snapshot_cash("synthetic-1"), "1000")
        self.assertEqual(self.ledger.snapshot_holdings("synthetic-1")["BTC/USDT"], "0")

    def test_insufficient_cash_rejected_atomically(self):
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.apply_fill(self.fill(quantity="20"))
        self.assertEqual(self.ledger.snapshot_cash("synthetic-1"), "1000")

    def test_negative_fee_and_derivative_side_rejected(self):
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.apply_fill(self.fill(fee="-1"))
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.apply_fill(self.fill(side="SHORT"))

    def test_equity_requires_complete_fresh_marks(self):
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.snapshot_equity("synthetic-1")
        self.ledger.apply_fill(self.fill())
        self.ledger.update_marks(self.marks(), timestamp=100)
        self.assertEqual(self.ledger.snapshot_equity("synthetic-1"), "999")

    def test_incomplete_stale_and_future_marks_fail_closed(self):
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.update_marks({"BTC/USDT": self.marks()["BTC/USDT"]}, timestamp=100)
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.update_marks(self.marks(0), timestamp=100, max_age_seconds=30)
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.update_marks(self.marks(101), timestamp=100)

    def test_quote_currency_must_match_account_currency(self):
        bad = {"BTC/USDC": MarketSpec("BTC/USDC", "BTC", "USDC")}
        with self.assertRaises(PortfolioLedgerError):
            SyntheticPortfolioLedger(account_id="a", account_currency="USDT",
                                     opening_cash="100", markets=bad)

    def test_account_isolation_and_audit_chain(self):
        self.ledger.apply_fill(self.fill())
        self.assertTrue(self.ledger.verify_audit_chain("synthetic-1"))
        with self.assertRaises(PortfolioLedgerError):
            self.ledger.snapshot_cash("another-account")
        snapshot = self.ledger.audit_snapshot("synthetic-1")
        snapshot["events"][0]["quantity"] = "999"
        self.assertNotEqual(snapshot["head_hash"], "0" * 64)


if __name__ == "__main__":
    unittest.main()
