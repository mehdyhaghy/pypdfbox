"""Ported upstream tests for ``PDFontFactory.createFont`` dispatch.

PDFBox 3.0.x has no dedicated ``PDFontFactoryTest.java`` — the factory
is exercised through ``PDFontTest`` (the relevant cases live in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDFontTest.java``,
methods ``testPDFontFactory*``). The cases ported here are the
subtype-dispatch ones; non-dispatch tests live alongside their
respective subtype implementations.

Skipped (one-line reason each):
* ``testPDFontFactoryReadFont*`` — those exercise full font-loading
  (binary FontFile parsing); covered by the subtype-specific upstream
  tests, not by the factory wrapper.
* ``testCachedFonts`` — depends on ``ResourceCache`` round-tripping,
  which our factory accepts as a parity kwarg but does not consult
  (cache is owned by the parser, not the factory).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]


def _font_dict(subtype: str | None) -> COSDictionary:
    raw = COSDictionary()
    if subtype is not None:
        raw.set_name(_SUBTYPE, subtype)
    return raw


# Mirrors PDFontTest#testPDFontFactoryType1.
def test_pd_font_factory_type1() -> None:
    out = PDFontFactory.create_font(_font_dict("Type1"))
    assert isinstance(out, PDType1Font)


# Mirrors PDFontTest#testPDFontFactoryMMType1.
def test_pd_font_factory_mm_type1() -> None:
    out = PDFontFactory.create_font(_font_dict("MMType1"))
    assert isinstance(out, PDMMType1Font)
    # MMType1 extends Type1 in PDFBox; preserve that here.
    assert isinstance(out, PDType1Font)


# Mirrors PDFontTest#testPDFontFactoryTrueType.
def test_pd_font_factory_true_type() -> None:
    out = PDFontFactory.create_font(_font_dict("TrueType"))
    assert isinstance(out, PDTrueTypeFont)


# Mirrors PDFontTest#testPDFontFactoryType3.
def test_pd_font_factory_type3() -> None:
    out = PDFontFactory.create_font(_font_dict("Type3"))
    assert isinstance(out, PDType3Font)


# Mirrors PDFontTest#testPDFontFactoryType0.
def test_pd_font_factory_type0() -> None:
    out = PDFontFactory.create_font(_font_dict("Type0"))
    assert isinstance(out, PDType0Font)


# Mirrors PDFontTest#testPDFontFactoryUnknownSubtype: a font dict with
# no /Subtype must not throw — upstream logs a warning and returns a
# PDType1Font wrapping the (malformed) dict.
def test_pd_font_factory_missing_subtype_falls_back_to_type1() -> None:
    out = PDFontFactory.create_font(_font_dict(None))
    assert isinstance(out, PDType1Font)


# Mirrors the IllegalArgumentException check upstream performs by
# refusing non-dictionary inputs at the API boundary.
def test_pd_font_factory_non_dictionary_raises() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.create_font("not a dict")  # type: ignore[arg-type]


# Mirrors PDFontTest's null-input handling: createFont(null) returns
# null in upstream (it short-circuits before the dispatch).
def test_pd_font_factory_none_returns_none() -> None:
    assert PDFontFactory.create_font(None) is None  # type: ignore[arg-type]


# Mirrors PDFontTest#testPDFontFactoryResourceCacheKwarg-style cases:
# the second argument is accepted for signature parity but does not
# alter dispatch.
def test_pd_font_factory_resource_cache_kwarg_does_not_alter_dispatch() -> None:
    raw = _font_dict("TrueType")
    sentinel = object()
    out = PDFontFactory.create_font(raw, resource_cache=sentinel)
    assert isinstance(out, PDTrueTypeFont)
