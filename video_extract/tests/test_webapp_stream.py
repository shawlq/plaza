import unittest

from webapp.app import _parse_byte_range


class ParseByteRangeTests(unittest.TestCase):
    def test_explicit_range(self) -> None:
        self.assertEqual(_parse_byte_range("bytes=100-199", 1000), (100, 199))

    def test_open_ended_range(self) -> None:
        self.assertEqual(_parse_byte_range("bytes=100-", 1000), (100, 999))

    def test_suffix_range(self) -> None:
        self.assertEqual(_parse_byte_range("bytes=-100", 1000), (900, 999))

    def test_suffix_range_larger_than_file(self) -> None:
        self.assertEqual(_parse_byte_range("bytes=-5000", 1000), (0, 999))


if __name__ == "__main__":
    unittest.main()
