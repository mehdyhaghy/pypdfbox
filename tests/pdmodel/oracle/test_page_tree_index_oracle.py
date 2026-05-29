"""Live PDFBox differential parity for the PDPageTree INDEX / LOOKUP surface.

Complements ``test_page_tree_oracle`` (flat traversal + mutation round-trips)
by isolating the read-only query contract of :class:`PDPageTree` on a
multi-level, **unbalanced** ``/Kids`` tree built from scratch — no fixture
dependency, so the comparison is purely about how each library walks an
arbitrary nested page tree:

* ``get_count()`` — the O(1) stored ``/Count`` of the root ``/Pages`` node;
* iteration order — the document-order sequence the ``Iterable`` yields,
  identified per page by a unique integer MediaBox width;
* ``index_of(page)`` — the 0-based document index of every leaf;
* ``index_of(foreign)`` — ``-1`` for a page never added to the tree;
* ``get(index)`` round-trip — ``get(index_of(p))`` is the same page object,
  and a direct ``get(i)`` yields the width we expect at index ``i``.

The Java side is ``oracle/probes/PageTreeIndexProbe.java``; it emits a single
JSON object that this test rebuilds field-for-field through ``PDPageTree`` so
the comparison is value-for-value.
"""

from __future__ import annotations

import json

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_WIDTHS = [100, 101, 102, 103, 104, 105]

_TYPE = COSName.get_pdf_name("Type")
_PAGE = COSName.get_pdf_name("Page")
_PAGES = COSName.get_pdf_name("Pages")
_KIDS = COSName.get_pdf_name("Kids")
_PARENT = COSName.get_pdf_name("Parent")
_COUNT = COSName.get_pdf_name("Count")


def _pages_node(parent: COSDictionary) -> COSDictionary:
    node = COSDictionary()
    node.set_item(_TYPE, _PAGES)
    node.set_item(_KIDS, COSArray())
    node.set_item(_PARENT, parent)
    return node


def _add_node(parent: COSDictionary, child: COSDictionary) -> None:
    kids = parent.get_dictionary_object(_KIDS)
    kids.add(child)
    child.set_item(_PARENT, parent)


def _add_leaf(parent: COSDictionary, leaves: list[PDPage], width: int) -> None:
    page_dict = COSDictionary()
    page_dict.set_item(_TYPE, _PAGE)
    page_dict.set_item(_PARENT, parent)
    page = PDPage(page_dict)
    page.set_media_box(PDRectangle(width, width))
    parent.get_dictionary_object(_KIDS).add(page_dict)
    leaves.append(page)


def _build(doc: PDDocument) -> tuple[PDPageTree, list[PDPage]]:
    """Hand-wire the identical unbalanced tree the Java probe builds.

    Shape (depth-first leaf order = widths 100..105):
        root /Pages
          A /Pages
            p0 (100), p1 (101)
            B /Pages
              p2 (102), p3 (103), p4 (104)
          p5 (105)
    """
    tree = doc.get_pages()
    root = tree.get_cos_object()
    root.set_item(_KIDS, COSArray())

    a = _pages_node(root)
    b = _pages_node(a)

    leaves: list[PDPage] = []
    _add_leaf(a, leaves, _WIDTHS[0])
    _add_leaf(a, leaves, _WIDTHS[1])
    _add_node(a, b)
    _add_leaf(b, leaves, _WIDTHS[2])
    _add_leaf(b, leaves, _WIDTHS[3])
    _add_leaf(b, leaves, _WIDTHS[4])
    _add_node(root, a)
    _add_leaf(root, leaves, _WIDTHS[5])

    b.set_int(_COUNT, 3)
    a.set_int(_COUNT, 5)
    root.set_int(_COUNT, 6)
    return tree, leaves


def _report() -> dict:
    doc = PDDocument()
    try:
        tree, leaves = _build(doc)
        count = tree.get_count()
        order = [int(p.get_media_box().get_width()) for p in tree]
        index_of = [tree.index_of(p) for p in leaves]
        get_widths = [int(tree.get(i).get_media_box().get_width()) for i in range(count)]
        round_trip = all(
            tree.get(tree.index_of(p)).get_cos_object() is p.get_cos_object()
            for p in leaves
        )
        foreign = PDPage(PDRectangle(999, 999))
        foreign_index_of = tree.index_of(foreign)
    finally:
        doc.close()
    return {
        "count": count,
        "order": order,
        "indexOf": index_of,
        "getWidths": get_widths,
        "roundTrip": round_trip,
        "foreignIndexOf": foreign_index_of,
    }


@requires_oracle
def test_page_tree_index_lookup_matches_pdfbox() -> None:
    java = json.loads(run_probe_text("PageTreeIndexProbe"))
    py = _report()
    assert py == java, (
        "PDPageTree index/lookup surface diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def test_page_tree_index_report_self_consistent() -> None:
    """Regression pin that runs without the live oracle: the document-order
    iteration, ``index_of`` per page, and ``get(index)`` round-trip must agree
    on the built unbalanced tree, and a foreign page resolves to ``-1``."""
    py = _report()
    assert py["count"] == 6
    assert py["order"] == _WIDTHS
    assert py["indexOf"] == [0, 1, 2, 3, 4, 5]
    assert py["getWidths"] == _WIDTHS
    assert py["roundTrip"] is True
    assert py["foreignIndexOf"] == -1
