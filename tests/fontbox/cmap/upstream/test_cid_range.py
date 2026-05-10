"""Ported from upstream PDFBox 3.0.x ``CIDRangeTest.java``.

Source: ``fontbox/src/test/java/org/apache/fontbox/cmap/CIDRangeTest.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap import CIDRange


def test_cid_range_one_byte() -> None:
    cid_range = CIDRange(0, 20, 65, 1)
    assert cid_range.get_code_length() == 1

    assert cid_range.map_bytes(bytes([0])) == 65
    assert cid_range.map_bytes(bytes([10])) == 75
    # out of range
    assert cid_range.map_bytes(bytes([30])) == -1
    # wrong code length
    assert cid_range.map_bytes(bytes([0, 10])) == -1

    assert cid_range.map_int(0, 1) == 65
    assert cid_range.map_int(10, 1) == 75
    # out of range
    assert cid_range.map_int(30, 1) == -1
    # wrong code length
    assert cid_range.map_int(10, 2) == -1

    assert cid_range.unmap(65) == 0
    assert cid_range.unmap(75) == 10
    # out of range
    assert cid_range.unmap(100) == -1


def test_cid_range_two_byte() -> None:
    cid_range = CIDRange(256, 280, 65, 2)
    assert cid_range.get_code_length() == 2

    assert cid_range.map_bytes(bytes([1, 0])) == 65
    assert cid_range.map_bytes(bytes([1, 10])) == 75
    # out of range
    assert cid_range.map_bytes(bytes([1, 30])) == -1
    # wrong code length
    assert cid_range.map_bytes(bytes([10])) == -1

    assert cid_range.map_int(256, 2) == 65
    assert cid_range.map_int(266, 2) == 75
    # out of range
    assert cid_range.map_int(290, 2) == -1
    # wrong code length
    assert cid_range.map_int(256, 1) == -1

    assert cid_range.unmap(65) == 256
    assert cid_range.unmap(75) == 266
    # out of range
    assert cid_range.unmap(100) == -1


def test_cid_range_one_byte_via_map_overload() -> None:
    """``map`` overload dispatcher mirrors the upstream Java overloads
    ``map(byte[])`` and ``map(int, int)`` — same expectations as
    :func:`test_cid_range_one_byte` but via the dispatching entry point."""
    cid_range = CIDRange(0, 20, 65, 1)

    # map(byte[])
    assert cid_range.map(bytes([0])) == 65
    assert cid_range.map(bytes([10])) == 75
    assert cid_range.map(bytes([30])) == -1
    assert cid_range.map(bytes([0, 10])) == -1

    # map(int, int)
    assert cid_range.map(0, 1) == 65
    assert cid_range.map(10, 1) == 75
    assert cid_range.map(30, 1) == -1
    assert cid_range.map(10, 2) == -1


def test_cid_range_two_byte_via_map_overload() -> None:
    cid_range = CIDRange(256, 280, 65, 2)

    assert cid_range.map(bytes([1, 0])) == 65
    assert cid_range.map(bytes([1, 10])) == 75
    assert cid_range.map(bytes([1, 30])) == -1
    assert cid_range.map(bytes([10])) == -1

    assert cid_range.map(256, 2) == 65
    assert cid_range.map(266, 2) == 75
    assert cid_range.map(290, 2) == -1
    assert cid_range.map(256, 1) == -1
