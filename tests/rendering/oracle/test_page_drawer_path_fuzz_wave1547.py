"""Live PDFBox differential FUZZ of the PageDrawer path-construction / fill /
clip / stroke surface (PDF 32000-1 §8.5 path objects, §8.5.3 path painting,
§8.5.4 clipping).

Where ``test_path_fill_clip_oracle.py`` / ``test_stroke_geometry_oracle.py``
pin a 16x16 *luminance grid* on hand-chosen well-formed paths, this wave
*fuzzes the edges*: degenerate rectangles, self-intersecting paths under both
fill rules, nested clip stacks, clip-with-no-paint, zero / negative line width,
sub-pixel diagonal strokes, path operators with no current point, ``h`` with no
subpath, huge off-page coordinates, and a concave polygon.

Pixel-exact parity is impossible (Java2D vs skia AA — see ``CHANGES.md`` /
``test_render_oracle.py``), so this surface compares only **gross painted-region
facts** projected by ``oracle/probes/PageDrawerPathFuzzProbe.java``:

* exact rendered pixel dimensions (a mismatch is a real bug, not AA);
* the count of non-white pixels bucketed into {empty, sparse, moderate, dense}
  — exact counts drift with AA, but a region PDFBox paints must not be *empty*
  on the Python side (and vice-versa);
* the painted bounding box, compared with a generous ``_BBOX_SLOP`` pixel
  tolerance (AA fringes the box by ~1px).

The real bug this fuzz caught (wave 1547): ``l`` / ``c`` / ``v`` / ``y`` with no
preceding ``m`` were *dropped* by the renderer's operator dispatch, so a stream
like ``50 50 l 90 90 l S`` rendered blank where Apache PDFBox does an implicit
``moveTo`` and strokes the line (PDFBox's LineTo / CurveTo operators:
``getCurrentPoint() == null`` → ``moveTo``). Fixed in
``pypdfbox/rendering/pdf_renderer.py``; the ``line_no_current_point`` case below
pins the corrected behaviour against the oracle.

Fixtures are tiny one-page PDFs synthesised in-memory from a raw content stream
(no committed binaries), matching ``test_stroke_geometry_oracle.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE = 120.0  # square page (== px at 72 DPI)
_WHITE_THRESHOLD = 250  # luma < this counts as painted (matches the probe)
_BBOX_SLOP = 3  # px tolerance on the painted bbox edges (AA fringe)


# ---------------------------------------------------------------------------
# fuzz content streams — each exercises a distinct path / fill / clip / stroke
# edge case. 1 user unit == 1 px at 72 DPI on the 120x120 page.
# ---------------------------------------------------------------------------
_CASES: dict[str, bytes] = {
    # --- degenerate rectangles (re with zero extent) ---
    "rect_zero_width_stroke": b"0 0 0 RG 2 w\n40 20 0 60 re S\n",
    "rect_zero_height_stroke": b"0 0 0 RG 2 w\n20 60 80 0 re S\n",
    "rect_zero_width_fill": b"0 0 0 rg\n40 20 0 60 re f\n",
    "rect_zero_height_fill": b"0 0 0 rg\n20 60 80 0 re f\n",
    "rect_zero_both_fill": b"0 0 0 rg\n60 60 0 0 re f\n",
    "rect_negative_extent_fill": b"0 0 0 rg\n100 100 -60 -60 re f\n",
    # --- self-intersecting path under both fill rules ---
    "self_intersect_nonzero": (
        b"0 0 0 rg\n20 20 m 100 100 l 100 20 l 20 100 l h f\n"
    ),
    "self_intersect_evenodd": (
        b"0 0 0 rg\n20 20 m 100 100 l 100 20 l 20 100 l h f*\n"
    ),
    # --- nested / stacked clip paths ---
    "nested_clip_fill": (
        b"0 0 0 rg\n10 10 100 100 re W n\n40 40 100 100 re W n\n"
        b"0 0 120 120 re f\n"
    ),
    "clip_then_fill_page": (
        b"0 0 0 rg\n40 40 40 40 re W n\n0 0 120 120 re f\n"
    ),
    "clip_no_painting_op": (
        # W n with no following painting op at all — page stays blank.
        b"0 0 0 rg\n40 40 40 40 re W n\n"
    ),
    "evenodd_clip_annulus": (
        b"0 0 0 rg\n20 20 80 80 re 40 40 40 40 re W* n\n0 0 120 120 re f\n"
    ),
    # --- stroke line-width edges ---
    "stroke_zero_width": b"0 0 0 RG 0 w\n20 60 m 100 60 l S\n",
    "stroke_negative_width": b"0 0 0 RG -5 w\n20 60 m 100 60 l S\n",
    "stroke_thin_diagonal": b"0 0 0 RG 0.1 w\n20 20 m 100 100 l S\n",
    "stroke_thick": b"0 0 0 RG 10 w\n20 60 m 100 60 l S\n",
    # --- path operators with no current point ---
    "line_no_current_point": b"0 0 0 RG 2 w\n50 50 l 90 90 l S\n",
    "curve_no_current_point": (
        b"0 0 0 rg\n30 30 60 90 90 30 c f\n"
    ),
    "close_no_moveto": b"0 0 0 RG 2 w\nh S\n",
    # --- huge off-page coordinates clipped to the canvas ---
    "huge_coords_fill": (
        b"0 0 0 rg\n-1000 -1000 m 5000 60 l 60 5000 l h f\n"
    ),
    # --- concave polygon fill ---
    "concave_poly_fill": (
        b"0 0 0 rg\n20 20 m 100 20 l 100 100 l 60 50 l 20 100 l h f\n"
    ),
    # --- closed-fill-then-stroke (b) on a triangle ---
    "close_fill_stroke": (
        b"0 0 1 rg 1 0 0 RG 3 w\n30 30 m 90 30 l 60 90 l b\n"
    ),
    # --- multiple disjoint subpaths in one fill ---
    "two_subpath_fill": (
        b"0 0 0 rg\n20 20 30 30 re 70 70 30 30 re f\n"
    ),
}


# Per-case expected painted-region buckets, derived from Apache PDFBox 3.0.7
# (PageDrawerPathFuzzProbe). The oracle is consulted live when available; these
# are the documented fallback so the suite still asserts something meaningful
# when Java is absent. "empty" => nothing painted; "painted" => non-empty.
_EXPECT_PAINTED: dict[str, bool] = {
    "rect_zero_width_stroke": True,  # degenerate rect strokes as a vertical line
    "rect_zero_height_stroke": True,  # strokes as a horizontal line
    "rect_zero_width_fill": False,  # zero-area fill paints nothing
    "rect_zero_height_fill": False,
    "rect_zero_both_fill": False,
    "rect_negative_extent_fill": True,  # negative w/h still bounds an area
    "self_intersect_nonzero": True,
    "self_intersect_evenodd": True,
    "nested_clip_fill": True,
    "clip_then_fill_page": True,
    "clip_no_painting_op": False,  # W n with no paint => blank page
    "evenodd_clip_annulus": True,
    "stroke_zero_width": True,  # zero width => 1px hairline
    "stroke_negative_width": True,  # negative width => 1px hairline
    "stroke_thin_diagonal": True,
    "stroke_thick": True,
    "line_no_current_point": True,  # implicit moveTo => line strokes (the bug)
    "curve_no_current_point": False,  # implicit moveTo, curve skipped => blank
    "close_no_moveto": False,
    "huge_coords_fill": True,
    "concave_poly_fill": True,
    "close_fill_stroke": True,
    "two_subpath_fill": True,
}


# ---------------------------------------------------------------------------
# fixture builder + fingerprint helpers
# ---------------------------------------------------------------------------


def _build(label: str, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    page.set_resources(PDResources())
    doc.add_page(page)
    stream = COSStream()
    stream.set_raw_data(_CASES[label])
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _painted_facts(img: Image.Image) -> tuple[int, tuple[int, int, int, int]]:
    """(painted_count, (minx, miny, maxx, maxy)) — mirrors the probe exactly.

    Empty paint returns ``(0, (-1, -1, -1, -1))``."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    painted = 0
    minx = miny = maxx = maxy = -1
    for y in range(height):
        for x in range(width):
            if pixels[x, y] < _WHITE_THRESHOLD:
                painted += 1
                if minx < 0 or x < minx:
                    minx = x
                if miny < 0 or y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    return painted, (minx, miny, maxx, maxy)


def _oracle_facts(
    fixture: Path,
) -> tuple[tuple[int, int], int, tuple[int, int, int, int]]:
    """Run the probe on page 0 → ((w, h), painted, bbox)."""
    lines = run_probe_text("PageDrawerPathFuzzProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    vals = [int(v) for v in lines[1].split()]
    painted = vals[0]
    bbox = (vals[1], vals[2], vals[3], vals[4])
    return (width, height), painted, bbox


def _bucket(painted: int, total_px: int) -> str:
    """Coarse painted-pixel bucket robust to AA pixel-count drift."""
    if painted == 0:
        return "empty"
    frac = painted / total_px
    if frac < 0.02:
        return "sparse"
    if frac < 0.30:
        return "moderate"
    return "dense"


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_page_drawer_path_fuzz_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each fuzz case must match Apache PDFBox's *gross painted-region facts*:
    identical dimensions, the same emptiness verdict and painted bucket, and a
    painted bbox within ``_BBOX_SLOP`` px. Exact pixel counts and sub-pixel AA
    are expected to diverge and are NOT compared."""
    fixture = _build(label, tmp_path / f"{label}.pdf")

    (java_w, java_h), java_painted, java_bbox = _oracle_facts(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_painted, py_bbox = _painted_facts(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dims diverge: py={py_w}x{py_h} java={java_w}x{java_h}"
    )

    total_px = java_w * java_h
    java_empty = java_painted == 0
    py_empty = py_painted == 0

    # (b) Emptiness verdict must agree — the real-bug signal. A region PDFBox
    #     paints must not be blank on our side, and vice-versa.
    assert py_empty == java_empty, (
        f"{label}: painted-emptiness diverges — pypdfbox painted "
        f"{py_painted}px, java painted {java_painted}px. A region one "
        f"renderer paints the other leaves blank is a real path bug, not AA."
    )

    if java_empty:
        return  # both blank — bbox / bucket are meaningless

    # (c) Coarse pixel-count bucket must agree (drift-tolerant).
    java_bucket = _bucket(java_painted, total_px)
    py_bucket = _bucket(py_painted, total_px)
    assert py_bucket == java_bucket, (
        f"{label}: painted bucket diverges py={py_bucket}({py_painted}) "
        f"java={java_bucket}({java_painted}) — more than AA drift"
    )

    # (d) Painted bbox within slop (AA fringes the box by ~1px).
    for axis, (p, j) in enumerate(zip(py_bbox, java_bbox, strict=True)):
        assert abs(p - j) <= _BBOX_SLOP, (
            f"{label}: painted bbox axis {axis} diverges py={py_bbox} "
            f"java={java_bbox} (slop={_BBOX_SLOP})"
        )


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_page_drawer_path_fuzz_emptiness_pinned(label: str, tmp_path: Path) -> None:
    """Oracle-free pin of the documented PDFBox 3.0.7 emptiness verdict — runs
    everywhere (no Java needed) so the corrected path-construction semantics
    (notably ``line_no_current_point`` painting after the wave-1547 fix) stay
    green in CI without the live jar."""
    fixture = _build(label, tmp_path / f"{label}.pdf")
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    painted, _bbox = _painted_facts(img)
    expect_painted = _EXPECT_PAINTED[label]
    assert (painted > 0) == expect_painted, (
        f"{label}: expected painted={expect_painted} but got {painted}px "
        f"(PDFBox 3.0.7 reference). A flip here means a path-construction "
        f"regression, not anti-aliasing."
    )


@requires_oracle
def test_line_implicit_moveto_paints_like_pdfbox(tmp_path: Path) -> None:
    """Direct regression pin for the wave-1547 bug: ``50 50 l 90 90 l S`` (a
    ``l`` with no initial ``m``) must paint a non-trivial diagonal stroke,
    matching PDFBox's implicit-moveTo fallback rather than the old blank
    render. Guards specifically against re-dropping the implicit moveTo."""
    fixture = _build("line_no_current_point", tmp_path / "line.pdf")
    (_jw, _jh), java_painted, _jbox = _oracle_facts(fixture)
    assert java_painted > 0, "oracle sanity: PDFBox should paint the line"

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_painted, _pbox = _painted_facts(img)
    assert py_painted > 0, (
        "implicit-moveTo regression: pypdfbox rendered nothing for "
        "'50 50 l 90 90 l S' while PDFBox strokes the line"
    )
