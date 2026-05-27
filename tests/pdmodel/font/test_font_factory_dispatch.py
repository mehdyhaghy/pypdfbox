"""Dispatch-table tests for ``PDFontFactory.create_font`` — mirrors upstream
PDFBox ``PDFontFactory.createFont`` exactly: a ``/Type1`` (or ``/MMType1``)
whose ``/FontDescriptor`` *contains* a ``/FontFile3`` routes to
``PDType1CFont`` regardless of the FontFile3 ``/Subtype``; a top-level
``/CIDFontType0`` / ``/CIDFontType2`` raises; an unknown / missing
``/Subtype`` falls back to ``PDType1Font``.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
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


def test_type1_with_font_file3_open_type_dispatches_to_type1c() -> None:
    # Upstream PDFontFactory checks only containsKey(FONT_FILE3) for the
    # /Type1 arm — it does NOT inspect the FontFile3 /Subtype. A FontFile3
    # of /Subtype /OpenType therefore still routes to PDType1CFont.
    raw = _make_font_dict("Type1")
    _attach_font_file3(raw, "OpenType")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1CFont)


def test_type1_with_font_file3_missing_subtype_dispatches_to_type1c() -> None:
    # /FontFile3 present but with no /Subtype name — upstream still routes
    # to PDType1CFont because it only tests containsKey(FONT_FILE3).
    raw = _make_font_dict("Type1")
    descriptor = COSDictionary()
    descriptor.set_item(_FONT_FILE3, COSStream())
    raw.set_item(_FONT_DESCRIPTOR, descriptor)
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1CFont)


# ---------- top-level CIDFont subtypes are not allowed (raise) ----------


def test_top_level_cid_font_type0_raises() -> None:
    # A CIDFont is only legal as a /Type0 descendant. Upstream raises
    # IOException("Type 0 descendant font not allowed"); we raise OSError.
    import pytest

    raw = _make_font_dict("CIDFontType0")
    _attach_font_file3(raw, "CIDFontType0C")
    with pytest.raises(OSError, match="Type 0 descendant font not allowed"):
        PDFontFactory.create_font(raw)


def test_top_level_cid_font_type0_bare_raises() -> None:
    import pytest

    raw = _make_font_dict("CIDFontType0")
    with pytest.raises(OSError, match="Type 0 descendant font not allowed"):
        PDFontFactory.create_font(raw)


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


def test_top_level_cid_font_type2_raises() -> None:
    import pytest

    raw = _make_font_dict("CIDFontType2")
    with pytest.raises(OSError, match="Type 2 descendant font not allowed"):
        PDFontFactory.create_font(raw)


def test_unknown_subtype_falls_back_to_type1() -> None:
    # Upstream logs a warning and falls back to PDType1Font for any
    # unrecognised /Subtype.
    raw = _make_font_dict("Bogus")
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)


def test_missing_subtype_falls_back_to_type1() -> None:
    raw = COSDictionary()  # no /Subtype at all
    out = PDFontFactory.create_font(raw)
    assert isinstance(out, PDType1Font)


def test_none_returns_none() -> None:
    assert PDFontFactory.create_font(None) is None  # type: ignore[arg-type]


def test_non_dictionary_raises_type_error() -> None:
    import pytest

    with pytest.raises(TypeError):
        PDFontFactory.create_font("not a dict")  # type: ignore[arg-type]
