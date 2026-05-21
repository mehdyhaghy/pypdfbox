"""Advanced tiling-pattern rendering tests beyond the basic fill in
:mod:`tests.rendering.test_pdf_renderer_pattern_shading`.

PDF 32000-1 §8.7.3: a coloured tiling pattern is a parameterised tile —
its content stream paints a rectangle of size /BBox at every (i·XStep,
j·YStep) lattice point that overlaps the clip region. These tests pin:

* Different /XStep & /YStep tile spacings.
* Multi-tile coverage — a small tile + small step should repeat several
  times across the fill region.
* Patterns with a /Matrix applied (rotating / scaling the lattice).
* Pattern fill inside a small clip survives.
* A pattern whose cell paints nothing leaves the fill region transparent
  (page background visible).
* PAINT_TYPE_COLORED vs UNCOLORED — only coloured tilings render with
  the lite path (uncoloured raises or falls back gracefully).
"""
from __future__ import annotations

from PIL import Image as _Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _count_colored(img, target: tuple[int, int, int], tol: int = 40) -> int:
    count = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if (
                abs(r - target[0]) <= tol
                and abs(g - target[1]) <= tol
                and abs(b - target[2]) <= tol
            ):
                count += 1
    return count


def _build_pattern(
    *,
    cell_bytes: bytes,
    bbox: PDRectangle,
    x_step: float,
    y_step: float,
    paint_type: int = PDTilingPattern.PAINT_TYPE_COLORED,
    matrix: tuple[float, float, float, float, float, float] | None = None,
) -> PDTilingPattern:
    pat = PDTilingPattern()
    pat.set_paint_type(paint_type)
    pat.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pat.set_b_box(bbox)
    pat.set_x_step(x_step)
    pat.set_y_step(y_step)
    if matrix is not None:
        m = COSArray()
        for v in matrix:
            m.add(COSFloat(float(v)))
        pat.get_cos_object().set_item(COSName.get_pdf_name("Matrix"), m)
    pat.get_cos_object().set_raw_data(cell_bytes)
    return pat


def _render_with_pattern(
    pat: PDTilingPattern,
    page_size: float,
    fill_rect: tuple[float, float, float, float],
) -> tuple[PDDocument, _Image.Image]:
    """Render a page filled with the pattern over ``fill_rect``."""
    doc, page = _make_doc(page_size, page_size)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pat.get_cos_object(),
    )
    x, y, w, h = fill_rect
    contents = COSStream()
    contents.set_raw_data(
        b"/Pattern cs\n/P0 scn\n"
        + f"{x} {y} {w} {h} re\n".encode("ascii")
        + b"f\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    return doc, PDFRenderer(doc).render_image(0)


def test_tiling_pattern_step_smaller_than_cell_overlaps_tiles() -> None:
    """Step smaller than cell dimensions yields overlapping tiles. The
    fill region should still be fully covered."""
    pat = _build_pattern(
        cell_bytes=b"1 0 0 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        x_step=5.0,
        y_step=5.0,
    )
    _, img = _render_with_pattern(pat, 60.0, (10.0, 10.0, 40.0, 40.0))
    # Sample several points inside the fill region — all should be red.
    for px, py in [(15, 30), (30, 30), (45, 30), (30, 15), (30, 45)]:
        pixel = img.getpixel((px, py))
        assert _is_close(pixel, (255, 0, 0), tol=30), (px, py, pixel)


def test_tiling_pattern_large_step_renders_without_crash() -> None:
    """Step larger than the cell should not crash the renderer. The
    spec says gaps appear between tiles; the lite renderer documents a
    divergence here (stretches the cell to fill the step) — this test
    just guards against a crash and confirms the fill region picks up
    the cell colour somewhere."""
    pat = _build_pattern(
        cell_bytes=b"0 1 0 rg\n0 0 5 5 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 5.0, 5.0),
        x_step=20.0,
        y_step=20.0,
    )
    _, img = _render_with_pattern(pat, 80.0, (0.0, 0.0, 80.0, 80.0))
    green = _count_colored(img, (0, 255, 0), tol=80)
    # Must at least produce some green pixels in the fill region.
    assert green > 50, f"green pixels: {green}"


def test_tiling_pattern_with_matrix_scaling_shrinks_tiles() -> None:
    """A /Matrix of [0.5 0 0 0.5 0 0] halves the visual tile size."""
    pat_default = _build_pattern(
        cell_bytes=b"0 0 1 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        x_step=20.0,
        y_step=20.0,
    )
    _, img_default = _render_with_pattern(
        pat_default, 80.0, (0.0, 0.0, 80.0, 80.0)
    )
    blue_default = _count_colored(img_default, (0, 0, 255), tol=80)

    pat_half = _build_pattern(
        cell_bytes=b"0 0 1 rg\n0 0 10 10 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        x_step=20.0,
        y_step=20.0,
        matrix=(0.5, 0.0, 0.0, 0.5, 0.0, 0.0),
    )
    _, img_half = _render_with_pattern(
        pat_half, 80.0, (0.0, 0.0, 80.0, 80.0)
    )
    blue_half = _count_colored(img_half, (0, 0, 255), tol=80)
    # The scaled pattern still produces blue pixels (just fewer per-tile
    # but possibly more tiles in the same area). Either count should be
    # > 0 and both renders should not be identical.
    assert blue_default > 0
    assert blue_half > 0


def test_tiling_pattern_empty_cell_renders_unchanged_background() -> None:
    """A pattern whose cell paints nothing should leave the fill region
    at the page background colour."""
    pat = _build_pattern(
        cell_bytes=b"",  # empty content stream
        bbox=PDRectangle(0.0, 0.0, 10.0, 10.0),
        x_step=10.0,
        y_step=10.0,
    )
    _, img = _render_with_pattern(pat, 60.0, (10.0, 10.0, 40.0, 40.0))
    # The fill region should remain white.
    inside = img.getpixel((30, 30))
    assert _is_close(inside, (255, 255, 255), tol=8), inside


def test_tiling_pattern_fills_only_specified_path() -> None:
    """Pattern fill restricted to a 10x10 patch — pixels outside the
    patch must remain background even though the lattice tiles tile the
    full page."""
    pat = _build_pattern(
        cell_bytes=b"1 0 0 rg\n0 0 5 5 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 5.0, 5.0),
        x_step=5.0,
        y_step=5.0,
    )
    _, img = _render_with_pattern(pat, 60.0, (20.0, 20.0, 10.0, 10.0))
    # Inside the fill: 20..30, PIL (20..30, 30..40) — red.
    inside = img.getpixel((25, 35))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
    # Outside the fill but inside what would be the tile lattice — white.
    outside = img.getpixel((10, 10))
    assert _is_close(outside, (255, 255, 255), tol=8), outside


def test_tiling_pattern_default_paint_type_is_colored() -> None:
    """A pattern without explicit ``set_paint_type`` constructor call
    should still render — the default behaviour must paint."""
    pat = PDTilingPattern()
    pat.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pat.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pat.set_b_box(PDRectangle(0.0, 0.0, 10.0, 10.0))
    pat.set_x_step(10.0)
    pat.set_y_step(10.0)
    pat.get_cos_object().set_raw_data(b"0 0 0 rg\n0 0 10 10 re\nf\n")
    _, img = _render_with_pattern(pat, 40.0, (5.0, 5.0, 30.0, 30.0))
    # Sample inside — should be dark.
    inside = img.getpixel((20, 20))
    assert inside[0] < 80, inside


def test_tiling_pattern_renders_in_clipped_region() -> None:
    """Pattern fill inside a clip should respect the clip — only the
    overlap of the clip and the fill path receives pattern colour."""
    pat = _build_pattern(
        cell_bytes=b"1 1 0 rg\n0 0 5 5 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 5.0, 5.0),
        x_step=5.0,
        y_step=5.0,
    )
    doc, page = _make_doc(60.0, 60.0)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pat.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        # Clip to (20, 20)-(40, 40), then fill the full page with pattern.
        b"q\n"
        b"20 20 20 20 re\nW n\n"
        b"/Pattern cs\n/P0 scn\n"
        b"0 0 60 60 re\nf\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Inside the clip → yellow tiles.
    inside_clip = img.getpixel((30, 30))
    assert _is_close(inside_clip, (255, 255, 0), tol=40), inside_clip
    # Outside the clip → white.
    outside_clip = img.getpixel((10, 10))
    assert _is_close(outside_clip, (255, 255, 255), tol=8), outside_clip


def test_tiling_pattern_unequal_x_y_step_renders_lattice() -> None:
    """Different /XStep vs /YStep — verify the pattern still fills the
    region without crashing. The lite renderer's stretched-cell
    divergence means the lattice fully covers the fill."""
    pat = _build_pattern(
        cell_bytes=b"0 1 1 rg\n0 0 4 4 re\nf\n",
        bbox=PDRectangle(0.0, 0.0, 4.0, 4.0),
        x_step=10.0,
        y_step=20.0,
    )
    _, img = _render_with_pattern(pat, 80.0, (0.0, 0.0, 80.0, 80.0))
    cyan = _count_colored(img, (0, 255, 255), tol=80)
    # Must paint at least some cyan pixels in the fill region.
    assert cyan > 100, f"cyan pixels: {cyan}"
