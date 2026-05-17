from __future__ import annotations

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (6, 6)) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


def test_paste_image_expands_degenerate_ctm_bbox_to_single_pixel() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.ctm = (0.0, 0.0, 0.0, 0.0, 3.0, 2.0)  # noqa: SLF001

        renderer._paste_image(Image.new("RGB", (2, 2), (10, 20, 30)))  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((3, 2)) == (10, 20, 30)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_blend_channel_unknown_mode_preserves_backdrop_channel() -> None:
    backdrop = Image.new("L", (2, 1))
    backdrop.putpixel((0, 0), 40)
    backdrop.putpixel((1, 0), 180)
    source = Image.new("L", (2, 1), 250)

    blended = PDFRenderer._blend_channel(backdrop, source, "Unknown")  # noqa: SLF001

    assert blended.getpixel((0, 0)) == 40
    assert blended.getpixel((1, 0)) == 180


def test_hsl_set_sat_handles_repeated_minimum_components() -> None:
    assert PDFRenderer._hsl_set_sat(0.2, 0.8, 0.2, 0.5) == (0.0, 0.5, 0.0)  # noqa: SLF001
