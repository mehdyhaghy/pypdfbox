"""Hand-written tests for ``PDStructureElementNameTreeNode``.

Covers the typed ``convert_cos_to_pd`` / ``convertCOSToPD`` factory the
``/IDTree`` name-tree subclass overrides.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureElementNameTreeNode,
)


def test_convert_cos_to_pd_returns_structure_element() -> None:
    """``convert_cos_to_pd`` mirrors upstream
    ``PDStructureElementNameTreeNode.convertCOSToPD`` (Java lines 51-59)
    — typed factory wrapping a COSDictionary as ``PDStructureElement``."""
    tree = PDStructureElementNameTreeNode()
    d = COSDictionary()
    elt = tree.convert_cos_to_pd(d)
    assert isinstance(elt, PDStructureElement)
    assert elt.get_cos_object() is d


def test_convert_cos_to_pd_rejects_non_dictionary() -> None:
    """Upstream raises IOException when the leaf is not a COSDictionary;
    pypdfbox currently surfaces that as TypeError (see ``convert_cos_to_value``)."""
    tree = PDStructureElementNameTreeNode()
    with pytest.raises((TypeError, OSError)):
        tree.convert_cos_to_pd(COSString("nope"))


def test_create_child_node_returns_same_type() -> None:
    tree = PDStructureElementNameTreeNode()
    child = tree.create_child_node(COSDictionary())
    assert isinstance(child, PDStructureElementNameTreeNode)
