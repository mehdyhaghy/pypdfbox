"""Live PDFBox differential parity for the document outline (bookmark) tree
surface — wave-1454 agent 3/6.

This test builds outlines entirely with pypdfbox APIs (so the build-side
exercises ``PDOutlineNode.add_last``/``add_first``, ``open_node`` /
``close_node`` and the ``/Count`` propagation), then compares pypdfbox's
read-side walk against Apache PDFBox's ``OutlineTreeProbe`` JSON dump
byte-for-byte.

Canonical JSON shape (must match ``oracle/probes/OutlineTreeProbe.java``)::

    root := {
        "open_count": <signed int>,
        "child_count": <int>,
        "children": [ <item>, ... ]
    }
    item := {
        "title": <string>|null,
        "count": <signed int>|null,
        "is_open": <bool>,
        "dest": <int>,        // 0-based page index, -1 when unresolved
        "child_count": <int>,
        "children": [ <item>, ... ]
    }

The probe and pypdfbox dumper use the same canonical (key-order-fixed,
no-whitespace) form so the comparison is exact.
"""

from __future__ import annotations

import json
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageDestination,
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

# ---------- pypdfbox-side JSON dumper (mirrors OutlineTreeProbe) ----------


def _raw_count(item: PDOutlineItem):
    """Return the raw signed /Count integer or ``None`` when absent — mirrors
    ``OutlineTreeProbe.rawCount`` (reads the COS slot directly so we see
    the on-disk value, not the get_open_count() default of 0)."""
    from pypdfbox.cos import COSInteger

    c = item.get_cos_object().get_dictionary_object(COSName.COUNT)
    if isinstance(c, COSInteger):
        return c.int_value()
    if c is None:
        return None
    # Floats — collapse to int via the canonical numeric repr the probe uses.
    try:
        return int(c.float_value())  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        return None


def _resolve_page_index(doc: PDDocument, item: PDOutlineItem) -> int:
    """Reproduce ``OutlineTreeProbe.resolvePageIndex`` in pypdfbox terms."""
    dest = item.get_destination()
    if dest is None:
        action = item.get_action()
        if isinstance(action, PDActionGoTo):
            resolved = action.get_destination()
            # Our PDActionGoTo returns the bare string for the named form;
            # re-wrap so the named path below fires (see CHANGES.md).
            dest = PDNamedDestination(resolved) if isinstance(resolved, str) else resolved
    if dest is None:
        return -1
    if isinstance(dest, PDNamedDestination):
        dest = item._resolve_named_destination(doc, dest)
        if dest is None:
            return -1
    if not isinstance(dest, PDPageDestination):
        return -1
    page = dest.get_page()
    if page is not None:
        idx = doc.get_pages().index_of(page)
        if idx >= 0:
            return idx
    return dest.get_page_number()


def _dump_item(doc: PDDocument, item: PDOutlineItem) -> dict:
    children = list(item.children())
    return {
        "title": item.get_title(),
        "count": _raw_count(item),
        "is_open": item.is_node_open(),
        "dest": _resolve_page_index(doc, item),
        "child_count": len(children),
        "children": [_dump_item(doc, c) for c in children],
    }


def _dump_outline(doc: PDDocument) -> str:
    outline = doc.get_document_catalog().get_document_outline()
    if outline is None:
        return "null"
    children = list(outline.children())
    payload = {
        "open_count": outline.get_open_count(),
        "child_count": len(children),
        "children": [_dump_item(doc, c) for c in children],
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


# ---------- fixture builders ----------


def _build_open_close_pdf(path: Path) -> None:
    """Two top-level entries, each with two children. The first top-level is
    opened (positive count), the second is closed (negative count). Exercises
    add_last + open_node propagation into both open and closed parents."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(4)]
        for p in pages:
            doc.add_page(p)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        # ---- top-level "Open" parent with 2 children, opened ----
        opened = PDOutlineItem()
        opened.set_title("Open parent")
        opened.set_destination(pages[0])
        outline.add_last(opened)

        child_a = PDOutlineItem()
        child_a.set_title("opened > child A")
        child_a.set_destination(pages[1])
        opened.add_last(child_a)

        child_b = PDOutlineItem()
        child_b.set_title("opened > child B")
        child_b.set_destination(pages[2])
        opened.add_last(child_b)

        opened.open_node()

        # ---- top-level "Closed" parent with 2 children, left closed ----
        closed = PDOutlineItem()
        closed.set_title("Closed parent")
        closed.set_destination(pages[3])
        outline.add_last(closed)

        c_a = PDOutlineItem()
        c_a.set_title("closed > child A")
        c_a.set_destination(pages[0])
        closed.add_last(c_a)

        c_b = PDOutlineItem()
        c_b.set_title("closed > child B")
        c_b.set_destination(pages[1])
        closed.add_last(c_b)
        # Leave closed.

        doc.save(str(path))
    finally:
        doc.close()


def _build_named_dest_pdf(path: Path) -> None:
    """Outline whose items reach pages by:

    * explicit XYZ destination (/Dest = [page /XYZ ...]);
    * named destination via /Names/Dests name tree (/Dest = "Chapter1");
    * /A GoTo action with an explicit destination (no /Dest);
    * /A GoTo action whose /D is a named string (no /Dest, named-lookup
      path through the catalog).

    This is the dest-resolution matrix the wave-1454 brief calls out."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(3)]
        for p in pages:
            doc.add_page(p)

        # ---- /Names/Dests name tree: "Chapter1" -> page 1, "Appendix" -> page 2 ----
        ch1 = COSArray()
        ch1.add(pages[1].get_cos_object())
        ch1.add(COSName.get_pdf_name("Fit"))

        appx = COSArray()
        appx.add(pages[2].get_cos_object())
        appx.add(COSName.get_pdf_name("Fit"))

        names_dict = COSDictionary()
        kids_arr = COSArray()
        # /Names entries in a leaf are an array of (name, value) pairs.
        names_arr = COSArray()
        names_arr.add(COSString("Appendix"))
        names_arr.add(appx)
        names_arr.add(COSString("Chapter1"))
        names_arr.add(ch1)

        dests_leaf = COSDictionary()
        dests_leaf.set_item(COSName.get_pdf_name("Names"), names_arr)
        kids_arr.add(dests_leaf)
        names_dict.set_item(COSName.get_pdf_name("Kids"), kids_arr)

        # PDDocumentNameDictionary.set_dests expects a PDDestinationNameTreeNode.
        # Bypass the wrapper and write the catalog /Names/Dests directly so the
        # fixture is exactly what PDFBox encounters on a real PDF.
        catalog_dict = doc.get_document_catalog().get_cos_object()
        catalog_names = COSDictionary()
        catalog_names.set_item(COSName.get_pdf_name("Dests"), names_dict)
        catalog_dict.set_item(COSName.get_pdf_name("Names"), catalog_names)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        # 1) Explicit XYZ destination.
        explicit = PDOutlineItem()
        explicit.set_title("Explicit XYZ -> page 0")
        xyz = PDPageXYZDestination()
        xyz.set_page(pages[0])
        explicit.set_destination(xyz)
        outline.add_last(explicit)

        # 2) Named destination string -> Chapter1.
        named = PDOutlineItem()
        named.set_title("Named Dest -> Chapter1")
        named.set_destination(PDNamedDestination("Chapter1"))
        outline.add_last(named)

        # 3) /A GoTo action with an explicit destination (no /Dest).
        action_explicit = PDOutlineItem()
        action_explicit.set_title("GoTo explicit -> page 2")
        fit = PDPageFitDestination()
        fit.set_page(pages[2])
        go = PDActionGoTo()
        go.set_destination(fit)
        action_explicit.set_action(go)
        outline.add_last(action_explicit)

        # 4) /A GoTo action with named-destination string (no /Dest).
        action_named = PDOutlineItem()
        action_named.set_title("GoTo named -> Appendix")
        go_named = PDActionGoTo()
        go_named.set_destination("Appendix")
        action_named.set_action(go_named)
        outline.add_last(action_named)

        # 5) Item with neither /Dest nor /A — dest must resolve to -1.
        orphan = PDOutlineItem()
        orphan.set_title("Orphan (no dest)")
        outline.add_last(orphan)

        doc.save(str(path))
    finally:
        doc.close()


def _build_unicode_title_pdf(path: Path) -> None:
    """Outline titles exercising the COSString PDFDocEncoding vs UTF-16BE
    branch in ``COSString.get_string()``:

    * pure-ASCII title -> PDFDocEncoded;
    * Latin-1 supplemental (still PDFDocEncodable);
    * Greek / CJK (forces UTF-16BE with BOM);
    * embedded tab + newline (must be JSON-escaped by both sides);
    * empty string;
    * title with quote + backslash (JSON-escaping correctness)."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        for title in [
            "ASCII title",
            "Latin café",
            "Greek Αβγ",
            "CJK 中文",
            "Tab\there\nand newline",
            "",
            'Quote " and backslash \\',
        ]:
            item = PDOutlineItem()
            item.set_title(title)
            item.set_destination(page)
            outline.add_last(item)

        doc.save(str(path))
    finally:
        doc.close()


def _build_cyclic_next_pdf(path: Path) -> None:
    """Deliberately malformed outline whose ``/Next`` chain loops back on
    itself. PDFBox detects the cycle via its ``visited`` set in the iterator
    and stops; pypdfbox must match (otherwise the test would hang)."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        a = PDOutlineItem()
        a.set_title("A")
        a.set_destination(page)
        outline.add_last(a)

        b = PDOutlineItem()
        b.set_title("B")
        b.set_destination(page)
        outline.add_last(b)

        # Maliciously chain B.Next -> A so iteration cycles A -> B -> A -> ...
        b.set_next_sibling(a)
        # Update /Last to point at B (already does) but the /Prev/Next chain is
        # now cyclic: A -> B (via existing add_last), then B -> A (just added).
        # PDFBox should walk A, B and stop on the second visit to A.

        doc.save(str(path))
    finally:
        doc.close()


# ---------- differential tests ----------


@requires_oracle
def test_outline_open_close_counts_match_pdfbox(tmp_path: Path) -> None:
    """add_last + open_node / closed-leaf /Count propagation matches PDFBox.

    Verifies the signed /Count semantics from PDF §12.3.3:
      * opened parent with 2 children -> count = +2;
      * closed parent with 2 children -> count = -3 (PDFBox sign rule:
        |count| = subtree size including the leaves themselves);
      * outline root's getOpenCount() rolls up the *positive* contributions
        only (per PDDocumentOutline.isNodeOpen() == true).
    """
    pdf = tmp_path / "outline_open_close.pdf"
    _build_open_close_pdf(pdf)
    java = run_probe_text("OutlineTreeProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_named_and_action_destinations_match_pdfbox(tmp_path: Path) -> None:
    """Destination resolution matrix matches PDFBox across explicit /Dest,
    named /Dest, /A GoTo with explicit dest, /A GoTo with named-string dest,
    and the no-dest orphan case."""
    pdf = tmp_path / "outline_dests.pdf"
    _build_named_dest_pdf(pdf)
    java = run_probe_text("OutlineTreeProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_unicode_titles_match_pdfbox(tmp_path: Path) -> None:
    """Title decoding (PDFDocEncoding vs UTF-16BE) and JSON escaping
    match PDFBox across ASCII, Latin-1, Greek/CJK, tab/newline, empty
    string, and quote/backslash titles."""
    pdf = tmp_path / "outline_unicode.pdf"
    _build_unicode_title_pdf(pdf)
    java = run_probe_text("OutlineTreeProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_cyclic_next_chain_terminates_like_pdfbox(tmp_path: Path) -> None:
    """A malformed outline with a cyclic /Next chain terminates in both
    PDFBox and pypdfbox (the iterator's visited-set guard kicks in).
    The dumps must match — same item set, same order, no infinite loop."""
    pdf = tmp_path / "outline_cyclic.pdf"
    _build_cyclic_next_pdf(pdf)
    java = run_probe_text("OutlineTreeProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java


@requires_oracle
def test_outline_absent_emits_null(tmp_path: Path) -> None:
    """A document with no /Outlines emits the JSON token ``null`` on both
    sides — the empty-tree base case."""
    pdf = tmp_path / "no_outline.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(pdf))
    finally:
        doc.close()
    java = run_probe_text("OutlineTreeProbe", str(pdf))
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_outline(doc)
    finally:
        doc.close()
    assert py == java
    assert py == "null"
