"""PDFBOX-6228 — ``PDStructureElement.get_structure_tree_root`` must not loop
forever on a cyclic ``/P`` parent chain.

Upstream added a visited set to the private ``getStructureTreeRoot()`` walk and
logs ``"Element ignored: " + dict`` before returning ``null``. Accessibility
consumers reach the role map / class map through this walk, so a hand-crafted
(or corrupt) structure tree that loops must degrade to "no root", not hang.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)

_P = COSName.get_pdf_name("P")
_TYPE = COSName.get_pdf_name("Type")
_LOGGER = (
    "pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element"
)


def _elem(structure_type: str) -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_name(_TYPE, "StructElem")
    dictionary.set_name("S", structure_type)
    return dictionary


def test_structure_tree_root_self_cycle_returns_none() -> None:
    """An element that is its own ``/P`` terminates with ``None``."""
    dictionary = _elem("P")
    dictionary.set_item(_P, dictionary)

    element = PDStructureElement(dictionary)
    assert element.get_structure_tree_root() is None


def test_structure_tree_root_two_node_cycle_returns_none() -> None:
    """child -> parent -> child is caught on the second visit."""
    child = _elem("Span")
    parent = _elem("P")
    child.set_item(_P, parent)
    parent.set_item(_P, child)

    element = PDStructureElement(child)
    assert element.get_structure_tree_root() is None


def test_structure_tree_root_cycle_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Upstream logs the offending dictionary at WARNING level."""
    child = _elem("Span")
    parent = _elem("P")
    child.set_item(_P, parent)
    parent.set_item(_P, child)

    element = PDStructureElement(child)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        assert element.get_structure_tree_root() is None

    assert any("Element ignored" in record.getMessage() for record in caplog.records)


def test_structure_tree_root_deep_acyclic_chain_still_resolves() -> None:
    """The walk is unbounded, as upstream's is — a 64-deep chain still finds
    the root (the previous pypdfbox port capped the walk at 16 hops)."""
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")

    node = root
    for _ in range(64):
        child = _elem("Span")
        child.set_item(_P, node)
        node = child

    element = PDStructureElement(node)
    tree_root = element.get_structure_tree_root()
    assert tree_root is not None
    assert tree_root.get_cos_object() is root


def test_structure_tree_root_absent_parent_returns_none() -> None:
    """No ``/P`` at all is still just "no root"."""
    element = PDStructureElement(_elem("P"))
    assert element.get_structure_tree_root() is None


def test_is_root_attached_false_for_cyclic_chain() -> None:
    """The public predicate built on the walk stays consistent."""
    child = _elem("Span")
    parent = _elem("P")
    child.set_item(_P, parent)
    parent.set_item(_P, child)

    assert PDStructureElement(child).is_root_attached() is False
