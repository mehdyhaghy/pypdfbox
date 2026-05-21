"""Wave 1368 — CFF charset format 0 / 1 / 2 dispatch + boundary cases.

CFF spec §18 defines three on-disk charset formats:
* **Format 0**: one Card16 SID per glyph (after GID 0).
* **Format 1**: ``(first: Card16, nLeft: Card8)`` ranges.
* **Format 2**: ``(first: Card16, nLeft: Card16)`` ranges.

These tests pin down the dispatcher behaviour and exercise both the
CID-keyed and Type 1-name-keyed paths plus single-glyph and wide-range
edge cases.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.format1_charset import Format1Charset
from pypdfbox.fontbox.cff.format2_charset import Format2Charset


def test_dispatcher_format0_single_glyph_no_extra_sids() -> None:
    # n_glyphs=1 → only GID 0 (.notdef); no SIDs to decode after format byte.
    parser = CFFParser()
    inp = DataInputByteArray(b"\x00")
    cs = parser.read_charset(inp, n_glyphs=1, is_cid_font=False)
    assert cs.get_name_for_gid(0) == ".notdef"
    # No further bytes consumed past the format byte.
    assert inp.get_position() == 1


def test_dispatcher_format1_zero_extra_glyphs_consumes_only_format_byte() -> None:
    # n_glyphs=1 → the while-loop never enters (gid starts at 1 ≥ n_glyphs).
    parser = CFFParser()
    inp = DataInputByteArray(b"\x01")
    cs = parser.read_charset(inp, n_glyphs=1, is_cid_font=False)
    assert cs.get_name_for_gid(0) == ".notdef"
    assert inp.get_position() == 1


def test_dispatcher_format2_zero_extra_glyphs_consumes_only_format_byte() -> None:
    parser = CFFParser()
    inp = DataInputByteArray(b"\x02")
    cs = parser.read_charset(inp, n_glyphs=1, is_cid_font=True)
    assert cs.get_cid_for_gid(0) == 0
    assert inp.get_position() == 1


def test_format1_cid_wide_range_uses_one_byte_nleft() -> None:
    parser = CFFParser()
    # Format 1, CID-keyed: 1 range first=100 (Card16), nLeft=255 (Card8)
    # → 256 glyphs (1..256) covered after the .notdef at GID 0.
    payload = b"\x00\x64\xff"  # first=100, nLeft=255
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=257, is_cid_font=True)
    assert isinstance(cs, Format1Charset)
    # CID at GID 1 should be 100; at GID 256 (last) should be 100+255 = 355.
    assert cs.get_cid_for_gid(1) == 100
    assert cs.get_cid_for_gid(256) == 355


def test_format2_cid_wide_range_uses_two_byte_nleft() -> None:
    parser = CFFParser()
    # Format 2, CID-keyed: 1 range first=1000 (Card16), nLeft=999 (Card16)
    # → 1000 glyphs covered (1..1000) after .notdef.
    payload = b"\x03\xe8\x03\xe7"  # first=1000, nLeft=999
    inp = DataInputByteArray(payload)
    cs = parser.read_format2_charset(inp, n_glyphs=1001, is_cid_font=True)
    assert isinstance(cs, Format2Charset)
    assert cs.get_cid_for_gid(1) == 1000
    assert cs.get_cid_for_gid(1000) == 1999


def test_format0_cid_assigns_sequential_cids() -> None:
    parser = CFFParser()
    # n_glyphs=4 → 3 CIDs after .notdef. CIDs 1, 2, 3.
    inp = DataInputByteArray(b"\x00\x01\x00\x02\x00\x03")
    cs = parser.read_format0_charset(inp, n_glyphs=4, is_cid_font=True)
    assert cs.get_cid_for_gid(0) == 0
    assert cs.get_cid_for_gid(1) == 1
    assert cs.get_cid_for_gid(2) == 2
    assert cs.get_cid_for_gid(3) == 3


def test_format1_type1_two_ranges_resolve_names_via_standard_strings() -> None:
    parser = CFFParser()
    # Format 1, Type 1: two ranges that together cover gids 1..3.
    # range A: first=1 (SID "space"), nLeft=0 → just gid 1 → "space"
    # range B: first=2 (SID "exclam"), nLeft=1 → gids 2 ("exclam"), 3 ("quotedbl")
    payload = b"\x00\x01\x00\x00\x02\x01"
    inp = DataInputByteArray(payload)
    cs = parser.read_format1_charset(inp, n_glyphs=4, is_cid_font=False)
    assert cs.get_name_for_gid(0) == ".notdef"
    assert cs.get_name_for_gid(1) == "space"
    assert cs.get_name_for_gid(2) == "exclam"
    assert cs.get_name_for_gid(3) == "quotedbl"


def test_format2_type1_zero_nleft_is_one_glyph_per_range() -> None:
    parser = CFFParser()
    # Format 2 with nLeft=0 means one glyph per range (the spec: range
    # spans nLeft+1 glyphs). Two single-glyph ranges → gids 1 & 2.
    payload = b"\x00\x01\x00\x00\x00\x02\x00\x00"
    inp = DataInputByteArray(payload)
    cs = parser.read_format2_charset(inp, n_glyphs=3, is_cid_font=False)
    assert cs.get_name_for_gid(1) == "space"
    assert cs.get_name_for_gid(2) == "exclam"


def test_read_charset_format_three_is_rejected() -> None:
    parser = CFFParser()
    inp = DataInputByteArray(b"\x03")
    with pytest.raises(OSError, match="Incorrect charset format 3"):
        parser.read_charset(inp, n_glyphs=1, is_cid_font=False)


def test_read_charset_format_two_hundred_fifty_five_is_rejected() -> None:
    parser = CFFParser()
    inp = DataInputByteArray(b"\xff")
    with pytest.raises(OSError, match="Incorrect charset format 255"):
        parser.read_charset(inp, n_glyphs=1, is_cid_font=False)
