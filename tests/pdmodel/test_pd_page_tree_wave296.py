from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull
from pypdfbox.pdmodel import PDPageTree


def _nested_tree_with_null_kid() -> tuple[PDPageTree, COSDictionary]:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    root_kids = COSArray()
    root.set_item(COSName.KIDS, root_kids)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    inner = COSDictionary()
    inner.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    inner.set_int(COSName.get_pdf_name("Rotate"), 90)
    inner.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]
    inner_kids = COSArray()
    inner_kids.add(COSNull.NULL)
    inner.set_item(COSName.KIDS, inner_kids)  # type: ignore[attr-defined]

    root_kids.add(inner)
    return PDPageTree(root), inner


def test_repaired_null_kid_inherits_from_owning_page_tree_node_wave296() -> None:
    tree, inner = _nested_tree_with_null_kid()

    [page] = list(tree)

    assert page.get_cos_parent() is inner
    assert page.get_rotation() == 90


def test_repaired_null_kid_can_be_removed_from_nested_node_wave296() -> None:
    tree, inner = _nested_tree_with_null_kid()
    [page] = list(tree)

    assert tree.remove(page) is True

    assert list(tree) == []
    assert tree.get_count() == 0
    count = inner.get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(count, COSInteger)
    assert count.value == 0
