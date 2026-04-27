"""Parity tests for ``PDFontFactory`` static-method surface beyond the
core ``create_font`` dispatch — covers ``create_simple_font``,
``create_cid_font``, ``create_default_font`` and ``is_supported_subtype``.

Mirrors PDFBox ``PDFontFactory`` (org.apache.pdfbox.pdmodel.font).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_FONT_FILE3: COSName = COSName.get_pdf_name("FontFile3")


def _make_font_dict(subtype: str) -> COSDictionary:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, subtype)
    return raw


def _attach_font_file3(font_dict: COSDictionary, ff3_subtype: str) -> COSStream:
    descriptor = COSDictionary()
    stream = COSStream()
    stream.set_name(_SUBTYPE, ff3_subtype)
    descriptor.set_item(_FONT_FILE3, stream)
    font_dict.set_item(_FONT_DESCRIPTOR, descriptor)
    return stream


# ---------- create_default_font ----------


def test_create_default_font_helvetica_returns_pd_type1_font() -> None:
    out = PDFontFactory.create_default_font("Helvetica")
    assert isinstance(out, PDType1Font)
    assert out.get_name() == "Helvetica"
    assert out.get_subtype() == PDType1Font.SUB_TYPE


def test_create_default_font_unknown_falls_back_to_helvetica() -> None:
    out = PDFontFactory.create_default_font("Bogus")
    assert isinstance(out, PDType1Font)
    assert out.get_name() == Standard14Fonts.HELVETICA


def test_create_default_font_no_arg_defaults_to_helvetica() -> None:
    out = PDFontFactory.create_default_font()
    assert isinstance(out, PDType1Font)
    assert out.get_name() == Standard14Fonts.HELVETICA


def test_create_default_font_resolves_alias_to_canonical() -> None:
    # "ArialMT" is a registered Standard14 alias for Helvetica — the
    # factory should canonicalise the /BaseFont it writes.
    out = PDFontFactory.create_default_font("ArialMT")
    assert isinstance(out, PDType1Font)
    assert out.get_name() == Standard14Fonts.HELVETICA


def test_create_default_font_picks_named_standard14() -> None:
    out = PDFontFactory.create_default_font(Standard14Fonts.TIMES_BOLD)
    assert isinstance(out, PDType1Font)
    assert out.get_name() == Standard14Fonts.TIMES_BOLD


# ---------- is_supported_subtype ----------


@pytest.mark.parametrize(
    "subtype",
    [
        "Type0",
        "Type1",
        "Type1C",
        "MMType1",
        "Type3",
        "TrueType",
        "CIDFontType0",
        "CIDFontType2",
    ],
)
def test_is_supported_subtype_true_for_known(subtype: str) -> None:
    assert PDFontFactory.is_supported_subtype(subtype) is True


@pytest.mark.parametrize("subtype", ["Bogus", "", "type1", "OpenType"])
def test_is_supported_subtype_false_for_unknown(subtype: str) -> None:
    assert PDFontFactory.is_supported_subtype(subtype) is False


def test_is_supported_subtype_none_is_false() -> None:
    assert PDFontFactory.is_supported_subtype(None) is False


# ---------- create_simple_font ----------


def test_create_simple_font_on_type1_returns_pd_type1_font() -> None:
    raw = _make_font_dict("Type1")
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDType1Font)
    assert isinstance(out, PDSimpleFont)


def test_create_simple_font_on_type0_returns_none() -> None:
    raw = _make_font_dict("Type0")
    assert PDFontFactory.create_simple_font(raw) is None


def test_create_simple_font_on_true_type_returns_pd_true_type_font() -> None:
    raw = _make_font_dict("TrueType")
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDTrueTypeFont)
    assert isinstance(out, PDSimpleFont)


def test_create_simple_font_on_type3_returns_pd_type3_font() -> None:
    raw = _make_font_dict("Type3")
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDType3Font)
    assert isinstance(out, PDSimpleFont)


def test_create_simple_font_on_type1c_returns_pd_type1c_font() -> None:
    raw = _make_font_dict("Type1")
    _attach_font_file3(raw, "Type1C")
    out = PDFontFactory.create_simple_font(raw)
    assert isinstance(out, PDType1CFont)
    assert isinstance(out, PDSimpleFont)


def test_create_simple_font_on_unknown_returns_none() -> None:
    raw = _make_font_dict("CIDFontType2")
    assert PDFontFactory.create_simple_font(raw) is None


# ---------- create_cid_font ----------


def test_create_cid_font_on_cid_font_type0_with_cff_returns_pd_cid_font_type0() -> None:
    raw = _make_font_dict("CIDFontType0")
    _attach_font_file3(raw, "CIDFontType0C")
    out = PDFontFactory.create_cid_font(raw)
    assert isinstance(out, PDCIDFontType0)
    assert isinstance(out, PDCIDFont)


def test_create_cid_font_on_simple_font_returns_none() -> None:
    raw = _make_font_dict("Type1")
    assert PDFontFactory.create_cid_font(raw) is None


def test_create_cid_font_on_type0_returns_none() -> None:
    # /Type0 is the wrapping composite font, not a CID font itself.
    raw = _make_font_dict("Type0")
    assert PDFontFactory.create_cid_font(raw) is None


def test_create_cid_font_on_bare_cid_font_type0_returns_none() -> None:
    # Without the CFF /FontFile3 marker, bare CIDFontType0 is reached via
    # the Type0 descendant path; the top-level factory returns None.
    raw = _make_font_dict("CIDFontType0")
    assert PDFontFactory.create_cid_font(raw) is None


# ---------- create_font: signature parity (resource_cache kwarg accepted) ----------


def test_create_font_accepts_resource_cache_kwarg() -> None:
    raw = _make_font_dict("Type1")
    # Behavior must be identical with and without the parity kwarg.
    out = PDFontFactory.create_font(raw, resource_cache=None)
    assert isinstance(out, PDType1Font)


def test_create_font_resource_cache_is_ignored_by_dispatch() -> None:
    raw = _make_font_dict("Type0")
    sentinel = object()
    out = PDFontFactory.create_font(raw, resource_cache=sentinel)
    assert isinstance(out, PDType0Font)
