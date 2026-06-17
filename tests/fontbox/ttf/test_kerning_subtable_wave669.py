from __future__ import annotations

import struct
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.kerning_subtable import KerningSubtable


class _FakeFTSub:
    def __init__(
        self,
        coverage: int = 0,
        fmt: int = 0,
        pairs: dict[tuple[str, str], int] | None = None,
        apple: bool = False,
    ) -> None:
        self.coverage = coverage
        self.format = fmt
        self.kernTable = pairs if pairs is not None else {}
        self.apple = apple


def _format0_blob(
    pairs: list[tuple[int, int, int]],
    declared_pairs: int | None = None,
) -> bytes:
    n_pairs = len(pairs) if declared_pairs is None else declared_pairs
    body = struct.pack(">HHHH", n_pairs, 0, 0, 0)
    for left, right, value in pairs:
        body += struct.pack(">HHh", left, right, value)
    return struct.pack(">HHH", 0, 6 + len(body), 0x0001) + body


def _format2_blob(
    left_classes: list[int],
    right_classes: list[int],
    values: list[int],
) -> bytes:
    header_size = 6
    fmt2_header_size = 8
    array_offset = header_size + fmt2_header_size
    array = b"".join(struct.pack(">h", value) for value in values)
    left_offset = array_offset + len(array)
    left_table = struct.pack(">HH", 10, len(left_classes))
    left_table += b"".join(struct.pack(">H", value) for value in left_classes)
    right_offset = left_offset + len(left_table)
    right_table = struct.pack(">HH", 20, len(right_classes))
    right_table += b"".join(struct.pack(">H", value) for value in right_classes)
    body = struct.pack(">HHHH", 2, left_offset, right_offset, array_offset)
    body += array + left_table + right_table
    return struct.pack(">HHH", 0, 6 + len(body), 0x0201) + body


def test_apple_fonttools_subtable_keeps_raw_coverage_but_is_unsupported() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x80, fmt=1, apple=True))

    assert sub.get_coverage() == 0x80
    assert sub.get_format() == 1
    assert sub.is_horizontal() is False
    assert sub.is_minimum() is False
    assert sub.is_cross_stream() is False
    assert sub.get_kerning(1, 2) == 0


def test_from_bytes_truncated_apple_header_raises() -> None:
    with pytest.raises(ValueError, match="Apple header"):
        KerningSubtable.from_bytes(b"\x00\x00\x00\x08", version=1)


def test_format0_stops_cleanly_when_declared_pair_count_exceeds_body() -> None:
    sub = KerningSubtable.from_bytes(
        _format0_blob([(1, 2, -25)], declared_pairs=2)
    )

    assert sub.get_kerning(1, 2) == -25
    assert sub.get_kerning(3, 4) == 0
    assert sub.binary_search_pair(1, 2) == -25


def test_format2_truncated_body_raises() -> None:
    blob = struct.pack(">HHH", 0, 10, 0x0201) + b"\x00\x02\x00"

    with pytest.raises(ValueError, match="format-2 body"):
        KerningSubtable.from_bytes(blob)


def test_format2_invalid_and_truncated_class_tables_return_partial_maps() -> None:
    assert KerningSubtable._read_class_table(b"\x00\x01", 0) == {}

    body = struct.pack(">HH", 30, 2) + struct.pack(">H", 12)
    assert KerningSubtable._read_class_table(body, 0) == {30: 12}


def test_format2_out_of_range_class_index_returns_zero() -> None:
    sub = KerningSubtable.from_bytes(
        _format2_blob(left_classes=[1000], right_classes=[1000], values=[7])
    )

    assert sub.get_kerning(10, 20) == 0


def test_fonttools_pairs_without_ttf_and_empty_sequence_return_zeroes() -> None:
    sub = KerningSubtable(_FakeFTSub(coverage=0x01, pairs={("A", "V"): -80}))
    assert sub.get_kerning(1, 2) == 0

    # Upstream getKerning(int[]) returns null (not a zero-filled array) when
    # the subtable carries no pair data ("unsupported subtable" case).
    empty = KerningSubtable()
    assert empty.get_kerning([1, -1, 2]) is None


def test_get_kerning_sequence_accepts_tuple_input() -> None:
    sub = KerningSubtable.from_bytes(_format0_blob([(4, 5, -10)]))

    result: Any = sub.get_kerning((4, 5))
    assert result == [-10, 0]
