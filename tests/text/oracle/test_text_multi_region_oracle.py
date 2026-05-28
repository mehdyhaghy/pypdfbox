"""Live Apache PDFBox differential parity tests for PDFTextStripperByArea
with MULTIPLE named regions on a single page.

The single-region / boundary-clipping behaviour is already pinned by
``test_text_sort_area_oracle.py``. This module covers the *multi-region*
surface that file does not exercise:

  - **disjoint regions**: several non-overlapping rectangles, each
    capturing only the glyphs whose origin falls inside it. The remaining
    glyphs (outside every rectangle) are dropped from all regions.

  - **overlapping regions** (documented divergence): two rectangles
    sharing a zone, with a glyph whose origin lands in the overlap.
    Upstream's ``processTextPosition`` repoints a *single* page-wide
    ``charactersByArticle`` list per matching region and delegates to the
    base ``PDFTextStripper.processTextPosition``, whose
    ``suppressDuplicateOverlappingText`` dedup (on by default) is backed by
    one page-wide ``characterListMapping``. The first region iterated (in
    ``regionArea``'s ``HashMap`` order) records the glyph in that shared
    map; when the *same* glyph is offered to the second overlapping region
    the dedup recognises the coincident (text, x, y) and drops it. Net
    effect: a glyph in an overlap lands in **exactly one** region, not all
    of them. pypdfbox's lite stripper bins each region independently
    (per-region dedup, no shared map), so the glyph lands in **every**
    overlapping region. This is a recorded divergence (CHANGES.md):
    faithfully matching upstream would require replicating Java's
    non-spec ``HashMap`` iteration order to decide the surviving region.
    The test pins both sides so the divergence is observable and any
    future convergence is caught.

  - **region ordering**: ``getRegions`` / ``get_regions`` returns the
    region names in insertion order, and the per-region text is keyed by
    that name regardless of geometric position on the page.

Each test builds a deterministic PDF *with pypdfbox* (Standard-14
Helvetica, so PDFBox and pypdfbox resolve identical glyph metrics), then
runs the ``TextMultiRegionProbe`` Java program (compiled against the
pinned pdfbox-app-3.0.7 jar) on the same file and compares its per-region
output against pypdfbox's :class:`PDFTextStripperByArea`. Java PDFBox is
the reference.

The Java probe takes AWT ``Rectangle2D`` rects (top-left origin, y-down);
pypdfbox takes PDF user-space rects (bottom-left origin, y-up). The test
translates the *same* geometric rectangle between the two conventions
(``user_y = page_h - (awt_y + h)``).

Decorated ``@requires_oracle`` so they skip cleanly without Java + the
jar. Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

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


def _run_parity(
    pdf: Path, regions: list[tuple[str, _AwtRect]]
) -> tuple[dict[str, str], dict[str, str]]:
    """Run the Java probe and pypdfbox over the same regions; return
    (java_by_name, py_by_name)."""
    probe_args: list[str] = [str(pdf)]
    for name, (ax, ay, w, h) in regions:
        probe_args += [name, str(ax), str(ay), str(w), str(h)]
    java = _parse_probe(run_probe_text("TextMultiRegionProbe", *probe_args))

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
    return java, py


# Four runs in distinct quadrants of the page (user-space y-up).
_QUADRANT_RUNS: list[_Run] = [
    (100.0, 700.0, "TOPLEFT"),
    (400.0, 700.0, "TOPRIGHT"),
    (100.0, 100.0, "BOTLEFT"),
    (400.0, 100.0, "BOTRIGHT"),
]


@requires_oracle
def test_disjoint_regions_match_pdfbox(tmp_path: Path) -> None:
    """Two disjoint regions each capture only their own quadrant's glyph;
    the other two glyphs are dropped from both regions."""
    pdf = tmp_path / "disjoint.pdf"
    _build_doc(_QUADRANT_RUNS, pdf)

    # TOPLEFT user-y = 700 -> AWT y = 792-700 = 92. TOPRIGHT same band.
    regions = [
        ("left", (80.0, 80.0, 120.0, 40.0)),    # around TOPLEFT (awt 100,92)
        ("right", (380.0, 80.0, 120.0, 40.0)),  # around TOPRIGHT (awt 400,92)
    ]
    java, py = _run_parity(pdf, regions)
    assert py == java
    assert "TOPLEFT" in py["left"] and "TOPRIGHT" not in py["left"]
    assert "TOPRIGHT" in py["right"] and "TOPLEFT" not in py["right"]


@requires_oracle
def test_overlapping_regions_divergence_pinned(tmp_path: Path) -> None:
    """Overlap-suppression divergence is explicitly pinned.

    A glyph whose origin lands in the overlap of two regions is routed to
    *every* overlapping region by pypdfbox's lite stripper (independent
    per-region binning), but to *exactly one* region by Apache PDFBox
    (shared page-wide ``suppressDuplicateOverlappingText`` dedup). The test
    asserts pypdfbox's documented behaviour and asserts Java diverges in
    the documented way, so a future change on either side is caught. See
    the module docstring + CHANGES.md."""
    pdf = tmp_path / "overlap.pdf"
    # Single run sitting where two regions will overlap.
    _build_doc([(200.0, 400.0, "SHARED")], pdf)

    # SHARED user (200, 400) -> AWT (200, 392). Two rects that both contain
    # AWT point (200, 392) in their overlap.
    regions = [
        ("a", (150.0, 360.0, 100.0, 60.0)),  # x[150,250] y[360,420]
        ("b", (180.0, 380.0, 120.0, 50.0)),  # x[180,300] y[380,430]
    ]
    java, py = _run_parity(pdf, regions)

    # pypdfbox: the overlap glyph lands in BOTH regions (no shared dedup).
    assert "SHARED" in py["a"]
    assert "SHARED" in py["b"]

    # Apache PDFBox: the shared dedup map suppresses the duplicate, so the
    # glyph lands in EXACTLY ONE region (which one depends on Java's HashMap
    # order — we assert the count, not the identity, to stay JVM-stable).
    java_hits = [name for name, text in java.items() if "SHARED" in text]
    assert len(java_hits) == 1, f"expected exactly one Java region hit, got {java_hits}"

    # The two engines therefore disagree on the overlap glyph — this is the
    # recorded divergence.
    py_hits = [name for name, text in py.items() if "SHARED" in text]
    assert py_hits != java_hits


@requires_oracle
def test_four_regions_partition_match_pdfbox(tmp_path: Path) -> None:
    """Four regions, one per quadrant, partition the four glyphs exactly;
    insertion order of region names is preserved end-to-end."""
    pdf = tmp_path / "quad.pdf"
    _build_doc(_QUADRANT_RUNS, pdf)

    regions = [
        ("tl", (80.0, 80.0, 120.0, 40.0)),    # TOPLEFT  (awt 100,92)
        ("tr", (380.0, 80.0, 120.0, 40.0)),   # TOPRIGHT (awt 400,92)
        ("bl", (80.0, 680.0, 120.0, 40.0)),   # BOTLEFT  (awt 100,692)
        ("br", (380.0, 680.0, 120.0, 40.0)),  # BOTRIGHT (awt 400,692)
    ]
    java, py = _run_parity(pdf, regions)
    assert py == java
    assert list(py.keys()) == ["tl", "tr", "bl", "br"]
    assert "TOPLEFT" in py["tl"]
    assert "TOPRIGHT" in py["tr"]
    assert "BOTLEFT" in py["bl"]
    assert "BOTRIGHT" in py["br"]


@requires_oracle
def test_region_capturing_nothing_returns_separator(tmp_path: Path) -> None:
    """A registered region that matches no glyph still returns the single
    trailing line separator PDFBox emits per extracted region (not '')."""
    pdf = tmp_path / "empty_region.pdf"
    _build_doc([(100.0, 700.0, "ONLY")], pdf)

    regions = [
        ("hit", (80.0, 80.0, 120.0, 40.0)),     # captures ONLY
        ("miss", (400.0, 400.0, 50.0, 50.0)),   # captures nothing
    ]
    java, py = _run_parity(pdf, regions)
    assert py == java
    assert "ONLY" in py["hit"]
    # Empty region: PDFBox's per-region writePage still terminates with one
    # line separator, so the payload is exactly "\n", never "".
    assert py["miss"] == "\n"
