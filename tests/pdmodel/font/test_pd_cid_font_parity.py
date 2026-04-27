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
    # No /W2, no /DW2 -> spec default (880, -1000) returned as (v_y, v_x);
    # accessor flips to (v_x, v_y) form.
    v_x, v_y = font.get_position_vector(0)
    assert v_x == -1000.0
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
