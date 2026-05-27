"""Live PDFBox differential parity for the page-box accessors AND the
crop-box / rotate render geometry.

Two complementary surfaces are exercised against the same Apache PDFBox
3.0.7 oracle (``oracle/probes/PageBoxRenderProbe.java``):

* **accessor parity** (``read`` mode, exact match) — ``getMediaBox`` /
  ``getCropBox`` / ``getBleedBox`` / ``getTrimBox`` / ``getArtBox`` /
  ``getRotation``. The high-value branch is the *absent-box default*:
  ArtBox/TrimBox/BleedBox each fall back to the (already-resolved) CropBox,
  and the CropBox itself falls back to the MediaBox. A page that carries an
  explicit value for every box plus one with none of the optional boxes
  pins both the explicit-value and the default path.

* **render geometry** (``render`` mode, dims exact + 16x16 grid within
  MAD<6 / MAXDIFF<60) — upstream ``PDFRenderer.renderImage`` rasterises to
  the *crop* box: the rendered image spans the crop window (not the media
  box), a non-zero-origin crop offsets the painted content, and ``/Rotate``
  swaps the crop (not media) width/height and compounds with the crop. The
  fixtures put content in media-space that only partially overlaps a
  non-zero-origin crop window so a "render the whole media box" or a
  "don't offset the crop" regression diverges grossly.

Fixtures are built programmatically so we control the exact COS layout.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_CROP_BOX = COSName.get_pdf_name("CropBox")
_BLEED_BOX = COSName.get_pdf_name("BleedBox")
_TRIM_BOX = COSName.get_pdf_name("TrimBox")
_ART_BOX = COSName.get_pdf_name("ArtBox")
_ROTATE = COSName.get_pdf_name("Rotate")

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60


def _arr(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    a = COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])
    a.set_direct(True)
    return a


def _save(doc: PDDocument, path: Path) -> None:
    buf = io.BytesIO()
    try:
        doc.save(buf)
    finally:
        doc.close()
    path.write_bytes(buf.getvalue())


def _build_all_boxes(path: Path) -> None:
    """Page with a distinct MediaBox, a smaller non-zero-origin CropBox, and
    distinct Art/Trim/Bleed boxes — exercises the explicit-value accessor."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    cos = page.get_cos_object()
    cos.set_item(_CROP_BOX, _arr(50.0, 60.0, 562.0, 732.0))
    cos.set_item(_BLEED_BOX, _arr(40.0, 50.0, 572.0, 742.0))
    cos.set_item(_TRIM_BOX, _arr(70.0, 80.0, 542.0, 712.0))
    cos.set_item(_ART_BOX, _arr(90.0, 100.0, 522.0, 692.0))
    doc.add_page(page)
    _save(doc, path)


def _build_crop_default(path: Path) -> None:
    """Page with a non-zero-origin CropBox but NO Art/Trim/Bleed — every
    absent optional box must default to the resolved CropBox; the CropBox
    itself stays as written (inside media)."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 500.0, 700.0))
    page.get_cos_object().set_item(_CROP_BOX, _arr(100.0, 120.0, 400.0, 600.0))
    doc.add_page(page)
    _save(doc, path)


def _draw_content(doc: PDDocument, page: PDPage) -> None:
    """Two filled rects in media space that straddle a non-zero-origin crop
    window so cropping + offsetting are both observable."""
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color_gray(0.15)
    cs.add_rect(120.0, 120.0, 110.0, 90.0)
    cs.fill()
    cs.set_non_stroking_color_gray(0.55)
    cs.add_rect(300.0, 220.0, 100.0, 130.0)
    cs.fill()
    cs.close()


def _build_render_crop(path: Path) -> None:
    """Non-zero-origin CropBox + content — render must crop to the window
    and offset the painted content by the crop origin."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 500.0, 400.0))
    doc.add_page(page)
    _draw_content(doc, page)
    page.get_cos_object().set_item(_CROP_BOX, _arr(100.0, 100.0, 450.0, 380.0))
    _save(doc, path)


def _build_render_rotate_crop(path: Path) -> None:
    """/Rotate 90 + a non-square non-zero-origin CropBox — rotate and crop
    must compound (rendered dims = swapped crop width/height)."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 500.0, 400.0))
    doc.add_page(page)
    _draw_content(doc, page)
    page.get_cos_object().set_item(_CROP_BOX, _arr(80.0, 80.0, 420.0, 330.0))
    page.get_cos_object().set_item(_ROTATE, COSInteger.get(90))
    _save(doc, path)


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageBoxRenderProbe.fmt``."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: PDRectangle) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"
    )


def _py_read(fixture: Path, page_index: int) -> str:
    doc = PDDocument.load(fixture)
    try:
        page = doc.get_page(page_index)
        return (
            f"media {_box(page.get_media_box())} "
            f"crop {_box(page.get_crop_box())} "
            f"bleed {_box(page.get_bleed_box())} "
            f"trim {_box(page.get_trim_box())} "
            f"art {_box(page.get_art_box())} "
            f"rot {page.get_rotation()}"
        ) + "\n"
    finally:
        doc.close()


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


def _oracle_render(fixture: Path, page: int) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text(
        "PageBoxRenderProbe", "render", str(fixture), str(page)
    ).splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


_READ_BUILDERS = {
    "all_boxes": _build_all_boxes,
    "crop_default": _build_crop_default,
}

_RENDER_BUILDERS = {
    "crop_offset": _build_render_crop,
    "rotate_crop": _build_render_rotate_crop,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_READ_BUILDERS), ids=list(_READ_BUILDERS))
def test_page_box_accessors_match_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _READ_BUILDERS[label](fixture)
    java = run_probe_text("PageBoxRenderProbe", "read", str(fixture), "0")
    py = _py_read(fixture, 0)
    assert py == java, (
        f"{label}: page boxes diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_RENDER_BUILDERS), ids=list(_RENDER_BUILDERS))
def test_page_box_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _RENDER_BUILDERS[label](fixture)
    (java_w, java_h), java_grid = _oracle_render(fixture, 0)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # Exact crop-box pixel dimensions — a mismatch means the render sized to
    # the wrong box or mis-swapped the rotate, a real geometry bug not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — crop/rotate render geometry diverges"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )
