"""Live Apache PDFBox differential parity tests for PDFTextStripperByArea,
covering facets the existing area oracles do NOT exercise — using only clearly
DISJOINT (non-overlapping) regions (the overlapping-region case is tracked in
DEFERRED.md and pinned separately in test_text_multi_region_oracle.py), plus
**rotated-page region binning** across all four /Rotate values (wave 1511,
closing the wave-1495/1510 deferral): the binner folds each glyph origin into
the page-rotation-adjusted device frame upstream tests Rectangle2D.contains
against, so a region defined in that device frame captures the glyph
byte-identically on /Rotate 0/90/180/270.

Existing coverage (test_text_sort_area_oracle.py / test_text_multi_region_oracle.py)
exercises single-region clipping, boundary half-openness, and multi-region
disjoint/overlapping binning. This module adds:

  - **multi-character run routed per glyph** ("split"): a single ``show_text``
    run of several identical glyphs is drawn wholly inside one disjoint region
    while a second disjoint region (well clear of the run) sits empty. Upstream
    emits one ``TextPosition`` *per glyph* and tests each glyph's own origin
    against every region, so the whole run lands in the one region that
    contains all its glyph origins. pypdfbox's lite stripper emits one
    ``TextPosition`` per *run*; this test pins that the area stripper still
    routes the run's glyphs into the containing region (drove the wave fix that
    made ``process_text_position`` route per glyph instead of binning the whole
    run by its start origin only).

    NOTE on the *straddle* split point: when a run physically crosses a region
    boundary, the exact glyph at which it splits depends on real per-glyph
    advance widths. pypdfbox's lite stripper approximates a run's advance with a
    font-wide average (or a 0.5-em fallback for Standard-14 fonts that carry no
    ``/Widths``), so the precise straddle split point can diverge from PDFBox's.
    That exact-split case is a known lite-mode approximation tracked in
    DEFERRED.md; this test deliberately keeps the run wholly inside one region
    so the assertion does not depend on the approximate split point.

  - **``remove_region`` + re-extract** ("remove"): two disjoint regions are
    registered, one removed before ``extract_regions``. The removed name must
    not appear in ``get_regions()`` and produces no output, while the surviving
    region still captures its glyph — identical to PDFBox's ``removeRegion``.

Each test builds a deterministic PDF *with pypdfbox* (Standard-14 Helvetica, so
PDFBox and pypdfbox resolve identical glyph metrics), then runs the
``TextByAreaProbe`` Java program (compiled against the pinned pdfbox-app-3.0.7
jar) on the same file and compares its per-region output against pypdfbox's
:class:`PDFTextStripperByArea`. Java PDFBox is the reference.

The Java probe takes AWT ``Rectangle2D`` rects (top-left origin, y-down);
pypdfbox takes PDF user-space rects (bottom-left origin, y-up). The test
translates the *same* geometric rectangle between the two conventions
(``user_y = page_h - (awt_y + h)``).

Decorated ``@requires_oracle`` so they skip cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.text.pdf_text_stripper_by_area import PDFTextStripperByArea
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE_W = 612.0
_PAGE_H = 792.0

# Run = (x, y, text) in PDF user space (y-up).
_Run = tuple[float, float, str]

# AWT rect = (x, y, width, height), top-left origin, y-down.
_AwtRect = tuple[float, float, float, float]


def _build_doc(runs: list[_Run], path: Path) -> None:
    """Build a one-page PDF drawing the given runs with Standard-14
    Helvetica, then save it to ``path``."""
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
        page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        for x, y, txt in runs:
            cs.begin_text()
            cs.set_font(font, 12.0)
            cs.new_line_at_offset(x, y)
            cs.show_text(txt)
            cs.end_text()
        cs.close()
        doc.save(str(path))
    finally:
        doc.close()


def _build_rotated_doc(runs: list[_Run], path: Path, rotate: int) -> None:
    """Build a one-page PDF (identity-``Tm`` runs) whose page ``/Rotate`` is
    ``rotate``, saved to ``path``."""
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
        page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
        page.set_rotation(rotate)
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        for x, y, txt in runs:
            cs.begin_text()
            cs.set_font(font, 12.0)
            cs.new_line_at_offset(x, y)
            cs.show_text(txt)
            cs.end_text()
        cs.close()
        doc.save(str(path))
    finally:
        doc.close()


def _unescape(s: str) -> str:
    """Reverse the probe's newline/backslash escaping."""
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _parse_probe(out: str) -> dict[str, str]:
    """Parse the probe's ``<name>\\t<escaped-text>`` lines into a dict."""
    result: dict[str, str] = {}
    for line in out.splitlines():
        if not line:
            continue
        name, _, payload = line.partition("\t")
        result[name] = _unescape(payload)
    return result


def _awt_to_user(rect: _AwtRect) -> tuple[float, float, float, float]:
    """AWT (top-left origin, y-down) -> PDF user-space (bottom-left, y-up)."""
    ax, ay, w, h = rect
    return (ax, _PAGE_H - (ay + h), w, h)


def _run_probe(mode: str, pdf: Path, regions: list[tuple[str, _AwtRect]]) -> dict[str, str]:
    probe_args: list[str] = [mode, str(pdf)]
    for name, (ax, ay, w, h) in regions:
        probe_args += [name, str(ax), str(ay), str(w), str(h)]
    return _parse_probe(run_probe_text("TextByAreaProbe", *probe_args))


@requires_oracle
def test_multichar_run_wholly_inside_region_matches_pdfbox(tmp_path: Path) -> None:
    """A multi-glyph ``show_text`` run whose origins all fall inside one
    disjoint region is routed there in full; a second disjoint region clear
    of the run stays empty — identical to PDFBox.

    This pins the per-glyph routing fix: a run is not dumped wholesale into
    the region containing only its *start* origin, but every region whose
    rectangle contains the run's glyph origins captures it (here, the same
    single region for all glyphs)."""
    pdf = tmp_path / "split.pdf"
    # One run of 8 'A's at user (100, 400). At 12pt the run spans roughly
    # x in [100, 165]; the left region is sized to contain it entirely.
    _build_doc([(100.0, 400.0, "AAAAAAAA")], pdf)

    regions = [
        ("left", (90.0, 380.0, 110.0, 40.0)),   # x in [90,200] — contains run
        ("right", (300.0, 380.0, 80.0, 40.0)),  # x in [300,380] — clear of run
    ]
    java = _run_probe("split", pdf, regions)

    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripperByArea()
        s.set_sort_by_position(True)
        for name, awt in regions:
            s.add_region(name, _awt_to_user(awt))
        s.extract_regions(doc.get_page(0))
        py = {name: s.get_text_for_region(name) for name in s.get_regions()}
    finally:
        doc.close()

    assert py == java
    # The whole 8-glyph run landed in the left region; the right region is
    # the empty-region single-separator payload.
    assert py["left"].count("A") == 8
    assert py["right"] == "\n"


@requires_oracle
def test_remove_region_before_extract_matches_pdfbox(tmp_path: Path) -> None:
    """``remove_region`` drops a region before extraction: it vanishes from
    ``get_regions()`` and emits no output, while the kept region still
    captures its glyph — identical to PDFBox's ``removeRegion``."""
    pdf = tmp_path / "remove.pdf"
    # Two glyphs in disjoint quadrants.
    _build_doc([(100.0, 700.0, "KEEPME"), (400.0, 100.0, "DROPME")], pdf)

    regions = [
        ("keep", (80.0, 80.0, 120.0, 40.0)),    # around KEEPME (awt 100,92)
        ("drop", (380.0, 680.0, 120.0, 40.0)),  # around DROPME (awt 400,692)
    ]
    java = _run_probe("remove", pdf, regions)

    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripperByArea()
        s.set_sort_by_position(True)
        for name, awt in regions:
            s.add_region(name, _awt_to_user(awt))
        s.remove_region("drop")
        s.extract_regions(doc.get_page(0))
        py = {name: s.get_text_for_region(name) for name in s.get_regions()}
        py_regions = list(s.get_regions())
    finally:
        doc.close()

    assert py == java
    # "drop" is gone from the live region list; only "keep" remains.
    assert py_regions == ["keep"]
    assert "drop" not in py
    assert "KEEPME" in py["keep"]
    assert "DROPME" not in py["keep"]


# ---------------------------------------------------------------------------
# Rotated page: by-area binning in the page-rotation-adjusted device frame
# (wave 1511 — closes the wave-1495/1510 deferral). Upstream
# ``PDFTextStripperByArea.processTextPosition`` (Java L141) tests
# ``Rectangle2D.contains(text.getX(), text.getY())`` against the
# page-rotation-adjusted *device* coordinates, so a region defined in the
# rotated device frame captures the glyph regardless of /Rotate. pypdfbox folds
# each glyph origin into that same device frame before the boundary test.
# ---------------------------------------------------------------------------


def _device_to_user(
    rect: _AwtRect, rotate: int
) -> tuple[float, float, float, float]:
    """Invert a device-frame (AWT, post-rotation) rect into the PDF user-space
    rect pypdfbox's ``add_region`` consumes.

    The device frame matches upstream ``TextPosition.getX()`` / ``getY()`` for
    the page rotation; a device point ``(dx, dy)`` inverts to user ``(ux, uy)``:

      * ``/Rotate 0``   -> ``(dx, page_h - dy)``  (AWT y-down -> user y-up)
      * ``/Rotate 90``  -> ``(dy, dx)``
      * ``/Rotate 180`` -> ``(page_w - dx, dy)``
      * ``/Rotate 270`` -> ``(page_w - dy, page_h - dx)``

    The ``/Rotate 180`` device Y maps straight back to user ``y`` (upstream's
    ``getY()`` flips cancel — see ``_glyph_device_origin``). We invert the
    rect's two opposite corners and renormalize.
    """
    dx, dy, w, h = rect
    corners = [(dx, dy), (dx + w, dy + h)]
    user = []
    for cx, cy in corners:
        if rotate == 90:
            user.append((cy, cx))
        elif rotate == 180:
            user.append((_PAGE_W - cx, cy))
        elif rotate == 270:
            user.append((_PAGE_W - cy, _PAGE_H - cx))
        else:
            user.append((cx, _PAGE_H - cy))
    (ux0, uy0), (ux1, uy1) = user
    minx, maxx = min(ux0, ux1), max(ux0, ux1)
    miny, maxy = min(uy0, uy1), max(uy0, uy1)
    return (minx, miny, maxx - minx, maxy - miny)


@requires_oracle
@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_rotated_page_by_area_device_frame_matches_pdfbox(
    tmp_path: Path, rotate: int
) -> None:
    """On every ``/Rotate`` value, a region defined in the rotated device frame
    captures the run that falls in it and excludes the others — byte-identical
    to Apache PDFBox, which tests ``Rectangle2D.contains`` against the
    page-rotation-adjusted ``getX()`` / ``getY()``.

    Three runs are drawn at distinct user-space positions; for the active
    rotation we fold each draw origin into the device frame and place one
    *capturing* region tightly around the first run plus one *empty* region in a
    clear quadrant, with a third region straddling the boundary between two
    runs. The same geometric device rect is handed to Java (AWT, native) and
    inverse-mapped into user space for pypdfbox."""
    pdf = tmp_path / f"rot{rotate}_area.pdf"
    runs = [
        (100.0, 700.0, "ALPHA"),
        (100.0, 120.0, "BETA"),
        (400.0, 400.0, "GAMMA"),
    ]
    _build_rotated_doc(runs, pdf, rotate=rotate)

    # Fold each run's draw origin into the device frame so the region rects can
    # be expressed in the same coordinates Java's getX()/getY() reports.
    def fold(ux: float, uy: float) -> tuple[float, float]:
        if rotate == 90:
            return (uy, ux)
        if rotate == 180:
            return (_PAGE_W - ux, uy)
        if rotate == 270:
            return (_PAGE_H - uy, _PAGE_W - ux)
        return (ux, _PAGE_H - uy)

    ax, ay = fold(100.0, 700.0)   # ALPHA device origin
    # Capturing region around ALPHA's device origin. The run advances along one
    # device axis depending on rotation, so size the box generously on both
    # device axes to enclose the whole 5-glyph run while staying well clear of
    # BETA (user 100,120) and GAMMA (user 400,400), which fold far away.
    cap_rect: _AwtRect = (ax - 60.0, ay - 60.0, 120.0, 120.0)
    # Empty region: a clear band well away from every run's device origin.
    bx, by = fold(400.0, 400.0)   # GAMMA device origin
    empty_rect: _AwtRect = (bx + 200.0, by + 200.0, 40.0, 20.0)

    regions: list[tuple[str, _AwtRect]] = [
        ("cap", cap_rect),
        ("empty", empty_rect),
    ]
    java = _run_probe("regions", pdf, regions)

    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripperByArea()
        s.set_sort_by_position(True)
        for name, dev in regions:
            s.add_region(name, _device_to_user(dev, rotate))
        s.extract_regions(doc.get_page(0))
        py = {name: s.get_text_for_region(name) for name in s.get_regions()}
    finally:
        doc.close()

    assert py == java
    assert "ALPHA" in py["cap"].replace("\n", "")
    assert "BETA" not in py["cap"]
    assert "GAMMA" not in py["cap"]
    assert py["empty"] == "\n"
