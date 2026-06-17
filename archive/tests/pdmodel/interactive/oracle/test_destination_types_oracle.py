"""Live PDFBox differential parity for the complete set of explicit page
destination types — PDF 32000-1 §12.3.2.2 (Table 151) — plus named-destination
resolution through BOTH catalog surfaces.

Each destination has six explicit array syntaxes (XYZ / Fit / FitH / FitV /
FitR / FitB+FitBH+FitBV bounding-box variants) and two indirection surfaces
(/Names /Dests name tree, legacy /Dests catalog dict). The companion
``DestinationTypesProbe`` emits one JSON object per (surface, key) carrying:

* ``surface`` — ``"tree"`` for /Names /Dests, ``"dests"`` for legacy /Dests.
* ``key`` — the destination name (sort key).
* ``dest_type`` — upstream Java simple class name of the resolved
  :class:`PDPageDestination` subclass. Both upstream and pypdfbox collapse the
  FitB / FitBH / FitBV bounding-box variants onto the non-bounded wrapper
  classes (``FitB`` → ``PDPageFitDestination``, ``FitBH`` →
  ``PDPageFitWidthDestination``, ``FitBV`` → ``PDPageFitHeightDestination``);
  the bounded type is carried by each class's ``TYPE_BOUNDED`` flag in the
  ``/D[1]`` name, not by a dedicated subclass. The ``dest_type`` field
  therefore compares byte-for-byte, and the behaviourally-observable
  ``type_name`` (/D[1]) and the coordinate getters are identical too.
* ``type_name`` — the array's ``/D[1]`` PDF name (XYZ / Fit / FitB / FitH /
  FitBH / FitV / FitBV / FitR). This is the behaviourally-meaningful identity.
* ``page_index`` — 0-based, via :meth:`PDPageDestination.retrieve_page_number`.
* ``left`` / ``top`` / ``right`` / ``bottom`` / ``zoom`` — the type-appropriate
  getters. Each is ``null`` (JSON) / ``None`` (Python) where the destination
  type has no such accessor (e.g. ``zoom`` on FitR) AND where the slot is
  explicitly the PDF "retain current viewer value" sentinel (``null`` in the
  array, ``-1`` in the upstream Java getter).

Both ``Fit`` and the bounding-box variants ``FitB`` / ``FitBH`` / ``FitBV`` and
the "all coords null" XYZ case are exercised so each accessor is asserted on
every concrete subclass.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
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

# pypdfbox mirrors upstream's class set exactly: the FitB / FitBH / FitBV
# bounding-box variants are carried by the non-bounded wrapper classes'
# ``TYPE_BOUNDED`` flag (in /D[1]), not by dedicated subclasses. The concrete
# Python class name therefore equals the upstream Java simple class name, so
# the JSON ``dest_type`` field compares byte-for-byte with no remapping.
_PYPDFBOX_TO_UPSTREAM_CLASS = {
    PDPageXYZDestination: "PDPageXYZDestination",
    PDPageFitDestination: "PDPageFitDestination",
    PDPageFitWidthDestination: "PDPageFitWidthDestination",
    PDPageFitHeightDestination: "PDPageFitHeightDestination",
    PDPageFitRectangleDestination: "PDPageFitRectangleDestination",
}


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _arr(items: list) -> COSArray:
    arr = COSArray()
    for item in items:
        arr.add(item)
    return arr


def _build_battery_pdf(path: str) -> None:
    """Two pages — page 0 hosts legacy /Dests, page 1 hosts /Names /Dests."""
    doc = PDDocument()
    try:
        pages = [PDPage() for _ in range(2)]
        for p in pages:
            doc.add_page(p)
        pc = [p.get_cos_object() for p in pages]
        null = COSNull.NULL

        # --- Modern /Names /Dests name tree: every type + null-coord shapes.
        tree_battery: dict[str, COSArray] = {
            "a_xyz_full": _arr([pc[1], _name("XYZ"), _i(100), _i(200), _i(2)]),
            "b_xyz_null_left": _arr([pc[1], _name("XYZ"), null, _i(200), _i(2)]),
            "c_xyz_all_null": _arr([pc[1], _name("XYZ"), null, null, null]),
            "d_fit": _arr([pc[1], _name("Fit")]),
            "e_fitb": _arr([pc[1], _name("FitB")]),
            "f_fith": _arr([pc[1], _name("FitH"), _i(300)]),
            "g_fith_null": _arr([pc[1], _name("FitH"), null]),
            "h_fitbh": _arr([pc[1], _name("FitBH"), _i(350)]),
            "i_fitv": _arr([pc[1], _name("FitV"), _i(120)]),
            "j_fitv_null": _arr([pc[1], _name("FitV"), null]),
            "k_fitbv": _arr([pc[1], _name("FitBV"), _i(130)]),
            "l_fitr": _arr([pc[1], _name("FitR"), _i(10), _i(20), _i(30), _i(40)]),
            "m_fitr_null_top": _arr(
                [pc[1], _name("FitR"), _i(10), _i(20), _i(30), null]
            ),
        }
        names_arr = COSArray()
        for key in sorted(tree_battery):
            names_arr.add(COSString(key))
            names_arr.add(tree_battery[key])
        leaf = COSDictionary()
        leaf.set_item(_name("Names"), names_arr)
        names_dict = COSDictionary()
        names_dict.set_item(_name("Dests"), leaf)

        # --- Legacy catalog /Dests flat dict: one entry per type, points to page 0.
        legacy = COSDictionary()
        legacy.set_item(
            _name("legacy_xyz"),
            _arr([pc[0], _name("XYZ"), _i(50), _i(60), _i(1)]),
        )
        legacy.set_item(_name("legacy_fit"), _arr([pc[0], _name("Fit")]))
        legacy.set_item(_name("legacy_fitb"), _arr([pc[0], _name("FitB")]))
        legacy.set_item(_name("legacy_fith"), _arr([pc[0], _name("FitH"), _i(70)]))
        legacy.set_item(_name("legacy_fitv"), _arr([pc[0], _name("FitV"), _i(80)]))
        legacy.set_item(
            _name("legacy_fitr"),
            _arr([pc[0], _name("FitR"), _i(1), _i(2), _i(3), _i(4)]),
        )

        catalog = doc.get_document_catalog().get_cos_object()
        catalog.set_item(_name("Names"), names_dict)
        catalog.set_item(_name("Dests"), legacy)

        doc.save(path)
    finally:
        doc.close()


def _coord(value) -> object:
    """Normalise a pypdfbox coordinate getter result to the same JSON-friendly
    shape the probe emits: ``None`` survives as JSON ``null``; integral floats
    collapse to ``int`` so the json.dumps output matches the probe's
    ``Float.toString(n)`` (which prints "2" not "2.0" for integral values when
    we route through ``coord(Float)``)."""
    if value is None:
        return None
    f = float(value)
    if f == int(f):
        return int(f)
    return f


def _coord_or_none(dest: PDPageDestination, accessor: str) -> object:
    """Return ``_coord(getattr(dest, accessor)())`` if the accessor exists on
    this destination subclass, else ``None``. Mirrors the probe's
    ``instanceof``-keyed coordinate readers — accessors that don't apply to a
    concrete class emit JSON ``null``."""
    getter = getattr(dest, accessor, None)
    if getter is None:
        return None
    return _coord(getter())


def _describe(
    surface: str, key: str, dest: PDPageDestination | None
) -> dict[str, object]:
    if dest is None:
        return {
            "surface": surface,
            "key": key,
            "dest_type": None,
            "type_name": None,
            "page_index": -1,
            "left": None,
            "top": None,
            "right": None,
            "bottom": None,
            "zoom": None,
        }
    cls = type(dest)
    upstream_class = _PYPDFBOX_TO_UPSTREAM_CLASS.get(cls, cls.__name__)
    cos = dest.get_cos_object()
    type_name = cos.get_name(1) if isinstance(cos, COSArray) else None
    return {
        "surface": surface,
        "key": key,
        "dest_type": upstream_class,
        "type_name": type_name,
        "page_index": dest.retrieve_page_number(),
        "left": _coord_or_none(dest, "get_left"),
        "top": _coord_or_none(dest, "get_top"),
        "right": _coord_or_none(dest, "get_right"),
        "bottom": _coord_or_none(dest, "get_bottom"),
        "zoom": _coord_or_none(dest, "get_zoom"),
    }


def _dump(doc: PDDocument) -> list[dict[str, object]]:
    """Walk both catalog surfaces and emit the same canonical (surface, key)
    sorted list the probe produces."""
    catalog = doc.get_document_catalog()
    entries: list[dict[str, object]] = []

    # 1) /Names /Dests name tree.
    names_dict = catalog.get_names()
    if names_dict is not None:
        dests = names_dict.get_dests()
        if dests is not None:
            mapping = dests.get_names() or {}
            for key in sorted(mapping):
                entries.append(_describe("tree", key, mapping[key]))

    # 2) Legacy catalog /Dests flat dictionary. Resolve through the catalog so
    # we exercise the same find_named_destination_page() path the probe takes.
    legacy = catalog.get_cos_object().get_dictionary_object(_name("Dests"))
    if isinstance(legacy, COSDictionary):
        # Iterate the underlying dict in key-sorted order to match the probe.
        legacy_keys = sorted(k.get_name() for k in legacy.key_set())
        for key in legacy_keys:
            dest = catalog.find_named_destination_page(PDNamedDestination(key))
            entries.append(_describe("dests", key, dest))
    return entries


@pytest.fixture(scope="module")
def battery_pdf() -> Path:
    fd, path = tempfile.mkstemp(suffix="_destination_types_battery.pdf")
    os.close(fd)
    _build_battery_pdf(path)
    try:
        yield Path(path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


@requires_oracle
def test_destination_types_match_pdfbox(battery_pdf: Path) -> None:
    """pypdfbox's resolved destination type + class + coordinates match
    Apache PDFBox's for every PDF §12.3.2.2 destination shape, across BOTH the
    /Names /Dests name tree and the legacy /Dests catalog dict."""
    java = json.loads(run_probe_text("DestinationTypesProbe", str(battery_pdf)))
    doc = PDDocument.load(str(battery_pdf))
    try:
        py = _dump(doc)
    finally:
        doc.close()
    assert py == java

    # Sanity: the battery actually covers every type AND both surfaces.
    type_names = {e["type_name"] for e in java}
    assert type_names == {"XYZ", "Fit", "FitB", "FitH", "FitBH", "FitV", "FitBV", "FitR"}
    surfaces = {e["surface"] for e in java}
    assert surfaces == {"tree", "dests"}


# --- direct PDDestination.create dispatch parity --------------------------
#
# Pin each /D[1] type name → expected concrete pypdfbox subclass, and confirm
# the subclass maps to the upstream Java simple class name we compare against
# in the JSON oracle. A wrong dispatch surfaces as a subclass mismatch here
# rather than only as a coordinate diff in the oracle assertion.

_DISPATCH_CASES = [
    ("XYZ", PDPageXYZDestination, "PDPageXYZDestination"),
    ("Fit", PDPageFitDestination, "PDPageFitDestination"),
    ("FitB", PDPageFitDestination, "PDPageFitDestination"),
    ("FitH", PDPageFitWidthDestination, "PDPageFitWidthDestination"),
    ("FitBH", PDPageFitWidthDestination, "PDPageFitWidthDestination"),
    ("FitV", PDPageFitHeightDestination, "PDPageFitHeightDestination"),
    ("FitBV", PDPageFitHeightDestination, "PDPageFitHeightDestination"),
    ("FitR", PDPageFitRectangleDestination, "PDPageFitRectangleDestination"),
]


@pytest.mark.parametrize(
    ("type_name", "expected_cls", "upstream_class_name"),
    _DISPATCH_CASES,
    ids=[c[0] for c in _DISPATCH_CASES],
)
def test_create_dispatches_to_expected_subclass(
    type_name: str, expected_cls: type, upstream_class_name: str
) -> None:
    """``PDDestination.create`` builds the expected concrete subclass for every
    /D[1] type-name string, and the pypdfbox-to-upstream class-name mapping is
    consistent with the divergence documented in CHANGES.md."""
    arr = _arr([_i(0), _name(type_name)])
    dest = PDDestination.create(arr)
    assert isinstance(dest, expected_cls)
    assert dest.get_cos_object().get_name(1) == type_name
    assert _PYPDFBOX_TO_UPSTREAM_CLASS[expected_cls] == upstream_class_name
