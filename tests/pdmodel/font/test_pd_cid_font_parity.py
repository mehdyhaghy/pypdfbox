"""Parity tests for PDCIDFont upstream-named accessors.

Covers ``is_embedded``, ``get_program``, ``get_average_font_width``,
``get_default_width``, ``get_position_vector``, ``get_displacement``,
``get_height``, ``has_glyph``, ``get_bounding_box``, ``code_to_cid``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _bbox(*xs: float) -> COSArray:
    arr = COSArray()
    for x in xs:
        arr.add(COSFloat(float(x)))
    return arr


def _w_range(c1: int, c2: int, w: int) -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(c1))
    arr.add(COSInteger.get(c2))
    arr.add(COSInteger.get(w))
    return arr


# ---------- is_embedded ----------


def test_is_embedded_false_when_no_descriptor() -> None:
    font = PDCIDFontType0()
    assert font.is_embedded() is False


def test_is_embedded_false_when_descriptor_has_no_font_files() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.is_embedded() is False


def test_is_embedded_true_for_font_file() -> None:
    font = PDCIDFontType0()
    fd = PDFontDescriptor()
    fd.set_font_file(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_font_file2() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_file2(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


def test_is_embedded_true_for_font_file3() -> None:
    font = PDCIDFontType0()
    fd = PDFontDescriptor()
    fd.set_font_file3(COSStream())
    font.set_font_descriptor(fd)
    assert font.is_embedded() is True


# ---------- get_program ----------


def test_get_program_none_when_not_embedded() -> None:
    font = PDCIDFontType0()
    assert font.get_program() is None


def test_get_program_returns_font_file2_bytes() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    stream = COSStream()
    payload = b"\x00OTTO" + b"abc" * 8
    stream.set_data(payload)
    fd.set_font_file2(stream)
    font.set_font_descriptor(fd)
    assert font.get_program() == payload


def test_get_program_prefers_font_file_over_font_file3() -> None:
    font = PDCIDFontType0()
    fd = PDFontDescriptor()
    s1 = COSStream()
    s1.set_data(b"FONT-FILE-1")
    s3 = COSStream()
    s3.set_data(b"FONT-FILE-3")
    fd.set_font_file(s1)
    fd.set_font_file3(s3)
    font.set_font_descriptor(fd)
    assert font.get_program() == b"FONT-FILE-1"


# ---------- get_default_width / get_average_font_width ----------


def test_get_default_width_alias_returns_dw() -> None:
    font = PDCIDFontType0()
    font.set_dw(425)
    assert font.get_default_width() == 425.0


def test_get_average_font_width_falls_back_to_dw_when_no_w() -> None:
    font = PDCIDFontType2()
    font.set_dw(700)
    assert font.get_average_font_width() == 700.0


def test_get_average_font_width_default_when_w_and_dw_absent() -> None:
    font = PDCIDFontType0()
    # /DW absent -> 1000; /W absent -> empty parsed table -> falls back to /DW.
    assert font.get_average_font_width() == 1000.0


def test_get_average_font_width_arithmetic_mean_of_w() -> None:
    font = PDCIDFontType0()
    # /W [1 3 600] -> CIDs 1..3 each 600 -> mean = 600.
    font.set_w(_w_range(1, 3, 600))
    assert font.get_average_font_width() == 600.0


# ---------- has_glyph ----------


def test_has_glyph_true_for_explicit_w_entry() -> None:
    font = PDCIDFontType2()
    font.set_w(_w_range(10, 12, 800))
    assert font.has_glyph(11) is True


def test_has_glyph_true_via_positive_dw_when_unmapped() -> None:
    font = PDCIDFontType0()
    font.set_dw(500)
    assert font.has_glyph(99999) is True


def test_has_glyph_false_when_explicit_w_is_zero() -> None:
    font = PDCIDFontType0()
    font.set_w(_w_range(7, 7, 0))
    font.set_dw(500)  # DW is irrelevant — explicit /W wins.
    assert font.has_glyph(7) is False


def test_has_glyph_false_when_dw_is_zero_and_unmapped() -> None:
    font = PDCIDFontType2()
    font.set_dw(0)
    assert font.has_glyph(42) is False


# ---------- get_bounding_box ----------


def test_get_bounding_box_none_when_no_descriptor() -> None:
    font = PDCIDFontType0()
    assert font.get_bounding_box() is None


def test_get_bounding_box_none_when_descriptor_has_no_bbox() -> None:
    font = PDCIDFontType2()
    font.set_font_descriptor(PDFontDescriptor())
    assert font.get_bounding_box() is None


def test_get_bounding_box_returns_pdrectangle_when_present() -> None:
    font = PDCIDFontType2()
    fd = PDFontDescriptor()
    fd.set_font_b_box(_bbox(-100, -200, 1100, 900))
    font.set_font_descriptor(fd)
    rect = font.get_bounding_box()
    assert isinstance(rect, PDRectangle)
    assert rect.get_lower_left_x() == -100.0
    assert rect.get_lower_left_y() == -200.0
    assert rect.get_upper_right_x() == 1100.0
    assert rect.get_upper_right_y() == 900.0


def test_get_bounding_box_returns_none_for_short_array() -> None:
    font = PDCIDFontType0()
    fd = PDFontDescriptor()
    fd.set_font_b_box(_bbox(0, 0, 100))  # only 3 entries
    font.set_font_descriptor(fd)
    assert font.get_bounding_box() is None


# ---------- get_displacement / get_position_vector / get_height ----------


def test_get_displacement_horizontal_uses_glyph_width_over_1000() -> None:
    font = PDCIDFontType0()
    font.set_w(_w_range(5, 5, 750))
    dx, dy = font.get_displacement(5)
    assert dx == 0.75
    assert dy == 0.0


def test_get_displacement_falls_back_to_dw_for_unmapped() -> None:
    font = PDCIDFontType2()
    font.set_dw(500)
    dx, dy = font.get_displacement(123)
    assert dx == 0.5
    assert dy == 0.0


def test_get_height_zero_when_no_w2_entry() -> None:
    font = PDCIDFontType2()
    assert font.get_height(0) == 0.0


def test_get_height_returns_w1y_from_w2() -> None:
    font = PDCIDFontType2()
    # /W2 [5 5 880 -500 -1000] -> CID 5 triple = (880, -500, -1000)
    arr = COSArray()
    for v in (5, 5, 880, -500, -1000):
        arr.add(COSInteger.get(v))
    font.set_w2(arr)
    assert font.get_height(5) == 880.0


def test_get_position_vector_falls_back_to_default_dw2() -> None:
    font = PDCIDFontType2()
    # No /W2, no /DW2 -> upstream default position vector formula
    # ``(widthForCID(cid)/2, dw2[0])`` (PDCIDFont.getDefaultPositionVector).
    # With /DW unset (defaults to 1000) and dw2[0] defaulting to 880,
    # the result is (500, 880).
    v_x, v_y = font.get_position_vector(0)
    assert v_x == 500.0
    assert v_y == 880.0


def test_get_position_vector_uses_w2_triple_when_present() -> None:
    font = PDCIDFontType2()
    arr = COSArray()
    for v in (5, 5, 880, -250, -900):
        arr.add(COSInteger.get(v))
    font.set_w2(arr)
    assert font.get_position_vector(5) == (-250.0, -900.0)


# ---------- code_to_cid ----------


def test_code_to_cid_default_returns_code() -> None:
    font = PDCIDFontType0()
    assert font.code_to_cid(0) == 0
    assert font.code_to_cid(42) == 42
    assert font.code_to_cid(0xFFFF) == 0xFFFF


# ---------- get_base_font ----------


def test_get_base_font_none_when_absent() -> None:
    font = PDCIDFontType0()
    assert font.get_base_font() is None


def test_get_base_font_round_trip() -> None:
    from pypdfbox.cos import COSDictionary, COSName

    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "CIDFontType2")  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("BaseFont"), "ArialMT")
    font = PDCIDFontType2(raw)
    assert font.get_base_font() == "ArialMT"
    # Mirrors get_name on PDCIDFont (PDFont.get_name reads /BaseFont).
    assert font.get_name() == "ArialMT"


# ---------- get_width (code -> width via CID) ----------


def test_get_width_returns_dw_when_no_w_table() -> None:
    font = PDCIDFontType0()
    font.set_dw(777)
    assert font.get_width(5) == 777.0


def test_get_width_uses_w_table_via_code_to_cid() -> None:
    font = PDCIDFontType0()
    font.set_w(_w_range(10, 12, 600))
    assert font.get_width(10) == 600.0
    assert font.get_width(11) == 600.0
    assert font.get_width(12) == 600.0
    # Outside /W -> /DW (default 1000)
    assert font.get_width(13) == 1000.0


# ---------- has_explicit_width ----------


def test_has_explicit_width_true_for_w_entry() -> None:
    font = PDCIDFontType0()
    font.set_w(_w_range(5, 7, 500))
    assert font.has_explicit_width(5) is True
    assert font.has_explicit_width(6) is True
    assert font.has_explicit_width(7) is True


def test_has_explicit_width_false_for_unmapped_cid_even_with_dw() -> None:
    """``has_explicit_width`` is strictly about ``/W`` membership — a
    positive ``/DW`` does NOT make a CID 'explicitly' wide."""
    font = PDCIDFontType0()
    font.set_dw(900)
    assert font.has_explicit_width(42) is False


def test_has_explicit_width_false_when_no_w() -> None:
    font = PDCIDFontType0()
    assert font.has_explicit_width(0) is False


# ---------- get_vertical_displacement_vector_y ----------


def test_get_vertical_displacement_vector_y_default_dw2() -> None:
    """Spec default for /DW2 displacement_vector_y is -1000 when /DW2
    and /W2 are both absent."""
    font = PDCIDFontType0()
    assert font.get_vertical_displacement_vector_y(0) == -1000.0
    assert font.get_vertical_displacement_vector_y(42) == -1000.0


def test_get_vertical_displacement_vector_y_uses_dw2_when_set() -> None:
    font = PDCIDFontType2()
    dw2 = COSArray()
    for v in (900, -880):
        dw2.add(COSInteger.get(v))
    font.set_dw2(dw2)
    assert font.get_vertical_displacement_vector_y(0) == -880.0


def test_get_vertical_displacement_vector_y_uses_w2_when_present() -> None:
    """``/W2`` form 2: ``c1 c2 w1y v_x v_y`` — the ``w1y`` slot is what
    ``get_vertical_displacement_vector_y`` returns."""
    font = PDCIDFontType2()
    arr = COSArray()
    for v in (5, 5, -880, -500, 900):
        arr.add(COSInteger.get(v))
    font.set_w2(arr)
    assert font.get_vertical_displacement_vector_y(5) == -880.0
    # CID outside /W2 -> /DW2 displacement_vector_y default (-1000).
    assert font.get_vertical_displacement_vector_y(6) == -1000.0


# ---------- read_cid_to_gid_map ----------


def test_read_cid_to_gid_map_none_when_absent() -> None:
    font = PDCIDFontType2()
    assert font.read_cid_to_gid_map() is None


def test_read_cid_to_gid_map_none_for_identity_name() -> None:
    """``/CIDToGIDMap /Identity`` is not a stream — upstream's typed
    getCOSStream() returns null in that case."""
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.read_cid_to_gid_map() is None


def test_read_cid_to_gid_map_decodes_big_endian_words() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(
        b"\x00\x00"  # CID 0 -> GID 0
        b"\x00\x2a"  # CID 1 -> GID 42
        b"\x01\x00"  # CID 2 -> GID 256
        b"\xff\xff"  # CID 3 -> GID 65535
    )
    font.set_cid_to_gid_map(stream)
    out = font.read_cid_to_gid_map()
    assert out == [0, 42, 256, 0xFFFF]


def test_read_cid_to_gid_map_ignores_trailing_odd_byte() -> None:
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x12\x34\xff")  # 3 bytes -> 1 GID, trailing byte discarded
    font.set_cid_to_gid_map(stream)
    assert font.read_cid_to_gid_map() == [0x1234]
