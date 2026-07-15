import unittest

from inventory.store import Store


class TestStore(unittest.TestCase):
    def test_add_and_total(self):
        s = Store()
        s.add_item("widget", 2.5, 4)
        s.add_item("gadget", 10.0, 1)
        self.assertAlmostEqual(s.total_value(), 20.0)

    def test_merge_qty(self):
        s = Store()
        s.add_item("widget", 2.0, 1)
        s.add_item("widget", 2.0, 2)
        self.assertEqual(s.items["widget"]["qty"], 3)

    def test_negative_rejected(self):
        s = Store()
        with self.assertRaises(ValueError):
            s.add_item("bad", -1, 1)


if __name__ == "__main__":
    unittest.main()
