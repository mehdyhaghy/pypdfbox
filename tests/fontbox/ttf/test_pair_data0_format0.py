"""Tests for :class:`PairData0Format0` and the :class:`PairData` ABC."""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.pair_data import PairData
from pypdfbox.fontbox.ttf.pair_data0_format0 import PairData0Format0
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream, TTFDataStream


def _stream(data: bytes) -> TTFDataStream:
    """Wrap raw bytes into a :class:`TTFDataStream` so we can call ``read``
    on a :class:`PairData0Format0`."""
    return MemoryTTFDataStream(data)


def _format0_body(pairs: list[tuple[int, int, int]]) -> bytes:
    """Build a kern format-0 body — header (8 bytes) plus
    ``len(pairs) * 6`` entry bytes."""
    n = len(pairs)
    # searchRange / entrySelector / rangeShift are tied to the
    # binary-search header; values don't matter for our reader.
    buf = struct.pack(">HHHH", n, 0, 0, 0)
    for left, right, value in pairs:
        buf += struct.pack(">HHh", left, right, value)
    return buf


def test_pair_data_is_abstract() -> None:
    with pytest.raises(TypeError):
        PairData()  # type: ignore[abstract]


def test_format0_subclasses_pair_data() -> None:
    assert issubclass(PairData0Format0, PairData)


def test_empty_pair_list_returns_zero() -> None:
    pd = PairData0Format0()
    pd.read(_stream(_format0_body([])))
    assert pd.get_kerning(1, 2) == 0


def test_simple_pair_lookup() -> None:
    pd = PairData0Format0()
    pd.read(_stream(_format0_body([(1, 2, -50), (3, 4, 100), (5, 6, 25)])))
    assert pd.get_kerning(1, 2) == -50
    assert pd.get_kerning(3, 4) == 100
    assert pd.get_kerning(5, 6) == 25


def test_missing_pair_returns_zero() -> None:
    pd = PairData0Format0()
    pd.read(_stream(_format0_body([(1, 2, -50), (3, 4, 100)])))
    assert pd.get_kerning(7, 8) == 0
    assert pd.get_kerning(1, 3) == 0  # left matches, right doesn't


def test_signed_value_range() -> None:
    pd = PairData0Format0()
    pd.read(_stream(_format0_body([(10, 20, -32768), (10, 21, 32767)])))
    assert pd.get_kerning(10, 20) == -32768
    assert pd.get_kerning(10, 21) == 32767


def test_compare_matches_java_comparator() -> None:
    # PairData0Format0.compare must order ascending by (first, second).
    assert PairData0Format0.compare((1, 2, 0), (1, 3, 0)) < 0
    assert PairData0Format0.compare((1, 3, 0), (1, 2, 0)) > 0
    assert PairData0Format0.compare((2, 0, 0), (1, 99, 0)) > 0
    assert PairData0Format0.compare((1, 2, 0), (1, 2, 99)) == 0  # value column ignored


def test_binary_search_finds_middle_entry() -> None:
    # 1000 pairs — exercises the bisect path.
    pairs = [(i, i, i - 500) for i in range(1000)]
    pd = PairData0Format0()
    pd.read(_stream(_format0_body(pairs)))
    assert pd.get_kerning(500, 500) == 0
    assert pd.get_kerning(0, 0) == -500
    assert pd.get_kerning(999, 999) == 499
