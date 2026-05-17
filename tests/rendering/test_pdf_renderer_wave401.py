from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import (
    _GState,
    _matmul,
    _to_float,
    _to_pil_affine,
)


def _make_doc(width: float = 20.0, height: float = 20.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (20, 20)) -> tuple[PDDocument, PDFRenderer]:
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


def test_matrix_helpers_and_graphics_state_clone_preserve_values() -> None:
    original = _GState(
        ctm=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
        stroke_rgb=(7, 8, 9),
        fill_rgb=(10, 11, 12),
        line_width=3.5,
    )
    original.text_font = object()
    original.fill_pattern = object()
    original.clip_mask = Image.new("L", (2, 2), 255)
    clone = original.clone()

    assert clone is not original
    assert clone.ctm == original.ctm
    assert clone.stroke_rgb == (7, 8, 9)
    assert clone.fill_pattern is original.fill_pattern
    assert clone.clip_mask is original.clip_mask

    clone.stroke_rgb = (1, 2, 3)
    clone.text_matrix = (9.0, 0.0, 0.0, 9.0, 0.0, 0.0)
    assert original.stroke_rgb == (7, 8, 9)
    assert original.text_matrix == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    assert _matmul(
        (2.0, 0.0, 0.0, 2.0, 10.0, 20.0),
        (1.0, 0.0, 0.0, 1.0, 3.0, 4.0),
    ) == (2.0, 0.0, 0.0, 2.0, 13.0, 24.0)
    assert _to_pil_affine((1.0, 2.0, 3.0, 4.0, 5.0, 6.0)) == (
        1.0,
        3.0,
        5.0,
        2.0,
        4.0,
        6.0,
    )
    assert _to_float(COSFloat(1.25)) == 1.25
    assert _to_float(COSName.get_pdf_name("NotANumber")) == 0.0
    assert _to_float(None) == 0.0


def test_even_odd_clip_intersects_existing_clip_and_clears_pending() -> None:
    doc, renderer = _prepared_renderer()
    try:
        existing = Image.new("L", (20, 20), 0)
        existing.paste(255, (0, 0, 10, 20))
        renderer._gs.clip_mask = existing  # noqa: SLF001

        renderer.process_operator("re", [COSFloat(0), COSFloat(0), COSFloat(20), COSFloat(20)])
        renderer.process_operator("re", [COSFloat(5), COSFloat(5), COSFloat(10), COSFloat(10)])
        renderer.process_operator("W*", [])
        renderer._apply_pending_clip(default_even_odd=False)  # noqa: SLF001

        clip = renderer._gs.clip_mask  # noqa: SLF001
        assert clip is not None
        assert renderer._pending_clip is None  # noqa: SLF001
        assert clip.getpixel((2, 2)) == 255
        assert clip.getpixel((8, 8)) == 0
        assert clip.getpixel((18, 2)) == 0
    finally:
        _finish(renderer)
        doc.close()


def test_empty_path_paint_consumes_pending_clip_without_changing_canvas() -> None:
    doc, renderer = _prepared_renderer()
    try:
        before = renderer._image.copy()  # noqa: SLF001
        renderer.process_operator("W", [])
        renderer._paint(stroke=False, fill=True, even_odd=False)  # noqa: SLF001

        assert renderer._pending_clip is None  # noqa: SLF001
        assert renderer._gs.clip_mask is None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_fill_mask_with_rgb_preserves_rgba_canvas_alpha() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._image = Image.new("RGBA", (4, 4), (255, 255, 255, 0))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        mask = Image.new("L", (4, 4), 0)
        mask.putpixel((1, 1), 255)

        renderer._fill_mask_with_rgb(mask, (12, 34, 56))  # noqa: SLF001

        assert renderer._image.getpixel((1, 1)) == (12, 34, 56, 255)  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255, 0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_paint_through_clip_strokes_only_inside_clip_region() -> None:
    doc, renderer = _prepared_renderer()
    try:
        clip = Image.new("L", (20, 20), 0)
        clip.paste(255, (0, 0, 10, 20))
        renderer._gs.clip_mask = clip  # noqa: SLF001
        renderer._gs.stroke_rgb = (255, 0, 0)  # noqa: SLF001
        renderer._gs.line_width = 2.0  # noqa: SLF001
        renderer.process_operator("m", [COSFloat(2), COSFloat(10)])
        renderer.process_operator("l", [COSFloat(18), COSFloat(10)])
        renderer.process_operator("S", [])
        _finish(renderer)

        assert renderer._image.getpixel((5, 10))[0] > 200  # noqa: SLF001
        assert renderer._image.getpixel((15, 10)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
