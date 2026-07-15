import unittest

from stats import mean, median, variance, top_k


class TestStats(unittest.TestCase):
    def test_mean(self):
        self.assertAlmostEqual(mean([1, 2, 3, 4]), 2.5)

    def test_median_odd(self):
        self.assertEqual(median([5, 1, 3]), 3)

    def test_median_even(self):
        self.assertAlmostEqual(median([4, 1, 3, 2]), 2.5)

    def test_median_even_unsorted(self):
        self.assertAlmostEqual(median([10, 2, 8, 4]), 6.0)

    def test_variance_sample(self):
        # sample variance of [2, 4, 4, 4, 5, 5, 7, 9] is 32/7
        self.assertAlmostEqual(variance([2, 4, 4, 4, 5, 5, 7, 9]), 32 / 7)

    def test_variance_two(self):
        self.assertAlmostEqual(variance([1, 3]), 2.0)

    def test_top_k(self):
        self.assertEqual(top_k([1, 9, 5, 3, 7], 2), [9, 7])

    def test_top_k_all(self):
        self.assertEqual(top_k([2, 1], 5), [2, 1])


if __name__ == "__main__":
    unittest.main()
