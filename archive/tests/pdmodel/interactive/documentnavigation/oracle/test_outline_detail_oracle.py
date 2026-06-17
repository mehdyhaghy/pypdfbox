"""Live PDFBox differential parity for the document-outline (bookmarks)
*detail* surface — the ``/Count`` open/closed sign convention, ``isNodeOpen`` /
``getOpenCount``, the ``/C`` RGB colour, the ``/F`` bold/italic style flags, and
each item's destination-vs-action target
(``pypdfbox.pdmodel.interactive.documentnavigation.outline``).

This complements ``test_outline_oracle.py`` (which checks the depth-first
title/page-index walk) by asserting the per-item *attributes* PDFBox exposes,
against the ``OutlineDetailProbe`` Java oracle. Each item is reduced to one
canonical line so the two languages compare byte-for-byte::

    <depth>\t<title>\t<rawCount>\t<isNodeOpen>\t<openCount>\t<color>\t<bold>\t<italic>\t<target>

* ``rawCount``   — raw signed ``/Count`` integer (``none`` when absent); the
  +N-open / -N-closed sign convention of PDF 32000-1:2008 §12.3.3.
* ``isNodeOpen`` / ``openCount`` — ``isNodeOpen()`` (count > 0) and the
  ``getOpenCount()`` getter.
* ``color``      — ``getTextColor()`` RGB components (PDFBox materializes
  ``[0,0,0]`` when ``/C`` is absent), rendered with a trailing ``.0`` dropped.
* ``bold`` / ``italic`` — ``isBold()`` / ``isItalic()`` (``/F`` bit 1 / bit 0).
* ``target``     — ``dest:<pageIndex>`` for a resolvable page destination
  (``/Dest`` or an ``/A`` GoTo), ``action:<subtype>`` for a non-GoTo ``/A``
  action, ``none`` otherwise.

The high-value cases the task calls out: the open/closed ``/Count`` *sign*,
``getOpenCount`` (count of visible descendants), and the ``/F`` bit decoding —
plus a set-then-read (``open_node`` / ``close_node``) round-trip.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName, COSNumber
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDDocumentOutline,
    PDOutlineItem,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_COUNT = COSName.get_pdf_name("Count")


def _build_outline_pdf(path: Path) -> None:
    """Build a PDF with the task's nested outline:

    * root with 2 top-level items;
    * item A (first, top-level) OPEN with 2 children  -> /Count = +2;
    * item B (second, top-level) CLOSED with 1 child   -> /Count = -1;
    * one child (A1) with /C [1 0 0] red + /F 3 bold+italic;
    * A1 has a GoTo dest (page 1); A2 has a URI action;
    * B1 has a GoTo dest (page 2).
    """
    doc = PDDocument()
    try:
        p0 = PDPage()
        p1 = PDPage()
        p2 = PDPage()
        doc.add_page(p0)
        doc.add_page(p1)
        doc.add_page(p2)

        outline = PDDocumentOutline()
        doc.get_document_catalog().set_document_outline(outline)

        # Top-level item A (will be opened, 2 visible children -> +2).
        item_a = PDOutlineItem()
        item_a.set_title("Chapter A")
        dest_a = PDPageXYZDestination()
        dest_a.set_page(p0)
        item_a.set_destination(dest_a)
        outline.add_last(item_a)

        # Child A1: red bold+italic, GoTo dest -> page 1.
        a1 = PDOutlineItem()
        a1.set_title("Section A1")
        a1.set_text_color((1.0, 0.0, 0.0))
        a1.set_text_flags(PDOutlineItem.FLAG_BOLD | PDOutlineItem.FLAG_ITALIC)
        goto = PDActionGoTo()
        d1 = PDPageXYZDestination()
        d1.set_page(p1)
        goto.set_destination(d1)
        a1.set_action(goto)
        item_a.add_last(a1)

        # Child A2: URI action (no dest).
        a2 = PDOutlineItem()
        a2.set_title("Section A2")
        uri = PDActionURI()
        uri.set_uri("https://example.com/a2")
        a2.set_action(uri)
        item_a.add_last(a2)

        # Open item A: now /Count = +2 (two visible children).
        item_a.open_node()

        # Top-level item B (will be closed, 1 child -> -1).
        item_b = PDOutlineItem()
        item_b.set_title("Chapter B")
        dest_b = PDPageXYZDestination()
        dest_b.set_page(p0)
        item_b.set_destination(dest_b)
        outline.add_last(item_b)

        # Child B1: plain, GoTo dest -> page 2.
        b1 = PDOutlineItem()
        b1.set_title("Section B1")
        gotob = PDActionGoTo()
        db1 = PDPageXYZDestination()
        db1.set_page(p2)
        gotob.set_destination(db1)
        b1.set_action(gotob)
        item_b.add_last(b1)

        # B is open by default after add_last; close it -> /Count = -1.
        item_b.close_node()

        doc.save(str(path))
    finally:
        doc.close()


def _fmt(v: float) -> str:
    """Mirror ``OutlineDetailProbe.fmt`` — drop a trailing ``.0``."""
    if v == int(v):
        return str(int(v))
    # Java Float.toString — single-precision repr. Our floats come from the
    # COS array round-trip; for the integral test values this branch never
    # fires, but keep parity for robustness.
    return repr(float(v))


def _escape(title: str | None) -> str:
    if title is None:
        return "null"
    return (
        title.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _raw_count(item: PDOutlineItem) -> str:
    c = item.get_cos_object().get_dictionary_object(_COUNT)
    if not isinstance(c, COSNumber):
        return "none"
    return str(c.int_value())


def _color(item: PDOutlineItem) -> str:
    comps = item.get_text_color_pd_color().get_components()
    return ",".join(_fmt(v) for v in comps)


def _target(doc: PDDocument, item: PDOutlineItem) -> str:
    dest = item.get_destination()
    action = item.get_action()
    if dest is None and isinstance(action, PDActionGoTo):
        resolved = action.get_destination()
        dest = PDNamedDestination(resolved) if isinstance(resolved, str) else resolved
    if dest is not None:
        page_dest: PDPageDestination | None = None
        if isinstance(dest, PDNamedDestination):
            resolved_dest = item._resolve_named_destination(doc, dest)
            if isinstance(resolved_dest, PDPageDestination):
                page_dest = resolved_dest
        elif isinstance(dest, PDPageDestination):
            page_dest = dest
        if page_dest is not None:
            return f"dest:{_resolve_page_index(doc, page_dest)}"
    if action is not None:
        sub = action.get_sub_type()
        return f"action:{'null' if sub is None else sub}"
    return "none"


def _resolve_page_index(doc: PDDocument, page_dest: PDPageDestination) -> int:
    page = page_dest.get_page()
    if page is not None:
        idx = doc.get_pages().index_of(page)
        if idx >= 0:
            return idx
    return page_dest.get_page_number()


def _dump_detail(doc: PDDocument) -> str:
    outline = doc.get_document_catalog().get_document_outline()
    lines: list[str] = []

    def walk(node, depth: int) -> None:
        for item in node.children():
            lines.append(
                "\t".join(
                    [
                        str(depth),
                        _escape(item.get_title()),
                        _raw_count(item),
                        "true" if item.is_node_open() else "false",
                        str(item.get_open_count()),
                        _color(item),
                        "true" if item.is_bold() else "false",
                        "true" if item.is_italic() else "false",
                        _target(doc, item),
                    ]
                )
            )
            walk(item, depth + 1)

    if outline is not None:
        walk(outline, 0)
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_outline_detail_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's per-item outline-detail dump equals PDFBox's, covering the
    /Count sign, isNodeOpen, getOpenCount, /C colour, /F bold/italic, and
    dest-vs-action target for every item in the nested tree."""
    pdf = tmp_path / "outline_detail.pdf"
    _build_outline_pdf(pdf)

    java = run_probe_text("OutlineDetailProbe", str(pdf))

    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_detail(doc)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_outline_count_sign_facts(tmp_path: Path) -> None:
    """Sanity-pin the high-value /Count sign facts the probe asserts: item A
    open with +2, item B closed with -1 — both as pypdfbox reads them and as
    PDFBox reads them (the lines must be present in the oracle output)."""
    pdf = tmp_path / "outline_detail.pdf"
    _build_outline_pdf(pdf)
    java = run_probe_text("OutlineDetailProbe", str(pdf))
    java_lines = java.splitlines()

    # Chapter A: depth 0, raw /Count = +2, open, getOpenCount = 2.
    a_line = next(line for line in java_lines if line.split("\t")[1] == "Chapter A")
    a = a_line.split("\t")
    assert a[2] == "2"
    assert a[3] == "true"
    assert a[4] == "2"

    # Chapter B: depth 0, raw /Count = -1, closed, getOpenCount = -1.
    b_line = next(line for line in java_lines if line.split("\t")[1] == "Chapter B")
    b = b_line.split("\t")
    assert b[2] == "-1"
    assert b[3] == "false"
    assert b[4] == "-1"

    # Section A1: red bold+italic, GoTo dest -> page 1.
    a1_line = next(line for line in java_lines if line.split("\t")[1] == "Section A1")
    a1 = a1_line.split("\t")
    assert a1[5] == "1,0,0"
    assert a1[6] == "true"  # bold
    assert a1[7] == "true"  # italic
    assert a1[8] == "dest:1"

    # Section A2: URI action, no dest.
    a2_line = next(line for line in java_lines if line.split("\t")[1] == "Section A2")
    a2 = a2_line.split("\t")
    assert a2[8] == "action:URI"

    # And pypdfbox agrees with the whole dump.
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump_detail(doc)
    finally:
        doc.close()
    assert py == java


def test_open_close_node_count_sign_roundtrip() -> None:
    """Set-then-read round-trip of the /Count sign convention via open_node /
    close_node, independent of the oracle (pure pypdfbox behaviour the probe
    relies on).

    A fresh detached item carries no /Count, so it is treated as *closed*;
    appending two children widens the (negative) closed count to -2 (verified
    identical to PDFBox: addLast on a fresh item gives openCount=-2). Opening
    flips it to +2; closing flips back to -2. is_node_open / get_open_count
    track the sign. Mirrors PDOutlineNode#switchNodeCount."""
    parent = PDOutlineItem()
    parent.set_title("Parent")
    c1 = PDOutlineItem()
    c2 = PDOutlineItem()
    parent.add_last(c1)
    parent.add_last(c2)

    # Fresh item starts closed (no /Count); two children -> -2 (closed, |2|).
    assert parent.get_open_count() == -2
    assert parent.is_node_open() is False
    assert parent.get_count() == -2
    assert parent.is_collapsed() is True

    parent.open_node()
    assert parent.is_node_open() is True
    assert parent.get_open_count() == 2
    assert parent.get_count() == 2
    assert parent.is_collapsed() is False

    # Opening again is a no-op (already open).
    parent.open_node()
    assert parent.get_open_count() == 2

    parent.close_node()
    assert parent.is_node_open() is False
    assert parent.get_open_count() == -2
    assert parent.is_collapsed() is True


def test_text_flag_bit_decoding() -> None:
    """The /F bit decoding: bit 0 = italic, bit 1 = bold (PDF §12.3.3)."""
    item = PDOutlineItem()
    assert item.get_text_flags() == 0
    assert item.is_bold() is False
    assert item.is_italic() is False

    item.set_text_flags(1)  # bit 0 -> italic only
    assert item.is_italic() is True
    assert item.is_bold() is False

    item.set_text_flags(2)  # bit 1 -> bold only
    assert item.is_italic() is False
    assert item.is_bold() is True

    item.set_text_flags(3)  # both
    assert item.is_italic() is True
    assert item.is_bold() is True

    # Round-trip via the typed setters.
    item2 = PDOutlineItem()
    item2.set_bold(True)
    item2.set_italic(True)
    assert item2.get_text_flags() == (PDOutlineItem.FLAG_BOLD | PDOutlineItem.FLAG_ITALIC)
    item2.set_bold(False)
    assert item2.get_text_flags() == PDOutlineItem.FLAG_ITALIC


def test_text_color_read() -> None:
    """/C RGB triple reads back as a (r, g, b) tuple in [0, 1]."""
    item = PDOutlineItem()
    assert item.get_text_color() is None  # absent -> None (pypdfbox divergence)
    item.set_text_color((1.0, 0.0, 0.0))
    assert item.get_text_color() == (1.0, 0.0, 0.0)
    assert item.get_text_color_pd_color().get_components() == [1.0, 0.0, 0.0]
