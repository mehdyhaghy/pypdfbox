from __future__ import annotations

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 12.0, height: float = 12.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (12, 12)) -> tuple[PDDocument, PDFRenderer]:
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


def test_paste_image_with_blend_preserves_rgba_canvas_mode() -> None:
    doc, renderer = _prepared_renderer((3, 3))
    try:
        renderer._image = Image.new("RGBA", (3, 3), (0, 255, 0, 128))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001

        renderer._paste_image_with_blend(  # noqa: SLF001
            Image.new("RGB", (1, 1), (255, 0, 0)),
            None,
            (1, 1, 1, 1),
            None,
            BlendMode.MULTIPLY,
        )

        assert renderer._image.mode == "RGBA"  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (0, 0, 0, 255)  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (0, 255, 0, 128)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_apply_smask_resizes_luminance_mask_to_source_dimensions() -> None:
    class _SmallMask:
        def to_pil_image(self) -> Image.Image:
            return Image.new("L", (1, 1), 64)

    doc, renderer = _prepared_renderer()
    source = Image.new("RGB", (2, 2), (10, 20, 30))
    try:
        rgba = renderer._apply_smask(source, _SmallMask())  # noqa: SLF001

        assert rgba.mode == "RGBA"
        assert rgba.size == (2, 2)
        assert {rgba.getpixel((x, y))[3] for x in range(2) for y in range(2)} == {64}
    finally:
        _finish(renderer)
        doc.close()


def test_draw_glyph_upgrades_missing_width_with_substitute_metrics(
    monkeypatch: object,
) -> None:
    class _Font:
        def get_glyph_width(self, _code: int) -> float:
            return 0.0

    class _Substitute:
        def get_width(self, glyph_name: str) -> float:
            assert glyph_name == "A"
            return 700.0

    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.text_font_size = 10.0  # noqa: SLF001
        monkeypatch.setattr(  # type: ignore[attr-defined]
            renderer,
            "_resolve_font_program",
            lambda _font: _Substitute(),
        )

        advance = renderer._draw_glyph(_Font(), 65, None, None)  # noqa: SLF001

        assert advance == 700.0
    finally:
        _finish(renderer)
        doc.close()


def test_fill_aggdraw_path_composites_glyph_path_through_clip_mask() -> None:
    doc, renderer = _prepared_renderer((8, 8))
    try:
        clip = Image.new("L", (8, 8), 0)
        clip.paste(255, (0, 0, 4, 8))
        renderer._gs.clip_mask = clip  # noqa: SLF001

        path = aggdraw.Path()
        path.moveto(0.0, 0.0)
        path.lineto(8.0, 0.0)
        path.lineto(8.0, 8.0)
        path.lineto(0.0, 8.0)
        path.close()

        renderer._fill_aggdraw_path(  # noqa: SLF001
            path,
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            (255, 0, 0),
        )
        _finish(renderer)

        assert renderer._image.getpixel((2, 4)) == (255, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((6, 4)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
