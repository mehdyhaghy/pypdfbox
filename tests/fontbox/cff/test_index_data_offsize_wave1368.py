"""Wave 1368 — CFF INDEX parsing across offSize 1/2/3/4 + edge counts.

CFF spec §5 INDEX layout:

* ``count`` (Card16) — number of objects in the INDEX.
* ``offSize`` (Card8, 1..4) — byte width of each entry in the offset
  array (only present if ``count > 0``).
* ``offset[count + 1]`` — each ``offSize`` bytes, big-endian.
* ``data`` — the per-object byte payload.

Exercises ``read_index_data`` and ``read_index_data_offsets`` past the
happy paths covered by ``test_cff_parser_coverage.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray


def test_read_index_data_count_zero_returns_empty_list() -> None:
    # count == 0 → no offSize / offsets / data follow.
    inp = DataInputByteArray(b"\x00\x00")
    assert CFFParser.read_index_data(inp) == []
    # Cursor lands right after the 2-byte count.
    assert inp.get_position() == 2


def test_read_index_data_offsets_count_zero_returns_empty_list() -> None:
    inp = DataInputByteArray(b"\x00\x00")
    assert CFFParser.read_index_data_offsets(inp) == []


def test_read_index_data_single_entry_off_size_1() -> None:
    # count=1, offSize=1, offsets=[1, 4] (3 data bytes), data=b"abc"
    inp = DataInputByteArray(b"\x00\x01\x01\x01\x04abc")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"abc"]


def test_read_index_data_single_entry_off_size_2() -> None:
    # count=1, offSize=2, offsets=[0x0001, 0x0005], data=b"data"
    inp = DataInputByteArray(b"\x00\x01\x02\x00\x01\x00\x05data")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"data"]


def test_read_index_data_single_entry_off_size_3() -> None:
    # count=1, offSize=3, offsets=[0x000001, 0x000003], data=b"ab"
    inp = DataInputByteArray(b"\x00\x01\x03\x00\x00\x01\x00\x00\x03ab")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"ab"]


def test_read_index_data_single_entry_off_size_4() -> None:
    # count=1, offSize=4, offsets=[0x00000001, 0x00000005], data=b"java"
    inp = DataInputByteArray(
        b"\x00\x01\x04\x00\x00\x00\x01\x00\x00\x00\x05java"
    )
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"java"]


def test_read_index_data_three_entries_off_size_1() -> None:
    # count=3, offSize=1, offsets=[1,2,4,7], data="a"+"bc"+"def"
    inp = DataInputByteArray(b"\x00\x03\x01\x01\x02\x04\x07abcdef")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"a", b"bc", b"def"]


def test_read_index_data_offsets_rejects_offset_past_buffer_length() -> None:
    # count=1, offSize=1, offsets=[1, 200] but buffer length is only 6.
    inp = DataInputByteArray(b"\x00\x01\x01\x01\xc8\xaa")
    with pytest.raises(OSError, match="illegal offset value"):
        CFFParser.read_index_data_offsets(inp)


def test_read_index_data_empty_data_entries_when_offsets_are_equal() -> None:
    # count=2, offSize=1, offsets=[1,1,1] → both entries are zero-length.
    inp = DataInputByteArray(b"\x00\x02\x01\x01\x01\x01")
    entries = CFFParser.read_index_data(inp)
    assert entries == [b"", b""]


def test_read_string_index_data_decodes_each_entry_as_iso_8859_1() -> None:
    # count=2, offSize=1, offsets=[1, 4, 8], data=b"abc\xe9foo" but
    # second entry is 4 bytes "\xe9foo" (\xe9 = "é" in ISO-8859-1).
    # Total data bytes: 7 → offsets must be [1, 4, 8].
    inp = DataInputByteArray(b"\x00\x02\x01\x01\x04\x08" + b"abc\xe9foo")
    values = CFFParser.read_string_index_data(inp)
    assert values == ["abc", "\xe9foo"]


def test_read_string_index_data_count_zero_returns_empty_list() -> None:
    inp = DataInputByteArray(b"\x00\x00")
    assert CFFParser.read_string_index_data(inp) == []


def test_read_string_index_data_rejects_decreasing_offsets() -> None:
    # count=1, offSize=1, offsets=[5, 4] → length = -1 → must raise.
    inp = DataInputByteArray(b"\x00\x01\x01\x05\x04xx")
    with pytest.raises(OSError, match="Negative index data length"):
        CFFParser.read_string_index_data(inp)


def test_read_off_size_rejects_zero() -> None:
    inp = DataInputByteArray(b"\x00")
    with pytest.raises(OSError, match="Illegal .* offSize value 0"):
        CFFParser.read_off_size(inp)


def test_read_off_size_rejects_five() -> None:
    inp = DataInputByteArray(b"\x05")
    with pytest.raises(OSError, match="Illegal .* offSize value 5"):
        CFFParser.read_off_size(inp)


def test_read_off_size_accepts_all_four_widths() -> None:
    inp = DataInputByteArray(b"\x01\x02\x03\x04")
    assert CFFParser.read_off_size(inp) == 1
    assert CFFParser.read_off_size(inp) == 2
    assert CFFParser.read_off_size(inp) == 3
    assert CFFParser.read_off_size(inp) == 4
