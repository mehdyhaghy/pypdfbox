"""Live PDFBox differential parity for the per-outline-item ``/A`` action vs
``/Dest`` destination accessors
(``pypdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem``).

PDF 32000-1:2008 §12.3.3 allows an outline item to carry both ``/A`` and
``/Dest`` simultaneously; PDFBox exposes both accessors (``getAction()`` and
``getDestination()``) and they must round-trip *independently*. This test
covers the four cardinality cases:

    (a) only ``/A`` (URI)            — getAction != null, getDestination == null
    (b) only ``/Dest`` (GoTo XYZ)    — getAction == null, getDestination != null
    (c) BOTH ``/A`` and ``/Dest``    — both accessors return their values
    (d) neither                       — both accessors return null

The "both present" case is the high-value differential: a buggy outline that
strips one accessor when the other is present (or routes ``/Dest`` through
the ``/A`` action) would pass cases (a)/(b) but fail (c).

Each item is reduced to one canonical line so the two languages compare
byte-for-byte::

    <depth>\\t<title>\\t<action>\\t<destination>
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
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


def _build_pdf(path: Path) -> None:
    """Build the four-case outline PDF used by the differential.

    Items (top-level, in /First -> /Next order):
        (a) "Only A (URI)"        — /A URI only, no /Dest.
        (b) "Only Dest (XYZ)"     — /Dest XYZ -> page 1, no /A.
        (c) "Both A and Dest"     — /A GoTo XYZ -> page 0 AND /Dest XYZ -> page 2.
        (d) "Neither"             — no /A and no /Dest.
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

        # (a) Only /A (URI).
        a = PDOutlineItem()
        a.set_title("Only A (URI)")
        uri = PDActionURI()
        uri.set_uri("https://example.com/a")
        a.set_action(uri)
        outline.add_last(a)

        # (b) Only /Dest (XYZ).
        b = PDOutlineItem()
        b.set_title("Only Dest (XYZ)")
        dest_b = PDPageXYZDestination()
        dest_b.set_page(p1)
        dest_b.set_left(100)
        dest_b.set_top(200)
        dest_b.set_zoom(1.5)
        b.set_destination(dest_b)
        outline.add_last(b)

        # (c) BOTH /A and /Dest. /A is a GoTo to page 0, /Dest is XYZ -> page 2.
        c = PDOutlineItem()
        c.set_title("Both A and Dest")
        goto = PDActionGoTo()
        goto_dest = PDPageXYZDestination()
        goto_dest.set_page(p0)
        goto.set_destination(goto_dest)
        c.set_action(goto)
        dest_c = PDPageXYZDestination()
        dest_c.set_page(p2)
        dest_c.set_left(50)
        dest_c.set_top(75)
        c.set_destination(dest_c)
        outline.add_last(c)

        # (d) Neither.
        d = PDOutlineItem()
        d.set_title("Neither")
        outline.add_last(d)

        doc.save(str(path))
    finally:
        doc.close()


def _escape(title: str | None) -> str:
    if title is None:
        return "null"
    return (
        title.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _fmt_num(v: float | int | None) -> str:
    """Mirror ``OutlineActionDestProbe.fmtNum``: ``null`` for absent, else
    drop a trailing ``.0`` so ``0.0`` -> ``"0"``."""
    if v is None:
        return "null"
    if float(v) == int(v):
        return str(int(v))
    return repr(float(v))


def _resolve_page_index(doc: PDDocument, page_dest: PDPageDestination) -> int:
    page = page_dest.get_page()
    if page is not None:
        idx = doc.get_pages().index_of(page)
        if idx >= 0:
            return idx
    return page_dest.get_page_number()


def _resolve_dest(doc: PDDocument, dest: object | None) -> str:
    if dest is None:
        return "none"
    if isinstance(dest, PDNamedDestination):
        n = dest.get_named_destination()
        return "named:" + ("" if n is None else n)
    if isinstance(dest, PDPageDestination):
        return f"page{_resolve_page_index(doc, dest)}"
    return "none"


def _action_str(doc: PDDocument, action: PDAction | None) -> str:
    if action is None:
        return "none"
    if isinstance(action, PDActionURI):
        uri = action.get_uri()
        return "URI:uri=" + ("" if uri is None else uri)
    if isinstance(action, PDActionGoTo):
        raw = action.get_destination()
        if isinstance(raw, str):
            raw = PDNamedDestination(raw)
        return "GoTo:dest=" + _resolve_dest(doc, raw)
    sub = action.get_sub_type()
    return "null" if sub is None else sub


# Map Python destination class names back to PDFBox simple class names so the
# canonical line is byte-identical. The current "XYZ" branch is handled
# explicitly; all other PDPageDestination subclasses share the same simple
# name between PDFBox and pypdfbox.
_DEST_TYPE_NAME = {
    "PDPageFitDestination": "PDPageFitDestination",
    "PDPageFitHeightDestination": "PDPageFitHeightDestination",
    "PDPageFitWidthDestination": "PDPageFitWidthDestination",
    "PDPageFitRectangleDestination": "PDPageFitRectangleDestination",
    "PDPageFitBoundingBoxDestination": "PDPageFitBoundingBoxDestination",
    "PDPageFitBoundingBoxHeightDestination": "PDPageFitBoundingBoxHeightDestination",
    "PDPageFitBoundingBoxWidthDestination": "PDPageFitBoundingBoxWidthDestination",
}


def _destination_str(doc: PDDocument, dest: object | None) -> str:
    if dest is None:
        return "none"
    if isinstance(dest, PDNamedDestination):
        n = dest.get_named_destination()
        return "named:" + ("" if n is None else n)
    if isinstance(dest, PDPageXYZDestination):
        idx = _resolve_page_index(doc, dest)
        return (
            f"XYZ:page={idx},"
            f"left={_fmt_num(dest.get_left())},"
            f"top={_fmt_num(dest.get_top())},"
            f"zoom={_fmt_num(dest.get_zoom())}"
        )
    if isinstance(dest, PDPageDestination):
        type_name = _DEST_TYPE_NAME.get(type(dest).__name__, type(dest).__name__)
        return f"{type_name}:page={_resolve_page_index(doc, dest)}"
    return "none"


def _dump(doc: PDDocument) -> str:
    outline = doc.get_document_catalog().get_document_outline()
    lines: list[str] = []

    def walk(node, depth: int) -> None:
        for item in node.children():
            lines.append(
                "\t".join(
                    [
                        str(depth),
                        _escape(item.get_title()),
                        _action_str(doc, item.get_action()),
                        _destination_str(doc, item.get_destination()),
                    ]
                )
            )
            walk(item, depth + 1)

    if outline is not None:
        walk(outline, 0)
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_outline_action_dest_matches_pdfbox(tmp_path: Path) -> None:
    """pypdfbox's per-item ``/A`` + ``/Dest`` dump equals PDFBox's, across
    the four cardinality cases (only-A, only-Dest, both, neither)."""
    pdf = tmp_path / "outline_action_dest.pdf"
    _build_pdf(pdf)

    java = run_probe_text("OutlineActionDestProbe", str(pdf))

    doc = PDDocument.load(str(pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()

    assert py == java


@requires_oracle
def test_outline_action_dest_both_present_independence(tmp_path: Path) -> None:
    """The high-value "both /A and /Dest" case: ``get_action()`` and
    ``get_destination()`` must each return their own value independently.

    Pins the salient facts of item (c) inline so a regression that silently
    drops one accessor when the other is present is caught by name, not by
    a byte-diff on an opaque canonical line."""
    pdf = tmp_path / "outline_action_dest_both.pdf"
    _build_pdf(pdf)

    java = run_probe_text("OutlineActionDestProbe", str(pdf))
    java_lines = java.splitlines()
    both_line = next(line for line in java_lines if line.split("\t")[1] == "Both A and Dest")
    parts = both_line.split("\t")

    # PDFBox sees both accessors populated on the same item.
    assert parts[2] == "GoTo:dest=page0"
    assert parts[3] == "XYZ:page=2,left=50,top=75,zoom=null"

    # And pypdfbox sees the same — separately, not via cross-routing.
    doc = PDDocument.load(str(pdf))
    try:
        item = next(
            it
            for it in doc.get_document_catalog().get_document_outline().children()
            if it.get_title() == "Both A and Dest"
        )
        action = item.get_action()
        dest = item.get_destination()

        assert isinstance(action, PDActionGoTo)
        action_dest = action.get_destination()
        assert isinstance(action_dest, PDPageDestination)
        assert _resolve_page_index(doc, action_dest) == 0

        assert isinstance(dest, PDPageXYZDestination)
        assert _resolve_page_index(doc, dest) == 2
        assert dest.get_left() == 50
        assert dest.get_top() == 75
        assert dest.get_zoom() is None
    finally:
        doc.close()


@requires_oracle
def test_outline_action_dest_only_a_only_dest_neither(tmp_path: Path) -> None:
    """Sanity-pin the three single-cardinality cases (only-A, only-Dest,
    neither) so a regression in any one of them is named explicitly."""
    pdf = tmp_path / "outline_action_dest_solo.pdf"
    _build_pdf(pdf)

    java = run_probe_text("OutlineActionDestProbe", str(pdf))
    by_title = {line.split("\t")[1]: line.split("\t") for line in java.splitlines()}

    a = by_title["Only A (URI)"]
    assert a[2] == "URI:uri=https://example.com/a"
    assert a[3] == "none"

    b = by_title["Only Dest (XYZ)"]
    assert b[2] == "none"
    assert b[3] == "XYZ:page=1,left=100,top=200,zoom=1.5"

    d = by_title["Neither"]
    assert d[2] == "none"
    assert d[3] == "none"

    # pypdfbox agrees with the whole dump.
    doc = PDDocument.load(str(pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java
