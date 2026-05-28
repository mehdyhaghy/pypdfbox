from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 8.0, height: float = 8.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (8, 8)) -> tuple[PDDocument, PDFRenderer]:
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


def test_pattern_color_operators_resolve_trailing_name_after_tints() -> None:
    class _Resources:
        def __init__(self) -> None:
            self.names: list[str] = []

        def get_pattern(self, name: COSName) -> object:
            self.names.append(name.name)
            return patterns[name.name]

    fill_pattern = object()
    stroke_pattern = object()
    patterns = {"PFill": fill_pattern, "PStroke": stroke_pattern}
    doc, renderer = _prepared_renderer()
    try:
        renderer._resources = _Resources()  # noqa: SLF001

        renderer.process_operator(
            "scn",
            [COSFloat(0.25), COSName.get_pdf_name("PFill")],
        )
        renderer.process_operator(
            "SCN",
            [COSFloat(0.5), COSFloat(0.75), COSName.get_pdf_name("PStroke")],
        )

        assert renderer._gs.fill_pattern is fill_pattern  # noqa: SLF001
        assert renderer._gs.stroke_pattern is stroke_pattern  # noqa: SLF001
        assert renderer._resources.names == ["PFill", "PStroke"]  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_shading_fill_dispatches_resolved_resource(monkeypatch: Any) -> None:
    class _Resources:
        def get_shading(self, name: COSName) -> object:
            assert name.name == "Shade1"
            return shading

    shading = object()
    calls: list[tuple[object, object | None]] = []
    doc, renderer = _prepared_renderer()
    try:
        renderer._resources = _Resources()  # noqa: SLF001

        def _paint_shading(shading_arg: object, *, region_mask: object | None) -> None:
            calls.append((shading_arg, region_mask))

        monkeypatch.setattr(renderer, "_paint_shading", _paint_shading)

        renderer.process_operator("sh", [COSName.get_pdf_name("Shade1")])

        assert calls == [(shading, None)]
    finally:
        _finish(renderer)
        doc.close()


def test_extgstate_normal_blend_resets_mode_and_preserves_missing_alpha() -> None:
    class _ExtGState:
        def get_cos_object(self) -> COSDictionary:
            # Carries an explicit /BM /Normal — upstream applies the blend
            # mode only when the dict contains /BM, so an explicit Normal
            # resets a prior non-Normal mode (a /BM-absent ExtGState would
            # leave it unchanged).
            d = COSDictionary()
            d.set_item(COSName.get_pdf_name("BM"), COSName.get_pdf_name("Normal"))
            return d

        def get_blend_mode(self) -> BlendMode:
            return BlendMode.NORMAL

        def get_soft_mask_typed(self) -> object:
            return soft_mask

        def get_stroking_alpha_constant(self) -> None:
            return None

        def get_non_stroking_alpha_constant(self) -> None:
            return None

    class _Resources:
        def get_ext_gstate(self, name: COSName) -> _ExtGState:
            assert name.name == "GS1"
            return _ExtGState()

    soft_mask = object()
    doc, renderer = _prepared_renderer()
    try:
        renderer._resources = _Resources()  # noqa: SLF001
        renderer._gs.blend_mode = BlendMode.MULTIPLY  # noqa: SLF001
        renderer._gs.stroke_alpha = 0.25  # noqa: SLF001
        renderer._gs.fill_alpha = 0.75  # noqa: SLF001

        renderer.process_operator("gs", [COSName.get_pdf_name("GS1")])

        assert renderer._gs.blend_mode is None  # noqa: SLF001
        assert renderer._gs.soft_mask is soft_mask  # noqa: SLF001
        assert renderer._gs.stroke_alpha == 0.25  # noqa: SLF001
        assert renderer._gs.fill_alpha == 0.75  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_resolve_font_does_not_cache_factory_miss(monkeypatch: Any) -> None:
    class _Resources:
        def __init__(self) -> None:
            self.calls = 0

        def get_font(self, _name: COSName) -> COSDictionary:
            self.calls += 1
            return COSDictionary()

    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

    resources = _Resources()
    doc, renderer = _prepared_renderer()
    try:
        renderer._resources = resources  # noqa: SLF001
        monkeypatch.setattr(PDFontFactory, "create_font", lambda _font_dict: None)
        font_name = COSName.get_pdf_name("FNone")

        assert renderer._resolve_font(font_name) is None  # noqa: SLF001
        assert renderer._resolve_font(font_name) is None  # noqa: SLF001
        assert resources.calls == 2
    finally:
        _finish(renderer)
        doc.close()
