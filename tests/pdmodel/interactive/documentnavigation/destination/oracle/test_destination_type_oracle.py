"""Live PDFBox differential parity for explicit page-destination TYPES +
COORDINATES (``pypdfbox.pdmodel.interactive.documentnavigation.destination``).

Builds a small PDF whose catalog ``/Names /Dests`` name tree carries one entry
per destination shape — XYZ (full / per-coordinate null / all-null), Fit, FitB,
FitH, FitBH, FitV, FitBV, FitR (full + null edge) — then compares pypdfbox's
resolved destination type + coordinates against Apache PDFBox's, via the
``DestTypeProbe`` Java oracle.

Each destination is reduced to one canonical line so the two languages compare
byte-for-byte without tripping over object layout or float rendering. Canonical
line grammar (must match ``oracle/probes/DestTypeProbe.java``)::

    <name>\t<typeName>\t<coords>

Where ``typeName`` is the destination array's ``/D[1]`` type name (XYZ / Fit /
FitB / FitH / FitBH / FitV / FitBV / FitR) — the behaviourally-meaningful
identity, NOT the Java wrapper class, which upstream collapses (FitH and FitBH
both resolve to ``PDPageFitWidthDestination``; pypdfbox keeps dedicated
same page-fit classes as PDFBox). ``coords`` are the
type-appropriate getters, with both languages normalising the "unset" slot to
``-1`` (upstream's int / float sentinel; pypdfbox's ``None``).

Coordinate values in the battery are integral so int (left/top/right/bottom)
and float (XYZ zoom) getters render identically across the language boundary.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDPageDestination,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _array(items: list) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _build_battery_pdf(path: str) -> None:
    """Write a single-page PDF whose ``/Names /Dests`` tree exercises every
    destination type + a representative set of null-coordinate shapes."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        page_cos = page.get_cos_object()

        def name(s: str) -> COSName:
            return COSName.get_pdf_name(s)

        null = COSNull.NULL

        def i(v: int) -> COSInteger:
            return COSInteger.get(v)

        # name -> destination array. Every array targets the (only) page.
        battery: dict[str, COSArray] = {
            "xyz_full": _array([page_cos, name("XYZ"), i(100), i(200), i(2)]),
            "xyz_null_left": _array([page_cos, name("XYZ"), null, i(200), i(2)]),
            "xyz_null_top": _array([page_cos, name("XYZ"), i(100), null, i(2)]),
            "xyz_null_zoom": _array([page_cos, name("XYZ"), i(100), i(200), null]),
            "xyz_all_null": _array([page_cos, name("XYZ"), null, null, null]),
            "fit": _array([page_cos, name("Fit")]),
            "fitb": _array([page_cos, name("FitB")]),
            "fith": _array([page_cos, name("FitH"), i(300)]),
            "fith_null": _array([page_cos, name("FitH"), null]),
            "fitbh": _array([page_cos, name("FitBH"), i(350)]),
            "fitbh_null": _array([page_cos, name("FitBH"), null]),
            "fitv": _array([page_cos, name("FitV"), i(120)]),
            "fitv_null": _array([page_cos, name("FitV"), null]),
            "fitbv": _array([page_cos, name("FitBV"), i(130)]),
            "fitbv_null": _array([page_cos, name("FitBV"), null]),
            "fitr": _array([page_cos, name("FitR"), i(10), i(20), i(30), i(40)]),
            "fitr_null_top": _array([page_cos, name("FitR"), i(10), i(20), i(30), null]),
        }

        names_arr = COSArray()
        for key in sorted(battery):
            names_arr.add(COSString(key))
            names_arr.add(battery[key])
        dests_leaf = COSDictionary()
        dests_leaf.set_item(name("Names"), names_arr)

        names_dict = COSDictionary()
        names_dict.set_item(name("Dests"), dests_leaf)

        doc.get_document_catalog().get_cos_object().set_item(name("Names"), names_dict)
        doc.save(path)
    finally:
        doc.close()


def _num(value: float | None) -> str:
    """Render one coordinate exactly as ``DestTypeProbe.num`` does: the unset
    slot (``None`` here, ``-1``/``-1.0`` upstream) prints as ``-1``; an integral
    value prints as a plain int."""
    if value is None:
        return "-1"
    f = float(value)
    if f == int(f):
        return str(int(f))
    return str(f)


def _coords(dest: PDPageDestination, type_name: str) -> str:
    """Mirror ``DestTypeProbe.coords`` for the pypdfbox concrete subclass."""
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


def _dump_dests(doc: PDDocument) -> str:
    """Reproduce ``DestTypeProbe`` in pypdfbox terms: walk the catalog
    ``/Names /Dests`` tree and emit ``<name>\\t<typeName>\\t<coords>`` per
    entry, sorted by name."""
    catalog = doc.get_document_catalog()
    names = catalog.get_names()
    lines: list[str] = []
    if names is not None:
        dests = names.get_dests()
        if dests is not None:
            mapping = dests.get_names() or {}
            for key in sorted(mapping):
                dest = mapping[key]
                if dest is None:
                    lines.append(f"{key}\tnull\t")
                    continue
                type_name = dest.get_cos_object().get_name(1) or "null"
                lines.append(f"{key}\t{type_name}\t{_coords(dest, type_name)}")
    return "".join(line + "\n" for line in lines)


@pytest.fixture(scope="module")
def battery_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_dest_type_battery.pdf")
    os.close(fd)
    _build_battery_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_destination_types_and_coordinates_match_pdfbox(battery_pdf: Path) -> None:
    """pypdfbox's resolved destination type + coordinates equal PDFBox's for
    every destination shape in the battery."""
    java = run_probe_text("DestTypeProbe", str(battery_pdf))
    doc = PDDocument.load(str(battery_pdf))
    try:
        py = _dump_dests(doc)
    finally:
        doc.close()
    assert py == java
    # Sanity: the battery must actually cover every type the probe knows.
    for type_name in ("XYZ", "Fit\t", "FitB\t", "FitH\t", "FitBH\t", "FitV\t",
                      "FitBV\t", "FitR\t"):
        assert type_name in java


# --- direct PDDestination.create dispatch parity --------------------------
#
# The name-tree path above resolves through PDDestination.create internally;
# these cases pin the factory's concrete-subtype dispatch directly so a wrong
# dispatch shows up as a subclass mismatch rather than only a coordinate diff.

_DISPATCH_CASES = [
    ("XYZ", PDPageXYZDestination),
    ("Fit", PDPageFitDestination),
    ("FitB", PDPageFitDestination),
    ("FitH", PDPageFitWidthDestination),
    ("FitBH", PDPageFitWidthDestination),
    ("FitV", PDPageFitHeightDestination),
    ("FitBV", PDPageFitHeightDestination),
    ("FitR", PDPageFitRectangleDestination),
]


@pytest.mark.parametrize(
    ("type_name", "expected_cls"),
    _DISPATCH_CASES,
    ids=[c[0] for c in _DISPATCH_CASES],
)
def test_create_dispatches_to_expected_subclass(type_name: str, expected_cls) -> None:
    """``PDDestination.create`` builds the expected concrete subclass and keeps
    the ``/D[1]`` type name intact.

    Bounding-box variants reuse the same classes as PDFBox while preserving
    the distinct ``/D[1]`` type name.
    """
    arr = _array([COSInteger.get(0), COSName.get_pdf_name(type_name)])
    dest = PDDestination.create(arr)
    assert isinstance(dest, expected_cls)
    assert dest.get_cos_object().get_name(1) == type_name
