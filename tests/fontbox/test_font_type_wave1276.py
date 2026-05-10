"""Wave 1276 — :class:`pypdfbox.fontbox.font_type.FontType` parity.

Mirrors upstream ``PDFontFactory$FontType`` (java L64-114) coverage:
the descendant-subtype-string classifying constructor (L73-88), the
direct ``COSName`` constructor (L90-94), the no-subtype constructor
(L96-99), :meth:`get_subtype` (L101-104), and :meth:`is_cid_subtype`
(L106-113).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.fontbox.font_type import FontType

# ---------- constructor — string subtype classification ----------


@pytest.mark.parametrize(
    "subtype_str,expected",
    [
        ("Type1", "CIDFontType0"),
        ("Type1C", "CIDFontType0"),
        ("TrueType", "CIDFontType2"),
        ("OpenType", "CIDFontType2"),
    ],
)
def test_subtype_string_classifies_to_cid_name(
    subtype_str: str, expected: str
) -> None:
    ft = FontType(COSName.get_pdf_name("Type0"), subtype_str)
    assert ft.get_subtype() == COSName.get_pdf_name(expected)


def test_unrecognized_subtype_string_yields_none() -> None:
    ft = FontType(COSName.get_pdf_name("Type0"), "Type3")
    assert ft.get_subtype() is None


# ---------- constructor — direct COSName subtype ----------


def test_direct_cos_name_subtype_is_preserved() -> None:
    direct = COSName.get_pdf_name("CIDFontType0")
    ft = FontType(COSName.get_pdf_name("Type0"), direct)
    # Identity-preserving: passed-through, not re-classified.
    assert ft.get_subtype() is direct


def test_no_subtype_constructor_yields_none() -> None:
    ft = FontType(COSName.get_pdf_name("Type1"))
    assert ft.get_subtype() is None


# ---------- is_cid_subtype gates on /Type0 ----------


def test_is_cid_subtype_true_for_type0_with_matching_descendant() -> None:
    cid0 = COSName.get_pdf_name("CIDFontType0")
    ft = FontType(COSName.get_pdf_name("Type0"), "Type1")
    assert ft.is_cid_subtype(cid0) is True


def test_is_cid_subtype_false_for_type0_with_mismatching_descendant() -> None:
    cid2 = COSName.get_pdf_name("CIDFontType2")
    ft = FontType(COSName.get_pdf_name("Type0"), "Type1")  # → CIDFontType0
    assert ft.is_cid_subtype(cid2) is False


def test_is_cid_subtype_false_for_non_type0_even_with_cid_subtype() -> None:
    cid0 = COSName.get_pdf_name("CIDFontType0")
    # Direct construction so subtype is exactly CIDFontType0 but /Type is
    # /Type1 — upstream returns False unconditionally for non-Type0.
    ft = FontType(COSName.get_pdf_name("Type1"), cid0)
    assert ft.is_cid_subtype(cid0) is False


def test_is_cid_subtype_false_when_subtype_is_none() -> None:
    cid0 = COSName.get_pdf_name("CIDFontType0")
    ft = FontType(COSName.get_pdf_name("Type0"))
    assert ft.is_cid_subtype(cid0) is False
