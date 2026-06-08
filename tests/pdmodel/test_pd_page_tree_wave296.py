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


def test_repaired_null_kid_has_no_synthetic_parent_or_inheritance_wave296() -> None:
    tree, inner = _nested_tree_with_null_kid()

    [page] = list(tree)

    assert page.get_cos_parent() is None
    assert page.get_rotation() == 0
    assert inner.get_dictionary_object(COSName.KIDS)[0] is page.get_cos_object()  # type: ignore[attr-defined,index]


def test_repaired_null_kid_without_parent_is_not_removed_from_nested_node_wave296() -> None:
    tree, inner = _nested_tree_with_null_kid()
    [page] = list(tree)

    assert tree.remove(page) is False

    assert [item.get_cos_object() for item in tree] == [page.get_cos_object()]
    assert tree.get_count() == 1
    count = inner.get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(count, COSInteger)
    assert count.value == 1
