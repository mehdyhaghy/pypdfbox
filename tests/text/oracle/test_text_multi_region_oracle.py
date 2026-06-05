"""Live Apache PDFBox differential parity tests for PDFTextStripperByArea
with MULTIPLE named regions on a single page.

The single-region / boundary-clipping behaviour is already pinned by
``test_text_sort_area_oracle.py``. This module covers the *multi-region*
surface that file does not exercise:

  - **disjoint regions**: several non-overlapping rectangles, each
    capturing only the glyphs whose origin falls inside it. The remaining
    glyphs (outside every rectangle) are dropped from all regions.

  - **overlapping regions** (converged, wave 1492): two or more rectangles
    sharing a zone, with a glyph whose origin lands in the overlap.
    Upstream's ``processTextPosition`` repoints a *single* page-wide
    ``charactersByArticle`` list per matching region (walking ``regionArea``
    in ``HashMap`` order) and delegates to the base
    ``PDFTextStripper.processTextPosition``, whose
    ``suppressDuplicateOverlappingText`` dedup (on by default) is backed by
    one page-wide ``characterListMapping``. The first region iterated records
    the glyph in that shared map; when the *same* glyph is offered to the
    second overlapping region the dedup recognises the coincident (text, x, y)
    and drops it. Net effect: an overlap glyph lands in **exactly one**
    region. pypdfbox now reproduces this faithfully: it iterates matching
    regions in Java-HashMap order (``_hashmap_order``) and applies the same
    shared page-wide dedup, so the surviving region is byte-identical to
    Java's. Empirically the surviving region is fixed by the region name's
    ``String.hashCode`` bucket index (deterministic across JVMs), independent
    of insertion order — verified live for ``{a,b}`` (→a), ``{r1,r2}`` (→r2,
    *not* insertion order), ``{left,right}`` (→left), and 3-way overlaps.
    With ``setSuppressDuplicateOverlappingText(false)`` the shared dedup is
    off and the glyph lands in **every** matching region on both sides.

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
    pdf: Path,
    regions: list[tuple[str, _AwtRect]],
    *,
    suppress: bool = True,
) -> tuple[dict[str, str], dict[str, str]]:
    """Run the Java probe and pypdfbox over the same regions; return
    (java_by_name, py_by_name).

    When ``suppress`` is False both engines disable
    ``setSuppressDuplicateOverlappingText`` so an overlap glyph lands in
    every matching region (no shared dedup)."""
    probe_args: list[str] = [str(pdf)]
    if not suppress:
        probe_args.append("--no-suppress")
    for name, (ax, ay, w, h) in regions:
        probe_args += [name, str(ax), str(ay), str(w), str(h)]
    java = _parse_probe(run_probe_text("TextMultiRegionProbe", *probe_args))

    doc = PDDocument.load(str(pdf))
    try:
        s = PDFTextStripperByArea()
        s.set_sort_by_position(True)
        if not suppress:
            s.set_suppress_duplicate_overlapping_text(False)
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
def test_overlapping_regions_converge_with_pdfbox(tmp_path: Path) -> None:
    """Overlap glyph lands in EXACTLY the same single region as PDFBox.

    A glyph whose origin lands in the overlap of two regions is routed to a
    single region by Apache PDFBox (shared page-wide
    ``suppressDuplicateOverlappingText`` dedup, default on) — the FIRST region
    in ``regionArea``'s ``HashMap`` iteration order. pypdfbox now reproduces
    both the shared dedup and the HashMap order, so per-region output is
    byte-identical to Java. See the module docstring + CHANGES.md (wave 1492
    convergence)."""
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

    # Full per-region parity.
    assert py == java

    # The overlap glyph survives in exactly one region on BOTH sides, and it
    # is the SAME region. ``a`` wins (HashMap bucket index 1 < ``b``'s 2).
    java_hits = [name for name, text in java.items() if "SHARED" in text]
    py_hits = [name for name, text in py.items() if "SHARED" in text]
    assert java_hits == py_hits == ["a"]


@requires_oracle
def test_overlapping_survivor_not_insertion_order(tmp_path: Path) -> None:
    """The surviving overlap region follows Java's HashMap bucket order, not
    insertion order — pinned with a region set where the two disagree.

    For ``{"r1", "r2"}`` the HashMap iterates ``r2`` before ``r1`` (bucket
    index 0 < 15), so ``r2`` wins even though ``r1`` was inserted first. The
    swapped-insertion run confirms the winner is insertion-order-independent.
    """
    pdf = tmp_path / "overlap_hash.pdf"
    _build_doc([(200.0, 400.0, "SHARED")], pdf)
    rect_a = (150.0, 360.0, 100.0, 60.0)
    rect_b = (180.0, 380.0, 120.0, 50.0)

    for order in ([("r1", rect_a), ("r2", rect_b)], [("r2", rect_b), ("r1", rect_a)]):
        java, py = _run_parity(pdf, order)
        assert py == java
        java_hits = [name for name, text in java.items() if "SHARED" in text]
        assert java_hits == ["r2"], f"insertion {[n for n, _ in order]}: {java_hits}"


@requires_oracle
def test_three_way_overlap_converges(tmp_path: Path) -> None:
    """A glyph inside three overlapping regions lands in exactly one region
    (the HashMap-first one) on both engines."""
    pdf = tmp_path / "tri_overlap.pdf"
    _build_doc([(200.0, 400.0, "X")], pdf)
    regions = [
        ("p", (150.0, 360.0, 120.0, 60.0)),
        ("q", (160.0, 370.0, 130.0, 55.0)),
        ("s", (170.0, 380.0, 140.0, 50.0)),
    ]
    java, py = _run_parity(pdf, regions)
    assert py == java
    java_hits = [name for name, text in java.items() if "X" in text]
    assert len(java_hits) == 1


@requires_oracle
def test_overlap_suppress_off_glyph_in_every_region(tmp_path: Path) -> None:
    """With suppression OFF the overlap glyph lands in EVERY matching region
    on both engines (the shared dedup is disabled)."""
    pdf = tmp_path / "tri_no_suppress.pdf"
    _build_doc([(200.0, 400.0, "X")], pdf)
    regions = [
        ("p", (150.0, 360.0, 120.0, 60.0)),
        ("q", (160.0, 370.0, 130.0, 55.0)),
        ("s", (170.0, 380.0, 140.0, 50.0)),
    ]
    java, py = _run_parity(pdf, regions, suppress=False)
    assert py == java
    java_hits = sorted(name for name, text in java.items() if "X" in text)
    assert java_hits == ["p", "q", "s"]


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
