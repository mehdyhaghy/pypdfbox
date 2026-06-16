"""Live Apache PDFBox differential fuzz of ``PDFTextStripperByArea``'s
REGION-API surface (wave 1551).

The existing area oracles pin single-region clipping, boundary half-openness,
multi-region disjoint/overlap binning, and rotated-page binning. This module
fuzzes the *region-management* facets they do not exhaustively cover, driven by
the ``TextByAreaFuzzProbe`` Java program over a synthetic four-glyph page built
with pypdfbox (Standard-14 Helvetica, so PDFBox and pypdfbox resolve identical
glyph metrics):

  - **degenerate geometry**: zero-width / zero-height / zero-area (point)
    regions; regions fully off the page (positive and negative coordinates); a
    region exactly the page size; a region larger than the page; negative
    width/height rectangles; boundary-edge (half-open ``Rectangle2D.contains``)
    inclusion/exclusion.
  - **region lifecycle**: duplicate ``add_region`` of the same name (upstream
    *appends* the name a second time to ``getRegions`` while the last rect wins
    in the area map), ``remove_region`` of a registered / unregistered name,
    re-extraction clearing prior state.
  - **error/edge contracts**: ``get_text_for_region`` of an unregistered name
    and before any ``extract_regions`` call.
  - the ``set_sort_by_position`` toggle applied across the whole matrix.

The probe runs ~28 cases per sort mode (56 total). Every region rectangle is an
AWT ``Rectangle2D`` (top-left origin, y-down) hard-coded in the probe; the
Python side mirrors the *same* geometric rectangle through its user-space
inverse (``user_y = page_h - (awt_y + h)``) so both engines see identical
inputs. Apache PDFBox 3.0.7 is the reference.

Honest divergences pinned BOTH sides (see inline ``DIVERGENCE`` notes):
  - ``get_text_for_region`` of an unregistered / never-extracted name: upstream
    throws ``NullPointerException`` (``regionText.get(name)`` is ``null`` and
    ``.toString()`` NPEs); pypdfbox returns ``""`` (a deliberate, gentler
    contract relied on by the upstream-ported test + several hand tests).

Decorated ``@requires_oracle`` so it skips cleanly without Java + the jar.
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

# Synthetic layout — must match the comment block in TextByAreaFuzzProbe.java.
#   user (100, 700) "ALPHA"   -> awt (100,  92)
#   user (400, 700) "BRAVO"   -> awt (400,  92)
#   user (100, 400) "CHARLIE" -> awt (100, 392)
#   user (400, 100) "DELTA"   -> awt (400, 692)
_RUNS = [
    (100.0, 700.0, "ALPHA"),
    (400.0, 700.0, "BRAVO"),
    (100.0, 400.0, "CHARLIE"),
    (400.0, 100.0, "DELTA"),
]

# AWT rect = (x, y, width, height), top-left origin, y-down.
_AwtRect = tuple[float, float, float, float]


def _build_doc(path: Path) -> None:
    doc = PDDocument()
    try:
        font = PDFontFactory.create_default_font("Helvetica")
        page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
        doc.add_page(page)
        cs = PDPageContentStream(doc, page)
        for x, y, txt in _RUNS:
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
    return s.replace("\\r", "\r").replace("\\n", "\n").replace("\\\\", "\\")


def _parse_probe(out: str) -> dict[str, str]:
    """Parse ``CASE:<name>:<payload>`` lines into {name: unescaped_payload}."""
    result: dict[str, str] = {}
    for line in out.splitlines():
        if not line.startswith("CASE:"):
            continue
        rest = line[len("CASE:") :]
        name, _, payload = rest.partition(":")
        result[name] = _unescape(payload)
    return result


def _awt_to_user(rect: _AwtRect) -> tuple[float, float, float, float]:
    ax, ay, w, h = rect
    return (ax, _PAGE_H - (ay + h), w, h)


def _single(page: PDPage, rect: _AwtRect, *, sort: bool) -> str:
    """pypdfbox single-region extraction, mirroring the probe's ``single``."""
    s = PDFTextStripperByArea()
    s.set_sort_by_position(sort)
    s.add_region("r", _awt_to_user(rect))
    s.extract_regions(page)
    return s.get_text_for_region("r")


# The same degenerate-geometry rects the probe hard-codes (probe order).
_GEOM_CASES: list[tuple[str, _AwtRect]] = [
    ("around_alpha", (80, 80, 120, 40)),
    ("zero_width", (100, 80, 0, 40)),
    ("zero_height", (80, 92, 120, 0)),
    ("zero_area_point", (100, 92, 0, 0)),
    ("outside_page", (5000, 5000, 100, 100)),
    ("outside_top", (100, -500, 100, 100)),
    ("neg_origin_reaches", (-50, 60, 300, 80)),
    ("neg_origin_empty", (-500, -500, 100, 100)),
    ("larger_than_page", (-100, -100, 5000, 5000)),
    ("exact_page", (0, 0, 612, 792)),
    ("neg_width", (200, 92, -120, 40)),
    ("neg_height", (80, 132, 120, -40)),
    ("left_edge_inclusive", (100, 80, 120, 40)),
    ("right_edge_exclusive", (0, 80, 100, 40)),
    ("around_charlie", (80, 380, 120, 40)),
    ("tall_column", (80, 80, 120, 360)),
]

# DIVERGENCE: negative-width/height rectangles. Java's ``Rectangle2D.Double``
# with a negative dimension is an EMPTY rectangle (``contains()`` always false),
# so the probe captures nothing. pypdfbox's tuple form deliberately *normalizes*
# negative dimensions into a valid rect (``_normalize_rect`` — pinned as intended
# behaviour by ``test_add_region_normalizes_negative_dimensions``), so the same
# ``(200, 92, -120, 40)`` becomes ``[80, 200] x ...`` and captures ALPHA. These
# cases are pinned BOTH sides separately, not in the byte-parity loop.
_NEG_DIM_CASES = {"neg_width", "neg_height"}


@pytest.fixture(scope="module")
def _pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("byarea_fuzz") / "doc.pdf"
    _build_doc(path)
    return path


@requires_oracle
@pytest.mark.parametrize("sort", [True, False], ids=["sort", "nosort"])
def test_degenerate_geometry_matches_pdfbox(_pdf: Path, sort: bool) -> None:
    """Every degenerate single-region geometry returns byte-identical text on
    both engines for both sort states.

    Covers zero-area, off-page (positive + negative coords), exact-page,
    larger-than-page, negative width/height, and half-open boundary edge
    inclusion/exclusion."""
    flag = "sort" if sort else "nosort"
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), flag))

    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)
        for name, rect in _GEOM_CASES:
            if name in _NEG_DIM_CASES:
                continue  # documented divergence — pinned separately below
            py = _single(page, rect, sort=sort)
            assert py == java[name], f"{name} (sort={sort})"

        # DIVERGENCE pinned BOTH sides: negative-dimension rects.
        for name, rect in _GEOM_CASES:
            if name not in _NEG_DIM_CASES:
                continue
            py = _single(page, rect, sort=sort)
            # Java: empty rectangle -> no capture.
            assert java[name] == "\n"
            # pypdfbox: normalized rect captures ALPHA.
            assert py == "ALPHA\n"
    finally:
        doc.close()

    # Spot-pin the load-bearing expectations so a future probe drift is caught.
    assert java["around_alpha"] == "ALPHA\n"
    assert java["zero_width"] == "\n"
    assert java["zero_height"] == "\n"
    assert java["zero_area_point"] == "\n"
    assert java["outside_page"] == "\n"
    assert java["neg_origin_empty"] == "\n"
    # Negative-coordinate region overlapping the ALPHA band still captures it.
    assert java["neg_origin_reaches"] == "ALPHA\n"
    # Page-spanning / exact-page regions capture every glyph.
    assert java["larger_than_page"] == "ALPHA BRAVO\nCHARLIE\nDELTA\n"
    assert java["exact_page"] == "ALPHA BRAVO\nCHARLIE\nDELTA\n"
    # AWT Rectangle2D.Double with negative width/height -> contains() is always
    # false (empty rectangle), so no glyph is captured.
    assert java["neg_width"] == "\n"
    assert java["neg_height"] == "\n"
    # Half-open contains(): glyph origin on the LEFT edge is inside; a region
    # whose RIGHT edge is exactly the glyph x excludes it.
    assert java["left_edge_inclusive"] == "ALPHA\n"
    assert java["right_edge_exclusive"] == "\n"


@requires_oracle
@pytest.mark.parametrize("sort", [True, False], ids=["sort", "nosort"])
def test_duplicate_region_name_appends(_pdf: Path, sort: bool) -> None:
    """Re-adding a region name appends it again to ``get_regions`` while the
    last rect wins in the area map — byte-for-byte upstream parity (the fix this
    wave landed).

    Upstream ``addRegion`` unconditionally ``regions.add(name)`` +
    ``regionArea.put(name, rect)``: ``add("r"); add("r")`` yields
    ``getRegions() == ["r", "r"]`` and ``getTextForRegion("r")`` carries the
    SECOND rect's capture (CHARLIE, not ALPHA)."""
    flag = "sort" if sort else "nosort"
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), flag))

    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)
        s = PDFTextStripperByArea()
        s.set_sort_by_position(sort)
        s.add_region("r", _awt_to_user((80, 80, 120, 40)))    # ALPHA
        s.add_region("r", _awt_to_user((80, 380, 120, 40)))   # CHARLIE
        s.extract_regions(page)
        py_regions = list(s.get_regions())
        py_text = s.get_text_for_region("r")
    finally:
        doc.close()

    assert java["dup_replace_regions"] == "REGIONS:r,r"
    assert ",".join(py_regions) == "r,r"
    assert py_text == java["dup_replace_text"] == "CHARLIE\n"


@requires_oracle
@pytest.mark.parametrize("sort", [True, False], ids=["sort", "nosort"])
def test_remove_region_lifecycle_matches_pdfbox(_pdf: Path, sort: bool) -> None:
    """``remove_region`` of a registered name drops it from ``get_regions`` and
    the kept region still captures; removing an unregistered name is a silent
    no-op — region list + kept text byte-identical to PDFBox."""
    flag = "sort" if sort else "nosort"
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), flag))

    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)

        # remove a registered region
        s = PDFTextStripperByArea()
        s.set_sort_by_position(sort)
        s.add_region("keep", _awt_to_user((80, 80, 120, 40)))
        s.add_region("drop", _awt_to_user((80, 380, 120, 40)))
        s.remove_region("drop")
        s.extract_regions(page)
        assert "REGIONS:" + ",".join(s.get_regions()) == java["remove_regions"]
        assert s.get_text_for_region("keep") == java["remove_kept"]

        # remove an unregistered name -> no-op
        s2 = PDFTextStripperByArea()
        s2.set_sort_by_position(sort)
        s2.add_region("only", _awt_to_user((80, 80, 120, 40)))
        s2.remove_region("never_added")
        s2.extract_regions(page)
        assert (
            "REGIONS:" + ",".join(s2.get_regions())
            == java["remove_unregistered_regions"]
        )
        assert s2.get_text_for_region("only") == java["remove_unregistered_text"]
    finally:
        doc.close()

    assert java["remove_regions"] == "REGIONS:keep"
    assert java["remove_kept"] == "ALPHA\n"
    assert java["remove_unregistered_regions"] == "REGIONS:only"
    assert java["remove_unregistered_text"] == "ALPHA\n"


@requires_oracle
@pytest.mark.parametrize("sort", [True, False], ids=["sort", "nosort"])
def test_many_small_regions_match_pdfbox(_pdf: Path, sort: bool) -> None:
    """Eight tiny 4x4 regions stepped across the ALPHA glyph band: each
    region's per-glyph capture is byte-identical to PDFBox."""
    flag = "sort" if sort else "nosort"
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), flag))

    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)
        s = PDFTextStripperByArea()
        s.set_sort_by_position(sort)
        for i in range(8):
            s.add_region(f"m{i}", _awt_to_user((100 + i * 2, 90 + i, 4, 4)))
        s.extract_regions(page)
        py = {n: s.get_text_for_region(n) for n in s.get_regions()}
    finally:
        doc.close()

    for i in range(8):
        name = f"m{i}"
        assert py[name] == java[f"many_small_{name}"], name
    # The first tiny region on ALPHA's origin captures the leading glyph.
    assert py["m0"] == "A\n"


@requires_oracle
@pytest.mark.parametrize("sort", [True, False], ids=["sort", "nosort"])
def test_reextract_clears_prior_state_matches_pdfbox(
    _pdf: Path, sort: bool
) -> None:
    """A capturing extraction followed by re-extraction with an off-page region
    must not leak the first capture — byte-identical to PDFBox."""
    flag = "sort" if sort else "nosort"
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), flag))

    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)
        s = PDFTextStripperByArea()
        s.set_sort_by_position(sort)
        s.add_region("r", _awt_to_user((80, 80, 120, 40)))
        s.extract_regions(page)
        first = s.get_text_for_region("r")
        s.remove_region("r")
        s.add_region("r", _awt_to_user((5000, 5000, 10, 10)))
        s.extract_regions(page)
        second = s.get_text_for_region("r")
    finally:
        doc.close()

    assert first == java["reextract_first"] == "ALPHA\n"
    assert second == java["reextract_second"] == "\n"


@requires_oracle
def test_unregistered_and_before_extract_divergence(_pdf: Path) -> None:
    """DIVERGENCE pinned BOTH sides: ``get_text_for_region`` of an unregistered
    name (or before any ``extract_regions``) throws ``NullPointerException`` in
    Apache PDFBox (``regionText.get(name)`` is ``null``; ``.toString()`` NPEs),
    whereas pypdfbox returns ``""`` — a deliberate gentler contract relied on by
    the upstream-ported test and several hand tests. We pin the Java NPE here so
    a future engine change that started raising is detected, and assert the
    pypdfbox side keeps the documented ``""`` contract."""
    java = _parse_probe(run_probe_text("TextByAreaFuzzProbe", str(_pdf), "sort"))

    # Java side: NPE for both cases (the probe traps it as EXC:<type>).
    assert java["unregistered_name"] == "EXC:NullPointerException"
    assert java["before_extract"] == "EXC:NullPointerException"
    assert java["remove_dropped"] == "EXC:NullPointerException"

    # pypdfbox side: gentler "" contract (documented divergence — CHANGES.md).
    doc = PDDocument.load(str(_pdf))
    try:
        page = doc.get_page(0)

        s = PDFTextStripperByArea()
        s.add_region("r", _awt_to_user((80, 80, 120, 40)))
        s.extract_regions(page)
        assert s.get_text_for_region("does_not_exist") == ""

        s2 = PDFTextStripperByArea()
        s2.add_region("r", _awt_to_user((80, 80, 120, 40)))
        assert s2.get_text_for_region("r") == ""  # before extract

        s3 = PDFTextStripperByArea()
        s3.add_region("keep", _awt_to_user((80, 80, 120, 40)))
        s3.add_region("drop", _awt_to_user((80, 380, 120, 40)))
        s3.remove_region("drop")
        s3.extract_regions(page)
        assert s3.get_text_for_region("drop") == ""  # removed -> never extracted
    finally:
        doc.close()
