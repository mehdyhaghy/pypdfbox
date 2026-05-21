"""PDType0Font.is_descendant_cjk + is_cmap_predefined predicates.

Wave 1369 round-out for the predicate pair PDFBox uses to gate the
ToUnicode UCS2 fallback (PDFBOX-6022 / §9.10.2).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def _build_type0(
    encoding_value: object,
    registry: str = "Adobe",
    ordering: str = "Identity",
) -> PDType0Font:
    descendant = COSDictionary()
    descendant.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    descendant.set_item(
        COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2")
    )
    descendant.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))
    info = COSDictionary()
    info.set_item(COSName.get_pdf_name("Registry"), COSName.get_pdf_name(registry))
    info.set_item(COSName.get_pdf_name("Ordering"), COSName.get_pdf_name(ordering))
    info.set_item(COSName.get_pdf_name("Supplement"), COSInteger.get(0))
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), info)
    arr = COSArray()
    arr.add(descendant)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))
    font_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_value)
    return PDType0Font(font_dict)


@pytest.mark.parametrize(
    "ordering,expected",
    [
        ("GB1", True),
        ("CNS1", True),
        ("Japan1", True),
        ("Korea1", True),
        ("Identity", False),
        ("KR", False),  # not in the four-collection CJK set
    ],
)
def test_is_descendant_cjk_for_each_ordering(
    ordering: str, expected: bool
) -> None:
    font = _build_type0(
        COSName.get_pdf_name("Identity-H"),
        registry="Adobe",
        ordering=ordering,
    )
    assert font.is_descendant_cjk() is expected


def test_is_descendant_cjk_false_for_non_adobe_registry() -> None:
    # The CJK predicate gates strictly on Adobe registry.
    font = _build_type0(
        COSName.get_pdf_name("Identity-H"),
        registry="CustomVendor",
        ordering="Japan1",
    )
    assert font.is_descendant_cjk() is False


def test_is_descendant_cjk_false_when_no_descendant() -> None:
    # No /DescendantFonts at all — predicate gracefully returns False.
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )
    font = PDType0Font(font_dict)
    assert font.is_descendant_cjk() is False


def test_is_cmap_predefined_true_for_cosname_encoding() -> None:
    # /Encoding is a COSName -> predefined CMap reference.
    font = _build_type0(COSName.get_pdf_name("Identity-H"))
    assert font.is_cmap_predefined() is True


def test_is_cmap_predefined_false_for_embedded_cmap_stream() -> None:
    # Embedded CMap streams produce False even if they're parseable.
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("CMap"))
    font = _build_type0(stream)
    assert font.is_cmap_predefined() is False


def test_is_cmap_predefined_false_when_no_encoding() -> None:
    # An /Encoding entry is required for a well-formed Type 0 font; absent
    # one the predicate returns False rather than raising.
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))
    font = PDType0Font(font_dict)
    assert font.is_cmap_predefined() is False


@pytest.mark.parametrize(
    "encoding_name,ordering,expect_predefined,expect_cjk",
    [
        # The two combinations that satisfy both predicates simultaneously
        # — the PDFBOX-6022 UCS2-fallback trigger.
        ("Identity-H", "Japan1", True, True),
        ("Identity-V", "GB1", True, True),
        # Only one predicate holds.
        ("Identity-H", "Identity", True, False),
        # Both predicates false (embedded CMap, non-CJK descendant).
    ],
)
def test_pdfbox_6022_trigger_matrix(
    encoding_name: str,
    ordering: str,
    expect_predefined: bool,
    expect_cjk: bool,
) -> None:
    font = _build_type0(
        COSName.get_pdf_name(encoding_name),
        registry="Adobe",
        ordering=ordering,
    )
    assert font.is_cmap_predefined() is expect_predefined
    assert font.is_descendant_cjk() is expect_cjk
