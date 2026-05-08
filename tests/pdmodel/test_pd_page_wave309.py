from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDPage


def test_get_cos_parent_accepts_legacy_p_alias_wave309() -> None:
    page_dict = COSDictionary()
    parent = COSDictionary()
    page_dict.set_item(COSName.get_pdf_name("P"), parent)

    page = PDPage(page_dict)

    assert page.get_cos_parent() is parent


def test_get_cos_parent_prefers_parent_over_legacy_p_alias_wave309() -> None:
    page_dict = COSDictionary()
    parent = COSDictionary()
    legacy_parent = COSDictionary()
    page_dict.set_item(COSName.PARENT, parent)  # type: ignore[attr-defined]
    page_dict.set_item(COSName.get_pdf_name("P"), legacy_parent)

    page = PDPage(page_dict)

    assert page.get_cos_parent() is parent
