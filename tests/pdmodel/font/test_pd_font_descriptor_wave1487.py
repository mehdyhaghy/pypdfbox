"""Wave 1487 regression tests for :class:`PDFontDescriptor` lazy-cache and
``/FontBBox`` leniency semantics.

These pin three behaviours that diverged from Apache PDFBox 3.0.7 before this
wave (oracle-confirmed via ``FontDescCacheLenientProbe``):

1. ``/Flags`` is lazily cached on first read (sentinel ``-1``); the setter
   overwrites the cache. A direct mutation of the underlying dict after the
   first read is NOT observed (stale cache) — upstream lines 386-403.
2. ``/CapHeight`` and ``/XHeight`` lazily cache ``abs()`` of the dict value on
   first read (sentinel ``Float.NEGATIVE_INFINITY``); the setter caches the
   RAW value, so the PDFBOX-429 abs() workaround only fires on the cache-miss
   dict read — upstream lines 522-573.
3. ``get_font_bounding_box`` zero-pads a malformed short ``/FontBBox`` array to
   4 entries (and coerces non-numeric entries to 0), mirroring
   ``new PDRectangle(rect)`` -> ``Arrays.copyOf(toFloatArray(), 4)`` — upstream
   lines 411-419 + PDRectangle(COSArray) lines 143-160.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_FLAGS = COSName.get_pdf_name("Flags")
_CAP_HEIGHT = COSName.get_pdf_name("CapHeight")
_X_HEIGHT = COSName.get_pdf_name("XHeight")
_FONT_BBOX = COSName.get_pdf_name("FontBBox")


# ---------- /Flags lazy cache ----------


def test_flags_default_zero_caches() -> None:
    fd = PDFontDescriptor()
    assert fd.get_flags() == 0
    # The cache is now populated; a direct dict write is not observed.
    fd.get_cos_object().set_int(_FLAGS, 64)
    assert fd.get_flags() == 0


def test_flags_first_read_caches_dict_value() -> None:
    d = COSDictionary()
    d.set_int(_FLAGS, 4)
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 4


def test_flags_direct_dict_mutation_after_read_is_stale() -> None:
    d = COSDictionary()
    d.set_int(_FLAGS, 4)
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 4
    d.set_int(_FLAGS, 64)  # bypasses the setter -> not observed
    assert fd.get_flags() == 4
    assert fd.is_symbolic() is True
    assert fd.is_italic() is False


def test_set_flags_refreshes_cache() -> None:
    d = COSDictionary()
    d.set_int(_FLAGS, 4)
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 4
    fd.set_flags(64)
    assert fd.get_flags() == 64
    assert fd.is_symbolic() is False
    assert fd.is_italic() is True
    # The dict was updated too.
    assert fd.get_cos_object().get_int(_FLAGS, 0) == 64


def test_flag_helpers_drive_through_cache() -> None:
    fd = PDFontDescriptor()
    fd.set_serif(True)
    assert fd.is_serif() is True
    assert fd.get_flags() == PDFontDescriptor.FLAG_SERIF
    fd.set_serif(False)
    assert fd.is_serif() is False
    assert fd.get_flags() == 0


# ---------- /CapHeight, /XHeight lazy cache + abs workaround ----------


def test_cap_height_abs_on_dict_read_then_raw_setter() -> None:
    d = COSDictionary()
    d.set_float(_CAP_HEIGHT, 662.0)
    fd = PDFontDescriptor(d)
    assert fd.get_cap_height() == pytest.approx(662.0)
    fd.set_cap_height(-100.0)
    assert fd.get_cap_height() == pytest.approx(-100.0)  # raw, not abs
    assert fd.get_cos_object().get_float(_CAP_HEIGHT, 0.0) == pytest.approx(-100.0)


def test_cap_height_negative_dict_read_returns_abs() -> None:
    d = COSDictionary()
    d.set_float(_CAP_HEIGHT, -662.0)
    assert PDFontDescriptor(d).get_cap_height() == pytest.approx(662.0)


def test_cap_height_default_zero() -> None:
    assert PDFontDescriptor().get_cap_height() == pytest.approx(0.0)


def test_cap_height_setter_on_fresh_descriptor_caches_raw() -> None:
    fd = PDFontDescriptor()
    fd.set_cap_height(-700.0)
    assert fd.get_cap_height() == pytest.approx(-700.0)


def test_cap_height_as_integer_dict_value() -> None:
    d = COSDictionary()
    d.set_item(_CAP_HEIGHT, COSInteger.get(662))
    assert PDFontDescriptor(d).get_cap_height() == pytest.approx(662.0)


def test_x_height_abs_on_dict_read_then_raw_setter() -> None:
    d = COSDictionary()
    d.set_float(_X_HEIGHT, 450.0)
    fd = PDFontDescriptor(d)
    assert fd.get_x_height() == pytest.approx(450.0)
    fd.set_x_height(-50.0)
    assert fd.get_x_height() == pytest.approx(-50.0)
    assert fd.get_cos_object().get_float(_X_HEIGHT, 0.0) == pytest.approx(-50.0)


def test_x_height_negative_dict_read_returns_abs() -> None:
    d = COSDictionary()
    d.set_float(_X_HEIGHT, -450.0)
    assert PDFontDescriptor(d).get_x_height() == pytest.approx(450.0)


# ---------- /FontBBox short-array zero-padding ----------


def test_bbox_three_entries_zero_padded() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(-200))
    arr.add(COSInteger.get(1000))
    d = COSDictionary()
    d.set_item(_FONT_BBOX, arr)
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    # toFloatArray -> [0, -200, 1000, 0]; corners normalised.
    assert r.get_lower_left_x() == pytest.approx(0.0)
    assert r.get_lower_left_y() == pytest.approx(-200.0)
    assert r.get_upper_right_x() == pytest.approx(1000.0)
    assert r.get_upper_right_y() == pytest.approx(0.0)


def test_bbox_empty_array_zero_padded() -> None:
    d = COSDictionary()
    d.set_item(_FONT_BBOX, COSArray())
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    assert r.get_lower_left_x() == pytest.approx(0.0)
    assert r.get_upper_right_x() == pytest.approx(0.0)


def test_bbox_non_numeric_entry_coerced_to_zero() -> None:
    # A non-numeric entry is coerced to 0 by toFloatArray semantics, not
    # rejected — matches upstream COSArray.toFloatArray.
    arr = COSArray()
    arr.add(COSInteger.get(10))
    arr.add(COSString("oops"))
    arr.add(COSInteger.get(100))
    arr.add(COSInteger.get(200))
    d = COSDictionary()
    d.set_item(_FONT_BBOX, arr)
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    # values [10, 0, 100, 200] -> ll (10,0) ur (100,200)
    assert r.get_lower_left_x() == pytest.approx(10.0)
    assert r.get_lower_left_y() == pytest.approx(0.0)
    assert r.get_upper_right_x() == pytest.approx(100.0)
    assert r.get_upper_right_y() == pytest.approx(200.0)


def test_bbox_non_array_returns_none() -> None:
    d = COSDictionary()
    d.set_item(_FONT_BBOX, COSString("bad bbox"))
    assert PDFontDescriptor(d).get_font_bounding_box() is None


def test_bbox_missing_returns_none() -> None:
    assert PDFontDescriptor(COSDictionary()).get_font_bounding_box() is None


def test_bbox_four_entries_unchanged() -> None:
    arr = COSArray()
    for v in (0, -200, 1000, 900):
        arr.add(COSInteger.get(v))
    d = COSDictionary()
    d.set_item(_FONT_BBOX, arr)
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    assert r.get_lower_left_y() == pytest.approx(-200.0)
    assert r.get_upper_right_y() == pytest.approx(900.0)


def test_bbox_five_entries_truncated() -> None:
    arr = COSArray()
    for v in (0, -200, 1000, 900, 12345):
        arr.add(COSInteger.get(v))
    d = COSDictionary()
    d.set_item(_FONT_BBOX, arr)
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    # 5th entry ignored (copyOf truncates to 4).
    assert r.get_upper_right_x() == pytest.approx(1000.0)
    assert r.get_upper_right_y() == pytest.approx(900.0)


def test_set_font_bounding_box_round_trip_then_clear() -> None:
    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0.0, -200.0, 1000.0, 900.0))
    assert _FONT_BBOX in fd.get_cos_object()
    fd.set_font_bounding_box(None)
    assert _FONT_BBOX not in fd.get_cos_object()
    assert fd.get_font_bounding_box() is None
