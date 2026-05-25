"""Wave 1403 — branch round-out for :class:`CFFParser`.

Closes two partial arcs:

* ``[366,371]`` — :meth:`read_dict_data` with an ``offset`` but no
  ``dict_size`` (the ``dict_size > 0`` guard is False), so the windowed
  read is skipped and an empty :class:`DictData` is returned.
* ``[848,823]`` — :meth:`parse_cid_font_dicts` where a Font DICT's
  Private DICT has no ``Subrs`` entry (``local_subr_offset`` is the
  default ``0``), so the local-subrs read is skipped and the loop moves
  on to the next FD.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData


def _dict_operand(value: int) -> bytes:
    """Encode a small non-negative int (0..246) as a CFF DICT operand."""
    assert 0 <= value <= 246
    return bytes([value + 139])


def test_read_dict_data_offset_without_size_returns_empty() -> None:
    """``read_dict_data(input, offset=0, dict_size=None)`` skips the
    windowed read (``dict_size > 0`` guard False) and returns an empty
    dict ([366,371] arc)."""
    inp = DataInputByteArray(b"\x8b\x14")  # operand 0, defaultWidthX op
    out = CFFParser.read_dict_data(inp, offset=0, dict_size=None)
    assert isinstance(out, DictData)
    # Nothing was parsed because the windowed branch was skipped.
    assert out.get_entry("defaultWidthX") is None


def test_parse_cid_font_dicts_private_without_subrs_skips_local_subrs() -> None:
    """A CID Font DICT whose Private DICT has no ``Subrs`` operator takes
    the ``local_subr_offset > 0`` False arc ([848,823]); parsing still
    completes and the FD's Private map is recorded."""
    parser = CFFParser()

    # ---- build the input byte buffer --------------------------------
    # Private DICT (empty) lives at a known offset; an empty private DICT
    # is valid — all values fall back to defaults, and crucially there is
    # no Subrs entry so get_number("Subrs", 0) == 0.
    private_dict_bytes = b""  # empty -> no Subrs

    # Font DICT carries a Private operator: operands [size, offset].
    # Operator 18 == "Private".
    buf = bytearray()
    buf.append(0x00)  # offset 0 padding so real offsets are non-zero

    private_offset = len(buf)
    buf += private_dict_bytes  # zero-length, but offset is recorded
    private_size = len(private_dict_bytes)  # == 0

    # Font DICT bytes: Private size, Private offset, then operator 18.
    font_dict_bytes = bytes(
        _dict_operand(private_size) + _dict_operand(private_offset) + b"\x12"
    )

    # FDArray INDEX (count=1, offSize=1): header then one entry.
    fdarray_offset = len(buf)
    index = bytearray()
    index += (1).to_bytes(2, "big")  # count = 1
    index.append(1)  # offSize = 1
    index.append(1)  # offsets[0] = 1
    index.append(1 + len(font_dict_bytes))  # offsets[1]
    index += font_dict_bytes
    buf += index

    # FDSelect format 0 with one glyph -> 1 format byte + 1 fd byte.
    fdselect_offset = len(buf)
    buf.append(0)  # format 0
    buf.append(0)  # glyph 0 -> FD 0

    input_ = DataInputByteArray(bytes(buf))

    # ---- build the Top DICT pointing at those offsets ----------------
    top_dict = DictData()
    fd_array_entry = parser.read_entry(
        DataInputByteArray(_dict_operand(fdarray_offset) + b"\x0c\x24")
    )  # operator 12 36 == FDArray
    fd_select_entry = parser.read_entry(
        DataInputByteArray(_dict_operand(fdselect_offset) + b"\x0c\x25")
    )  # operator 12 37 == FDSelect
    top_dict.add(fd_array_entry)
    top_dict.add(fd_select_entry)

    font = CFFCIDFont()
    parser.parse_cid_font_dicts(input_, top_dict, font, nr_of_char_strings=1)

    # The FD's Private map was recorded; local subrs absent.
    priv = font.get_priv_dicts()
    assert len(priv) == 1
    assert isinstance(priv[0], dict)
    assert priv[0].get("Subrs") is None


def test_parse_cid_font_dicts_records_font_dict_name() -> None:
    """Sanity companion: the FD's FontName resolves via the empty-
    operand path and the font dictionaries list is populated."""
    parser = CFFParser()
    buf = bytearray()
    buf.append(0x00)
    private_offset = len(buf)
    private_size = 0
    font_dict_bytes = bytes(
        _dict_operand(private_size) + _dict_operand(private_offset) + b"\x12"
    )
    fdarray_offset = len(buf)
    index = bytearray()
    index += (1).to_bytes(2, "big")
    index.append(1)
    index.append(1)
    index.append(1 + len(font_dict_bytes))
    index += font_dict_bytes
    buf += index
    fdselect_offset = len(buf)
    buf.append(0)
    buf.append(0)
    input_ = DataInputByteArray(bytes(buf))

    top_dict = DictData()
    top_dict.add(
        parser.read_entry(
            DataInputByteArray(_dict_operand(fdarray_offset) + b"\x0c\x24")
        )
    )
    top_dict.add(
        parser.read_entry(
            DataInputByteArray(_dict_operand(fdselect_offset) + b"\x0c\x25")
        )
    )

    font = CFFCIDFont()
    parser.parse_cid_font_dicts(input_, top_dict, font, nr_of_char_strings=1)
    fonts: list[dict[str, Any]] = font.get_font_dicts()
    assert len(fonts) == 1
