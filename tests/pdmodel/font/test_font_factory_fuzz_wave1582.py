"""Fuzz / parity coverage for ``PDFontFactory.create_font`` dispatch
(wave 1582).

Hammers the subtype dispatch table that builds the right ``PDFont``
subclass from a ``/Font`` dictionary's ``/Subtype``, matching upstream
PDFBox ``PDFontFactory.createFont`` (read from
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/PDFontFactory.java``):

* ``/Type1`` -> ``PDType1Font`` (or ``PDType1CFont`` when the descriptor
  contains ``/FontFile3``).
* ``/MMType1`` -> ``PDMMType1Font`` (or ``PDType1CFont`` w/ ``/FontFile3``).
* ``/TrueType`` -> ``PDTrueTypeFont``.
* ``/Type3`` -> ``PDType3Font`` (with ``/FontMatrix`` / ``/CharProcs``).
* ``/Type0`` -> ``PDType0Font`` with a ``CIDFontType0`` vs
  ``CIDFontType2`` descendant.
* top-level ``/CIDFontType0`` / ``/CIDFontType2`` -> raise (a CIDFont is
  only legal as a Type0 descendant).
* unknown / missing ``/Subtype`` -> warn + fall back to ``PDType1Font``
  (upstream PDFBOX-1988 behaviour).
* a Standard-14 ``Helvetica`` with no embedded program -> standard-14
  metrics.
* the descendant-CIDFont factory ``create_descendant_font``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_mm_type1_font import PDMMType1Font
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE2: COSName = COSName.get_pdf_name("FontFile2")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")
_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_FONT_MATRIX: COSName = COSName.get_pdf_name("FontMatrix")
_CHAR_PROCS: COSName = COSName.get_pdf_name("CharProcs")


def _font_dict(subtype: str, base_font: str | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_name(_TYPE, "Font")
    d.set_name(_SUBTYPE, subtype)
    if base_font is not None:
        d.set_name(_BASE_FONT, base_font)
    return d


def _with_font_file3(d: COSDictionary, ff3_subtype: str | None = None) -> COSDictionary:
    descriptor = COSDictionary()
    stream = COSStream()
    if ff3_subtype is not None:
        stream.set_name(_SUBTYPE, ff3_subtype)
    descriptor.set_item(_FONT_FILE3, stream)
    d.set_item(_FONT_DESCRIPTOR, descriptor)
    return d


def _type0_with_descendant(
    descendant_subtype: str, encoding: str = "Identity-H"
) -> COSDictionary:
    d = _font_dict("Type0", "Test-Identity")
    d.set_name(_ENCODING, encoding)
    descendant = COSDictionary()
    descendant.set_name(_TYPE, "Font")
    descendant.set_name(_SUBTYPE, descendant_subtype)
    descendant.set_name(_BASE_FONT, "Test-Identity")
    arr = COSArray()
    arr.add(descendant)
    d.set_item(_DESCENDANT_FONTS, arr)
    return d


# ---------- simple-font subtype dispatch ----------


@pytest.mark.parametrize(
    ("subtype", "expected"),
    [
        ("Type1", PDType1Font),
        ("MMType1", PDMMType1Font),
        ("TrueType", PDTrueTypeFont),
        ("Type3", PDType3Font),
    ],
    ids=["type1", "mmtype1", "truetype", "type3"],
)
def test_simple_subtype_dispatch(subtype: str, expected: type) -> None:
    out = PDFontFactory.create_font(_font_dict(subtype))
    assert type(out) is expected
    assert out.get_cos_object() is not None


@pytest.mark.parametrize(
    "subtype",
    ["Type1", "MMType1", "TrueType", "Type3"],
    ids=["type1", "mmtype1", "truetype", "type3"],
)
def test_simple_fonts_are_simple_font_subclass(subtype: str) -> None:
    out = PDFontFactory.create_font(_font_dict(subtype))
    assert isinstance(out, PDSimpleFont)


# ---------- Type1 / MMType1 + FontFile3 -> PDType1CFont ----------


def test_type1_plain_stays_type1() -> None:
    out = PDFontFactory.create_font(_font_dict("Type1"))
    assert type(out) is PDType1Font
    assert not isinstance(out, PDType1CFont)


def test_type1_with_font_file3_routes_to_type1c() -> None:
    out = PDFontFactory.create_font(_with_font_file3(_font_dict("Type1"), "Type1C"))
    assert isinstance(out, PDType1CFont)


def test_type1_with_font_descriptor_but_no_font_file3_stays_type1() -> None:
    d = _font_dict("Type1")
    d.set_item(_FONT_DESCRIPTOR, COSDictionary())
    out = PDFontFactory.create_font(d)
    assert type(out) is PDType1Font


@pytest.mark.parametrize(
    "ff3_subtype",
    ["Type1C", "OpenType", "CIDFontType0C", None],
    ids=["type1c", "opentype", "cidtype0c", "no_subtype"],
)
def test_type1_font_file3_ignores_inner_subtype(ff3_subtype: str | None) -> None:
    # Upstream checks only containsKey(FONT_FILE3); never inspects its
    # /Subtype.
    out = PDFontFactory.create_font(_with_font_file3(_font_dict("Type1"), ff3_subtype))
    assert isinstance(out, PDType1CFont)


def test_mmtype1_plain_stays_mmtype1() -> None:
    out = PDFontFactory.create_font(_font_dict("MMType1"))
    assert type(out) is PDMMType1Font


def test_mmtype1_with_font_file3_routes_to_type1c() -> None:
    out = PDFontFactory.create_font(_with_font_file3(_font_dict("MMType1"), "Type1C"))
    assert isinstance(out, PDType1CFont)
    assert not isinstance(out, PDMMType1Font)


# ---------- Type3 properties ----------


def test_type3_carries_font_matrix_and_char_procs() -> None:
    d = _font_dict("Type3")
    fm = COSArray()
    for v in (0.001, 0.0, 0.0, 0.001, 0.0, 0.0):
        fm.add(COSFloat(v))
    d.set_item(_FONT_MATRIX, fm)
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("a"), COSStream())
    d.set_item(_CHAR_PROCS, char_procs)
    out = PDFontFactory.create_font(d)
    assert isinstance(out, PDType3Font)
    matrix = out.get_font_matrix()
    assert matrix is not None
    # FontMatrix scale element (first) round-trips to ~0.001.
    assert float(matrix[0]) == pytest.approx(0.001)
    assert out.get_char_procs() is not None


# ---------- Type0 with CIDFontType0 / CIDFontType2 descendant ----------


@pytest.mark.parametrize(
    ("descendant_subtype", "descendant_cls"),
    [
        ("CIDFontType0", PDCIDFontType0),
        ("CIDFontType2", PDCIDFontType2),
    ],
    ids=["cidtype0", "cidtype2"],
)
def test_type0_builds_with_descendant(
    descendant_subtype: str, descendant_cls: type
) -> None:
    out = PDFontFactory.create_font(_type0_with_descendant(descendant_subtype))
    assert type(out) is PDType0Font
    descendant = out.get_descendant_font()
    assert isinstance(descendant, descendant_cls)
    assert isinstance(descendant, PDCIDFont)


def test_type0_with_no_descendant_still_builds() -> None:
    d = _font_dict("Type0", "Test")
    d.set_name(_ENCODING, "Identity-H")
    out = PDFontFactory.create_font(d)
    assert type(out) is PDType0Font
    assert out.get_descendant_font() is None


def test_type0_always_returns_type0_regardless_of_descendant() -> None:
    # Even a malformed descendant subtype keeps the parent on PDType0Font;
    # the descendant wrap fails lazily, not at create_font time.
    out = PDFontFactory.create_font(_type0_with_descendant("Bogus"))
    assert type(out) is PDType0Font


# ---------- top-level CIDFont subtypes are illegal ----------


@pytest.mark.parametrize(
    ("subtype", "message"),
    [
        ("CIDFontType0", "Type 0 descendant font not allowed"),
        ("CIDFontType2", "Type 2 descendant font not allowed"),
    ],
    ids=["cidtype0", "cidtype2"],
)
def test_top_level_cid_font_raises(subtype: str, message: str) -> None:
    with pytest.raises(OSError, match=message):
        PDFontFactory.create_font(_font_dict(subtype))


# ---------- unknown / missing subtype -> PDType1Font fallback ----------


@pytest.mark.parametrize(
    "subtype",
    ["Bogus", "Type1C", "type1", "TRUETYPE", "Type42", "OpenType", "Type9"],
    ids=["bogus", "type1c", "lower_type1", "upper_truetype", "type42", "opentype", "type9"],
)
def test_unknown_subtype_falls_back_to_type1(subtype: str) -> None:
    # Upstream: LOG.warn + return new PDType1Font(dict). Note case
    # sensitivity — "type1" / "TRUETYPE" are NOT the canonical names so
    # they fall through to the default arm (PDFBOX-1988).
    out = PDFontFactory.create_font(_font_dict(subtype))
    assert type(out) is PDType1Font


def test_missing_subtype_falls_back_to_type1() -> None:
    d = COSDictionary()
    d.set_name(_TYPE, "Font")
    out = PDFontFactory.create_font(d)
    assert type(out) is PDType1Font


def test_no_type_and_no_subtype_falls_back_to_type1() -> None:
    out = PDFontFactory.create_font(COSDictionary())
    assert type(out) is PDType1Font


def test_wrong_type_still_dispatches_by_subtype() -> None:
    # Upstream logs an error for /Type != /Font but proceeds with subtype
    # dispatch (the warning is non-fatal for create_font).
    d = COSDictionary()
    d.set_name(_TYPE, "NotAFont")
    d.set_name(_SUBTYPE, "TrueType")
    out = PDFontFactory.create_font(d)
    assert isinstance(out, PDTrueTypeFont)


# ---------- standard-14 substitution (Helvetica, no embedded program) ----------


def test_helvetica_no_embedded_program_uses_standard14_metrics() -> None:
    d = _font_dict("Type1", "Helvetica")
    out = PDFontFactory.create_font(d)
    assert isinstance(out, PDType1Font)
    assert out.is_standard14()
    # Standard-14 Helvetica space advance is 278/1000 em.
    assert out.get_width(32) == pytest.approx(278.0)


@pytest.mark.parametrize(
    "name",
    ["Helvetica", "Times-Roman", "Courier", "Symbol", "ZapfDingbats"],
    ids=["helvetica", "times", "courier", "symbol", "zapf"],
)
def test_standard14_core_fonts_are_standard14(name: str) -> None:
    out = PDFontFactory.create_font(_font_dict("Type1", name))
    assert isinstance(out, PDType1Font)
    assert out.is_standard14()


def test_create_default_font_is_helvetica() -> None:
    out = PDFontFactory.create_default_font()
    assert isinstance(out, PDType1Font)
    assert out.get_name() == "Helvetica"
    assert out.is_standard14()


@pytest.mark.parametrize(
    ("requested", "resolved"),
    [
        ("Times-Roman", "Times-Roman"),
        ("Courier", "Courier"),
        ("NoSuchFont", "Helvetica"),
        ("", "Helvetica"),
    ],
    ids=["times", "courier", "unknown_fallback", "empty_fallback"],
)
def test_create_default_font_resolves_or_falls_back(requested: str, resolved: str) -> None:
    out = PDFontFactory.create_default_font(requested)
    assert out.get_name() == resolved


# ---------- create_descendant_font factory ----------


def _descendant_dict(subtype: str, with_type: bool = True) -> COSDictionary:
    d = COSDictionary()
    if with_type:
        d.set_name(_TYPE, "Font")
    d.set_name(_SUBTYPE, subtype)
    d.set_name(_BASE_FONT, "Test")
    return d


@pytest.mark.parametrize(
    ("subtype", "expected"),
    [
        ("CIDFontType0", PDCIDFontType0),
        ("CIDFontType2", PDCIDFontType2),
    ],
    ids=["cidtype0", "cidtype2"],
)
def test_create_descendant_font_dispatch(subtype: str, expected: type) -> None:
    out = PDFontFactory.create_descendant_font(_descendant_dict(subtype))
    assert type(out) is expected
    assert isinstance(out, PDCIDFont)


def test_create_descendant_font_forwards_parent() -> None:
    parent = PDType0Font()
    out = PDFontFactory.create_descendant_font(_descendant_dict("CIDFontType2"), parent)
    assert out.get_parent() is parent


def test_create_descendant_font_none_returns_none() -> None:
    assert PDFontFactory.create_descendant_font(None) is None  # type: ignore[arg-type]


def test_create_descendant_font_no_type_defaults_to_font() -> None:
    # Absent /Type defaults to Font upstream (getCOSName(TYPE, FONT)), so a
    # descendant with no /Type but a valid CID subtype still builds.
    out = PDFontFactory.create_descendant_font(
        _descendant_dict("CIDFontType0", with_type=False)
    )
    assert isinstance(out, PDCIDFontType0)


def test_create_descendant_font_explicit_non_font_type_raises() -> None:
    # Upstream createDescendantFont raises IOException when /Type is
    # present and not /Font; pypdfbox raises OSError. (Wave 1582 fix:
    # previously this check was missing and the font built silently.)
    d = _descendant_dict("CIDFontType2")
    d.set_name(_TYPE, "Bogus")
    with pytest.raises(OSError, match="Expected 'Font' dictionary"):
        PDFontFactory.create_descendant_font(d)


@pytest.mark.parametrize(
    "subtype",
    ["Type1", "TrueType", "Type0", "Bogus"],
    ids=["type1", "truetype", "type0", "bogus"],
)
def test_create_descendant_font_non_cid_subtype_raises(subtype: str) -> None:
    with pytest.raises(OSError):
        PDFontFactory.create_descendant_font(_descendant_dict(subtype))


def test_create_descendant_font_missing_subtype_raises() -> None:
    d = COSDictionary()
    d.set_name(_TYPE, "Font")
    with pytest.raises(OSError):
        PDFontFactory.create_descendant_font(d)


# ---------- typed convenience wrappers ----------


def test_create_simple_font_returns_simple_only() -> None:
    assert isinstance(
        PDFontFactory.create_simple_font(_font_dict("TrueType")), PDTrueTypeFont
    )
    # A Type0 font is not a simple font -> None.
    assert (
        PDFontFactory.create_simple_font(_type0_with_descendant("CIDFontType2"))
        is None
    )


def test_create_cid_font_never_returns_from_top_level() -> None:
    # create_font never yields a bare CID font from a top-level dict, and a
    # Type0/Type1 dispatch isn't a PDCIDFont, so create_cid_font is None.
    assert PDFontFactory.create_cid_font(_font_dict("Type1")) is None
