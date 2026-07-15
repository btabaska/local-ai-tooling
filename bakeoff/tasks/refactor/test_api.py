import unittest

from pipeline.api import run


class TestApi(unittest.TestCase):
    def test_run_end_to_end(self):
        text = "d: double\nkeep: min[4]"
        self.assertEqual(run([1, 2, 3], text),
                         "2 rules applied; 2 values kept; total=10")

    def test_run_empty_rules(self):
        self.assertEqual(run([5], "# nothing"),
                         "0 rules applied; 1 values kept; total=5")


if __name__ == "__main__":
    unittest.main()
