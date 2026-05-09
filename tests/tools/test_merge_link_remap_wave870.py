from __future__ import annotations

import tests.tools.test_merge_link_remap as remap_helpers
from pypdfbox.cos import COSArray, COSDictionary, COSName


def test_wave870_link_dest_target_returns_none_without_annotation_array() -> None:
    page = COSDictionary()
    page.set_item(remap_helpers._ANNOTS, COSDictionary())

    assert remap_helpers._link_dest_target(page) is None


def test_wave870_link_dest_target_skips_malformed_and_non_link_annots() -> None:
    page = COSDictionary()
    annots = COSArray()
    annots.add(COSName.get_pdf_name("NotADictionary"))

    non_link = COSDictionary()
    non_link.set_name(remap_helpers._SUBTYPE, "Text")
    annots.add(non_link)

    empty_link_dest = COSDictionary()
    empty_link_dest.set_name(remap_helpers._SUBTYPE, "Link")
    empty_link_dest.set_item(remap_helpers._DEST, COSArray())
    annots.add(empty_link_dest)

    page.set_item(remap_helpers._ANNOTS, annots)

    assert remap_helpers._link_dest_target(page) is None
