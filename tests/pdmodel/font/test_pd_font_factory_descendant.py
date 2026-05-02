"""Coverage for PDFontFactory.create_descendant_font (Wave 186).

Mirrors PDFBox's package-private
``PDFontFactory.createDescendantFont(COSDictionary, PDType0Font)``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")


def _descendant_dict(subtype: str, base_font: str = "Test") -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_name(_SUBTYPE, subtype)
    d.set_name(_BASE_FONT, base_font)
    return d


# ---------- positive dispatch ----------


def test_create_descendant_font_returns_cid_type0_for_cid_font_type0_subtype() -> None:
    d = _descendant_dict("CIDFontType0")
    font = PDFontFactory.create_descendant_font(d)
    assert isinstance(font, PDCIDFontType0)
    assert font.get_cos_object() is d


def test_create_descendant_font_returns_cid_type2_for_cid_font_type2_subtype() -> None:
    d = _descendant_dict("CIDFontType2")
    font = PDFontFactory.create_descendant_font(d)
    assert isinstance(font, PDCIDFontType2)
    assert font.get_cos_object() is d


def test_create_descendant_font_forwards_parent_to_subclass() -> None:
    parent = PDType0Font()
    d = _descendant_dict("CIDFontType2")
    font = PDFontFactory.create_descendant_font(d, parent)
    assert isinstance(font, PDCIDFontType2)
    assert font.get_parent() is parent


def test_create_descendant_font_parent_defaults_to_none() -> None:
    d = _descendant_dict("CIDFontType0")
    font = PDFontFactory.create_descendant_font(d)
    assert isinstance(font, PDCIDFontType0)
    assert font.get_parent() is None


# ---------- error / edge cases ----------


def test_create_descendant_font_returns_none_for_none_input() -> None:
    assert PDFontFactory.create_descendant_font(None) is None  # type: ignore[arg-type]


def test_create_descendant_font_raises_type_error_for_non_dict() -> None:
    with pytest.raises(TypeError):
        PDFontFactory.create_descendant_font("not a dict")  # type: ignore[arg-type]


def test_create_descendant_font_raises_for_non_cid_subtype() -> None:
    """Mirrors upstream's ``IOException`` for an invalid descendant type
    — pypdfbox uses :class:`OSError` (its IOException analogue per
    project conventions)."""
    d = _descendant_dict("Type1")  # not a CID subtype
    with pytest.raises(OSError):
        PDFontFactory.create_descendant_font(d)


def test_create_descendant_font_raises_for_missing_subtype() -> None:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    # No /Subtype.
    with pytest.raises(OSError):
        PDFontFactory.create_descendant_font(d)


def test_create_descendant_font_raises_for_top_level_type0() -> None:
    """A composite Type0 font dict isn't a *descendant* — calling
    ``create_descendant_font`` on it should raise rather than silently
    accept (the descendant must be a CIDFont)."""
    d = _descendant_dict("Type0")
    with pytest.raises(OSError):
        PDFontFactory.create_descendant_font(d)


# ---------- round-trip via PDType0Font ----------


def test_create_descendant_font_returns_same_subclass_as_type0_resolution() -> None:
    """The descendant wrapping done by :meth:`create_descendant_font`
    must match what :meth:`PDType0Font.get_descendant_font` returns when
    the same dict is hung off a Type0 parent — both paths feed the
    renderer / metric layers and need to agree on the concrete subclass.
    """
    from pypdfbox.cos import COSArray

    d = _descendant_dict("CIDFontType2")
    parent = PDType0Font()
    parent_dict = parent.get_cos_object()
    arr = COSArray()
    arr.add(d)
    parent_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)

    via_factory = PDFontFactory.create_descendant_font(d, parent)
    via_parent = parent.get_descendant_font()

    assert type(via_factory) is type(via_parent)
    assert via_factory.get_cos_object() is via_parent.get_cos_object()
