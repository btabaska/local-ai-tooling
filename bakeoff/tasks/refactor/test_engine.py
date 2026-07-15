import unittest

from pipeline.engine import apply_rules


class TestEngine(unittest.TestCase):
    def test_ops(self):
        out, log = apply_rules([1, 2, 3], [("d", "double", []), ("m", "min", ["4"])])
        self.assertEqual(out, [4, 6])
        self.assertEqual(log, ["d", "m"])

    def test_log_isolated_between_calls(self):
        apply_rules([1], [("a", "double", [])])
        out, log = apply_rules([1], [("b", "add", ["1"])])
        self.assertEqual(log, ["b"])

    def test_unknown_op(self):
        with self.assertRaises(ValueError):
            apply_rules([1], [("x", "nope", [])])


if __name__ == "__main__":
    unittest.main()
