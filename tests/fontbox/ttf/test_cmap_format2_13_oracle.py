"""Differential oracle parity for the rarely-exercised high-byte / DBCS
``cmap`` subtable readers: format 2 (high-byte mapping through table) and
format 13 (many-to-one).

DejaVu / Liberation (the only bundled fonts) carry only format 0/4/6/12
subtables, so the format-2 / format-13 byte arithmetic in
``CmapSubtable.process_subtype2`` / ``process_subtype13`` has never had a
live-oracle pin. These tests hand-build a subtable BODY (the bytes after the
6-byte header that ``init_subtable`` consumes), run pypdfbox's reader, and
compare the resulting ``characterCodeToGlyphId`` map against Apache PDFBox
3.0.7's package-private ``processSubtypeN`` driven through reflection by the
``CmapFormat2Probe`` Java probe over the very same bytes.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream
from tests.oracle.harness import requires_oracle, run_probe_text


def _u16(v: int) -> bytes:
    return struct.pack(">H", v & 0xFFFF)


def _s16(v: int) -> bytes:
    return struct.pack(">h", v)


def _u32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)


def _build_format2_body() -> bytes:
    """A format-2 (high-byte / DBCS) subtable BODY.

    Two sub-headers:

    * sub-header 0 (single-byte range): firstCode=0x20, entryCount=4 — maps
      single-byte codes 0x20..0x23 to glyphs via idDelta.
    * sub-header 1 (DBCS lead byte 0x81): firstCode=0x40, entryCount=3 —
      maps double-byte codes 0x8140..0x8142.

    subHeaderKeys[i] = 8 * subHeaderIndex; lead byte 0x00 -> index 0, lead
    byte 0x81 -> index 1, everything else -> index 0 (the spec's single-byte
    fallthrough). idRangeOffset is stored as the on-wire value the reader
    then re-bases via ``- (maxSubHeaderIndex + 1 - i - 1) * 8 - 2``.
    """
    # --- subHeaderKeys: 256 uint16, value = 8 * subHeaderIndex ---
    keys = [0] * 256
    keys[0x81] = 8  # lead byte 0x81 -> sub-header index 1
    sub_header_keys = b"".join(_u16(k) for k in keys)

    # maxSubHeaderIndex = max(keys[i] // 8) = 1  -> 2 sub-headers.
    # Each sub-header on wire: firstCode, entryCount, idDelta, idRangeOffset.
    # The glyphIndexArray starts right after the 2 sub-headers (2 * 8 bytes).
    # idRangeOffset on wire is measured from the field's own position to the
    # first glyphIndexArray entry for that sub-header.
    #
    # Layout after subHeaderKeys:
    #   subHeader[0] @ +0   (8 bytes)
    #   subHeader[1] @ +8   (8 bytes)
    #   glyphIndexArray @ +16
    #     [0..3] -> sub-header 0's 4 entries
    #     [4..6] -> sub-header 1's 3 entries
    #
    # For sub-header 0, idRangeOffset field sits at +6 within the sub-header
    # block (offset +0..+5 are firstCode/entryCount/idDelta). The on-wire
    # idRangeOffset is (start_of_array - position_of_field).
    #   sub-header 0 idRangeOffset field @ +6;  array entry 0 @ +16 -> 10.
    #   sub-header 1 idRangeOffset field @ +14; array entry 4 @ +24 -> 10.
    sh0 = _u16(0x20) + _u16(4) + _s16(0) + _u16(10)
    sh1 = _u16(0x40) + _u16(3) + _s16(0) + _u16(10)

    # glyphIndexArray: raw glyph indices; reader applies idDelta (here 0) and
    # treats 0 as "missing".
    gia = b"".join(
        _u16(g)
        for g in (
            0x05,  # 0x20 -> 5
            0x00,  # 0x21 -> missing (0 stays 0)
            0x07,  # 0x22 -> 7
            0x08,  # 0x23 -> 8
            0x10,  # 0x8140 -> 16
            0x11,  # 0x8141 -> 17
            0x00,  # 0x8142 -> missing
        )
    )
    return sub_header_keys + sh0 + sh1 + gia


def _build_format13_body() -> bytes:
    """A format-13 (many-to-one) subtable BODY: numGroups + groups."""
    groups = [
        (0x0041, 0x0043, 5),  # A,B,C all -> glyph 5
        (0x1F600, 0x1F602, 9),  # three emoji -> glyph 9
    ]
    body = _u32(len(groups))
    for first, last, gid in groups:
        body += _u32(first) + _u32(last) + _u32(gid)
    return body


def _py_map_format(format_num: int, num_glyphs: int, body: bytes) -> dict[int, int]:
    sub = CmapSubtable()
    data = RandomAccessReadDataStream(body)
    if format_num == 2:
        sub.process_subtype2(data, num_glyphs)
    elif format_num == 13:
        sub.process_subtype13(data, num_glyphs)
    else:  # pragma: no cover - defensive
        raise ValueError(format_num)
    return dict(sub._character_code_to_glyph_id)


def _oracle_map(format_num: int, num_glyphs: int, body: bytes) -> dict[int, int]:
    text = run_probe_text(
        "CmapFormat2Probe", str(format_num), str(num_glyphs), body.hex()
    )
    result: dict[int, int] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == "MAP":
            result[int(parts[1])] = int(parts[2])
    return result


# ----------------------------------------------------------------------
# Pure-Python self-checks (run everywhere, no oracle needed)
# ----------------------------------------------------------------------


def test_format2_python_map():
    body = _build_format2_body()
    m = _py_map_format(2, 64, body)
    # NOTE: the high byte of each charcode is the SUB-HEADER ARRAY INDEX (the
    # loop variable), not the lead byte 0x81 — upstream computes
    # ``(i << 8) + (firstCode + j)``. So sub-header 1's entries land at
    # 0x140.. not 0x8140... A raw glyph index of 0 still gets stored (the
    # reader only skips applying idDelta when p == 0, it does not skip the
    # entry), so 0x21 -> 0 and 0x142 -> 0 are present.
    assert m == {
        0x20: 5,
        0x21: 0,
        0x22: 7,
        0x23: 8,
        0x140: 16,
        0x141: 17,
        0x142: 0,
    }


def test_format2_invalid_glyph_dropped():
    # numGlyphs=8 means glyph ids 16/17 (the DBCS entries) are out of range
    # and must be dropped, leaving only the single-byte entries < 8.
    body = _build_format2_body()
    m = _py_map_format(2, 8, body)
    # 0x23->8, 0x140->16, 0x141->17 are dropped (gid >= 8); the gid-0 entries
    # (0x21, 0x142) survive because 0 < numGlyphs.
    assert m == {0x20: 5, 0x21: 0, 0x22: 7, 0x142: 0}


def test_format13_python_map():
    body = _build_format13_body()
    m = _py_map_format(13, 16, body)
    expected = {0x41: 5, 0x42: 5, 0x43: 5, 0x1F600: 9, 0x1F601: 9, 0x1F602: 9}
    assert m == expected


# ----------------------------------------------------------------------
# Live differential oracle
# ----------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("num_glyphs", [64, 8])
def test_format2_matches_pdfbox(num_glyphs):
    body = _build_format2_body()
    assert _py_map_format(2, num_glyphs, body) == _oracle_map(2, num_glyphs, body)


@requires_oracle
def test_format13_matches_pdfbox():
    body = _build_format13_body()
    assert _py_map_format(13, 16, body) == _oracle_map(13, 16, body)
