import unittest

from busbook.render import unite


class TestUnite(unittest.TestCase):

    def test_identical(self):
        self.assertEqual(unite([1, 2, 3, 4], [1, 2, 3, 4]),
                         [1, 2, 3, 4])

    def test_missing(self):
        self.assertEqual(unite([1, 2, 4], [1, 2, 3, 4]),
                         [1, 2, 3, 4])

    def test_middle(self):
        res = unite([1, 2, 4], [1, 3, 4])
        self.assertTrue(res == [1, 2, 3, 4] or res == [1, 3, 2, 4])

    def test_start(self):
        res = unite([1, 3], [2, 3])
        self.assertTrue(res == [1, 2, 3] or res == [2, 1, 3])

    def test_end(self):
        res = unite([1, 2], [1, 3])
        self.assertTrue(res == [1, 2, 3] or res == [1, 3, 2])

    def test_cycle(self):
        self.assertEqual(unite([1, 2, 1], [1, 2]),
                         [1, 2, 1])

    def test_long_cycle(self):
        self.assertEqual(unite([1, 2, 3, 2, 1, 2, 3], [2, 2, 2, 3]),
                         [1, 2, 3, 2, 1, 2, 3])


if __name__ == '__main__':
    unittest.main()
