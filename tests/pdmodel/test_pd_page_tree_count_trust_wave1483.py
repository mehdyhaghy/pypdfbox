"""Regression: ``PDPageTree.get(index)`` trusts the stored ``/Count`` for
descent, exactly as upstream ``PDPageTree.get(pageNum, node, encountered)``.

Upstream's 0-based ``get(int)`` does NOT walk the whole tree to find the page;
it descends using each intermediate node's stored ``/Count`` to decide whether
the requested page could possibly live under that subtree. That makes a
*lying* ``/Count`` observable in three distinct ways, all pinned here against
the literals Apache PDFBox 3.0.7 emits (confirmed live via
``oracle/probes/PageTreeCountTrustProbe.java`` — see the ``@requires_oracle``
differential at the bottom):

* ``/Count`` UNDERCOUNTS (root says 1, two real leaves): ``get(0)`` succeeds,
  ``get(1)`` raises ``IndexOutOfBoundsException`` (→ :class:`IndexError`,
  ``"1-based index out of bounds: 2"``).
* ``/Count`` OVERCOUNTS (root says 5, two real leaves): ``get(0)`` / ``get(1)``
  succeed, ``get(2)`` raises ``IllegalStateException`` (→ :class:`RuntimeError`,
  ``"1-based index not found: 3"``) — the count promised a third page that the
  ``/Kids`` walk can't deliver.
* honest tree, plain out-of-range: ``get(2)`` →
  ``"1-based index out of bounds: 3"`` (:class:`IndexError`); ``get(-1)`` maps
  to ``pageNum=0`` → ``"Index out of bounds: 0"`` (note: the bare upstream
  ``get(int)`` has no Python negative-index sugar — see the separate
  Pythonic-negative-index test which IS a pypdfbox extension).

``getCount()`` itself stays O(1) raw — it reports the stored (lying) value.
"""

from __future__ import annotations

import json

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_KIDS = COSName.get_pdf_name("Kids")
_PARENT = COSName.get_pdf_name("Parent")
_COUNT = COSName.get_pdf_name("Count")


def _leaf(parent: COSDictionary, width: int) -> COSDictionary:
    page = PDPage(PDRectangle(width, 200))
    d = page.get_cos_object()
    d.set_item(_PARENT, parent)
    return d


def _tree_with_count(real_widths: list[int], lied_count: int) -> PDPageTree:
    """Build a single-level tree whose root ``/Count`` is forced to
    ``lied_count`` regardless of how many real leaves were added."""
    tree = PDPageTree()
    root = tree.get_cos_object()
    kids = root.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    for w in real_widths:
        kids.add(_leaf(root, w))
    root.set_int(_COUNT, lied_count)
    return tree


def _width(page: PDPage) -> int:
    return int(page.get_media_box().get_width())


# ---------- scenario A: /Count undercounts ----------


def test_undercount_get_count_is_raw_stored_value() -> None:
    tree = _tree_with_count([100, 101], lied_count=1)
    # getCount() is the O(1) stored value, even though it lies.
    assert tree.get_count() == 1


def test_undercount_get0_succeeds() -> None:
    tree = _tree_with_count([100, 101], lied_count=1)
    assert _width(tree.get(0)) == 100


def test_undercount_get1_index_out_of_bounds() -> None:
    tree = _tree_with_count([100, 101], lied_count=1)
    with pytest.raises(IndexError, match="1-based index out of bounds: 2"):
        tree.get(1)


# ---------- scenario B: /Count overcounts ----------


def test_overcount_get_count_is_raw_stored_value() -> None:
    tree = _tree_with_count([200, 201], lied_count=5)
    assert tree.get_count() == 5


def test_overcount_first_two_pages_resolve() -> None:
    tree = _tree_with_count([200, 201], lied_count=5)
    assert _width(tree.get(0)) == 200
    assert _width(tree.get(1)) == 201


def test_overcount_get2_index_not_found_is_runtime_error() -> None:
    tree = _tree_with_count([200, 201], lied_count=5)
    with pytest.raises(RuntimeError, match="1-based index not found: 3"):
        tree.get(2)


# ---------- scenario C: honest tree, plain out-of-range ----------


def test_honest_out_of_range_index_error_message() -> None:
    tree = _tree_with_count([300, 301], lied_count=2)
    with pytest.raises(IndexError, match="1-based index out of bounds: 3"):
        tree.get(2)


def test_honest_get_count_matches_real_leaf_count() -> None:
    tree = _tree_with_count([300, 301], lied_count=2)
    assert tree.get_count() == 2


# ---------- recursion guard ----------


def test_self_referential_count_descent_raises_runtime_error() -> None:
    """A ``/Kids`` cycle (an intermediate node listing itself) is caught by
    the descent's recursion guard — :class:`RuntimeError` rather than a
    Python ``RecursionError`` / stack overflow. Mirrors upstream's
    ``IllegalStateException("Possible recursion found ...")``."""
    tree = PDPageTree()
    root = tree.get_cos_object()
    kids = root.get_dictionary_object(_KIDS)
    assert isinstance(kids, COSArray)
    # An intermediate /Pages node that lists itself as a kid.
    node = COSDictionary()
    node.set_item(_TYPE, COSName.get_pdf_name("Pages"))
    inner = COSArray()
    inner.add(node)  # cycle
    node.set_item(_KIDS, inner)
    node.set_item(_PARENT, root)
    node.set_int(_COUNT, 1)
    kids.add(node)
    root.set_int(_COUNT, 1)
    with pytest.raises(RuntimeError, match="Possible recursion found"):
        tree.get(0)


# ---------- Pythonic negative indexing is a pypdfbox extension ----------


def test_negative_index_resolves_against_walk() -> None:
    """``tree[-1]`` is a Python list-style convenience layered on top of the
    upstream 0-based ``get(int)`` (which would throw for a negative index).
    It resolves against the walked leaf count."""
    tree = _tree_with_count([400, 401, 402], lied_count=3)
    assert _width(tree[-1]) == 402
    assert _width(tree[-3]) == 400


# ---------- live differential ----------


@requires_oracle
def test_count_trust_matches_pdfbox() -> None:
    raw = run_probe_text("PageTreeCountTrustProbe")
    j = json.loads(raw)
    assert j == {
        "a_getCount": 1,
        "a_get0_width": 100,
        "a_get1": "IndexOutOfBoundsException: 1-based index out of bounds: 2",
        "b_getCount": 5,
        "b_get0_width": 200,
        "b_get1_width": 201,
        "b_get2": "IllegalStateException: 1-based index not found: 3",
        "c_getCount": 2,
        "c_get2": "IndexOutOfBoundsException: 1-based index out of bounds: 3",
        "c_get_neg1": "IndexOutOfBoundsException: Index out of bounds: 0",
    }
