import unittest

from tmm_core.reservation_allocations import (
    ReservationAllocationError,
    validate_sell_allocations,
)


class SellAllocationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.fills = [{
            "fill_id": "sell-1", "market_id": "BTC/USDT",
            "side": "SELL", "quantity": "0.4",
        }]
        self.reservations = [{
            "reservation_id": "r-1", "account_id": "paper-research",
            "market_id": "BTC/USDT", "version": 3,
            "authorized_quantity": "1.0", "consumed_quantity": "0.2",
        }]
        self.allocations = [{
            "allocation_id": "a-1", "fill_id": "sell-1",
            "reservation_id": "r-1", "reservation_version": 3,
            "allocated_quantity": "0.4",
        }]

    def validate(self, **overrides):
        args = {
            "account_id": "paper-research",
            "fills": self.fills,
            "reservations": self.reservations,
            "allocations": self.allocations,
        }
        args.update(overrides)
        return validate_sell_allocations(**args)

    def test_exact_sell_allocation_returns_canonical_record(self):
        result = self.validate()
        self.assertEqual(result[0]["allocated_quantity"], "0.4")
        self.assertEqual(result[0]["reservation_id"], "r-1")

    def test_partial_fill_can_allocate_only_executed_quantity(self):
        self.fills[0]["quantity"] = "0.25"
        self.allocations[0]["allocated_quantity"] = "0.25"
        self.assertEqual(self.validate()[0]["allocated_quantity"], "0.25")

    def test_multiple_reservations_can_fund_one_sell_fill(self):
        reservations = self.reservations + [{
            "reservation_id": "r-2", "account_id": "paper-research",
            "market_id": "BTC/USDT", "version": 1,
            "authorized_quantity": "0.5", "consumed_quantity": "0",
        }]
        allocations = self.allocations + [{
            "allocation_id": "a-2", "fill_id": "sell-1",
            "reservation_id": "r-2", "reservation_version": 1,
            "allocated_quantity": "0.1",
        }]
        self.assertEqual(len(self.validate(
            reservations=reservations, allocations=allocations
        )), 2)

    def test_sell_fill_without_allocation_is_rejected(self):
        with self.assertRaisesRegex(ReservationAllocationError, "equal each fill"):
            self.validate(allocations=[])

    def test_allocation_must_equal_fill_quantity(self):
        self.allocations[0]["allocated_quantity"] = "0.39"
        with self.assertRaisesRegex(ReservationAllocationError, "equal each fill"):
            self.validate()

    def test_reservation_over_consumption_is_rejected(self):
        self.reservations[0]["consumed_quantity"] = "0.7"
        with self.assertRaisesRegex(ReservationAllocationError, "over-consumption"):
            self.validate()

    def test_cross_account_is_rejected(self):
        self.reservations[0]["account_id"] = "other-account"
        with self.assertRaisesRegex(ReservationAllocationError, "cross-account"):
            self.validate()

    def test_cross_market_is_rejected(self):
        self.reservations[0]["market_id"] = "ETH/USDT"
        with self.assertRaisesRegex(ReservationAllocationError, "cross-market"):
            self.validate()

    def test_stale_reservation_version_is_rejected(self):
        self.allocations[0]["reservation_version"] = 2
        with self.assertRaisesRegex(ReservationAllocationError, "stale"):
            self.validate()

    def test_buy_fill_cannot_have_reservation_allocation(self):
        self.fills[0]["side"] = "BUY"
        with self.assertRaisesRegex(ReservationAllocationError, "BUY fills"):
            self.validate()

    def test_duplicate_allocation_id_is_rejected(self):
        duplicate = dict(self.allocations[0])
        with self.assertRaisesRegex(ReservationAllocationError, "allocation IDs"):
            self.validate(allocations=self.allocations + [duplicate])

    def test_zero_and_negative_allocation_are_rejected(self):
        for value in ("0", "-0.1"):
            self.allocations[0]["allocated_quantity"] = value
            with self.subTest(value=value):
                with self.assertRaisesRegex(ReservationAllocationError, "positive"):
                    self.validate()

    def test_non_finite_decimal_is_rejected(self):
        self.allocations[0]["allocated_quantity"] = "NaN"
        with self.assertRaisesRegex(ReservationAllocationError, "finite"):
            self.validate()

    def test_input_order_does_not_change_canonical_output(self):
        first = self.validate()
        self.allocations[0]["allocation_id"] = "z"
        second = self.validate()
        self.assertEqual(first[0]["allocation_id"], "a-1")
        self.assertEqual(second[0]["allocation_id"], "z")


if __name__ == "__main__":
    unittest.main()
