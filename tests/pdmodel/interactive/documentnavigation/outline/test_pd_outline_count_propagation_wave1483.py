"""Signed ``/Count`` bookkeeping in the document-outline tree — multi-level
ancestor-chain propagation through ``open_node`` / ``close_node`` /
``add_last`` / ``add_first``, and the always-open ``PDDocumentOutline`` root.

Upstream's per-pair insert-sibling count matrix (open/closed child × open/closed
parent) is already pinned in ``upstream/test_pd_outline_item.py``; the single
hop ``open_node`` on an open parent is in ``test_pd_outline_node_wave276.py``.
This file pins the angles those don't reach:

* deep (3+ level) propagation where every ancestor is open — contributions
  bubble all the way to a ``PDDocumentOutline`` root;
* a **closed middle ancestor** absorbing the swing and *stopping* propagation
  (its negative ``/Count`` widens, the root above it is untouched) — upstream
  ``PDOutlineNode#updateParentOpenCount`` else-branch;
* ``add_last`` / ``add_first`` of an **open child carrying descendants** —
  ``delta = 1 + child.get_open_count()`` (``updateParentOpenCountForAddedChild``)
  — into both a closed and an open parent;
* the document-outline root's positive ``/Count`` after a nested open, with
  ``is_node_open()`` hard-coded ``True`` (``PDDocumentOutline#isNodeOpen``);
* ``close_node`` deep in an open chain removing visible descendants from every
  open ancestor;
* ``is_node_open`` / ``get_open_count`` on a fresh item with no ``/Count``.

Every literal below was captured from Apache PDFBox 3.0.7 via
``oracle/probes/OutlineCountProbe.java`` (wave 1483). The plain tests pin those
values and pass without the oracle; ``test_matches_pdfbox_oracle`` re-runs the
same probe and asserts byte-for-byte equality when the live oracle is present.
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_document_outline import (
    PDDocumentOutline,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def test_a_deep_chain_all_open_bubbles_to_root() -> None:
    """root -> child -> grandchild, every ancestor open; opening the
    grandchild's subtree bubbles all the way to the root."""
    root = PDDocumentOutline()
    child = PDOutlineItem()
    grandchild = PDOutlineItem()
    leaf = PDOutlineItem()
    child.add_last(grandchild)  # child /Count 1 (closed)
    root.add_last(child)  # root /Count 1
    child.open_node()  # child open: child 1, root 2
    grandchild.add_last(leaf)  # grandchild closed: gc -1, child 2, root 3
    grandchild.open_node()  # grandchild open: gc 1, child 3, root 4
    assert root.get_open_count() == 3
    assert child.get_open_count() == 2
    assert grandchild.get_open_count() == 1
    assert leaf.get_open_count() == 0


def test_b_closed_middle_ancestor_absorbs_and_stops_propagation() -> None:
    """A closed middle ancestor widens its own negative ``/Count`` but does
    not propagate the swing to the open root above it."""
    root = PDDocumentOutline()
    child = PDOutlineItem()
    grandchild = PDOutlineItem()
    leaf = PDOutlineItem()
    grandchild.add_last(leaf)  # grandchild /Count 1 (closed)
    child.add_last(grandchild)  # child /Count 1 (closed, stays closed)
    root.add_last(child)  # root /Count 1
    grandchild.open_node()  # gc 1; child closed -> -2; root untouched
    assert root.get_open_count() == 1
    assert child.get_open_count() == -2
    assert grandchild.get_open_count() == 1


def test_c_add_last_open_child_with_descendants_into_closed_parent() -> None:
    """``delta = 1 + child.get_open_count()``; the closed parent subtracts it."""
    parent = PDOutlineItem()  # closed, /Count 0
    open_child = PDOutlineItem()
    open_child.add_last(PDOutlineItem())
    open_child.add_last(PDOutlineItem())  # open_child /Count 2 (closed)
    open_child.open_node()  # open_child /Count 2 (open)
    parent.add_last(open_child)  # delta 1+2=3; closed parent -> -3
    assert parent.get_open_count() == -3
    assert open_child.get_open_count() == 2


def test_d_add_first_open_child_with_descendants_into_open_parent() -> None:
    """``add_first`` uses the same ``update_parent_open_count_for_added_child``
    path; an open parent adds the delta."""
    parent = PDOutlineItem()
    parent.add_last(PDOutlineItem())  # parent 1 (closed)
    parent.open_node()  # parent 1 (open)
    new_first = PDOutlineItem()
    new_first.add_last(PDOutlineItem())  # new_first 1 (closed)
    new_first.open_node()  # new_first 1 (open)
    parent.add_first(new_first)  # delta 1+1=2; open parent -> 1+2=3
    assert parent.get_open_count() == 3
    assert new_first.get_open_count() == 1


def test_e_document_outline_root_count_after_nested_open() -> None:
    """The always-open root accumulates the swing of a nested open node."""
    root = PDDocumentOutline()
    a = PDOutlineItem()
    b = PDOutlineItem()
    a.add_last(b)  # a /Count 1 (closed)
    root.add_last(a)  # root /Count 1
    a.open_node()  # a open: a 1, root 2
    assert root.get_open_count() == 2
    assert a.get_open_count() == 1
    assert root.is_node_open() is True


def test_f_close_node_deep_in_open_chain_strips_visible_descendants() -> None:
    """Closing a node mid-chain removes its visible descendants from every
    open ancestor."""
    root = PDDocumentOutline()
    child = PDOutlineItem()
    grandchild = PDOutlineItem()
    child.add_last(grandchild)
    root.add_last(child)
    child.open_node()
    grandchild.add_last(PDOutlineItem())
    grandchild.add_last(PDOutlineItem())
    grandchild.open_node()
    grandchild.close_node()
    assert root.get_open_count() == 2
    assert child.get_open_count() == 1
    assert grandchild.get_open_count() == -2


def test_g_fresh_item_has_no_count_and_is_closed() -> None:
    """A fresh item carries no ``/Count``; ``get_open_count`` defaults to 0 and
    ``is_node_open`` is ``False``."""
    absent = PDOutlineItem()
    assert absent.is_node_open() is False
    assert absent.get_open_count() == 0


@requires_oracle
def test_matches_pdfbox_oracle() -> None:
    """Differential: the same build/open/close/add sequence in Apache PDFBox
    3.0.7 produces byte-identical ``/Count`` lines."""
    expected = (
        "A:3,2,1,0\n"
        "B:1,-2,1\n"
        "C:-3,2\n"
        "D:3,1\n"
        "E:2,1,isNodeOpen=true\n"
        "F:2,1,-2\n"
        "G:absent=false,count=0\n"
    )
    assert run_probe_text("OutlineCountProbe") == expected
