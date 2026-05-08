from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDPageTree


def test_bare_page_root_repair_creates_typed_parent_wave313() -> None:
    raw_page = COSDictionary()
    raw_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]

    tree = PDPageTree(raw_page)
    repaired_root = tree.get_cos_object()

    assert repaired_root.get_name(COSName.TYPE) == "Pages"  # type: ignore[attr-defined]
    assert raw_page.get_dictionary_object(COSName.PARENT) is repaired_root  # type: ignore[attr-defined]
    kids = repaired_root.get_dictionary_object(COSName.KIDS)  # type: ignore[attr-defined]
    assert isinstance(kids, COSArray)
    assert kids.get_object(0) is raw_page


def test_bare_page_root_repair_supports_parent_based_removal_wave313() -> None:
    raw_page = COSDictionary()
    raw_page.set_item(COSName.TYPE, COSName.PAGE)  # type: ignore[attr-defined]
    tree = PDPageTree(raw_page)
    page = tree[0]

    assert page.get_cos_parent() is tree.get_cos_object()
    assert tree.remove(page) is True
    assert list(tree) == []
    assert tree.get_count() == 0
