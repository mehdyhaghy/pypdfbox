"""Live Apache PDFBox differential parity for LINK ANNOTATION destinations.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation.PDAnnotationLink``
destination/action resolution, exercising:

* ``/Dest`` explicit page-target arrays — ``[page /XYZ l t z]``, ``[page /Fit]``,
  ``[page /FitH top]`` (PDFBox ``PDPageFitWidthDestination``, TYPE ``FitH``),
  ``[page /FitV left]`` (PDFBox ``PDPageFitHeightDestination``, TYPE ``FitV``);
* ``/Dest`` named destination (a ``COSString``) resolved through the catalog
  ``/Names /Dests`` name tree via
  :meth:`PDDocumentCatalog.find_named_destination_page`;
* ``/Dest`` named destination that is NOT registered (unresolved);
* ``/A /GoTo`` action whose ``/D`` is an explicit page-target array;
* ``/A /GoTo`` action whose ``/D`` is a named destination string resolved
  through the catalog.

How it works
------------
pypdfbox BUILDS a four-page fixture wiring one link per form (plus the
``/Names /Dests`` registry the named forms resolve against), saves it once,
then both the Java ``LinkDestinationProbe`` and a pypdfbox mirror reader emit
one canonical single-line record per link:

    page<p>.link<i>\t<source>\t<resolved>

``source`` is ``dest`` / ``action`` / ``none``; ``resolved`` is the canonical
target signal (``page<idx>:<fit>[:coords]`` for explicit/resolved targets,
``named:<name>->...`` for the named forms). The two emissions are compared
byte-for-byte.

A known, intentional divergence (wave 1454): ``PDActionGoTo.get_destination``
returns a ``str`` for a name/string ``/D`` rather than a ``PDNamedDestination``.
The mirror reader works WITH that contract — it wraps a ``str`` named target in
a :class:`PDNamedDestination` before resolving, asserting on the value-level
result (the resolved page), exactly as the Java side resolves via
``catalog.findNamedDestinationPage``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSArray, COSFloat, COSName, COSNull
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDDestinationNameTreeNode,
    PDNamedDestination,
    PDPageDestination,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "LinkDestinationProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors LinkDestinationProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text == "-0":
        text = "0"
    return text


def _coord(value: float | None) -> str:
    """Mirror the Java ``coord``: an unset slot prints ``null``."""
    if value is None:
        return "null"
    return _canon_float(value)


# ---------------------------------------------------------------------------
# fixture builder — pypdfbox builds the PDF the probe reads back
# ---------------------------------------------------------------------------


def _explicit_array(page: PDPage, type_name: str, *coords: float | None) -> COSArray:
    arr = COSArray()
    arr.add(page.get_cos_object())
    arr.add(COSName.get_pdf_name(type_name))
    for c in coords:
        # ``None`` writes a real COSNull so the unset XYZ slot exercises the
        # "use the current viewer value" path (PDFBox getX() returns the -1
        # sentinel; pypdfbox returns None — both render as "null").
        arr.add(COSFloat(float(c)) if c is not None else COSNull.NULL)
    return arr


def _build(path: Path) -> None:
    """Build a four-page fixture with one link per destination form."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(4)]
        for pg in pages:
            doc.add_page(pg)

        # Register two named destinations in /Names /Dests pointing at pages
        # 2 and 3 respectively (XYZ on page2, Fit on page3).
        xyz_named = PDPageXYZDestination()
        xyz_named.set_page(pages[2])
        xyz_named.set_left(100)
        xyz_named.set_top(700)
        xyz_named.set_zoom(2)
        fit_named = PDPageFitDestination()
        fit_named.set_page(pages[3])

        dests_tree = PDDestinationNameTreeNode()
        dests_tree.set_names({"DestA": xyz_named, "DestB": fit_named})
        names = PDDocumentNameDictionary()
        names.set_dests(dests_tree)
        doc.get_document_catalog().set_names(names)

        # link 0 on page0: /Dest explicit XYZ array -> page1.
        l0 = PDAnnotationLink()
        l0.set_rectangle(PDRectangle(10, 700, 110, 720))
        l0.set_destination(
            PDDestination.create(_explicit_array(pages[1], "XYZ", 50, 600, None))
        )
        pages[0].add_annotation(l0)

        # link 1 on page0: /Dest explicit Fit array -> page2.
        l1 = PDAnnotationLink()
        l1.set_rectangle(PDRectangle(10, 680, 110, 700))
        fit = PDPageFitDestination()
        fit.set_page(pages[2])
        l1.set_destination(fit)
        pages[0].add_annotation(l1)

        # link 2 on page0: /Dest explicit FitH (FitWidth, top coord) -> page3.
        l2 = PDAnnotationLink()
        l2.set_rectangle(PDRectangle(10, 660, 110, 680))
        fith = PDPageFitWidthDestination()
        fith.set_page(pages[3])
        fith.set_top(500)
        l2.set_destination(fith)
        pages[0].add_annotation(l2)

        # link 3 on page1: /Dest explicit FitV (FitHeight, left coord) -> page0.
        l3 = PDAnnotationLink()
        l3.set_rectangle(PDRectangle(10, 640, 110, 660))
        fitv = PDPageFitHeightDestination()
        fitv.set_page(pages[0])
        fitv.set_left(20)
        l3.set_destination(fitv)
        pages[1].add_annotation(l3)

        # link 4 on page1: /Dest named string "DestA" -> resolves to page2 XYZ.
        l4 = PDAnnotationLink()
        l4.set_rectangle(PDRectangle(10, 620, 110, 640))
        l4.set_destination("DestA")
        pages[1].add_annotation(l4)

        # link 5 on page1: /Dest named string "Missing" -> unresolved.
        l5 = PDAnnotationLink()
        l5.set_rectangle(PDRectangle(10, 600, 110, 620))
        l5.set_destination("Missing")
        pages[1].add_annotation(l5)

        # link 6 on page2: /A /GoTo explicit array -> page0 XYZ.
        l6 = PDAnnotationLink()
        l6.set_rectangle(PDRectangle(10, 580, 110, 600))
        go6 = PDActionGoTo()
        go6.set_destination(
            PDDestination.create(_explicit_array(pages[0], "XYZ", 0, 800, 1))
        )
        l6.set_action(go6)
        pages[2].add_annotation(l6)

        # link 7 on page2: /A /GoTo named /D "DestB" -> resolves to page3 Fit.
        l7 = PDAnnotationLink()
        l7.set_rectangle(PDRectangle(10, 560, 110, 580))
        go7 = PDActionGoTo()
        go7.set_named_destination("DestB")
        l7.set_action(go7)
        pages[2].add_annotation(l7)

        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# pypdfbox reader — mirrors LinkDestinationProbe byte-for-byte
# ---------------------------------------------------------------------------


def _page_signal(dest: PDPageDestination) -> str:
    idx = dest.retrieve_page_number()
    if isinstance(dest, PDPageXYZDestination):
        return (
            f"page{idx}:XYZ:left={_coord(dest.get_left())}"
            f",top={_coord(dest.get_top())}"
            f",zoom={_coord(dest.get_zoom())}"
        )
    # PDPageFitWidthDestination is TYPE "FitH" with a top coord; the height
    # variant is TYPE "FitV" with a left coord. Mirror upstream's class names.
    if isinstance(dest, PDPageFitWidthDestination):
        return f"page{idx}:FitH:top={_coord(dest.get_top())}"
    if isinstance(dest, PDPageFitHeightDestination):
        return f"page{idx}:FitV:left={_coord(dest.get_left())}"
    if isinstance(dest, PDPageFitDestination):
        return f"page{idx}:Fit"
    return f"page{idx}:{type(dest).__name__}"


def _resolve(catalog, dest) -> str:
    if dest is None:
        return "none"
    # Work WITH the wave-1454 contract: PDActionGoTo.get_destination returns a
    # bare str for a name/string /D. Wrap it so the catalog lookup runs the same
    # path Java's findNamedDestinationPage does.
    if isinstance(dest, str):
        dest = PDNamedDestination(dest)
    if isinstance(dest, PDNamedDestination):
        name = dest.get_named_destination() or ""
        page_dest = catalog.find_named_destination_page(dest)
        if page_dest is None:
            return f"named:{name}->unresolved"
        return f"named:{name}->{_page_signal(page_dest)}"
    if isinstance(dest, PDPageDestination):
        return _page_signal(dest)
    return "none"


def _py_records(path: Path) -> str:
    out: list[str] = []
    doc = PDDocument.load(path)
    try:
        catalog = doc.get_document_catalog()
        for p, page in enumerate(doc.get_pages()):
            link_index = 0
            for annot in page.get_annotations():
                if not isinstance(annot, PDAnnotationLink):
                    continue
                dest = annot.get_destination()
                if dest is not None:
                    source = "dest"
                    resolved = _resolve(catalog, dest)
                else:
                    action = annot.get_action()
                    if isinstance(action, PDActionGoTo):
                        source = "action"
                        resolved = _resolve(catalog, action.get_destination())
                    else:
                        source = "none"
                        resolved = "none"
                out.append(
                    f"page{p}.link{link_index}\t{source}\t{resolved}\n"
                )
                link_index += 1
    finally:
        doc.close()
    return "".join(out)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_link_destination_records_match_pdfbox() -> None:
    """Link /Dest (explicit XYZ/Fit/FitH/FitV, named, unresolved) and /A /GoTo
    (explicit + named) destination resolution match Apache PDFBox exactly."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "link_dest.pdf"
        _build(out)
        java = run_probe_text(_PROBE, str(out))
        py = _py_records(out)
    assert py == java, (
        f"link-destination record mismatch:\n--- pypdfbox ---\n{py}\n"
        f"--- PDFBox ---\n{java}"
    )
    # Sanity: every branch is exercised in the built fixture.
    assert "dest\tpage1:XYZ:left=50,top=600,zoom=null" in py
    assert "dest\tpage2:Fit" in py
    assert "dest\tpage3:FitH:top=500" in py
    assert "dest\tpage0:FitV:left=20" in py
    assert "dest\tnamed:DestA->page2:XYZ:left=100,top=700,zoom=2" in py
    assert "dest\tnamed:Missing->unresolved" in py
    assert "action\tpage0:XYZ:left=0,top=800,zoom=1" in py
    assert "action\tnamed:DestB->page3:Fit" in py


@requires_oracle
def test_named_destination_resolution_matches_pdfbox() -> None:
    """The /Names /Dests name-tree resolution of a link's named /Dest and a
    /A /GoTo named /D resolves to the same page index PDFBox reports."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "link_dest.pdf"
        _build(out)
        java = run_probe_text(_PROBE, str(out))

        doc = PDDocument.load(out)
        try:
            catalog = doc.get_document_catalog()
            # /Dest named string "DestA" -> page index 2.
            dest_a = catalog.find_named_destination_page(
                PDNamedDestination("DestA")
            )
            assert dest_a is not None
            assert dest_a.retrieve_page_number() == 2
            assert isinstance(dest_a, PDPageXYZDestination)

            # /A /GoTo named "DestB" -> page index 3 (Fit).
            dest_b = catalog.find_named_destination_page(
                PDNamedDestination("DestB")
            )
            assert dest_b is not None
            assert dest_b.retrieve_page_number() == 3
            assert isinstance(dest_b, PDPageFitDestination)

            # An unregistered name resolves to None (matching unresolved).
            assert (
                catalog.find_named_destination_page(PDNamedDestination("Missing"))
                is None
            )
        finally:
            doc.close()

    assert "named:DestA->page2" in java
    assert "named:DestB->page3:Fit" in java
    assert "named:Missing->unresolved" in java
