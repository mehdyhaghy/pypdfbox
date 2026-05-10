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


# ---------- TestPDNameTreeNode (Java) port: 3-level limits propagation ----------
# Ported from
# ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/TestPDNameTreeNode.java``
# (PDFBox 3.0.x). The upstream fixture builds a 3-level tree mirroring the
# typical name-tree shape — root with two intermediate kids, each pointing
# at a populated leaf — and asserts that ``/Limits`` are calculated bottom
# up while staying suppressed at the root.


def _populate(node: PDStringNameTreeNode, names: dict[str, str]) -> None:
    node.set_names(names)


@pytest.fixture
def three_level_tree() -> dict[str, PDStringNameTreeNode]:
    """Builds the same five-node tree as upstream's ``setUp``.

    Layout::

        node1 (root)
        ├── node2
        │   └── node5  {"Actinium" .. "Astatine"}
        └── node4
            └── node24 {"Xenon" .. "Zirconium"}
    """
    node5 = PDStringNameTreeNode()
    _populate(
        node5,
        {
            "Actinium": "89",
            "Aluminum": "13",
            "Americium": "95",
            "Antimony": "51",
            "Argon": "18",
            "Arsenic": "33",
            "Astatine": "85",
        },
    )

    node24 = PDStringNameTreeNode()
    _populate(
        node24,
        {
            "Xenon": "54",
            "Ytterbium": "70",
            "Yttrium": "39",
            "Zinc": "30",
            "Zirconium": "40",
        },
    )

    node2 = PDStringNameTreeNode()
    node2.set_kids([node5])

    node4 = PDStringNameTreeNode()
    node4.set_kids([node24])

    node1 = PDStringNameTreeNode()
    node1.set_kids([node2, node4])

    return {
        "node1": node1,
        "node2": node2,
        "node4": node4,
        "node5": node5,
        "node24": node24,
    }


def test_three_level_upper_limit(
    three_level_tree: dict[str, PDStringNameTreeNode],
) -> None:
    """Port of ``testUpperLimit``: per-level upper limits propagate from
    populated leaves into intermediate nodes; root has none."""
    assert three_level_tree["node5"].get_upper_limit() == "Astatine"
    assert three_level_tree["node2"].get_upper_limit() == "Astatine"

    assert three_level_tree["node24"].get_upper_limit() == "Zirconium"
    assert three_level_tree["node4"].get_upper_limit() == "Zirconium"

    assert three_level_tree["node1"].get_upper_limit() is None


def test_three_level_lower_limit(
    three_level_tree: dict[str, PDStringNameTreeNode],
) -> None:
    """Port of ``testLowerLimit``: symmetric to ``testUpperLimit``."""
    assert three_level_tree["node5"].get_lower_limit() == "Actinium"
    assert three_level_tree["node2"].get_lower_limit() == "Actinium"

    assert three_level_tree["node24"].get_lower_limit() == "Xenon"
    assert three_level_tree["node4"].get_lower_limit() == "Xenon"

    assert three_level_tree["node1"].get_lower_limit() is None


def test_convert_cos_to_pd_alias_matches_convert_cos_to_value() -> None:
    """``convert_cos_to_pd`` is the upstream-named hook (``convertCOSToPD``
    at ``PDNameTreeNode.java`` line 303) and must default to the same
    behaviour as :meth:`convert_cos_to_value` — exercised here against the
    string-leaf concrete subclass."""
    tree = PDStringNameTreeNode()
    base = COSString("payload")
    assert tree.convert_cos_to_pd(base) == tree.convert_cos_to_value(base)
    assert tree.convert_cos_to_pd(base) == "payload"
