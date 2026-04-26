"""Dispatch-table tests for ``PDFontFactory.create_font`` — covers the
``/FontDescriptor /FontFile3 /Subtype`` enrichment that distinguishes
CFF-backed fonts (Type1C, CIDFontType0C) from their plain counterparts,
plus regressions for the existing dispatch arms.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")


def _make_font_dict(subtype: str) -> COSDictionary:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, subtype)
    return raw


def _attach_font_file3(font_dict: COSDictionary, ff3_subtype: str) -> COSStream:
    """Attach a /FontDescriptor with a /FontFile3 stream whose own
    /Subtype is ``ff3_subtype`` to ``font_dict`` and return the stream."""
    descriptor = COSDictionary()
    stream = COSStream()
    stream.set_name(_SUBTYPE, ff3_subtype)
    descriptor.set_item(_FONT_FILE3, stream)
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor)
    return stream


# ---------- Type1C dispatch (FontFile3 /Subtype /Type1C) ----------


def test_type1_with_font_file3_type1c_dispatches_to_type1c_font() -> None:
    raw = _make_font_dict("Type1")
    _attach_font_file3(raw, "Type1C")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1CFont)
    assert out.get_cos_object() is raw


def test_type1_without_font_file3_dispatches_to_plain_type1_font() -> None:
    # Regression: bare /Type1 with no FontDescriptor stays on PDType1Font.
    raw = _make_font_dict("Type1")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert not isinstance(out, PDType1CFont)


def test_type1_with_font_descriptor_but_no_font_file3_stays_type1() -> None:
    raw = _make_font_dict("Type1")
    raw.set_item(_FONT_DESCRIPTOR, COSDictionary())
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert not isinstance(out, PDType1CFont)


def test_type1_with_font_file3_open_type_stays_type1() -> None:
    # /FontFile3 /Subtype /OpenType is NOT Type1C — must route to PDType1Font.
    raw = _make_font_dict("Type1")
    _attach_font_file3(raw, "OpenType")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert not isinstance(out, PDType1CFont)


def test_type1_with_font_file3_missing_subtype_stays_type1() -> None:
    # /FontFile3 stream with no /Subtype name on it — defensive case.
    raw = _make_font_dict("Type1")
    descriptor = COSDictionary()
    descriptor.set_item(_FONT_FILE3, COSStream())
    raw.set_item(_FONT_DESCRIPTOR, descriptor)
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)
    assert not isinstance(out, PDType1CFont)


# ---------- CIDFontType0 dispatch (FontFile3 /Subtype /CIDFontType0C) ----------


def test_cid_font_type0_with_font_file3_cid_font_type0c_dispatches() -> None:
    raw = _make_font_dict("CIDFontType0")
    _attach_font_file3(raw, "CIDFontType0C")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDCIDFontType0)
    assert out.get_cos_object() is raw


def test_cid_font_type0_without_font_file3_returns_none() -> None:
    # Bare /CIDFontType0 without the CFF marker is reached via the
    # Type0 descendant path; the top-level factory returns None here.
    raw = _make_font_dict("CIDFontType0")
    assert PDFontFactory.create_font(raw) is None


def test_cid_font_type0_with_font_file3_wrong_subtype_returns_none() -> None:
    raw = _make_font_dict("CIDFontType0")
    _attach_font_file3(raw, "OpenType")
    assert PDFontFactory.create_font(raw) is None


# ---------- regressions: existing dispatch arms unchanged ----------


def test_dispatches_true_type() -> None:
    raw = _make_font_dict("TrueType")
    assert isinstance(PDFontFactory.create_font(raw), PDTrueTypeFont)


def test_dispatches_type0() -> None:
    raw = _make_font_dict("Type0")
    assert isinstance(PDFontFactory.create_font(raw), PDType0Font)


def test_dispatches_type3() -> None:
    raw = _make_font_dict("Type3")
    assert isinstance(PDFontFactory.create_font(raw), PDType3Font)


def test_dispatches_mm_type1() -> None:
    raw = _make_font_dict("MMType1")
    assert isinstance(PDFontFactory.create_font(raw), PDMMType1Font)


def test_unknown_subtype_returns_none() -> None:
    raw = _make_font_dict("CIDFontType2")
    assert PDFontFactory.create_font(raw) is None


def test_none_returns_none() -> None:
    assert PDFontFactory.create_font(None) is None  # type: ignore[arg-type]


def test_non_dictionary_raises_type_error() -> None:
    import pytest

    with pytest.raises(TypeError):
        PDFontFactory.create_font("not a dict")  # type: ignore[arg-type]
