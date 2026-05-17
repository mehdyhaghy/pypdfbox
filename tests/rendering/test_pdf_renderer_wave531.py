from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer as renderer_mod
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


def test_graphics_state_clone_keeps_transparency_and_text_fields() -> None:
    state = _GState()
    fill_pattern = object()
    stroke_pattern = object()
    font = object()
    clip = Image.new("L", (1, 1), 128)
    soft_mask = object()
    blend_mode = object()

    state.ctm = (2.0, 0.0, 0.0, 3.0, 4.0, 5.0)
    state.stroke_rgb = (1, 2, 3)
    state.fill_rgb = (4, 5, 6)
    state.line_width = 7.0
    state.fill_pattern = fill_pattern
    state.stroke_pattern = stroke_pattern
    state.text_font = font
    state.text_font_size = 8.0
    state.text_matrix = (1.0, 0.0, 0.0, 1.0, 9.0, 10.0)
    state.text_line_matrix = (1.0, 0.0, 0.0, 1.0, 11.0, 12.0)
    state.text_charspace = 13.0
    state.text_wordspace = 14.0
    state.text_leading = 15.0
    state.text_rise = 16.0
    state.text_horizontal_scaling = 17.0
    state.clip_mask = clip
    state.blend_mode = blend_mode
    state.soft_mask = soft_mask
    state.stroke_alpha = 0.25
    state.fill_alpha = 0.75

    clone = state.clone()

    assert clone is not state
    assert clone.ctm == state.ctm
    assert clone.stroke_rgb == (1, 2, 3)
    assert clone.fill_rgb == (4, 5, 6)
    assert clone.line_width == 7.0
    assert clone.fill_pattern is fill_pattern
    assert clone.stroke_pattern is stroke_pattern
    assert clone.text_font is font
    assert clone.text_font_size == 8.0
    assert clone.text_matrix == state.text_matrix
    assert clone.text_line_matrix == state.text_line_matrix
    assert clone.text_charspace == 13.0
    assert clone.text_wordspace == 14.0
    assert clone.text_leading == 15.0
    assert clone.text_rise == 16.0
    assert clone.text_horizontal_scaling == 17.0
    assert clone.clip_mask is clip
    assert clone.blend_mode is blend_mode
    assert clone.soft_mask is soft_mask
    assert clone.stroke_alpha == 0.25
    assert clone.fill_alpha == 0.75


def test_save_restore_uses_clone_and_keeps_base_state_on_extra_restore() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001

        renderer.process_operator("q", [])
        renderer._gs.fill_rgb = (200, 0, 0)  # noqa: SLF001
        renderer.process_operator("Q", [])
        renderer.process_operator("Q", [])

        assert len(renderer._gs_stack) == 1  # noqa: SLF001
        assert renderer._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_process_operator_logs_and_swallows_handler_value_error(
    caplog: Any,
) -> None:
    def _raise_value_error(
        _renderer: PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise ValueError("synthetic handler boom")

    doc, renderer = _prepared_renderer()
    original = renderer_mod._DISPATCH.get("W531")  # noqa: SLF001
    renderer_mod._DISPATCH["W531"] = _raise_value_error  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer.process_operator("W531", [])

        assert "dropping operator W531: synthetic handler boom" in caplog.text
    finally:
        if original is None:
            renderer_mod._DISPATCH.pop("W531", None)  # noqa: SLF001
        else:
            renderer_mod._DISPATCH["W531"] = original  # noqa: SLF001
        _finish(renderer)
        doc.close()


def test_do_operator_routes_form_xobjects_by_transparency_group(
    monkeypatch: Any,
) -> None:
    class _Resources:
        def __init__(self, xobject: PDFormXObject) -> None:
            self.xobject = xobject

        def get_x_object(self, name: COSName) -> PDFormXObject:
            assert name.name == "Fm0"
            return self.xobject

    doc, renderer = _prepared_renderer()
    calls: list[str] = []
    form = PDFormXObject(COSStream())
    try:
        renderer._resources = _Resources(form)  # noqa: SLF001
        monkeypatch.setattr(
            renderer,
            "_render_form_xobject",
            lambda _form: calls.append("form"),
        )
        monkeypatch.setattr(
            renderer,
            "_render_transparency_group",
            lambda _form: calls.append("group"),
        )

        renderer.process_operator("Do", [COSName.get_pdf_name("Fm0")])

        group = COSDictionary()
        group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
        form.set_group(group)
        renderer.process_operator("Do", [COSName.get_pdf_name("Fm0")])

        assert calls == ["form", "group"]
    finally:
        _finish(renderer)
        doc.close()
