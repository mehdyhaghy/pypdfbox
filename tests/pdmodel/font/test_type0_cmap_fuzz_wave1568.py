"""Wave 1568 — Type0 / CID font CMap encode/decode fuzz + parity.

Hammers the composite-font code path that turns raw content-stream bytes
into CIDs and GIDs and back:

* multi-byte ``read_code`` driven by codespace ranges (1-byte, 2-byte and
  mixed-width codespaces — the variable-length next-code scan of
  ISO 32000-1 §9.7.6.2);
* code -> CID via ``cidrange`` / ``cidchar`` mappings;
* CID -> GID with ``/CIDToGIDMap`` = ``/Identity`` vs an explicit stream
  map (including out-of-range indexing);
* the predefined ``Identity-H`` / ``Identity-V`` CMaps and real CJK
  predefined CMaps (mixed-width codespaces);
* missing-glyph / out-of-range codes -> CID 0;
* width lookup over both ``/W`` array forms (``c [w1 w2 ...]`` and
  ``cFirst cLast w``) plus ``/DW`` default fallback, and the parallel
  ``/W2`` vertical forms.

Each assertion is the value upstream Apache PDFBox 3.0.7 produces for the
same input (``CMap.readCode`` / ``CMap.toCID``, ``PDCIDFontType2.codeToGID``,
``PDCIDFont.readWidths`` / ``readVerticalDisplacements``).
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.cmap import CMapParser
from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

# ---------- helpers ----------


def _ints(*values: int) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSInteger.get(v))
    return arr


def _w_form1(first: int, widths: list[int]) -> COSArray:
    """Build a ``/W`` array in the ``c [w1 w2 ...]`` form."""
    arr = COSArray()
    arr.add(COSInteger.get(first))
    inner = COSArray()
    for w in widths:
        inner.add(COSInteger.get(w))
    arr.add(inner)
    return arr


def _w_form2(c1: int, c2: int, w: int) -> COSArray:
    """Build a ``/W`` array in the ``cFirst cLast w`` form."""
    return _ints(c1, c2, w)


def _cid_to_gid_stream(gids: list[int]) -> COSStream:
    data = b"".join((g & 0xFFFF).to_bytes(2, "big") for g in gids)
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(data)
    return stream


def _type2(items: dict[str, COSBase]) -> PDCIDFontType2:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Subtype"), "CIDFontType2")
    for key, value in items.items():
        d.set_item(COSName.get_pdf_name(key), value)
    return PDCIDFontType2(d)


def _identity_h_cmap() -> CMap:
    c = CMap("Identity-H-built")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    c.add_cid_range(b"\x00\x00", b"\xff\xff", 0)
    return c


# ---------- codespace-driven read_code: byte-length determination ----------


@pytest.mark.parametrize(
    ("ranges", "data", "expected"),
    [
        # single 1-byte codespace
        ([(b"\x00", b"\xff")], b"\x41\x42", (0x41, 1)),
        # single 2-byte codespace
        ([(b"\x00\x00", b"\xff\xff")], b"\x12\x34", (0x1234, 2)),
        # mixed-width: ascii 1-byte, CJK lead 2-byte — ascii reads 1 byte
        (
            [(b"\x00", b"\x80"), (b"\x81\x40", b"\x9f\xfc")],
            b"\x41\x81\x50",
            (0x41, 1),
        ),
        # mixed-width: a 2-byte code consumes 2 bytes
        (
            [(b"\x00", b"\x80"), (b"\x81\x40", b"\x9f\xfc")],
            b"\x81\x50\x00",
            (0x8150, 2),
        ),
        # overlapping 1-byte + 2-byte: shortest match wins (min_len first)
        (
            [(b"\x00", b"\xff"), (b"\x00\x00", b"\xff\xff")],
            b"\x41\x42",
            (0x41, 1),
        ),
    ],
    ids=["1byte", "2byte", "mixed-ascii", "mixed-cjk", "overlap-shortest"],
)
def test_read_code_bytes_form_width(ranges, data, expected):
    c = CMap("t")
    for lo, hi in ranges:
        c.add_codespace_range(lo, hi)
    assert c.read_code(data, 0) == expected


def test_read_code_stream_zero_pads_truncated_tail():
    # Stream form mirrors upstream readCode: a tail shorter than min_len is
    # zero-extended (a lone 0x41 under a 2-byte codespace reads as 0x4100).
    c = CMap("t")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    assert c.read_code(io.BytesIO(b"\x41")) == 0x4100


def test_read_code_bytes_form_truncated_tail_stops():
    # Bytes form (pypdfbox enrichment) returns what it has so the caller can
    # advance to EOF rather than fabricating padding.
    c = CMap("t")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    assert c.read_code(b"\x41", 0) == (0x41, 1)


def test_read_code_stream_rewinds_on_codespace_miss():
    # A byte that neither completes a 1-byte code nor starts a valid 2-byte
    # code: upstream marks after min_len, speculatively reads the extension
    # byte, then resets so the next code starts right after min_len.
    c = CMap("t2")
    c.add_codespace_range(b"\x00", b"\x7f")
    c.add_codespace_range(b"\x81\x40", b"\x9f\xfc")
    stream = io.BytesIO(b"\x80\x41\x42")
    assert c.read_code(stream) == 0x80
    assert stream.tell() == 1  # extension byte was pushed back
    assert c.read_code(stream) == 0x41
    assert stream.tell() == 2


def test_read_code_no_codespace_is_single_byte():
    c = CMap("empty")
    assert c.read_code(b"\x05\x06", 0) == (0x05, 1)
    assert c.read_code(io.BytesIO(b"\x05\x06")) == 0x05


def test_read_code_offset_only_for_bytes_form():
    c = _identity_h_cmap()
    with pytest.raises(TypeError):
        c.read_code(io.BytesIO(b"\x00\x41"), 1)


# ---------- code -> CID via cidrange / cidchar ----------


def test_to_cid_cidrange_identity():
    c = _identity_h_cmap()
    assert c.to_cid(0x0041) == 0x41
    assert c.to_cid(0xFFFF) == 0xFFFF
    assert c.to_cid(0x0000) == 0


def test_to_cid_cidchar_direct_mapping():
    c = CMap("custom")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    c.add_cid_mapping(b"\x00\x41", 100)
    c.add_cid_mapping(b"\x00\x42", 200)
    assert c.to_cid(0x41) == 100
    assert c.to_cid(0x42) == 200
    # unmapped code -> 0 (.notdef), not the raw code
    assert c.to_cid(0x43) == 0


def test_to_cid_range_offset_arithmetic():
    c = CMap("custom")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    # codes 0x100..0x10F map to CID 50.. (offset preserved)
    c.add_cid_range(b"\x01\x00", b"\x01\x0f", 50)
    assert c.to_cid(0x0100) == 50
    assert c.to_cid(0x0105) == 55
    assert c.to_cid(0x010F) == 65
    assert c.to_cid(0x0110) == 0  # just past the range


def test_to_cid_empty_cmap_returns_zero():
    c = CMap("empty")
    assert c.to_cid(0x41) == 0
    assert c.to_cid(0xFFFF) == 0
    assert not c.has_cid_mappings()


@pytest.mark.parametrize("code", [0x0000, 0x10000, 0x1FFFF, 0xFFFFFF])
def test_to_cid_out_of_range_codes(code):
    # Codes outside the cidrange resolve to CID 0.
    c = CMap("custom")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    c.add_cid_range(b"\x00\x01", b"\x00\x10", 1)
    assert c.to_cid(code) == 0


# ---------- predefined Identity-H / Identity-V ----------


def test_identity_h_predefined():
    cm = CMapParser.parse_predefined("Identity-H")
    assert cm.get_wmode() == 0
    assert cm.get_min_code_length() == 2
    assert cm.get_max_code_length() == 2
    assert cm.to_cid(0x1234) == 0x1234
    assert cm.read_code(b"\x12\x34", 0) == (0x1234, 2)


def test_identity_v_predefined_is_vertical():
    cm = CMapParser.parse_predefined("Identity-V")
    assert cm.get_wmode() == 1
    assert cm.is_vertical()
    assert cm.to_cid(0xABCD) == 0xABCD


@pytest.mark.parametrize(
    ("name", "min_len", "max_len"),
    [
        ("90ms-RKSJ-H", 1, 2),   # mixed-width Shift-JIS
        ("GBK-EUC-H", 1, 2),     # mixed-width GBK
        ("UniGB-UCS2-H", 2, 2),  # pure 2-byte
    ],
)
def test_predefined_cjk_codespace_widths(name, min_len, max_len):
    cm = CMapParser.parse_predefined(name)
    assert cm.get_min_code_length() == min_len
    assert cm.get_max_code_length() == max_len
    # ascii 0x41 reads a single byte under the mixed-width codespaces and
    # two bytes under the pure 2-byte codespace.
    code, consumed = cm.read_code(b"\x41\x00", 0)
    assert consumed == min_len
    if min_len == 1:
        assert code == 0x41
    else:
        assert code == 0x4100


# ---------- CID -> GID: /CIDToGIDMap Identity vs stream ----------


def test_cid_to_gid_identity_no_program_is_passthrough():
    f = _type2({"CIDToGIDMap": COSName.get_pdf_name("Identity")})
    assert f.is_identity_cid_to_gid_map()
    # No embedded program to bound against → CID is the GID.
    assert f.cid_to_gid(5) == 5
    assert f.cid_to_gid(0x1234) == 0x1234


def test_cid_to_gid_absent_is_identity():
    f = _type2({})
    assert f.is_identity_cid_to_gid_map()
    assert f.cid_to_gid(7) == 7


def test_cid_to_gid_stream_lookup():
    f = _type2({"CIDToGIDMap": _cid_to_gid_stream([0, 10, 20, 30])})
    assert not f.is_identity_cid_to_gid_map()
    assert f.cid_to_gid(0) == 0
    assert f.cid_to_gid(1) == 10
    assert f.cid_to_gid(2) == 20
    assert f.cid_to_gid(3) == 30


def test_cid_to_gid_stream_out_of_range_is_zero():
    f = _type2({"CIDToGIDMap": _cid_to_gid_stream([0, 10, 20])})
    # CID beyond the stream length resolves to GID 0 (.notdef).
    assert f.cid_to_gid(3) == 0
    assert f.cid_to_gid(99) == 0


def test_cid_to_gid_negative_is_zero():
    f = _type2({"CIDToGIDMap": _cid_to_gid_stream([0, 10, 20])})
    assert f.cid_to_gid(-1) == 0
    f2 = _type2({"CIDToGIDMap": COSName.get_pdf_name("Identity")})
    assert f2.cid_to_gid(-5) == 0


def test_cid_to_gid_stream_odd_trailing_byte_ignored():
    # An odd trailing byte is dropped (upstream iterates 16-bit words).
    stream = COSStream()
    with stream.create_output_stream() as out:
        out.write(b"\x00\x05\x00\x0a\xff")  # 2 full words + 1 stray byte
    f = _type2({"CIDToGIDMap": stream})
    assert f.cid_to_gid(0) == 5
    assert f.cid_to_gid(1) == 10
    assert f.cid_to_gid(2) == 0


def test_code_to_gid_equals_cid_to_gid():
    f = _type2({"CIDToGIDMap": _cid_to_gid_stream([0, 11, 22, 33])})
    for cid in (0, 1, 2, 3):
        assert f.code_to_gid(cid) == f.cid_to_gid(cid)


# ---------- /W width lookup: both array forms + /DW default ----------


def test_w_form1_consecutive_widths():
    f = _type2({"W": _w_form1(20, [100, 200, 300])})
    widths = f.get_widths()
    assert widths == {20: 100.0, 21: 200.0, 22: 300.0}
    assert f.get_glyph_width(21) == 200.0


def test_w_form2_range_inclusive_clast():
    # cFirst cLast w — every CID in [10, 12] inclusive gets w (no off-by-one).
    f = _type2({"W": _w_form2(10, 12, 500)})
    assert f.get_widths() == {10: 500.0, 11: 500.0, 12: 500.0}
    # cLast itself is covered, cLast+1 is not.
    assert f.get_glyph_width(12) == 500.0
    assert f.get_glyph_width(13) == f.get_default_width()


def test_w_form2_single_cid_range():
    f = _type2({"W": _w_form2(7, 7, 444)})
    assert f.get_widths() == {7: 444.0}


def test_w_interleaved_both_forms():
    arr = COSArray()
    # 3 [400 410]  then  20 22 999
    arr.add(COSInteger.get(3))
    inner = COSArray()
    inner.add(COSInteger.get(400))
    inner.add(COSInteger.get(410))
    arr.add(inner)
    for v in (20, 22, 999):
        arr.add(COSInteger.get(v))
    f = _type2({"W": arr})
    assert f.get_widths() == {
        3: 400.0,
        4: 410.0,
        20: 999.0,
        21: 999.0,
        22: 999.0,
    }


def test_dw_default_width_used_when_unmapped():
    f = _type2({})
    assert f.get_default_width() == 1000.0  # spec default
    assert f.get_glyph_width(999) == 1000.0


def test_dw_explicit_override():
    f = _type2({"DW": COSInteger.get(777), "W": _w_form1(5, [600])})
    assert f.get_default_width() == 777.0
    assert f.get_glyph_width(5) == 600.0   # /W wins where present
    assert f.get_glyph_width(6) == 777.0   # /DW fallback elsewhere


def test_has_explicit_width_distinguishes_w_from_dw():
    f = _type2({"DW": COSInteger.get(500), "W": _w_form1(8, [600])})
    # /W carries CID 8 explicitly; CID 9 only has the /DW fallback.
    assert f.has_explicit_width(8)
    assert not f.has_explicit_width(9)


# ---------- /W2 vertical width forms ----------


def test_w2_form1_consecutive_triples():
    inner = _ints(-1000, 250, 880, -900, 300, 800)
    arr = COSArray()
    arr.add(COSInteger.get(5))
    arr.add(inner)
    f = _type2({"W2": arr})
    assert f.get_widths2() == {
        5: (-1000.0, 250.0, 880.0),
        6: (-900.0, 300.0, 800.0),
    }


def test_w2_form2_range():
    f = _type2({"W2": _ints(10, 12, -1100, 200, 900)})
    assert f.get_widths2() == {
        10: (-1100.0, 200.0, 900.0),
        11: (-1100.0, 200.0, 900.0),
        12: (-1100.0, 200.0, 900.0),
    }


def test_w2_vertical_displacement_default_dw2():
    # No /W2 for the CID → fall back to /DW2 displacement-vector-y (-1000).
    f = _type2({})
    assert f.get_vertical_displacement_vector_y(0x41) == -1000.0


# ---------- Type2 code_to_cid through the parent encoding CMap ----------


class _StubParent:
    def __init__(self, cmap: CMap) -> None:
        self._cmap = cmap

    def get_cmap(self) -> CMap:
        return self._cmap


def _type2_with_parent_cmap(cmap: CMap) -> PDCIDFontType2:
    f = _type2({})
    f._parent = _StubParent(cmap)  # type: ignore[attr-defined]
    return f


def test_type2_code_to_cid_cid_cmap():
    f = _type2_with_parent_cmap(_identity_h_cmap())
    assert f.code_to_cid(0x0041) == 0x41
    assert f.code_to_cid(0xFFFF) == 0xFFFF


def test_type2_code_to_cid_unicode_only_cmap():
    # A Unicode-only encoding CMap (UCS2-style): the first codepoint of
    # toUnicode(code) is the CID; unmapped codes fall through to 0.
    c = CMap("ucs2-style")
    c.add_codespace_range(b"\x00\x00", b"\xff\xff")
    c.add_base_font_character(b"\x00\x41", "A")
    f = _type2_with_parent_cmap(c)
    assert f.code_to_cid(0x41) == ord("A")  # 65
    assert f.code_to_cid(0xFFFF) == 0       # no unicode, no cid -> 0


def test_type2_code_to_cid_no_parent_passthrough():
    f = _type2({})
    assert f.code_to_cid(0x1234) == 0x1234


# ---------- encode_glyph_id round-trip ----------


@pytest.mark.parametrize("gid", [0, 1, 0x41, 0x1234, 0xFFFF, 0x10001])
def test_encode_glyph_id_is_two_byte_big_endian(gid):
    f = _type2({})
    encoded = f.encode_glyph_id(gid)
    assert encoded == (gid & 0xFFFF).to_bytes(2, "big")
    assert len(encoded) == 2
