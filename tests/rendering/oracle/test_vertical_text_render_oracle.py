"""Live PDFBox differential parity for *vertical writing-mode* text rendering.

Wave 1439. Companion to ``tests/pdmodel/font/oracle/test_vertical_font_oracle.py``
(wave 1428), which pinned the WMode-1 *metrics* on ``PDType0Font`` — ``/W2`` /
``/DW2`` displacement and position vectors. This file exercises the distinct
*render* path in ``pypdfbox.rendering``: when a Type0 font uses a ``-V`` encoding
CMap (``Identity-V``, WMode 1), the glyph-show operator must stack glyphs
DOWNWARD using the displacement vector's *y* component and shift each glyph by
the font's position vector — not advance left-to-right like a horizontal font.

The classic vertical-render bugs this guards against:

* **WMode ignored at render time** — the renderer advances rightward despite the
  vertical CMap, so the glyphs lay out as a horizontal row (the visible result
  is identical to ``Identity-H``);
* **wrong vertical advance** — glyphs overlap or are wrongly spaced because the
  advance uses the horizontal width instead of the ``/W2`` ``w1y`` displacement;
* **position vector not applied** — glyphs are not centred in the column, so the
  whole column sits at the wrong horizontal offset.

No vertical fixture ships in the corpus, so the test BUILDS two single-page PDFs
from the bundled LiberationSans TTF (already provenance-tracked) showing the same
string at the same size and origin:

* the **vertical** PDF via ``PDType0Font.load_vertical`` (``/Encoding
  /Identity-V``) — glyphs must stack into a tall, narrow column;
* a **horizontal** control via ``PDType0Font.load`` (``/Encoding /Identity-H``) —
  glyphs lay out as a wide, short row.

Both are rendered through Apache PDFBox (``oracle/probes/RenderProbe.java``) and
through pypdfbox at 72 DPI and compared with the same tolerance fingerprint the
page-render oracle uses:

* **exact page dimensions** — a mismatch is a real bug (wrong scale rounding),
  never anti-aliasing;
* **16x16 luminance grid** — average Rec.601 luminance per cell, compared by
  mean-absolute cell diff (MAD) and worst single-cell diff (MAXDIFF). Survives
  AA / sub-pixel coverage differences (Java2D vs Pillow/aggdraw) but catches a
  horizontally-laid-out column, an overlapping/over-spaced column, or a
  column at the wrong horizontal offset.

Gate is wave 1408's calibrated ``MAD < 6`` / ``MAXDIFF < 60``. Measured against
PDFBox 3.0.7 the vertical render lands at MAD ~0.1 / MAXDIFF ~5 (the vertical
glyph-advance path paints where PDFBox does). The vertical render measured
against the *horizontal control* grid is MAD ~8 / MAXDIFF ~92 — comfortably
OUTSIDE the gate (asserted below), proving the glyphs really stack vertically
and the WMode-1 path is not silently rendering left-to-right.

Divergence history:
  * Wave 1439 found ``PDFRenderer._show_string`` always advanced the text matrix
    horizontally (``trans = (1,0,0,1,tx,0)``) and never applied the position
    vector — WMode was ignored at render time, so an ``Identity-V`` font laid
    its glyphs out as a horizontal row identical to ``Identity-H``. Fixed in
    ``pypdfbox/rendering/pdf_renderer.py`` (``_show_string`` + ``_draw_glyph``):
    the vertical branch now advances downward by the displacement-y and prepends
    the position vector to the glyph's text-local matrix. See CHANGES.md.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate wave 1408 calibrated for whole-page / glyph render parity.
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Small page so a column of glyphs fills a large fraction of the canvas and the
# vertical-vs-horizontal layout difference dominates the coarse grid.
_PAGE_W = 200.0
_PAGE_H = 200.0
_FONT_SIZE = 28
_STRING = "ABCDEF"

_TTF = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _build(out: Path, *, vertical: bool) -> Path:
    """Save a one-page PDF showing ``_STRING`` in LiberationSans as either a
    vertical (``/Identity-V``) or horizontal (``/Identity-H``) Type0 font, at
    the same size and origin so the only difference is the writing mode."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    doc.add_page(page)
    with _TTF.open("rb") as fh:
        font = (
            PDType0Font.load_vertical(doc, fh, False)
            if vertical
            else PDType0Font.load(doc, fh, False)
        )
    encoded = font.encode(_STRING)
    # Vertical text starts near the top and runs down; horizontal starts low-
    # left and runs right. Both keep the run on-page for the small canvas.
    origin_x, origin_y = (90.0, 170.0) if vertical else (20.0, 90.0)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, _FONT_SIZE)
        cs.new_line_at_offset(origin_x, origin_y)
        cs.show_text(encoded)
        cs.end_text()
    sink = io.BytesIO()
    doc.save(sink)
    doc.close()
    out.write_bytes(sink.getvalue())
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror RenderProbe.java's cell mapping exactly
# ---------------------------------------------------------------------------


def _grid_from_image(img: Image.Image) -> list[int]:
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
        round(total[i] / count[i]) if count[i] else 255
        for i in range(_GRID * _GRID)
    ]


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _mad_maxdiff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_vertical_text_render_matches_pdfbox(tmp_path: Path) -> None:
    """A vertical (``Identity-V``) Type0 text run must render the same column
    of stacked glyphs PDFBox produces — exact dims + grid within tolerance."""
    fixture = _build(tmp_path / "vertical.pdf", vertical=True)
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"vertical: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance — catches a column rendered
    #     horizontally, glyphs overlapping/over-spaced (wrong advance), or a
    #     column at the wrong horizontal offset (position vector not applied).
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"vertical: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — vertical text render grossly divergent, not AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"vertical: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_horizontal_control_render_matches_pdfbox(tmp_path: Path) -> None:
    """The horizontal (``Identity-H``) control must also match PDFBox, so the
    divergence guard below isolates writing mode rather than a shared bug."""
    fixture = _build(tmp_path / "horizontal.pdf", vertical=False)
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    assert img.size == (java_w, java_h), (
        f"horizontal: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={img.size} java={java_w}x{java_h}"
    )
    mad, maxdiff = _mad_maxdiff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"horizontal control diverges from PDFBox: mad={mad:.2f} "
        f"maxdiff={maxdiff}"
    )


@requires_oracle
def test_vertical_render_differs_from_horizontal_control(tmp_path: Path) -> None:
    """The vertical render must DIFFER materially from the horizontal control.

    Same font, same string, same size and origin — only the writing mode
    changes. If the renderer ignored WMode-1 (advancing rightward despite the
    ``Identity-V`` CMap), the vertical PDF would render a horizontal row
    indistinguishable from the control and this guard would fail. Compared on
    PDFBox's own grids (engine-independent), the two layouts diverge well
    beyond the parity tolerance — proving the glyphs really stack vertically.
    """
    vfix = _build(tmp_path / "vertical.pdf", vertical=True)
    hfix = _build(tmp_path / "horizontal.pdf", vertical=False)
    _vdims, vgrid = _oracle_signature(vfix)
    _hdims, hgrid = _oracle_signature(hfix)
    mad, maxdiff = _mad_maxdiff(vgrid, hgrid)
    assert mad >= _MAD_TOLERANCE, (
        f"vertical and horizontal renders are too similar (MAD {mad:.2f} < "
        f"{_MAD_TOLERANCE}) — WMode-1 vertical layout is not taking effect; the "
        f"glyphs are laid out left-to-right like the horizontal control"
    )


def test_vertical_render_stacks_glyphs_vertically(tmp_path: Path) -> None:
    """No-oracle geometry pin: a vertical run's dark-pixel bounding box is tall
    and narrow (a column); the horizontal control's is wide and short (a row).

    This directly asserts the visible result of WMode-1 — glyphs stacked down
    a column — without needing the Java oracle, so the bug stays caught even
    where the oracle isn't available.
    """

    def _dark_bbox(fixture: Path) -> tuple[int, int]:
        with PDDocument.load(fixture) as doc:
            img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
        gray = img.convert("L")
        width, height = gray.size
        px = gray.load()
        xs: list[int] = []
        ys: list[int] = []
        for y in range(height):
            for x in range(width):
                if px[x, y] < 128:
                    xs.append(x)
                    ys.append(y)
        assert xs, f"{fixture.name}: render is blank — no glyphs painted"
        return (max(xs) - min(xs), max(ys) - min(ys))

    v_w, v_h = _dark_bbox(_build(tmp_path / "vertical.pdf", vertical=True))
    h_w, h_h = _dark_bbox(_build(tmp_path / "horizontal.pdf", vertical=False))

    # Vertical: taller than wide (a column). Horizontal: wider than tall (a row).
    assert v_h > v_w, (
        f"vertical run is not a column: dark box {v_w}x{v_h} (w x h) — glyphs "
        f"did not stack downward"
    )
    assert h_w > h_h, (
        f"horizontal control is not a row: dark box {h_w}x{h_h} (w x h)"
    )
    # And the two layouts are genuinely transposed, not just slightly off.
    assert v_h > h_h and h_w > v_w, (
        f"vertical/horizontal layouts not distinct: "
        f"vertical={v_w}x{v_h} horizontal={h_w}x{h_h}"
    )
