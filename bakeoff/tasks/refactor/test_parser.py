import unittest

from pipeline.parser import parse_rules


class TestParser(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_rules("a: double"), [("a", "double", [])])

    def test_args(self):
        self.assertEqual(parse_rules("k: min[10]"), [("k", "min", ["10"])])

    def test_multi_args(self):
        self.assertEqual(parse_rules("k: clamp[1,9]"), [("k", "clamp", ["1", "9"])])

    def test_nested_brackets(self):
        self.assertEqual(parse_rules("c: compose[a[1,2],b]"),
                         [("c", "compose", ["a[1,2]", "b"])])

    def test_comments_and_blanks(self):
        text = "# comment\n\na: double\n"
        self.assertEqual(parse_rules(text), [("a", "double", [])])


if __name__ == "__main__":
    unittest.main()
