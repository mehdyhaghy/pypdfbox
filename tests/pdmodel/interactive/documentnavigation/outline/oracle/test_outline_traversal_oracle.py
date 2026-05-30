"""Live PDFBox differential parity for the outline (bookmark) linked-list
navigation surface — pre-order traversal of /First, /Last, /Next, /Prev and
findDestinationPage.

Where ``test_outline_tree_oracle.py`` (wave 1454) compares a nested tree dump,
this test pins the *pointer* surface that the tree dump does not expose: for
every visited node it captures the title of its first/last child and its
next/previous sibling, whether it ``has_children()``, its ``is_node_open()`` /
``get_open_count()`` signed count, and the page index that ``find_destination_page``
resolves to. The traversal order is pre-order over ``children()`` so it walks
both the child pointers and the sibling chain.

Build side uses only pypdfbox APIs (``add_last`` / ``add_first`` /
``open_node`` / ``close_node`` + the ``/Count`` propagation), saves to disk,
re-loads, then walks the re-parsed outline and diffs the canonical JSON dump
against Apache PDFBox's ``OutlineTraversalProbe`` byte-for-byte.

Canonical element shape (must match ``oracle/probes/OutlineTraversalProbe.java``)::

    {
        "depth": <int>,
        "title": <string>|null,
        "has_children": <bool>,
        "is_open": <bool>,
        "open_count": <signed int>,
        "first_child": <string>|null,
        "last_child": <string>|null,
        "next": <string>|null,
        "prev": <string>|null,
        "find_dest": <int>            # 0-based page index, -1 unresolved
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- pypdfbox-side JSON dumper (mirrors OutlineTraversalProbe) ----------


def _title_of(item: PDOutlineItem | None):
    return item.get_title() if item is not None else None


def _find_dest(doc: PDDocument, item: PDOutlineItem) -> int:
    # pypdfbox find_destination_page returns a page COSDictionary (divergence
    # from upstream's PDPage — see CHANGES.md); resolve it to an index against
    # the page tree exactly as the Java probe resolves its PDPage.
    page_dict = item.find_destination_page(doc)
    if page_dict is None:
        return -1
    return doc.get_pages().index_of(page_dict)


def _dump_node(doc: PDDocument, item: PDOutlineItem, depth: int, out: list) -> None:
    out.append(
        {
            "depth": depth,
            "title": item.get_title(),
            "has_children": item.has_children(),
            "is_open": item.is_node_open(),
            "open_count": item.get_open_count(),
            "first_child": _title_of(item.get_first_child()),
            "last_child": _title_of(item.get_last_child()),
            "next": _title_of(item.get_next_sibling()),
            "prev": _title_of(item.get_previous_sibling()),
            "find_dest": _find_dest(doc, item),
        }
    )
    for child in item.children():
        _dump_node(doc, child, depth + 1, out)


def _dump_traversal(doc: PDDocument) -> str:
    outline = doc.get_document_catalog().get_document_outline()
    out: list = []
    if outline is not None:
        for child in outline.children():
            _dump_node(doc, child, 0, out)
    return json.dumps(out, separators=(",", ":"), ensure_ascii=False)


# ---------- fixture builder ----------


def _build_nested_outline(path: Path) -> None:
    """A three-level outline with mixed open/closed subtrees:

        Part I            (opened)   -> page 0   [first top-level]
            Chapter 1     (closed)   -> page 1
                Section 1.1          -> page 2
                Section 1.2          -> page 3
            Chapter 2     (opened)   -> page 1
        Part II           (closed)   -> page 2   [last top-level]
            Chapter 3                -> page 3

    This wires up every pointer the probe inspects: /First and /Last on the
    parents, /Next and /Prev across the sibling chains, has_children at each
    interior node, and the signed /Count from open_node / close_node.
    Destinations span explicit XYZ and Fit forms so find_destination_page
    resolves a real page index at every node.
    """
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(4)]
        for p in pages:
            doc.add_page(p)

        def xyz(page: PDPage) -> PDPageXYZDestination:
            d = PDPageXYZDestination()
            d.set_page(page)
            return d

        def fit(page: PDPage) -> PDPageFitDestination:
            d = PDPageFitDestination()
            d.set_page(page)
            return d

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        # ---- Part I (opened) ----
        part1 = PDOutlineItem()
        part1.set_title("Part I")
        part1.set_destination(xyz(pages[0]))
        outline.add_last(part1)

        ch1 = PDOutlineItem()
        ch1.set_title("Chapter 1")
        ch1.set_destination(fit(pages[1]))
        part1.add_last(ch1)

        sec11 = PDOutlineItem()
        sec11.set_title("Section 1.1")
        sec11.set_destination(xyz(pages[2]))
        ch1.add_last(sec11)

        sec12 = PDOutlineItem()
        sec12.set_title("Section 1.2")
        sec12.set_destination(fit(pages[3]))
        ch1.add_last(sec12)
        # Chapter 1 left closed (negative count).

        ch2 = PDOutlineItem()
        ch2.set_title("Chapter 2")
        ch2.set_destination(xyz(pages[1]))
        part1.add_last(ch2)

        part1.open_node()  # open Part I (positive count contribution)

        # ---- Part II (closed) ----
        part2 = PDOutlineItem()
        part2.set_title("Part II")
        part2.set_destination(fit(pages[2]))
        outline.add_last(part2)

        ch3 = PDOutlineItem()
        ch3.set_title("Chapter 3")
        ch3.set_destination(xyz(pages[3]))
        part2.add_last(ch3)
        # Part II left closed.

        doc.save(str(path))
    finally:
        doc.close()


# ---------- differential test ----------


@requires_oracle
def test_outline_traversal_matches_pdfbox(tmp_path: Path) -> None:
    """Pre-order traversal of a nested outline — first/last child, next/prev
    sibling, has_children, signed open count and findDestinationPage — matches
    Apache PDFBox 3.0.7 byte-for-byte."""
    pdf = tmp_path / "outline_nested.pdf"
    _build_nested_outline(pdf)
    java = run_probe_text("OutlineTraversalProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_traversal(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_traversal_absent_emits_empty_array(tmp_path: Path) -> None:
    """A document with no /Outlines yields an empty traversal array on both
    sides — the base case for the flat dump."""
    pdf = tmp_path / "no_outline.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OutlineTraversalProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_traversal(doc)
    finally:
        doc.close()
    assert py == java
    assert py == "[]"
