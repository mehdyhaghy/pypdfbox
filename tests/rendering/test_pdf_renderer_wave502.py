from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


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
    renderer._image = Image.new("RGB", size, (255, 255, 255))
    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._gs_stack = [_GState()]
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw
    if draw is not None:
        draw.flush()


def _float_array(values: list[float]) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


def test_build_path_mask_even_odd_flattens_curves_and_xors_overlap() -> None:
    doc, renderer = _prepared_renderer((8, 8))
    try:
        renderer._subpaths = [
            [
                ("M", 1.0, 1.0),
                ("C", 1.0, 4.0, 4.0, 7.0, 7.0, 7.0),
                ("L", 7.0, 1.0),
                ("Z",),
            ],
            [
                ("M", 3.0, 3.0),
                ("L", 7.0, 3.0),
                ("L", 7.0, 7.0),
                ("Z",),
            ],
        ]

        mask = renderer._build_path_mask(even_odd=True)

        assert mask is not None
        # Wave 1373: skia rasterises the mask with sub-pixel AA, so edge
        # pixels carry intermediate alpha. Interior pixels are still
        # fully covered (>= 128) and even-odd hole interior pixels stay
        # well below 128.
        assert mask.getpixel((2, 4)) >= 128
        # Pixel (6, 4) sits inside the even-odd hole (covered by both
        # subpaths so they cancel) and away from edges that would carry
        # AA partial coverage.
        assert mask.getpixel((6, 4)) <= 32
    finally:
        _finish(renderer)
        doc.close()


def test_unknown_pattern_fill_falls_back_to_solid_masked_fill() -> None:
    doc, renderer = _prepared_renderer((5, 5))
    try:
        renderer._gs.fill_pattern = object()
        renderer._gs.fill_rgb = (12, 34, 56)
        renderer._subpaths = [[("M", 1.0, 1.0), ("L", 4.0, 1.0), ("L", 4.0, 4.0), ("Z",)]]

        renderer._paint_pattern_fill(even_odd=False)
        _finish(renderer)

        # Wave 1373: skia AA blends edge pixels with the background;
        # sample a pixel safely inside the triangle to avoid the
        # hypotenuse-edge half-coverage region.
        assert renderer._image.getpixel((3, 2)) == (12, 34, 56)
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)
    finally:
        doc.close()


def test_tiling_pattern_pastes_repeated_tile_through_region_mask(monkeypatch: Any) -> None:
    class _Pattern:
        def get_b_box(self) -> PDRectangle:
            return PDRectangle(0.0, 0.0, 2.0, 2.0)

        def get_x_step(self) -> float:
            return 2.0

        def get_y_step(self) -> float:
            return 2.0

    doc, renderer = _prepared_renderer((5, 5))
    mask = Image.new("L", (5, 5), 0)
    mask.paste(255, (1, 1, 5, 5))
    try:
        tile = Image.new("RGB", (2, 2), (0, 0, 255))
        tile.putpixel((1, 1), (255, 0, 0))
        monkeypatch.setattr(renderer, "_render_tiling_cell", lambda *args, **kwargs: tile)

        renderer._paint_tiling_pattern(_Pattern(), region_mask=mask)
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)
        assert renderer._image.getpixel((2, 2)) == (0, 0, 255)
        assert renderer._image.getpixel((3, 3)) == (255, 0, 0)
    finally:
        doc.close()


def test_function_shading_cos_array_uses_zero_for_bad_subfunctions(
    monkeypatch: Any,
) -> None:
    class _Function:
        def __init__(self, value: float, raises: bool = False) -> None:
            self._value = value
            self._raises = raises

        def eval(self, _inputs: list[float]) -> list[float]:
            if self._raises:
                raise RuntimeError("eval boom")
            return [self._value]

    class _Shading:
        def get_domain(self) -> COSArray:
            return _float_array([0.0, 1.0, 0.0, 1.0])

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> COSArray:
            functions = COSArray()
            functions.add(COSDictionary())
            functions.add(COSDictionary())
            functions.add(COSDictionary())
            return functions

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    from pypdfbox.pdmodel.common.function import PDFunction

    created = [_Function(1.0), RuntimeError("create boom"), _Function(0.5, raises=True)]

    def _create(_obj: object) -> _Function:
        item = created.pop(0)
        if isinstance(item, RuntimeError):
            raise item
        return item

    doc, renderer = _prepared_renderer((1, 1))
    try:
        monkeypatch.setattr(PDFunction, "create", staticmethod(_create))

        renderer._paint_function_shading(_Shading(), region_mask=Image.new("L", (1, 1), 255))
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)
    finally:
        doc.close()


def test_soft_mask_alpha_restores_renderer_state_when_group_render_fails(
    monkeypatch: Any,
) -> None:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask

    doc, renderer = _prepared_renderer((2, 2))
    previous_image = renderer._image
    previous_draw = renderer._draw
    previous_resources = object()
    previous_clip = Image.new("L", (2, 2), 128)
    renderer._resources = previous_resources
    renderer._gs.clip_mask = previous_clip
    renderer._subpaths = [[("M", 9.0, 9.0)]]
    renderer._current_subpath = renderer._subpaths[0]
    renderer._pending_clip = "W"
    renderer._knockout_active = True
    renderer._knockout_snapshot = Image.new("RGB", (2, 2), (1, 2, 3))
    renderer._knockout_form_depth = 3

    form = PDFormXObject(COSStream())
    soft_mask = PDSoftMask()
    soft_mask.set_group(form)
    monkeypatch.setattr(
        renderer,
        "_render_form_xobject",
        lambda _form: (_ for _ in ()).throw(RuntimeError("group boom")),
    )
    try:
        assert renderer._render_soft_mask_alpha(soft_mask, (2, 2)) is None
        assert renderer._image is previous_image
        assert renderer._draw is previous_draw
        assert renderer._resources is previous_resources
        assert renderer._gs.clip_mask is previous_clip
        assert renderer._subpaths == [[("M", 9.0, 9.0)]]
        assert renderer._current_subpath is renderer._subpaths[0]
        assert renderer._pending_clip == "W"
        assert renderer._knockout_active is True
        assert renderer._knockout_snapshot is not None
        assert renderer._knockout_form_depth == 3
    finally:
        _finish(renderer)
        doc.close()
