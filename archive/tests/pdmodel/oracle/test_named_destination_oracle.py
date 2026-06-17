"""Live PDFBox differential parity for NAMED-DESTINATION RESOLUTION
(``pypdfbox.pdmodel`` catalog / name-tree / destination accessors).

Builds a multi-page PDF that wires named destinations through every
resolution surface PDFBox exposes, then compares pypdfbox's resolved page
index + fit type + coordinates against Apache PDFBox's, via the
``NamedDestProbe`` Java oracle.

Resolution surfaces exercised:

* **legacy ``/Dests``** — a flat name → destination dictionary directly on
  the catalog (PDF 1.1). ``intro`` → ``/XYZ`` on page index 1.
* **modern ``/Names /Dests`` name tree** — a multi-level tree (root → one
  intermediate ``/Kids`` node → two ``/Names`` leaves, each carrying
  ``/Limits``). ``chapter1`` → ``/FitH`` on page index 2; ``chapter2`` →
  ``/FitR`` on page index 3. This pins the binary-descent ``/Kids`` +
  ``/Limits`` traversal, not just a flat leaf.
* **link annotation ``/Dest`` as a named string** — the link on page 0
  carries ``/Dest (chapter1)``; the name resolves through the catalog.
* **GoTo action ``/D`` as a named string** — the catalog ``/OpenAction`` is
  a ``GoTo`` whose ``/D`` is ``(chapter2)``; the name resolves through the
  catalog.

Each resolved destination is reduced to ``<surface>\\t<pageIndex>\\t<typeName>\\t<coords>``
so the two languages compare byte-for-byte. The page index comes from
``PDPageDestination.retrieve_page_number`` / upstream ``retrievePageNumber``;
the type name from ``/D[1]``; ``coords`` follow the sibling
``DestTypeProbe`` grammar (XYZ → left,top,zoom; FitH/FitBH → top; FitV/FitBV
→ left; FitR → left,bottom,right,top; Fit/FitB → empty).

Note the deliberate, pre-existing local-API divergence (see ``CHANGES.md``):
pypdfbox's ``PDActionGoTo.get_destination`` returns a bare ``str`` for a
named-string ``/D`` whereas upstream returns a ``PDNamedDestination``. That
convention is orthogonal to *resolution* — both languages resolve the same
name to the same page/fit/coords — so this test reads the name through the
string accessor (``get_named_destination``) and resolves it via the catalog,
which is the behaviour the probe pins.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _array(items: list) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _build_pdf(path: str) -> None:
    """Write a 5-page PDF wiring named destinations through every surface."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(5)]
        for page in pages:
            doc.add_page(page)
        pc = [page.get_cos_object() for page in pages]
        catalog = doc.get_document_catalog().get_cos_object()

        # (a) Legacy catalog /Dests flat dict: "intro" -> /XYZ on page index 1.
        dests = COSDictionary()
        dests.set_item(
            _name("intro"),
            _array([pc[1], _name("XYZ"), _i(100), _i(700), _i(2)]),
        )
        catalog.set_item(_name("Dests"), dests)

        # (b) Modern /Names /Dests name tree: multi-level /Kids + /Limits.
        # root -> intermediate(/Kids) -> two leaves(/Names + /Limits).
        leaf1 = COSDictionary()
        leaf1.set_item(
            _name("Limits"), _array([COSString("chapter1"), COSString("chapter1")])
        )
        leaf1.set_item(
            _name("Names"),
            _array([COSString("chapter1"), _array([pc[2], _name("FitH"), _i(650)])]),
        )
        leaf2 = COSDictionary()
        leaf2.set_item(
            _name("Limits"), _array([COSString("chapter2"), COSString("chapter2")])
        )
        leaf2.set_item(
            _name("Names"),
            _array(
                [
                    COSString("chapter2"),
                    _array([pc[3], _name("FitR"), _i(10), _i(20), _i(30), _i(40)]),
                ]
            ),
        )
        intermediate = COSDictionary()
        intermediate.set_item(
            _name("Limits"), _array([COSString("chapter1"), COSString("chapter2")])
        )
        intermediate.set_item(_name("Kids"), _array([leaf1, leaf2]))
        dests_tree_root = COSDictionary()
        dests_tree_root.set_item(_name("Kids"), _array([intermediate]))
        names_dict = COSDictionary()
        names_dict.set_item(_name("Dests"), dests_tree_root)
        catalog.set_item(_name("Names"), names_dict)

        # (c) Link annotation on page 0 whose /Dest is a named string.
        link = COSDictionary()
        link.set_item(_name("Type"), _name("Annot"))
        link.set_item(_name("Subtype"), _name("Link"))
        link.set_item(_name("Rect"), _array([_i(0), _i(0), _i(100), _i(100)]))
        link.set_item(_name("Dest"), COSString("chapter1"))
        pc[0].set_item(_name("Annots"), _array([link]))

        # (d) Catalog /OpenAction GoTo whose /D is a named string.
        goto = COSDictionary()
        goto.set_item(_name("Type"), _name("Action"))
        goto.set_item(_name("S"), _name("GoTo"))
        goto.set_item(_name("D"), COSString("chapter2"))
        catalog.set_item(_name("OpenAction"), goto)

        doc.save(path)
    finally:
        doc.close()


def _num(value: float | None) -> str:
    """Render one coordinate as ``NamedDestProbe.num`` does."""
    if value is None:
        return "-1"
    f = float(value)
    return str(int(f)) if f == int(f) else str(f)


def _coords(dest: PDPageDestination, type_name: str) -> str:
    if type_name == "XYZ":
        return f"{_num(dest.get_left())},{_num(dest.get_top())},{_num(dest.get_zoom())}"
    if type_name in ("FitH", "FitBH"):
        return _num(dest.get_top())
    if type_name in ("FitV", "FitBV"):
        return _num(dest.get_left())
    if type_name == "FitR":
        return (
            f"{_num(dest.get_left())},{_num(dest.get_bottom())},"
            f"{_num(dest.get_right())},{_num(dest.get_top())}"
        )
    # Fit / FitB carry no coordinates.
    return ""


def _resolve(catalog, name: str | None) -> str:
    """Resolve a named destination through the catalog and reduce it to
    ``<pageIndex>\\t<typeName>\\t<coords>`` (mirrors ``NamedDestProbe``)."""
    if name is None:
        return "-1\tnull\t"
    dest = catalog.find_named_destination_page(PDNamedDestination(name))
    if dest is None:
        return "-1\tnull\t"
    type_name = dest.get_cos_object().get_name(1) or "null"
    return f"{dest.retrieve_page_number()}\t{type_name}\t{_coords(dest, type_name)}"


def _dump(doc: PDDocument) -> str:
    """Reproduce ``NamedDestProbe`` in pypdfbox terms."""
    catalog = doc.get_document_catalog()
    lines: list[str] = []

    # Legacy /Dests flat dictionary.
    lines.append(f"dests:intro\t{_resolve(catalog, 'intro')}")
    # Modern /Names /Dests name tree (multi-level).
    lines.append(f"tree:chapter1\t{_resolve(catalog, 'chapter1')}")
    lines.append(f"tree:chapter2\t{_resolve(catalog, 'chapter2')}")

    # Link annotation whose /Dest is a named string.
    for page_index, page in enumerate(doc.get_pages()):
        for annot in page.get_annotations():
            if isinstance(annot, PDAnnotationLink):
                dest = annot.get_destination()
                if isinstance(dest, PDNamedDestination):
                    name = dest.get_named_destination()
                    lines.append(f"link:{page_index}\t{_resolve(catalog, name)}")

    # OpenAction GoTo with a named /D.
    open_action = catalog.get_open_action()
    if isinstance(open_action, PDActionGoTo):
        name = open_action.get_named_destination()
        if name is not None:
            lines.append(f"action\t{_resolve(catalog, name)}")

    return "".join(line + "\n" for line in lines)


@pytest.fixture(scope="module")
def named_dest_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_named_dest.pdf")
    os.close(fd)
    _build_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_named_destinations_resolve_like_pdfbox(named_dest_pdf: Path) -> None:
    """pypdfbox resolves every named destination — via the legacy ``/Dests``
    dict, the multi-level ``/Names /Dests`` name tree, a link annotation's
    named ``/Dest``, and a GoTo action's named ``/D`` — to the SAME page
    index + fit type + coordinates as Apache PDFBox."""
    java = run_probe_text("NamedDestProbe", str(named_dest_pdf))
    doc = PDDocument.load(str(named_dest_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the battery must actually cover every resolution surface.
    assert "dests:intro\t" in java
    assert "tree:chapter1\t" in java
    assert "tree:chapter2\t" in java
    assert "link:0\t" in java
    assert "action\t" in java
    # And it must not have silently degraded to "unresolved" everywhere.
    assert "\t-1\tnull\t" not in java


@requires_oracle
def test_legacy_dests_and_name_tree_resolve_to_distinct_pages(
    named_dest_pdf: Path,
) -> None:
    """The legacy ``/Dests`` path and the name-tree path each resolve to
    their own page — proving neither shadows the other (legacy ``intro`` →
    page 1; tree ``chapter1`` → page 2; tree ``chapter2`` → page 3)."""
    doc = PDDocument.load(str(named_dest_pdf))
    try:
        catalog = doc.get_document_catalog()
        intro = catalog.find_named_destination_page(PDNamedDestination("intro"))
        ch1 = catalog.find_named_destination_page(PDNamedDestination("chapter1"))
        ch2 = catalog.find_named_destination_page(PDNamedDestination("chapter2"))
        assert intro is not None and intro.retrieve_page_number() == 1
        assert ch1 is not None and ch1.retrieve_page_number() == 2
        assert ch2 is not None and ch2.retrieve_page_number() == 3
        # Fit types are preserved through resolution.
        assert intro.get_cos_object().get_name(1) == "XYZ"
        assert ch1.get_cos_object().get_name(1) == "FitH"
        assert ch2.get_cos_object().get_name(1) == "FitR"
    finally:
        doc.close()
