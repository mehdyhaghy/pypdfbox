"""Live PDFBox differential parity for path-painting fill rules and clip-path
rasterisation (PDF 32000-1 §8.5.3.3 fill rules / §8.5.4 clipping).

Recent rendering waves pinned image-XObject masks, gs merge, and text-state
matrix — this surface owns the *path* fill-rule + clip raster, untouched by
those. The cases here exercise:

* **nonzero (``f``) vs even-odd (``f*``)** winding on a self-intersecting
  5-point star — nonzero fills the central pentagon solid, even-odd leaves
  it empty (a hole). The two rasters differ materially in the centre cells.
* **nonzero vs even-odd on two nested same-direction rectangles** — nonzero
  fills the whole outer rect solid (inner contributes a second positive
  winding), even-odd leaves the inner rect as a hole (an annulus). Again a
  materially different raster.
* **``W`` clip then fill** — a clip rectangle intersected with a larger fill
  rect: only the clipped sub-region is painted; the rest shows backdrop.
* **``W*`` even-odd clip on nested rects then fill** — the clip region is the
  annular band between the two rects; a large fill paints only that ring.

Pixel-EXACT parity is impossible (Pillow/skia vs Java2D AA — see ``CHANGES.md``
/ ``test_render_oracle.py``), so we compare the proven coarse fingerprint:
exact rendered dimensions plus a 16x16 average-luminance grid, gated at
``MAD < 6`` / ``MAXDIFF < 60`` against ``oracle/probes/PathFillClipProbe.java``
(72 DPI render — identical luminance math to ``RenderProbe`` / ``ImageMaskProbe``,
dedicated named probe per the wave brief).

The ``test_even_odd_vs_nonzero_differ`` guard proves the two fill rules
produce a *materially* different raster on the chosen paths, so the gate is
actually discriminating fill-rule semantics rather than passing any render.

Fixtures are tiny one-page PDFs synthesised in-memory via pypdfbox's own
content-stream API (no committed binaries).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_image_mask_oracle.py / test_soft_mask_oracle.py — well
# above the AA ceiling yet far below the gross-failure floor (a wrong fill
# rule, an ignored clip, or an inverted winding all diverge past this).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``PathFillClipProbe.java`` (integer-division of pixel coord over image
    size, clamped to the last cell). Matches PIL's "L" Rec.601 weights."""
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run PathFillClipProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("PathFillClipProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _new_doc_page() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    return doc, page


def _fill_backdrop(cs: PDPageContentStream, rgb: tuple[float, float, float]) -> None:
    cs.set_non_stroking_color(*rgb)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()


def _star_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """Five outer vertices of a regular pentagram, connected in 2-step
    order so the polyline self-intersects (the classic 5-point star)."""
    outer = [
        (cx + r * math.sin(2 * math.pi * k / 5), cy + r * math.cos(2 * math.pi * k / 5))
        for k in range(5)
    ]
    # Connect every second vertex (0,2,4,1,3) to draw the pentagram.
    return [outer[(2 * k) % 5] for k in range(5)]


def _trace_star(cs: PDPageContentStream) -> None:
    pts = _star_points(_MB / 2, _MB / 2, 70.0)
    cs.move_to(*pts[0])
    for p in pts[1:]:
        cs.line_to(*p)
    cs.close_path()


def _trace_nested_rects(cs: PDPageContentStream) -> None:
    """Two concentric rectangles, both traced counter-clockwise (same
    winding direction). Under nonzero the interior winds twice and stays
    filled solid; under even-odd the inner rect punches a hole."""
    # Outer rect CCW.
    cs.move_to(40, 40)
    cs.line_to(160, 40)
    cs.line_to(160, 160)
    cs.line_to(40, 160)
    cs.close_path()
    # Inner rect CCW (same direction).
    cs.move_to(80, 80)
    cs.line_to(120, 80)
    cs.line_to(120, 120)
    cs.line_to(80, 120)
    cs.close_path()


def _build_star_nonzero(path: Path) -> None:
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    _trace_star(cs)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_star_even_odd(path: Path) -> None:
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    _trace_star(cs)
    cs.fill_even_odd()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_nested_nonzero(path: Path) -> None:
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    _trace_nested_rects(cs)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_nested_even_odd(path: Path) -> None:
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    _trace_nested_rects(cs)
    cs.fill_even_odd()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_clip_nonzero(path: Path) -> None:
    """Clip to a centred rectangle (``W n``), then fill the whole page in
    a dark colour. Only the clipped sub-region shows the fill; the rest
    stays the white backdrop."""
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    cs.add_rect(60, 60, 80, 80)
    cs.clip()
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


def _build_clip_even_odd_annulus(path: Path) -> None:
    """Even-odd clip (``W* n``) on two nested same-direction rects forms an
    annular clip band; filling the whole page paints only the ring, leaving
    the inner square and the outer margin as white backdrop."""
    doc, page = _new_doc_page()
    cs = PDPageContentStream(doc, page)
    _fill_backdrop(cs, (1.0, 1.0, 1.0))
    _trace_nested_rects(cs)
    cs.clip_even_odd()
    cs.set_non_stroking_color(0.1, 0.1, 0.1)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "star_nonzero": _build_star_nonzero,
    "star_even_odd": _build_star_even_odd,
    "nested_nonzero": _build_nested_nonzero,
    "nested_even_odd": _build_nested_even_odd,
    "clip_nonzero": _build_clip_nonzero,
    "clip_even_odd_annulus": _build_clip_even_odd_annulus,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_path_fill_clip_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each fill-rule / clip variant must match Java PDFBox's render of the
    same fixture within the 16x16 fingerprint gate."""
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — fill rule / clip mis-applied, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
@pytest.mark.parametrize(
    ("nonzero", "even_odd"),
    [
        (_build_star_nonzero, _build_star_even_odd),
        (_build_nested_nonzero, _build_nested_even_odd),
    ],
    ids=["star", "nested_rects"],
)
def test_even_odd_vs_nonzero_differ(nonzero, even_odd, tmp_path: Path) -> None:
    """Guard: the two fill rules must produce a *materially* different raster
    on the chosen self-intersecting / nested path (nonzero fills the centre,
    even-odd leaves a hole). If they rendered identically the parity gate
    would be meaningless — a renderer that ignored ``*`` would still pass
    the per-variant test against an oracle that *also* ignored it, so this
    proves the chosen paths discriminate the rule."""
    nz = tmp_path / "nz.pdf"
    eo = tmp_path / "eo.pdf"
    nonzero(nz)
    even_odd(eo)

    with PDDocument.load(nz) as doc:
        nz_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    with PDDocument.load(eo) as doc:
        eo_img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)

    nz_grid = _grid_from_image(nz_img)
    eo_grid = _grid_from_image(eo_img)
    diffs = [abs(a - b) for a, b in zip(nz_grid, eo_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    # The central hole is several cells of near-white-vs-near-black.
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        f"even-odd and nonzero rasters indistinguishable (maxdiff={maxdiff}, "
        f"mad={mad:.2f}) — the chosen path does not discriminate fill rules"
    )
