"""Live PDFBox differential parity for the viewer-pref boundary getters
(``/ViewArea`` / ``/ViewClip`` / ``/PrintArea`` / ``/PrintClip``), the
unwrapped PDF 32000-2 enrichment entries (``/PickTrayByPDFSize`` /
``/NumCopies`` / ``/PrintPageRange`` / ``/Enforce``), and the catalog
``/OpenAction`` dispatch (destination array vs action dictionary, with the
exact subtype tag).

These extend the surface covered by :mod:`test_viewer_prefs_oracle` — that
sister file already pins the six boolean flags and the four enum-string
getters (``NonFullScreenPageMode`` / ``Direction`` / ``PrintScaling`` /
``Duplex``) plus the catalog page-layout / page-mode / lang / version.
Splitting the two probes lets each test set stay scoped to one orthogonal
concern.

Boundary getters (``getViewArea`` etc.) bake the PDF 32000-1 §12.2 Table 150
default ``CropBox`` straight into upstream PDViewerPreferences — pypdfbox
mirrors that exactly. ``/PickTrayByPDFSize``, ``/NumCopies``,
``/PrintPageRange``, and ``/Enforce`` have no upstream getter in PDFBox
3.0.7, so both sides read them off the raw ``/ViewerPreferences`` COS
dictionary (pypdfbox via its own accessor helpers).

``/OpenAction`` is the document-catalog open-action dispatch (PDF 32000-1
§12.6.4.1). Upstream's ``PDDocumentCatalog.getOpenAction()`` returns a
:class:`PDAction` (action dictionary) or a :class:`PDDestination`
(destination array) — pypdfbox's :meth:`PDDocumentCatalog.get_open_action`
matches that dispatch byte-for-byte after wave 1454.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences
from tests.oracle.harness import requires_oracle, run_probe_text

_NUM_COPIES = COSName.get_pdf_name("NumCopies")
_PRINT_PAGE_RANGE = COSName.get_pdf_name("PrintPageRange")
_PICK_TRAY = COSName.get_pdf_name("PickTrayByPDFSize")
_ENFORCE = COSName.get_pdf_name("Enforce")


def _b(value: bool) -> str:
    return "true" if value else "false"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _py_dump(fixture: Path) -> str:
    """Reproduce the canonical line-oriented dump emitted by
    ``ViewerPrefsAndOpenActionProbe.java`` from pypdfbox accessors."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        cat = doc.get_document_catalog()
        vp = cat.get_viewer_preferences()
        if vp is not None:
            lines.append(f"viewArea={vp.get_view_area()}")
            lines.append(f"viewClip={vp.get_view_clip()}")
            lines.append(f"printArea={vp.get_print_area()}")
            lines.append(f"printClip={vp.get_print_clip()}")
            lines.append(f"pickTrayByPDFSize={_b(vp.pick_tray_by_pdf_size())}")
            num_copies_raw = vp.get_num_copies_raw()
            if num_copies_raw is None:
                lines.append("numCopies=NULL")
            else:
                lines.append(f"numCopies={num_copies_raw}")
            ppr = vp.get_print_page_range()
            if ppr is None:
                lines.append("printPageRange=NULL")
            else:
                lines.append(
                    "printPageRange="
                    + ",".join(
                        str(ppr.get_object(i).int_value())
                        if hasattr(ppr.get_object(i), "int_value")
                        else "?"
                        for i in range(ppr.size())
                    )
                )
            enf = vp.get_enforce()
            if enf is None:
                lines.append("enforce=NULL")
            else:
                lines.append("enforce=" + ",".join(vp.get_enforce_names()))
        else:
            lines.append("viewArea=NULL")
            lines.append("viewClip=NULL")
            lines.append("printArea=NULL")
            lines.append("printClip=NULL")
            lines.append("pickTrayByPDFSize=false")
            lines.append("numCopies=NULL")
            lines.append("printPageRange=NULL")
            lines.append("enforce=NULL")

        oa = cat.get_open_action()
        if oa is None:
            lines.append("openAction.kind=NULL")
            lines.append("openAction.subType=NULL")
        elif isinstance(oa, PDAction):
            lines.append("openAction.kind=ACTION")
            lines.append(f"openAction.subType={_nz(oa.get_sub_type())}")
        elif isinstance(oa, PDPageDestination):
            arr = oa.get_cos_object()
            lines.append("openAction.kind=DESTINATION")
            if arr.size() >= 2:
                tag = arr.get_object(1)
                if isinstance(tag, COSName):
                    lines.append(f"openAction.subType={tag.get_name()}")
                else:
                    lines.append("openAction.subType=NULL")
            else:
                lines.append("openAction.subType=NULL")
        elif isinstance(oa, PDDestination):
            lines.append("openAction.kind=DESTINATION")
            lines.append("openAction.subType=NULL")
        else:
            lines.append("openAction.kind=NULL")
            lines.append("openAction.subType=NULL")
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# boundary getters — all four entries set / all defaulted / mixed
# ---------------------------------------------------------------------------


@requires_oracle
def test_boundary_getters_all_default_match_pdfbox(tmp_path: Path) -> None:
    """Empty /ViewerPreferences dict: all four boundary getters bake the
    PDF 32000-1 §12.2 Table 150 default ``CropBox`` straight into the
    return value, on both sides."""
    pdf = tmp_path / "boundary_default.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.get_document_catalog().set_viewer_preferences(PDViewerPreferences())
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert py == java, (
        f"boundary defaults diverge.\n--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_boundary_getters_no_viewer_prefs_matches_pdfbox(tmp_path: Path) -> None:
    """No /ViewerPreferences entry at all: the boundary getters can't run
    (PDFBox returns null for the wrapper), so we emit NULL sentinels — both
    sides must agree."""
    pdf = tmp_path / "boundary_absent.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert py == java, (
        f"boundary absent diverges.\n--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
@pytest.mark.parametrize(
    "boundary",
    ["MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox"],
)
def test_view_area_round_trips_through_pdfbox(
    tmp_path: Path, boundary: str
) -> None:
    """Every /ViewArea token round-trips through PDFBox unchanged."""
    pdf = tmp_path / f"view_area_{boundary}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_view_area(boundary)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    assert f"viewArea={boundary}\n" in java
    py = _py_dump(pdf)
    assert py == java, f"viewArea {boundary} diverges from PDFBox"


@requires_oracle
@pytest.mark.parametrize(
    "boundary",
    ["MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox"],
)
def test_print_clip_round_trips_through_pdfbox(
    tmp_path: Path, boundary: str
) -> None:
    """Every /PrintClip token round-trips through PDFBox unchanged. Covers
    the second of the two print-side boundary getters and the last of the
    four boundary entries; combined with the /ViewArea parametrize this
    pins the boundary surface enum-by-enum on both extremes."""
    pdf = tmp_path / f"print_clip_{boundary}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_print_clip(boundary)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    assert f"printClip={boundary}\n" in java
    py = _py_dump(pdf)
    assert py == java, f"printClip {boundary} diverges from PDFBox"


@requires_oracle
def test_all_four_boundaries_mixed_round_trip(tmp_path: Path) -> None:
    """All four boundary entries set to different /Name tokens read back
    identically on both sides."""
    pdf = tmp_path / "boundary_mixed.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_view_area("MediaBox")
        vp.set_view_clip("BleedBox")
        vp.set_print_area("TrimBox")
        vp.set_print_clip("ArtBox")
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "viewArea=MediaBox\n" in java
    assert "viewClip=BleedBox\n" in java
    assert "printArea=TrimBox\n" in java
    assert "printClip=ArtBox\n" in java
    assert py == java, "mixed-boundary round-trip diverges from PDFBox"


# ---------------------------------------------------------------------------
# /PickTrayByPDFSize — 32000-2 enrichment, no upstream getter; raw dict read
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("value", [True, False])
def test_pick_tray_round_trips_through_pdfbox(tmp_path: Path, value: bool) -> None:
    """/PickTrayByPDFSize round-trips through the raw /ViewerPreferences
    dictionary — both sides read the boolean off the dict (PDFBox 3.0.7
    has no typed getter)."""
    pdf = tmp_path / f"pick_tray_{value}.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_pick_tray_by_pdf_size(value)
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    assert f"pickTrayByPDFSize={_b(value)}\n" in java
    py = _py_dump(pdf)
    assert py == java, f"pickTrayByPDFSize {value} diverges from PDFBox"


# ---------------------------------------------------------------------------
# /Enforce — PDF 32000-2 §12.4.4 enrichment; raw name array
# ---------------------------------------------------------------------------


@requires_oracle
def test_enforce_round_trips_through_pdfbox(tmp_path: Path) -> None:
    """/Enforce as a name-array round-trips through PDFBox by raw COS
    inspection — pypdfbox writes a COSArray of COSName entries; PDFBox
    reads them straight back as names."""
    pdf = tmp_path / "enforce.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        vp = PDViewerPreferences()
        vp.set_enforce_names(["PrintScaling", "Duplex"])
        doc.get_document_catalog().set_viewer_preferences(vp)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    assert "enforce=PrintScaling,Duplex\n" in java
    py = _py_dump(pdf)
    assert py == java, "enforce round-trip diverges from PDFBox"


# ---------------------------------------------------------------------------
# /OpenAction dispatch — destination array vs action dictionary
# ---------------------------------------------------------------------------


@requires_oracle
def test_open_action_absent_matches_pdfbox(tmp_path: Path) -> None:
    """No /OpenAction entry: catalog dispatch yields None on both sides."""
    pdf = tmp_path / "open_action_absent.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=NULL\n" in java
    assert py == java, "open_action absent diverges from PDFBox"


@requires_oracle
def test_open_action_xyz_destination_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as an XYZ destination array (the canonical PDF
    32000-1 §12.3.2.2 page destination form) dispatches to
    :class:`PDPageXYZDestination` with the subtype tag ``"XYZ"``."""
    pdf = tmp_path / "open_action_xyz.pdf"
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        dest = PDPageXYZDestination()
        dest.set_page(page)
        dest.set_left(100)
        dest.set_top(200)
        dest.set_zoom(1.5)
        doc.get_document_catalog().set_open_action(dest)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=DESTINATION\n" in java
    assert "openAction.subType=XYZ\n" in java
    assert py == java, "open_action XYZ destination diverges from PDFBox"


@requires_oracle
def test_open_action_fit_destination_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a Fit destination array dispatches to
    :class:`PDPageFitDestination` with the subtype tag ``"Fit"``."""
    pdf = tmp_path / "open_action_fit.pdf"
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        dest = PDPageFitDestination()
        dest.set_page(page)
        doc.get_document_catalog().set_open_action(dest)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=DESTINATION\n" in java
    assert "openAction.subType=Fit\n" in java
    assert py == java, "open_action Fit destination diverges from PDFBox"


@requires_oracle
def test_open_action_goto_action_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a /GoTo action dictionary dispatches to
    :class:`PDActionGoTo` with the subtype tag ``"GoTo"``."""
    pdf = tmp_path / "open_action_goto.pdf"
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        action = PDActionGoTo()
        dest = PDPageFitDestination()
        dest.set_page(page)
        action.set_destination(dest)
        doc.get_document_catalog().set_open_action(action)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=ACTION\n" in java
    assert "openAction.subType=GoTo\n" in java
    assert py == java, "open_action GoTo action diverges from PDFBox"


@requires_oracle
def test_open_action_uri_action_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a /URI action dictionary dispatches to
    :class:`PDActionURI` with the subtype tag ``"URI"``."""
    pdf = tmp_path / "open_action_uri.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        action = PDActionURI()
        action.set_uri("https://example.com/")
        doc.get_document_catalog().set_open_action(action)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=ACTION\n" in java
    assert "openAction.subType=URI\n" in java
    assert py == java, "open_action URI action diverges from PDFBox"


@requires_oracle
def test_open_action_dict_without_subtype_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a COSDictionary with /D but no /S: PDFBox's
    ``PDActionFactory.createAction`` returns null for that case, so the
    catalog dispatch is null on both sides. This pins the pypdfbox
    divergence-fix from wave 1454 — the looser
    :meth:`PDDestinationOrAction.create` would have returned a
    :class:`PDActionGoTo` shorthand, but the catalog dispatch matches
    upstream strictly."""
    pdf = tmp_path / "open_action_no_subtype.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        raw = COSDictionary()
        # /D points at the catalog itself just to make the dict non-empty;
        # PDFBox doesn't care about the value because there's no /S.
        raw.set_item(
            COSName.get_pdf_name("D"), COSArray.of_cos_names(["irrelevant"])
        )
        doc.get_document_catalog().set_open_action(raw)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=NULL\n" in java
    assert py == java, (
        "open_action /D-only dict (no /S) diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
def test_open_action_name_shorthand_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a raw COSName (named-destination shorthand):
    PDFBox 3.0.7's catalog dispatch returns null because the
    ``getOpenAction()`` switch only handles COSDictionary / COSArray.
    pypdfbox's :meth:`PDDocumentCatalog.get_open_action` mirrors that
    strictly after wave 1454. (The looser
    :class:`PDDestinationOrAction` factory still resolves the shorthand
    for callers that want the legacy behavior.)"""
    pdf = tmp_path / "open_action_name.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("OpenAction"), COSName.get_pdf_name("Page1")
        )
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=NULL\n" in java
    assert py == java, "open_action COSName shorthand diverges from PDFBox"


@requires_oracle
def test_open_action_string_shorthand_matches_pdfbox(tmp_path: Path) -> None:
    """/OpenAction set as a raw COSString (legacy named-destination
    shorthand): same null result as the COSName shorthand — upstream
    catalog dispatch doesn't recognize it; pypdfbox matches."""
    pdf = tmp_path / "open_action_string.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("OpenAction"), COSString("legacy")
        )
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert "openAction.kind=NULL\n" in java
    assert py == java, "open_action COSString shorthand diverges from PDFBox"


@requires_oracle
def test_combined_boundary_and_open_action_round_trip(tmp_path: Path) -> None:
    """All four boundary entries, the boolean PickTrayByPDFSize, NumCopies,
    PrintPageRange, /Enforce, and a GoTo action /OpenAction set together —
    pypdfbox's dump matches PDFBox byte-for-byte. The "everything wired"
    case that catches any cross-field state interference between viewer-
    preferences entries and the catalog open-action dispatch."""
    pdf = tmp_path / "everything.pdf"
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        vp = PDViewerPreferences()
        vp.set_view_area("MediaBox")
        vp.set_view_clip("BleedBox")
        vp.set_print_area("TrimBox")
        vp.set_print_clip("ArtBox")
        vp.set_pick_tray_by_pdf_size(True)
        vp.set_num_copies(2)
        vp.set_print_page_range_pairs([(1, 1)])
        vp.set_enforce_names(["PrintScaling"])
        doc.get_document_catalog().set_viewer_preferences(vp)
        action = PDActionGoTo()
        dest = PDPageFitDestination()
        dest.set_page(page)
        action.set_destination(dest)
        doc.get_document_catalog().set_open_action(action)
        doc.save(pdf)
    finally:
        doc.close()
    java = run_probe_text("ViewerPrefsAndOpenActionProbe", str(pdf))
    py = _py_dump(pdf)
    assert py == java, (
        "combined viewer-prefs + open_action round-trip diverges.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def test_open_action_dispatch_strict_returns_none_for_dict_without_subtype() -> (
    None
):
    """Pure-Python sanity: a catalog with /OpenAction = COSDictionary
    without /S yields None from :meth:`get_open_action` (matching PDFBox
    3.0.7's PDActionFactory). No oracle needed."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        raw = COSDictionary()
        raw.set_item(
            COSName.get_pdf_name("D"), COSArray.of_cos_names(["irrelevant"])
        )
        doc.get_document_catalog().set_open_action(raw)
        assert doc.get_document_catalog().get_open_action() is None
    finally:
        doc.close()


def test_open_action_dispatch_strict_returns_none_for_name_shorthand() -> None:
    """Pure-Python sanity: a catalog with /OpenAction = COSName yields
    None from :meth:`get_open_action`, matching PDFBox 3.0.7's catalog
    dispatch. The looser :class:`PDDestinationOrAction` factory still
    handles the shorthand — only the catalog accessor is strict."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle.A4))
        cat = doc.get_document_catalog()
        cat.get_cos_object().set_item(
            COSName.get_pdf_name("OpenAction"), COSName.get_pdf_name("Page1")
        )
        assert cat.get_open_action() is None
    finally:
        doc.close()
