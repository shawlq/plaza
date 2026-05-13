from __future__ import annotations

import unittest

from webapp.range_utils import parse_byte_range_header


class ParseByteRangeHeaderTests(unittest.TestCase):
    def test_parses_standard_range(self) -> None:
        self.assertEqual(parse_byte_range_header("bytes=2-5", 16), (2, 5))

    def test_parses_open_ended_range(self) -> None:
        self.assertEqual(parse_byte_range_header("bytes=10-", 16), (10, 15))

    def test_parses_suffix_range(self) -> None:
        self.assertEqual(parse_byte_range_header("bytes=-4", 16), (12, 15))

    def test_clamps_oversized_suffix_range(self) -> None:
        self.assertEqual(parse_byte_range_header("bytes=-99", 16), (0, 15))

    def test_rejects_multi_range_requests(self) -> None:
        with self.assertRaisesRegex(ValueError, "Range 请求无效"):
            parse_byte_range_header("bytes=0-1,4-5", 16)

    def test_rejects_out_of_bounds_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "Range 请求超出文件大小"):
            parse_byte_range_header("bytes=16-", 16)


if __name__ == "__main__":
    unittest.main()
