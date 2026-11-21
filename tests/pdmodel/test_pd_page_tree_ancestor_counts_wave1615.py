"""PDFBOX-6318: cycle-safe ancestor /Count updates and orphan guards."""

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDPage, PDPageTree


def _count(node: COSDictionary) -> int:
    value = node.get_dictionary_object(COSName.COUNT)  # type: ignore[attr-defined]
    assert isinstance(value, COSInteger)
    return value.value


def _nested_tree() -> tuple[PDPageTree, COSDictionary, COSDictionary]:
    root = COSDictionary()
    root.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner = COSDictionary()
    inner.set_item(COSName.TYPE, COSName.PAGES)  # type: ignore[attr-defined]
    inner.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    inner.set_item(COSName.KIDS, COSArray())  # type: ignore[attr-defined]
    inner.set_int(COSName.COUNT, 0)  # type: ignore[attr-defined]
    root_kids = COSArray()
    root_kids.add(inner)
    root.set_item(COSName.KIDS, root_kids)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 0)  # type: ignore[attr-defined]
    return PDPageTree(root), root, inner


def test_add_with_self_parent_root_increments_once_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tree = PDPageTree()
    root = tree.get_root()
    root.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.pd_page_tree"):
        tree.add(PDPage())
    assert _count(root) == 1
    assert "cycle" in caplog.text


def test_remove_from_nested_node_decrements_every_ancestor() -> None:
    tree, root, inner = _nested_tree()
    page = PDPage()
    page.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    inner_kids = inner.get_dictionary_object(COSName.KIDS)  # type: ignore[attr-defined]
    assert isinstance(inner_kids, COSArray)
    inner_kids.add(page.get_cos_object())
    inner.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    assert tree.remove(page) is True
    assert _count(inner) == 0
    assert _count(root) == 0


def test_remove_with_parent_cycle_terminates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    tree, root, inner = _nested_tree()
    root.set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    page = PDPage()
    page.get_cos_object().set_item(COSName.PARENT, inner)  # type: ignore[attr-defined]
    inner_kids = inner.get_dictionary_object(COSName.KIDS)  # type: ignore[attr-defined]
    assert isinstance(inner_kids, COSArray)
    inner_kids.add(page.get_cos_object())
    inner.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]
    root.set_int(COSName.COUNT, 1)  # type: ignore[attr-defined]

    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.pd_page_tree"):
        assert tree.remove(page) is True
    assert _count(inner) == 0
    assert _count(root) == 0
    assert "cycle" in caplog.text


def test_insert_with_parent_cycle_warns(caplog: pytest.LogCaptureFixture) -> None:
    tree = PDPageTree()
    root = tree.get_root()
    first = PDPage()
    tree.add(first)
    root.set_item(COSName.PARENT, root)  # type: ignore[attr-defined]
    with caplog.at_level(logging.WARNING, logger="pypdfbox.pdmodel.pd_page_tree"):
        tree.insert_before(PDPage(), first)
    assert _count(root) == 2
    assert "cycle" in caplog.text


def test_remove_orphan_warns_until_3_0() -> None:
    # Upstream throws; 2.x warns and returns False (raises in 3.0).
    with pytest.deprecated_call(match="orphan"):
        assert PDPageTree().remove(PDPage()) is False


def test_remove_parent_without_kids_warns_until_3_0() -> None:
    page = PDPage()
    page.get_cos_object().set_item(COSName.PARENT, COSDictionary())  # type: ignore[attr-defined]
    with pytest.deprecated_call(match="no /Kids"):
        assert PDPageTree().remove(page) is False
