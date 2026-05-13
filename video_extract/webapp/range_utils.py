"""Helpers for parsing HTTP Range headers for local video streaming."""

from __future__ import annotations


def parse_byte_range_header(range_header: str, file_size: int) -> tuple[int, int]:
    """Parse a single ``Range: bytes=...`` request into inclusive offsets.

    Supports standard byte ranges (``bytes=start-end``), open-ended ranges
    (``bytes=start-``), and suffix ranges (``bytes=-length``). Multi-range
    requests are rejected because the current streaming endpoint serves a
    single contiguous segment at a time.
    """

    if file_size <= 0:
        raise ValueError("Range 请求超出文件大小")

    try:
        unit, value = range_header.split("=", 1)
    except ValueError as exc:
        raise ValueError("Range 请求无效") from exc

    if unit.strip().lower() != "bytes":
        raise ValueError("Range 请求无效")

    value = value.strip()
    if not value or "," in value:
        raise ValueError("Range 请求无效")

    try:
        start_text, end_text = value.split("-", 1)
    except ValueError as exc:
        raise ValueError("Range 请求无效") from exc

    start_text = start_text.strip()
    end_text = end_text.strip()

    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        else:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            if suffix_length >= file_size:
                return 0, file_size - 1
            start = file_size - suffix_length
            end = file_size - 1
    except ValueError as exc:
        raise ValueError("Range 请求无效") from exc

    if start < 0 or end < start or start >= file_size:
        raise ValueError("Range 请求超出文件大小")

    return start, min(end, file_size - 1)
