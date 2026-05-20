from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel import PDPage, PDPageTree
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")
_PARENT = COSName.PARENT  # type: ignore[attr-defined]
_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_PAGE = COSName.PAGE  # type: ignore[attr-defined]
_PAGES = COSName.PAGES  # type: ignore[attr-defined]


def _page(label: str) -> PDPage:
    page = PDPage()
    page.get_cos_object().set_string(COSName.get_pdf_name("Label"), label)
    return page


def _label(page: PDPage) -> str | None:
    return page.get_cos_object().get_string(COSName.get_pdf_name("Label"))


def _raw_name_leaf(name: str, value: str) -> COSDictionary:
    leaf = COSDictionary()
    names = COSArray()
    names.add(COSString(name))
    names.add(COSString(value))
    leaf.set_item(_NAMES, names)
    limits = COSArray()
    limits.add(COSString(name))
    limits.add(COSString(name))
    leaf.set_item(_LIMITS, limits)
    return leaf


def test_page_tree_get_document_and_iterator_aliases() -> None:
    document = object()
    tree = PDPageTree(document=document)  # type: ignore[arg-type]
    tree.add(_page("first"))
    tree.add(_page("second"))

    assert tree.get_document() is document
    assert [_label(page) for page in tree.iterator()] == ["first", "second"]
    assert _label(tree.get(1)) == "second"


def test_page_tree_walk_ignores_parent_cycle() -> None:
    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    kids = COSArray()
    kids.add(root)
    root.set_item(_KIDS, kids)
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    tree = PDPageTree(root)

    assert list(tree) == []
    assert len(tree) == 0


def test_remove_uses_declared_nested_parent_and_updates_count_chain() -> None:
    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    root_kids = COSArray()
    root.set_item(_KIDS, root_kids)
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    child = COSDictionary()
    child.set_item(_TYPE, _PAGES)
    child.set_item(_PARENT, root)
    child_kids = COSArray()
    child.set_item(_KIDS, child_kids)
    child.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]
    root_kids.add(child)

    page = _page("nested")
    page.get_cos_object().set_item(_PARENT, child)
    child_kids.add(page.get_cos_object())

    tree = PDPageTree(root)

    assert tree.remove(page) is True
    assert child_kids.size() == 0
    assert tree.get_count() == 0
    child_count = child.get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(child_count, COSInteger)
    assert child_count.value == 0


def test_insert_before_rejects_target_missing_from_declared_parent() -> None:
    parent = COSDictionary()
    parent.set_item(_KIDS, COSArray())
    target = _page("target")
    target.get_cos_object().set_item(_PARENT, parent)

    tree = PDPageTree()

    with pytest.raises(ValueError, match="declared parent's /Kids"):
        tree.insert_before(_page("new"), target)


def test_insert_after_rejects_target_without_parent_kids_array() -> None:
    parent = COSDictionary()
    target = _page("target")
    target.get_cos_object().set_item(_PARENT, parent)

    tree = PDPageTree()

    with pytest.raises(ValueError, match="no /Kids parent array"):
        tree.insert_after(_page("new"), target)


def test_page_tree_clear_repairs_missing_kids_array() -> None:
    root = COSDictionary()
    root.set_item(_TYPE, _PAGES)
    root.set_int(COSName.COUNT, 3)  # type: ignore[attr-defined]
    tree = PDPageTree(root)

    tree.clear()

    kids = root.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    assert kids.size() == 0
    assert tree.get_count() == 0


def test_name_tree_get_kids_replaces_bad_child_with_empty_node(
    caplog: pytest.LogCaptureFixture,
) -> None:
    root_dict = COSDictionary()
    kids = COSArray()
    kids.add(COSName.get_pdf_name("BadChild"))
    root_dict.set_item(_KIDS, kids)
    root = PDStringNameTreeNode(root_dict)

    with caplog.at_level(logging.WARNING):
        wrapped = root.get_kids()

    assert wrapped is not None
    assert len(wrapped) == 1
    assert wrapped[0].get_parent() is root
    assert wrapped[0].get_names() is None
    assert "Bad child node at position 0" in caplog.text


def test_name_tree_odd_names_array_reads_complete_pairs_and_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tree = PDStringNameTreeNode()
    names = COSArray()
    names.add(COSString("alpha"))
    names.add(COSString("A"))
    names.add(COSString("orphan"))
    tree.get_cos_object().set_item(_NAMES, names)

    with caplog.at_level(logging.WARNING):
        assert tree.get_names() == {"alpha": "A"}

    assert "Names array has odd size: 3" in caplog.text


def test_name_tree_read_names_rejects_missing_value() -> None:
    tree = PDStringNameTreeNode()
    names = COSArray()
    names.add(COSString("alpha"))
    names.add(None)  # type: ignore[arg-type]
    tree.get_cos_object().set_item(_NAMES, names)

    # Per Wave 1360, ``_read_names_array`` no longer rejects ``None`` /
    # ``COSNull`` value slots in the base class — the embedded-files
    # name tree subclass tolerates them per upstream
    # ``TestEmbeddedFiles#testNullEmbeddedFile``. The string-typed
    # subclass still rejects non-string values inside
    # ``convert_cos_to_value``.
    with pytest.raises(OSError, match="COSString"):
        tree.get_names()


def test_name_tree_get_value_searches_child_with_invalid_limits() -> None:
    first = _raw_name_leaf("alpha", "A")
    limits = first.get_dictionary_object(_LIMITS)
    assert isinstance(limits, COSArray)
    limits.set(0, COSString("zulu"))
    limits.set(1, COSString("alpha"))

    root_dict = COSDictionary()
    kids = COSArray()
    kids.add(first)
    root_dict.set_item(_KIDS, kids)
    root = PDStringNameTreeNode(root_dict)

    assert root.get_value("alpha") == "A"


def test_name_tree_get_value_logs_for_empty_node(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tree = PDStringNameTreeNode()

    with caplog.at_level(logging.WARNING):
        assert tree.get_value("missing") is None

    assert 'NameTreeNode does not have "Names" nor "Kids" objects.' in caplog.text


def test_name_tree_limit_setters_store_null_for_none() -> None:
    leaf = PDStringNameTreeNode()

    leaf.set_lower_limit(None)
    leaf.set_upper_limit(None)

    limits = leaf.get_cos_object().get_dictionary_object(_LIMITS)
    assert isinstance(limits, COSArray)
    assert limits.get_string(0) is None
    assert limits.get_string(1) is None
