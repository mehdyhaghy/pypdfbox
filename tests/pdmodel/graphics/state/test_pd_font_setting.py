from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSNull,
)
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.graphics.state import (
    PDExtendedGraphicsState,
    PDFontSetting,
)


def test_empty_wrapper_round_trip() -> None:
    fs = PDFontSetting()
    arr = fs.get_cos_object()
    assert isinstance(arr, COSArray)
    assert arr.size() == 2
    assert fs.get_font() is None
    assert fs.get_font_size() == 0.0


def test_set_font_size_round_trip() -> None:
    fs = PDFontSetting()
    fs.set_font_size(14.0)
    assert fs.get_font_size() == 14.0
    fs.set_font_size(8.5)
    assert fs.get_font_size() == 8.5


def test_set_font_typed_pdfont_writes_cos_object() -> None:
    font_dict = COSDictionary()
    font_dict.set_name("Type", "Font")
    font_dict.set_name("Subtype", "Type1")
    font_dict.set_name("BaseFont", "Helvetica")
    font = PDType1Font(font_dict)

    fs = PDFontSetting()
    fs.set_font(font)
    fs.set_font_size(12.0)

    # The slot must hold the underlying COSDictionary so the writer can
    # serialise it (typed PDFont wrappers are not COSBase subclasses).
    assert fs.get_cos_object().get_object(0) is font_dict
    rt = fs.get_font()
    assert rt is not None
    assert isinstance(rt, PDType1Font)
    assert rt.get_cos_object() is font_dict
    assert fs.get_font_size() == 12.0


def test_set_font_none_clears_to_cos_null() -> None:
    fs = PDFontSetting()
    font_dict = COSDictionary()
    font_dict.set_name("Type", "Font")
    font_dict.set_name("Subtype", "Type1")
    fs.set_font(font_dict)
    assert fs.get_font() is not None
    fs.set_font(None)
    assert fs.get_cos_object().get_object(0) is COSNull.NULL
    assert fs.get_font() is None


def test_wrapping_existing_array_reads_back_through_factory() -> None:
    font_dict = COSDictionary()
    font_dict.set_name("Type", "Font")
    font_dict.set_name("Subtype", "Type1")
    font_dict.set_name("BaseFont", "Times-Roman")
    arr = COSArray()
    arr.add(font_dict)
    arr.add(COSFloat(10.5))

    fs = PDFontSetting(arr)
    assert fs.get_cos_object() is arr
    rt = fs.get_font()
    assert isinstance(rt, PDType1Font)
    assert rt.get_cos_object() is font_dict
    assert fs.get_font_size() == 10.5


def test_constructor_rejects_non_array_cosbase() -> None:
    with pytest.raises(TypeError):
        PDFontSetting(COSName.get_pdf_name("F1"))


def test_extended_graphics_state_round_trip_via_typed_setter() -> None:
    gs = PDExtendedGraphicsState()
    assert gs.get_font_setting() is None

    font_dict = COSDictionary()
    font_dict.set_name("Type", "Font")
    font_dict.set_name("Subtype", "Type1")
    font_dict.set_name("BaseFont", "Courier")
    fs = PDFontSetting()
    fs.set_font(PDType1Font(font_dict))
    fs.set_font_size(9.0)

    gs.set_font_setting(fs)

    rt = gs.get_font_setting()
    assert isinstance(rt, PDFontSetting)
    # The wrapper now reads the same COSArray we just stored.
    assert rt.get_cos_object() is fs.get_cos_object()
    assert rt.get_font_size() == 9.0
    rt_font = rt.get_font()
    assert isinstance(rt_font, PDType1Font)
    assert rt_font.get_cos_object() is font_dict


def test_set_font_setting_none_removes_font_key() -> None:
    gs = PDExtendedGraphicsState()
    fs = PDFontSetting()
    fs.set_font_size(7.5)
    gs.set_font_setting(fs)
    assert gs.get_cos_object().get_item("Font") is fs.get_cos_object()

    gs.set_font_setting(None)
    assert gs.get_cos_object().get_item("Font") is None
    assert gs.get_font_setting() is None


def test_typed_wrapper_coexists_with_raw_helpers() -> None:
    gs = PDExtendedGraphicsState()
    font_name = COSName.get_pdf_name("F1")
    gs.set_font(font_name)
    gs.set_font_size(11.0)

    # Raw helpers still work …
    assert gs.get_font() is font_name
    assert gs.get_font_size() == 11.0

    # … and the typed wrapper sees the same array.
    fs = gs.get_font_setting()
    assert isinstance(fs, PDFontSetting)
    assert fs.get_cos_object() is gs.get_cos_object().get_item("Font")
    assert fs.get_font_size() == 11.0
    # /F1 is a COSName, not a COSDictionary, so PDFontFactory yields None.
    assert fs.get_font() is None
