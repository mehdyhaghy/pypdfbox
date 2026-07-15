"""Indexed page access (``PDPageTree.get``/``__getitem__``) fast-path parity.

``_get_cos`` descends the page tree trusting each node's stored ``/Count``. To
keep ``get(i)`` in a loop from being O(n²) (each call otherwise materialises the
whole ``/Kids`` list) it now:

* iterates ``/Kids`` lazily (one resolved entry at a time), and
* takes a direct-index fast path on a *flat* node — one whose stored
  ``/Count`` equals its ``/Kids`` length, so every kid contributes exactly one
  page and the target maps to a directly computable slot.

These tests pin that the observable results (returned page identity, order,
and out-of-range exceptions) are identical to a document-order walk for flat
trees, nested trees with honest ``/Count``, single-page ``/Pages`` children,
and ``null``-kid repair — the shapes any parser or the pypdfbox API produces.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_COUNT = COSName.get_pdf_name("Count")
_PARENT = COSName.get_pdf_name("Parent")
_SN = COSName.get_pdf_name("Sn")


def _leaf(sn: int, parent: COSDictionary | None = None) -> COSDictionary:
    p = PDPage(PDRectangle(10, 10))
    d = p.get_cos_object()
    d.set_int(_SN, sn)
    if parent is not None:
        d.set_item(_PARENT, parent)
    return d


def _pages(count: int | None, parent: COSDictionary | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _PAGES)
    d.set_item(_KIDS, COSArray())
    if count is not None:
        d.set_int(_COUNT, count)
    if parent is not None:
        d.set_item(_PARENT, parent)
    return d


def _add(node: COSDictionary, kid: object) -> None:
    node.get_dictionary_object(_KIDS).add(kid)


def _sn(page: PDPage) -> int:
    return page.get_cos_object().get_dictionary_object(_SN).value


# ---------- flat tree ----------


def test_flat_tree_indexed_matches_iterator() -> None:
    doc = PDDocument()
    for _ in range(50):
        doc.add_page(PDPage())
    tree = doc.get_pages()
    walked = [p.get_cos_object() for p in tree]
    for i in range(50):
        assert tree[i].get_cos_object() is walked[i]
    doc.close()


def test_flat_tree_out_of_range_raises_index_error() -> None:
    doc = PDDocument()
    for _ in range(3):
        doc.add_page(PDPage())
    tree = doc.get_pages()
    with pytest.raises(IndexError, match="1-based index out of bounds: 4"):
        tree.get(3)
    doc.close()


def test_flat_tree_negative_index() -> None:
    doc = PDDocument()
    pages = [PDPage() for _ in range(4)]
    for p in pages:
        doc.add_page(p)
    tree = doc.get_pages()
    assert tree[-1].get_cos_object() is pages[-1].get_cos_object()
    assert tree[-4].get_cos_object() is pages[0].get_cos_object()
    doc.close()


# ---------- nested honest tree ----------


def _nested_honest() -> tuple[PDPageTree, list[COSDictionary]]:
    root = _pages(None)
    a = _leaf(1, root)
    mid1 = _pages(None, root)
    b = _leaf(2, mid1)
    mid2 = _pages(None, mid1)
    c = _leaf(3, mid2)
    d = _leaf(4, mid2)
    _add(mid2, c)
    _add(mid2, d)
    mid2.set_int(_COUNT, 2)
    _add(mid1, b)
    _add(mid1, mid2)
    mid1.set_int(_COUNT, 3)
    f = _leaf(5, root)
    _add(root, a)
    _add(root, mid1)
    _add(root, f)
    root.set_int(_COUNT, 5)
    return PDPageTree(root), [a, b, c, d, f]


def test_nested_honest_indexed_matches_iterator() -> None:
    tree, order = _nested_honest()
    walked = [p.get_cos_object() for p in tree]
    assert walked == order
    for i, expected in enumerate(order):
        assert tree[i].get_cos_object() is expected


def test_nested_honest_negative_index() -> None:
    tree, order = _nested_honest()
    assert tree[-1].get_cos_object() is order[-1]
    assert tree[-5].get_cos_object() is order[0]


# ---------- flat-count node with a single-page /Pages child ----------


def test_flat_count_node_with_unit_pages_child_falls_back() -> None:
    """A node whose ``/Count == len(/Kids)`` but which contains a *unit*
    ``/Pages`` child (count 1) still resolves correctly — the fast path only
    returns a directly-jumped slot when it is a leaf, otherwise it defers to
    the faithful linear scan."""
    root = _pages(None)
    mid = _pages(None, root)
    x = _leaf(10, mid)
    _add(mid, x)
    mid.set_int(_COUNT, 1)
    y = _leaf(11, root)
    _add(root, mid)  # slot 0: unit /Pages node
    _add(root, y)  # slot 1: leaf
    root.set_int(_COUNT, 2)  # == len(/Kids) == 2, flat-looking
    tree = PDPageTree(root)
    assert [_sn(p) for p in tree] == [10, 11]
    assert _sn(tree[0]) == 10  # slot 0 is a /Pages node -> lazy scan -> x
    assert _sn(tree[1]) == 11  # slot 1 is a leaf -> direct jump -> y


# ---------- null-kid repair on the fast path ----------


def test_null_kid_repaired_on_fast_path() -> None:
    root = _pages(None)
    a = _leaf(1, root)
    _add(root, a)
    _add(root, COSNull.NULL)  # null kid -> repaired to empty /Page
    b = _leaf(2, root)
    _add(root, b)
    root.set_int(_COUNT, 3)  # flat-looking: 3 == len(/Kids)
    tree = PDPageTree(root)
    assert tree[0].get_cos_object() is a
    # index 1 lands on the repaired placeholder (a fresh empty /Page leaf).
    repaired = tree[1].get_cos_object()
    assert repaired.get_dictionary_object(_TYPE) == _PAGE
    assert repaired.get_dictionary_object(_SN) is None
    assert tree[2].get_cos_object() is b


# ---------- differential mini-fuzz over honest / real-shaped trees ----------


def _make_honest(depth: int, rng: random.Random, counter: list[int]):
    """Build a page tree whose every /Pages node carries an HONEST /Count
    (== reachable leaves), i.e. a spec-conformant tree. Returns (cos, leaves)."""
    if depth <= 0 or rng.random() < 0.5:
        counter[0] += 1
        leaf = _leaf(counter[0])
        return leaf, [leaf]
    node = _pages(None)
    leaves: list[COSDictionary] = []
    for _ in range(rng.randint(0, 4)):
        child, child_leaves = _make_honest(depth - 1, rng, counter)
        if child.get_dictionary_object(_KIDS) is not None or child_leaves:
            child.set_item(_PARENT, node)
        _add(node, child)
        leaves.extend(child_leaves)
    node.set_int(_COUNT, len(leaves))
    return node, leaves


def test_honest_tree_fuzz_indexed_matches_walk() -> None:
    rng = random.Random(99)
    for _ in range(500):
        root, leaves = _make_honest(rng.randint(1, 4), rng, [0])
        if root.get_dictionary_object(_TYPE) != _PAGES:
            wrap = _pages(len(leaves))
            _add(wrap, root)
            root = wrap
        tree = PDPageTree(root)
        walked = [p.get_cos_object() for p in tree]
        assert walked == leaves
        for i in range(len(leaves)):
            assert tree[i].get_cos_object() is leaves[i]
        # out of range
        with pytest.raises(IndexError):
            tree.get(len(leaves))
