"""Wave 1368 — FDSelect format 0 / 3 dispatch + range-walk edge cases.

CFF spec §19 FDSelect for CID-keyed fonts:

* **Format 0**: one Card8 FD index per glyph.
* **Format 3**: ``nRanges`` (Card16) ``(first: Card16, fd: Card8)``
  ranges followed by a Card16 sentinel (the GID one past the last
  covered glyph).

Exercises the dispatcher, format-3 range walk including out-of-range
GIDs, sentinel-only walks, and the boundary cases the upstream tests
don't isolate.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.fd_select import (
    FDSelect,
    Format0FDSelect,
    Format3FDSelect,
)


def test_dispatcher_format0_returns_format0_fdselect() -> None:
    # Format byte 0, then 4 Card8 FD indices for 4 glyphs.
    inp = DataInputByteArray(b"\x00\x00\x01\x02\x03")
    fds = CFFParser.read_fd_select(inp, n_glyphs=4)
    assert isinstance(fds, Format0FDSelect)
    assert fds.get_format() == 0
    assert fds.get_fds() == [0, 1, 2, 3]
    assert fds.get_num_glyphs() == 4


def test_dispatcher_format3_returns_format3_fdselect() -> None:
    # Format byte 3, nRanges=1, (first=0, fd=2), sentinel=5
    inp = DataInputByteArray(b"\x03\x00\x01\x00\x00\x02\x00\x05")
    fds = CFFParser.read_fd_select(inp, n_glyphs=5)
    assert isinstance(fds, Format3FDSelect)
    assert fds.get_format() == 3
    assert fds.get_sentinel() == 5
    assert fds.get_num_ranges() == 1
    assert fds.get_ranges() == [(0, 2)]


def test_dispatcher_format2_is_rejected() -> None:
    # CFF spec defines only Format 0 and Format 3 for FDSelect; any
    # other value (e.g. 2) must raise.
    inp = DataInputByteArray(b"\x02")
    with pytest.raises(ValueError):
        CFFParser.read_fd_select(inp, n_glyphs=1)


def test_dispatcher_format255_is_rejected() -> None:
    inp = DataInputByteArray(b"\xff")
    with pytest.raises(ValueError):
        CFFParser.read_fd_select(inp, n_glyphs=1)


def test_format0_fdselect_zero_glyphs_yields_empty_array() -> None:
    # n_glyphs=0 → no bytes consumed past the format byte.
    inp = DataInputByteArray(b"\x00")
    fds = CFFParser.read_format0_fd_select(inp, n_glyphs=0)
    assert isinstance(fds, Format0FDSelect)
    assert fds.get_fds() == []
    assert fds.get_num_glyphs() == 0


def test_format3_fdselect_zero_ranges_with_sentinel() -> None:
    # nRanges=0, sentinel=42. Empty but valid.
    inp = DataInputByteArray(b"\x00\x00\x00\x2a")
    fds = CFFParser.read_format3_fd_select(inp)
    assert isinstance(fds, Format3FDSelect)
    assert fds.get_num_ranges() == 0
    assert fds.get_sentinel() == 42


def test_format3_fdselect_two_adjacent_ranges_resolve_each_gid() -> None:
    # nRanges=2: range A (first=0, fd=1) covers gid 0..4
    # range B (first=5, fd=2) covers gid 5..9, sentinel=10
    inp = DataInputByteArray(
        b"\x00\x02"  # nRanges
        b"\x00\x00\x01"  # range A
        b"\x00\x05\x02"  # range B
        b"\x00\x0a"  # sentinel
    )
    fds = CFFParser.read_format3_fd_select(inp)
    assert fds.get_fd_index(0) == 1
    assert fds.get_fd_index(4) == 1
    assert fds.get_fd_index(5) == 2
    assert fds.get_fd_index(9) == 2


def test_format3_fdselect_out_of_range_gid_returns_minus_one() -> None:
    # Single range first=0..fd=1, sentinel=3 (covers gids 0,1,2).
    # gid==3 (== sentinel) is *past* the last covered glyph → -1 per
    # the range-walk impl mirroring upstream.
    fds = Format3FDSelect(ranges=[(0, 1)], sentinel=3)
    assert fds.get_fd_index(0) == 1
    assert fds.get_fd_index(2) == 1
    assert fds.get_fd_index(3) == -1


def test_format3_fdselect_negative_gid_returns_zero() -> None:
    fds = Format3FDSelect(ranges=[(0, 7)], sentinel=10)
    assert fds.get_fd_index(-1) == 0
    assert fds.get_fd_index(-100) == 0


def test_format3_fdselect_empty_ranges_returns_zero() -> None:
    # No ranges at all — get_fd_index must short-circuit to 0.
    fds = Format3FDSelect(ranges=[], sentinel=0)
    assert fds.get_fd_index(0) == 0
    assert fds.get_num_glyphs() == 0


def test_fdselect_base_handles_none_inner_safely() -> None:
    # Constructing FDSelect() with no fontTools inner object must not
    # blow up — get_fd_index falls back to 0 and bool() conversion of
    # an int gid must not be interpreted as a boolean.
    fds = FDSelect(None)
    assert fds.get_fd_index(0) == 0
    assert fds.get_num_glyphs() == 0
    assert fds.get_format() == 0


def test_format0_fdselect_get_fd_index_out_of_range_returns_zero() -> None:
    fds = Format0FDSelect([1, 2, 3])
    assert fds.get_fd_index(-1) == 0
    assert fds.get_fd_index(3) == 0  # past end
    assert fds.get_fd_index(100) == 0
    # In-range values still work.
    assert fds.get_fd_index(0) == 1
    assert fds.get_fd_index(2) == 3


def test_format3_fdselect_to_string_lists_ranges_and_sentinel() -> None:
    fds = Format3FDSelect(ranges=[(0, 0), (5, 1)], sentinel=10)
    s = fds.to_string()
    # The Range3 inner repr must list each (first, fd) pair.
    assert "first=0" in s
    assert "fd=0" in s
    assert "first=5" in s
    assert "fd=1" in s
    assert "sentinel=10" in s


def test_dispatcher_format3_with_two_ranges_consumes_all_bytes() -> None:
    # 2 ranges + sentinel: 1 (format) + 2 (nRanges) + 2 * 3 (ranges) + 2 (sentinel) = 11
    payload = (
        b"\x03"
        b"\x00\x02"
        b"\x00\x00\x01"
        b"\x00\x07\x02"
        b"\x00\x0a"
    )
    inp = DataInputByteArray(payload)
    fds = CFFParser.read_fd_select(inp, n_glyphs=10)
    assert isinstance(fds, Format3FDSelect)
    # Cursor must be exactly at the end of the payload.
    assert inp.get_position() == len(payload)
