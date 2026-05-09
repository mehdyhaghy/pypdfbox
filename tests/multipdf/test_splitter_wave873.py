from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from tests.multipdf.test_splitter_cid_fonts import (
    _DESCENDANT_FONTS,
    _FONT,
    _FONT_DESCRIPTOR,
    _FONT_FILE2,
    _RESOURCES,
    _extract_font_file2,
)


def test_wave873_extract_font_file2_returns_none_for_missing_resource_chain() -> None:
    assert _extract_font_file2(COSDictionary()) is None

    page = COSDictionary()
    page.set_item(_RESOURCES, COSName.get_pdf_name("NotResources"))
    assert _extract_font_file2(page) is None


def test_wave873_extract_font_file2_returns_none_for_broken_font_chain() -> None:
    page = COSDictionary()
    resources = COSDictionary()
    page.set_item(_RESOURCES, resources)
    assert _extract_font_file2(page) is None

    resources.set_item(_FONT, COSName.get_pdf_name("NotFontDict"))
    assert _extract_font_file2(page) is None

    fonts = COSDictionary()
    resources.set_item(_FONT, fonts)
    fonts.set_item(COSName.get_pdf_name("F1"), COSName.get_pdf_name("NotFont"))
    assert _extract_font_file2(page) is None


@pytest.mark.parametrize("descendants", [COSDictionary(), COSArray()])
def test_wave873_extract_font_file2_returns_none_for_bad_descendants(
    descendants: object,
) -> None:
    page = COSDictionary()
    resources = COSDictionary()
    fonts = COSDictionary()
    f1 = COSDictionary()
    page.set_item(_RESOURCES, resources)
    resources.set_item(_FONT, fonts)
    fonts.set_item(COSName.get_pdf_name("F1"), f1)
    f1.set_item(_DESCENDANT_FONTS, descendants)

    assert _extract_font_file2(page) is None


def test_wave873_extract_font_file2_returns_none_for_broken_descriptor_chain() -> None:
    page = COSDictionary()
    resources = COSDictionary()
    fonts = COSDictionary()
    f1 = COSDictionary()
    descendants = COSArray()
    page.set_item(_RESOURCES, resources)
    resources.set_item(_FONT, fonts)
    fonts.set_item(COSName.get_pdf_name("F1"), f1)
    f1.set_item(_DESCENDANT_FONTS, descendants)

    descendants.add(COSName.get_pdf_name("NotCIDFont"))
    assert _extract_font_file2(page) is None

    cid = COSDictionary()
    descendants.set(0, cid)
    cid.set_item(_FONT_DESCRIPTOR, COSName.get_pdf_name("NotDescriptor"))
    assert _extract_font_file2(page) is None

    descriptor = COSDictionary()
    cid.set_item(_FONT_DESCRIPTOR, descriptor)
    descriptor.set_item(_FONT_FILE2, COSName.get_pdf_name("NotStream"))
    assert _extract_font_file2(page) is None
