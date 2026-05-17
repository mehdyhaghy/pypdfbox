from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer as renderer_module
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 5.0, height: float = 5.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (5, 5)) -> tuple[PDDocument, PDFRenderer]:
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


def test_process_operator_logs_and_swallows_handler_os_error(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    def _raise_os_error(
        _renderer: PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise OSError("synthetic stream failure")

    doc, renderer = _prepared_renderer()
    original = renderer_module._DISPATCH.get("W591")  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setitem(renderer_module._DISPATCH, "W591", _raise_os_error)  # noqa: SLF001

        renderer.process_operator("W591", [])

        assert "dropping operator W591: synthetic stream failure" in caplog.text
    finally:
        if original is None:
            renderer_module._DISPATCH.pop("W591", None)  # noqa: SLF001
        else:
            monkeypatch.setitem(renderer_module._DISPATCH, "W591", original)  # noqa: SLF001
        _finish(renderer)
        doc.close()


def test_pattern_fill_with_stroke_and_clip_routes_stroke_through_clip(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    calls: list[tuple[str, bool, bool, bool]] = []
    try:
        renderer._gs.fill_pattern = object()  # noqa: SLF001
        renderer._gs.clip_mask = Image.new("L", (5, 5), 255)  # noqa: SLF001
        renderer._subpaths = [  # noqa: SLF001
            [("M", 1.0, 1.0), ("L", 4.0, 1.0), ("L", 4.0, 4.0), ("Z",)]
        ]
        renderer._current_subpath = renderer._subpaths[0]  # noqa: SLF001

        def _pattern_fill(*, even_odd: bool) -> None:
            calls.append(("pattern", False, True, even_odd))

        def _through_clip(
            *,
            stroke: bool,
            fill: bool,
            even_odd: bool,
            clip_mask: Image.Image,
        ) -> None:
            assert clip_mask is renderer._gs.clip_mask  # noqa: SLF001
            calls.append(("clip", stroke, fill, even_odd))

        monkeypatch.setattr(renderer, "_paint_pattern_fill", _pattern_fill)
        monkeypatch.setattr(renderer, "_paint_through_clip", _through_clip)

        renderer._paint(stroke=True, fill=True, even_odd=True)  # noqa: SLF001

        assert calls == [
            ("pattern", False, True, True),
            ("clip", True, False, False),
        ]
        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_show_inline_image_logs_legacy_decode_failure_and_skips_paste(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _InlineImage:
        def to_pil_image(self) -> None:
            return None

        def get_cos_object(self) -> COSDictionary:
            raise RuntimeError("params boom")

        def get_stream(self) -> bytes:
            return b""

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setattr(
            renderer,
            "_paste_image",
            lambda _image: (_ for _ in ()).throw(AssertionError("pasted")),
        )

        renderer.show_inline_image(_InlineImage())

        assert "cannot decode inline image: params boom" in caplog.text
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()

