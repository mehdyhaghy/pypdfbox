from __future__ import annotations

from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)


def test_wave345_append_kid_structure_element_sets_parent_pointer() -> None:
    parent = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")

    parent.append_kid(child)

    assert child.get_parent() is parent.get_cos_object()


def test_wave345_remove_kid_structure_element_clears_parent_pointer() -> None:
    parent = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    parent.append_kid(child)

    assert parent.remove_kid(child) is True

    assert child.get_parent() is None


def test_wave345_failed_remove_kid_structure_element_leaves_parent_pointer() -> None:
    parent = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    child.set_parent(parent)

    assert parent.remove_kid(child) is False

    assert child.get_parent() is parent.get_cos_object()
