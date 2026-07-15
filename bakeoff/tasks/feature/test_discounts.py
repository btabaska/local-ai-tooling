import unittest

from inventory.discounts import percent_off, bulk_discount, best_discount
from inventory.store import Store


class TestDiscounts(unittest.TestCase):
    def test_percent_off(self):
        d = percent_off(10)
        self.assertAlmostEqual(d(100.0), 90.0)

    def test_percent_off_bounds(self):
        with self.assertRaises(ValueError):
            percent_off(101)
        with self.assertRaises(ValueError):
            percent_off(-1)

    def test_bulk_discount_applies_over_threshold(self):
        # 5% off totals of 50.0 or more, otherwise unchanged
        d = bulk_discount(threshold=50.0, percent=5)
        self.assertAlmostEqual(d(60.0), 57.0)
        self.assertAlmostEqual(d(49.99), 49.99)

    def test_best_discount_picks_cheapest_result(self):
        d = best_discount([percent_off(10), bulk_discount(threshold=50.0, percent=25)])
        # for 100.0: 10% -> 90.0, bulk 25% -> 75.0; best is 75.0
        self.assertAlmostEqual(d(100.0), 75.0)

    def test_best_discount_empty_is_identity(self):
        d = best_discount([])
        self.assertAlmostEqual(d(42.0), 42.0)


class TestCheckout(unittest.TestCase):
    def test_checkout_total_applies_best_discount(self):
        s = Store()
        s.add_item("widget", 25.0, 4)  # total 100.0
        total = s.checkout_total(discounts=[percent_off(10), percent_off(20)])
        self.assertAlmostEqual(total, 80.0)

    def test_checkout_total_no_discounts(self):
        s = Store()
        s.add_item("widget", 5.0, 2)
        self.assertAlmostEqual(s.checkout_total(discounts=[]), 10.0)


if __name__ == "__main__":
    unittest.main()
