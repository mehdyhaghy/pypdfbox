from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 4.0, height: float = 4.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (4, 4)) -> tuple[PDDocument, PDFRenderer]:
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


def _soft_mask(subtype: str, stream_data: bytes) -> PDSoftMask:
    stream = COSStream()
    stream.set_raw_data(stream_data)
    mask = PDSoftMask()
    mask.set_subtype(COSName.get_pdf_name(subtype))
    mask.set_group(stream)
    return mask


def test_render_soft_mask_alpha_uses_group_paint_alpha_and_restores_state() -> None:
    doc, renderer = _prepared_renderer()
    original_resources = object()
    renderer._resources = original_resources  # noqa: SLF001
    renderer._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001
    try:
        mask = _soft_mask("Alpha", b"0 0 0 rg\n0 0 2 2 re\nf\n")

        alpha = renderer._render_soft_mask_alpha(mask, (4, 4))  # noqa: SLF001

        assert alpha is not None
        assert alpha.mode == "L"
        assert alpha.getpixel((1, 1)) == 255
        assert alpha.getpixel((3, 3)) == 0
        assert renderer._image.size == (4, 4)  # noqa: SLF001
        assert renderer._resources is original_resources  # noqa: SLF001
        assert renderer._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_soft_mask_luminosity_uses_backdrop_colour_for_empty_group() -> None:
    doc, renderer = _prepared_renderer((2, 2))
    try:
        mask = _soft_mask("Luminosity", b"")
        backdrop = COSArray()
        backdrop.add(COSFloat(0.5))
        mask.set_backdrop_color(backdrop)

        alpha = renderer._render_soft_mask_alpha(mask, (2, 2))  # noqa: SLF001

        assert alpha is not None
        assert {alpha.getpixel((x, y)) for x in range(2) for y in range(2)} == {
            128
        }
    finally:
        _finish(renderer)
        doc.close()
