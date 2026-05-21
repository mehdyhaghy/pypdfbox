from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSStream
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


def test_paste_image_multiplies_source_alpha_with_clip_mask() -> None:
    doc, renderer = _prepared_renderer((5, 5))
    try:
        clip = Image.new("L", (5, 5), 0)
        clip.paste(255, (2, 2, 3, 3))
        renderer._gs.clip_mask = clip  # noqa: SLF001
        renderer._gs.ctm = (1.0, 0.0, 0.0, 1.0, 2.0, 2.0)  # noqa: SLF001

        source = Image.new("RGBA", (1, 1), (255, 0, 0, 128))
        renderer._paste_image(source)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((1, 2)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 127, 127)  # noqa: SLF001
        assert renderer._image.getpixel((3, 2)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_render_form_xobject_restores_resources_when_stream_is_not_cosstream() -> None:
    class _Form:
        def __init__(self) -> None:
            self.resources = object()

        def get_matrix(self) -> list[float]:
            return [1.0, 0.0, 0.0, 1.0, 1.0, 0.0]

        def get_bbox(self) -> None:
            return None

        def get_resources(self) -> object:
            return self.resources

        def get_cos_object(self) -> object:
            return object()

    doc, renderer = _prepared_renderer()
    previous_resources = object()
    try:
        renderer._resources = previous_resources  # noqa: SLF001
        renderer._gs.ctm = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # noqa: SLF001

        renderer._render_form_xobject(_Form())  # noqa: SLF001

        assert renderer._resources is previous_resources  # noqa: SLF001
        assert renderer._gs.ctm == (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_tiling_cell_restores_resources_when_pattern_has_none() -> None:
    class _BBox:
        def get_width(self) -> float:
            return 1.0

        def get_height(self) -> float:
            return 1.0

        def get_lower_left_x(self) -> float:
            return 0.0

        def get_lower_left_y(self) -> float:
            return 0.0

    class _Pattern:
        def get_cos_object(self) -> COSStream:
            stream = COSStream()
            stream.set_raw_data(b"")
            return stream

        def get_resources(self) -> None:
            return None

    doc, renderer = _prepared_renderer()
    previous_resources = object()
    try:
        renderer._resources = previous_resources  # noqa: SLF001

        tile = renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(),
            bbox=_BBox(),
            tile_size=(2, 2),
        )

        assert tile is not None
        assert tile.size == (2, 2)
        # Wave 1373: empty content streams produce a transparent RGBA
        # tile (was opaque-white RGB) so /XStep × /YStep gaps show the
        # page background.
        assert tile.mode == "RGBA"
        assert tile.getpixel((0, 0)) == (0, 0, 0, 0)
        assert renderer._resources is previous_resources  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_fill_aggdraw_path_with_clip_refreshes_draw_and_preserves_outside() -> None:
    doc, renderer = _prepared_renderer((4, 4))
    try:
        clip = Image.new("L", (4, 4), 0)
        clip.paste(255, (1, 1, 3, 3))
        renderer._gs.clip_mask = clip  # noqa: SLF001

        path = aggdraw.Path()
        path.moveto(0.0, 0.0)
        path.lineto(4.0, 0.0)
        path.lineto(4.0, 4.0)
        path.lineto(0.0, 4.0)
        path.close()

        renderer._fill_aggdraw_path(  # noqa: SLF001
            path,
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
            (0, 0, 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (0, 0, 255)  # noqa: SLF001
        assert renderer._draw is not None  # noqa: SLF001
    finally:
        doc.close()
