"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/PDNameTreeNodeTest.java``
(PDFBox 3.0.x). Kids/Limits behaviour, value lookup across siblings, and
empty-tree edge cases — translated to pytest using PDStringNameTreeNode as
the upstream test's COSObjectable concrete subclass stand-in.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode
from pypdfbox.pdmodel.common.pd_string_name_tree_node import PDStringNameTreeNode

_KIDS = COSName.KIDS  # type: ignore[attr-defined]
_NAMES = COSName.get_pdf_name("Names")
_LIMITS = COSName.get_pdf_name("Limits")


@pytest.fixture
def empty_root() -> PDStringNameTreeNode:
    """Equivalent to upstream's ``@BeforeEach setUp`` allocating a fresh root."""
    return PDStringNameTreeNode()


def test_upper_limit(empty_root: PDStringNameTreeNode) -> None:
    """Port of ``testUpperLimit`` — set+get round-trips a parented node."""
    parent = PDStringNameTreeNode()
    leaf = PDStringNameTreeNode()
    leaf.set_parent(parent)
    leaf.set_upper_limit("foo")
    assert leaf.get_upper_limit() == "foo"


def test_lower_limit(empty_root: PDStringNameTreeNode) -> None:
    """Port of ``testLowerLimit`` — symmetric to upper-limit round-trip."""
    parent = PDStringNameTreeNode()
    leaf = PDStringNameTreeNode()
    leaf.set_parent(parent)
    leaf.set_lower_limit("foo")
    assert leaf.get_lower_limit() == "foo"


def test_get_value_with_no_names_or_kids(empty_root: PDStringNameTreeNode) -> None:
    """Port of upstream behaviour: missing /Names AND /Kids returns None.

    Upstream prints a warning and returns null; we log the same and return
    None.
    """
    assert empty_root.get_value("missing") is None


def test_get_value_walks_into_correct_kid() -> None:
    """Port of ``testGetValue`` — descent picks the kid whose Limits cover
    the requested key, and only that kid."""
    leaf_one = PDStringNameTreeNode()
    leaf_one.set_names({"a": "A", "b": "B"})

    leaf_two = PDStringNameTreeNode()
    leaf_two.set_names({"y": "Y", "z": "Z"})

    root = PDStringNameTreeNode()
    root.set_kids([leaf_one, leaf_two])

    assert root.get_value("a") == "A"
    assert root.get_value("z") == "Z"
    # Out-of-range key still returns None even when limits are present.
    assert root.get_value("m") is None


def test_get_kids_returns_none_when_absent(empty_root: PDStringNameTreeNode) -> None:
    """Port of ``testGetKids`` for the no-children case."""
    assert empty_root.get_kids() is None


def test_get_names_returns_none_when_absent(empty_root: PDStringNameTreeNode) -> None:
    """Port of ``testGetNames`` for the no-names case."""
    assert empty_root.get_names() is None


def test_set_names_writes_sorted_pairs() -> None:
    """Port of ``testSetNames``: ``/Names`` array stores ``[k1 v1 k2 v2 ...]``
    in sorted-key order regardless of insertion order."""
    tree = PDStringNameTreeNode()
    tree.set_names({"banana": "B", "apple": "A"})

    arr = tree.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(arr, COSArray)
    assert arr.size() == 4
    assert arr.get_object(0).get_string() == "apple"
    assert arr.get_object(1).get_string() == "A"
    assert arr.get_object(2).get_string() == "banana"
    assert arr.get_object(3).get_string() == "B"


def test_set_kids_writes_kids_array_and_clears_names() -> None:
    """Port of ``testSetKids``: setting kids clears any existing /Names and
    populates a /Kids array of dictionaries."""
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_names({"orig": "O"})
    root.set_kids([leaf])

    assert root.get_cos_object().get_dictionary_object(_NAMES) is None
    kids_array = root.get_cos_object().get_dictionary_object(_KIDS)
    assert isinstance(kids_array, COSArray)
    assert kids_array.size() == 1
    assert isinstance(kids_array.get_object(0), COSDictionary)


def test_get_value_via_existing_cos_dictionary() -> None:
    """Port of ``testGetValueFromExisting``: feed a hand-built COSDictionary
    representing a root with a single /Names entry through the wrapper."""
    arr = COSArray()
    arr.add(COSString("alpha"))
    arr.add(COSString("payload"))
    dic = COSDictionary()
    dic.set_item(_NAMES, arr)

    tree = PDStringNameTreeNode(dic)
    assert tree.get_value("alpha") == "payload"
    assert tree.get_names() == {"alpha": "payload"}


def test_pd_name_tree_node_abstract_constructor_rejects_direct_instantiation() -> None:
    """Upstream relies on abstract-method enforcement — Python emits TypeError
    rather than Java's ``InstantiationException``."""
    with pytest.raises(TypeError):
        PDNameTreeNode()  # type: ignore[abstract]


def test_set_lower_upper_limit_at_root_does_not_leak() -> None:
    """Port of ``testRootLimitsSuppressed``: a root node must not carry
    /Limits even if the calculator runs after set_kids."""
    leaf = PDStringNameTreeNode()
    leaf.set_names({"a": "A"})
    root = PDStringNameTreeNode()
    root.set_kids([leaf])

    assert root.get_cos_object().get_dictionary_object(_LIMITS) is None
