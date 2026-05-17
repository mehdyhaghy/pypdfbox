from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


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


def test_process_operator_accepts_none_operands_and_unknown_ops() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001

        renderer.process_operator("not-real", None)
        renderer.process_operator("g", None)

        assert renderer._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_shading_fill_logs_resource_failure_and_skips_missing_shading(
    caplog: Any,
) -> None:
    class _BrokenResources:
        def get_shading(self, _name: COSName) -> object:
            raise RuntimeError("shade boom")

    class _MissingResources:
        def get_shading(self, _name: COSName) -> None:
            return None

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")

        renderer.process_operator("sh", [COSName.get_pdf_name("S0")])
        renderer._resources = _MissingResources()  # noqa: SLF001
        renderer.process_operator("sh", [COSName.get_pdf_name("S0")])
        renderer._resources = _BrokenResources()  # noqa: SLF001
        renderer.process_operator("sh", [COSName.get_pdf_name("S0")])

        assert "cannot resolve shading S0: shade boom" in caplog.text
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_soft_mask_alpha_restores_state_when_group_render_fails(
    monkeypatch: Any,
    caplog: Any,
) -> None:
    doc, renderer = _prepared_renderer((2, 2))
    mask = PDSoftMask()
    mask.set_subtype(COSName.get_pdf_name("Alpha"))
    stream = COSStream()
    stream.set_raw_data(b"0 0 m\n")
    mask.set_group(stream)
    previous_resources = object()
    previous_subpaths = [[("M", 9.0, 9.0)]]
    previous_image = renderer._image  # noqa: SLF001
    previous_draw = renderer._draw  # noqa: SLF001
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        renderer._resources = previous_resources  # noqa: SLF001
        renderer._subpaths = previous_subpaths  # noqa: SLF001
        renderer._current_subpath = previous_subpaths[0]  # noqa: SLF001
        renderer._pending_clip = "W"  # noqa: SLF001
        renderer._knockout_active = True  # noqa: SLF001
        renderer._knockout_snapshot = Image.new("RGB", (2, 2), (1, 2, 3))  # noqa: SLF001
        renderer._knockout_form_depth = 7  # noqa: SLF001

        def _raise_group(_form: object) -> None:
            assert renderer._gs.soft_mask is None  # noqa: SLF001
            raise RuntimeError("mask render boom")

        monkeypatch.setattr(renderer, "_render_form_xobject", _raise_group)

        assert renderer._render_soft_mask_alpha(mask, (2, 2)) is None  # noqa: SLF001

        assert "soft-mask group render failed: mask render boom" in caplog.text
        assert renderer._image is previous_image  # noqa: SLF001
        assert renderer._draw is previous_draw  # noqa: SLF001
        assert renderer._resources is previous_resources  # noqa: SLF001
        assert renderer._subpaths is previous_subpaths  # noqa: SLF001
        assert renderer._current_subpath is previous_subpaths[0]  # noqa: SLF001
        assert renderer._pending_clip == "W"  # noqa: SLF001
        assert renderer._knockout_active is True  # noqa: SLF001
        assert renderer._knockout_form_depth == 7  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_pending_clip_without_path_clears_pending_marker() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._pending_clip = "W*"  # noqa: SLF001

        renderer.process_operator("n", [])

        assert renderer._pending_clip is None  # noqa: SLF001
        assert renderer._gs.clip_mask is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
