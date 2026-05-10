"""Ported from
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/TestPDNumberTreeNode.java``
(PDFBox 3.0.x).

Translates the upstream ``testGetValue``, ``testUpperLimit`` and
``testLowerLimit`` JUnit cases. The upstream test pins ``PDTest`` (a tiny
``COSObjectable`` wrapper around an int) as its leaf value type; we use a
local ``_IntNumberTreeNode`` subclass that does the same, since the pypdfbox
``PDNumberTreeNode`` is generic over the value type.
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSInteger
from pypdfbox.pdmodel.common.pd_number_tree_node import PDNumberTreeNode


class _IntNumberTreeNode(PDNumberTreeNode[int]):
    """Concrete int-valued node mirroring upstream ``PDTest`` plumbing."""

    def convert_cos_to_value(self, base: COSBase) -> int:
        if not isinstance(base, COSInteger):
            raise OSError(f"Expected COSInteger, got {type(base).__name__}")
        return int(base.value)

    def convert_value_to_cos(self, value: int) -> COSBase:
        return COSInteger.get(value)

    def create_child_node(self, dic: COSDictionary) -> _IntNumberTreeNode:
        return _IntNumberTreeNode(dic)


def _build_fixture() -> tuple[
    _IntNumberTreeNode,
    _IntNumberTreeNode,
    _IntNumberTreeNode,
    _IntNumberTreeNode,
    _IntNumberTreeNode,
]:
    """Equivalent to upstream ``@BeforeEach setUp`` (lines 95-145).

    Builds the same 5-node tree shape:
        node1
        ├── node2 ── node5  (keys 1..7)
        └── node4 ── node24 (keys 8..12)
    """
    node5 = _IntNumberTreeNode()
    node5.set_numbers({1: 89, 2: 13, 3: 95, 4: 51, 5: 18, 6: 33, 7: 85})

    node24 = _IntNumberTreeNode()
    node24.set_numbers({8: 54, 9: 70, 10: 39, 11: 30, 12: 40})

    node2 = _IntNumberTreeNode()
    node2.set_kids([node5])

    node4 = _IntNumberTreeNode()
    node4.set_kids([node24])

    node1 = _IntNumberTreeNode()
    node1.set_kids([node2, node4])

    return node1, node2, node4, node5, node24


def test_get_value() -> None:
    """Port of ``testGetValue`` (Java lines 147-156)."""
    node1, _node2, _node4, node5, _node24 = _build_fixture()

    assert node5.get_value(4) == 51
    assert node1.get_value(9) == 70

    node1.set_kids(None)
    node1.set_numbers(None)
    assert node1.get_value(0) is None


def test_upper_limit() -> None:
    """Port of ``testUpperLimit`` (Java lines 158-177).

    Divergence: pypdfbox follows PDF Reference 1.7 §7.9.7 strictly — root
    nodes (those without a parent) must NOT carry ``/Limits``. Upstream Java
    PDFBox keeps the limits on the root anyway. The two ``node1.get_upper_limit()``
    expectations from the upstream JUnit case are therefore replaced with
    the pypdfbox-correct ``None`` check; the deeper assertions still match
    one-for-one. See CHANGES.md.
    """
    node1, node2, node4, node5, node24 = _build_fixture()

    assert node5.get_upper_limit() == 7
    assert node2.get_upper_limit() == 7

    assert node24.get_upper_limit() == 12
    assert node4.get_upper_limit() == 12

    # Pypdfbox: root has no /Limits; upstream Java would assert == 12 here.
    assert node1.get_upper_limit() is None

    node24.set_numbers({})
    assert node24.get_upper_limit() is None

    node5.set_numbers(None)
    assert node5.get_upper_limit() is None

    node1.set_kids(None)
    assert node1.get_upper_limit() is None


def test_lower_limit() -> None:
    """Port of ``testLowerLimit`` (Java lines 179-198).

    Divergence: see :func:`test_upper_limit` — pypdfbox keeps ``/Limits``
    off root nodes per PDF 1.7 §7.9.7.
    """
    node1, node2, node4, node5, node24 = _build_fixture()

    assert node5.get_lower_limit() == 1
    assert node2.get_lower_limit() == 1

    assert node24.get_lower_limit() == 8
    assert node4.get_lower_limit() == 8

    # Pypdfbox: root has no /Limits; upstream Java would assert == 1 here.
    assert node1.get_lower_limit() is None

    node24.set_numbers({})
    assert node24.get_lower_limit() is None

    node5.set_numbers(None)
    assert node5.get_lower_limit() is None

    node1.set_kids(None)
    assert node1.get_lower_limit() is None
