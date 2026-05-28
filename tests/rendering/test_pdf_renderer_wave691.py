from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState, _to_float


def _make_doc(
    width: float = 4.0,
    height: float = 4.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (4, 4),
) -> tuple[PDDocument, PDFRenderer]:
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


class _Box:
    def get_width(self) -> float:
        return 1.0

    def get_height(self) -> float:
        return 1.0

    def get_lower_left_x(self) -> float:
        return 0.0

    def get_lower_left_y(self) -> float:
        return 0.0


def test_to_float_and_rgb_even_odd_fill_fallback_paths() -> None:
    doc, renderer = _prepared_renderer(size=(3, 3))
    try:
        assert _to_float(object()) == 0.0  # noqa: SLF001

        renderer._gs.fill_rgb = (90, 30, 10)  # noqa: SLF001
        renderer._subpaths = [  # noqa: SLF001
            [
                ("M", 0.0, 0.0),
                ("L", 2.0, 0.0),
                ("L", 2.0, 2.0),
                ("Z",),
            ],
        ]

        renderer._fill_even_odd_via_pil()  # noqa: SLF001
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (90, 30, 10)  # noqa: SLF001
    finally:
        doc.close()


def test_pending_clip_skips_degenerate_even_odd_and_nonzero_paths() -> None:
    doc, renderer = _prepared_renderer(size=(3, 3))
    try:
        renderer._subpaths = [[("M", 0.0, 0.0), ("L", 1.0, 0.0)]]  # noqa: SLF001
        renderer._pending_clip = "W*"  # noqa: SLF001

        renderer._apply_pending_clip(default_even_odd=True)  # noqa: SLF001
        assert renderer._gs.clip_mask is not None  # noqa: SLF001
        assert renderer._gs.clip_mask.getbbox() is None  # noqa: SLF001

        renderer._gs.clip_mask = None  # noqa: SLF001
        renderer._subpaths = [[("M", 0.0, 0.0), ("L", 1.0, 0.0)]]  # noqa: SLF001
        renderer._pending_clip = "W"  # noqa: SLF001

        renderer._apply_pending_clip(default_even_odd=False)  # noqa: SLF001
        assert renderer._gs.clip_mask is not None  # noqa: SLF001
        assert renderer._gs.clip_mask.getbbox() is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_tiling_cell_restores_state_when_resources_lookup_fails(
    monkeypatch: Any,
) -> None:
    class _Pattern:
        def __init__(self) -> None:
            self.stream = COSStream()
            self.stream.set_raw_data(b"q\n")

        def get_cos_object(self) -> COSStream:
            return self.stream

        def get_resources(self) -> object:
            raise RuntimeError("resources unavailable")

    doc, renderer = _prepared_renderer()
    try:
        original_resources = object()
        renderer._resources = original_resources  # noqa: SLF001
        monkeypatch.setattr(renderer, "_process_form_bytes", lambda _data: None)

        tile = renderer._render_tiling_cell(  # noqa: SLF001
            _Pattern(),
            bbox=_Box(),
            tile_size=(2, 2),
        )

        assert tile is not None
        assert tile.size == (2, 2)
        assert renderer._resources is original_resources  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_shading_and_tiling_noops_preserve_canvas(monkeypatch: Any) -> None:
    class _Pattern:
        def get_b_box(self) -> _Box:
            return _Box()

        def get_x_step(self) -> float:
            return 1.0

        def get_y_step(self) -> float:
            return 1.0

    doc, renderer = _prepared_renderer(size=(2, 2))
    try:
        before = renderer._image.copy()  # noqa: SLF001
        renderer._paint_tiling_pattern(_Pattern(), region_mask=None)  # noqa: SLF001

        renderer._image = None  # noqa: SLF001
        renderer._paint_shading(object(), region_mask=None)  # noqa: SLF001

        renderer._image = before.copy()  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        monkeypatch.setattr(renderer, "_evaluate_shading_rgb", lambda *_args: None)

        renderer._paint_shading(  # noqa: SLF001
            object(),
            region_mask=Image.new("L", (2, 2), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.tobytes() == before.tobytes()  # noqa: SLF001
    finally:
        doc.close()


def test_do_image_ignores_soft_mask_lookup_failure(monkeypatch: Any) -> None:
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    class _Resources:
        def __init__(self, xobject: PDImageXObject) -> None:
            self.xobject = xobject

        def get_x_object(self, _name: COSName) -> PDImageXObject:
            return self.xobject

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        image_xobject = PDImageXObject(COSStream())
        renderer._resources = _Resources(image_xobject)  # noqa: SLF001
        monkeypatch.setattr(
            renderer,
            "_decode_image_xobject",
            lambda _xobject: Image.new("RGB", (1, 1), (10, 20, 30)),
        )
        monkeypatch.setattr(
            image_xobject,
            "get_soft_mask",
            lambda: (_ for _ in ()).throw(RuntimeError("bad smask")),
        )

        pasted: list[Image.Image] = []
        # _paste_image grew an ``interpolate`` kwarg (wave 1446 inline + wave
        # 1447 XObject Do wiring), so the monkeypatch must accept it.
        monkeypatch.setattr(
            renderer,
            "_paste_image",
            lambda img, interpolate=True: pasted.append(img),  # noqa: ARG005
        )

        renderer._op_do(None, [COSName.get_pdf_name("Im0")])  # noqa: SLF001

        assert len(pasted) == 1
        assert pasted[0].getpixel((0, 0)) == (10, 20, 30)
    finally:
        _finish(renderer)
        doc.close()
