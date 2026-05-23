from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _AggdrawPathPen, _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer() -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._draw = object()  # type: ignore[assignment]  # noqa: SLF001
    renderer._image = object()  # type: ignore[assignment]  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    return doc, renderer


def test_inline_image_operator_ignores_missing_parameters_or_data(
    monkeypatch: Any,
) -> None:
    class _InlineOperator:
        def __init__(self, data: bytes | None) -> None:
            self._data = data

        def get_image_parameters(self) -> None:
            return None

        def get_image_data(self) -> bytes | None:
            return self._data

    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(
            renderer,
            "show_inline_image",
            lambda _image: (_ for _ in ()).throw(AssertionError("shown")),
        )

        renderer._op_inline_image(_InlineOperator(b"abc"), [])  # noqa: SLF001
        renderer._op_inline_image(_InlineOperator(None), [])  # noqa: SLF001
    finally:
        doc.close()


def test_type1_command_builder_returns_none_for_move_only_path() -> None:
    path = PDFRenderer._build_aggdraw_path_from_commands(  # noqa: SLF001
        [("moveto", 10.0, 20.0)],
        scale=0.5,
    )

    assert path is None


def test_aggdraw_pen_ignores_quadratic_without_current_point() -> None:
    pen = _AggdrawPathPen(scale=1.0)

    pen.q_curve_to((1.0, 1.0), (2.0, 2.0))

    assert pen.has_segments is False


def test_aggdraw_pen_single_quadratic_marks_segment_after_move() -> None:
    pen = _AggdrawPathPen(scale=1.0)

    pen.move_to((0.0, 0.0))
    pen.q_curve_to((2.0, 2.0))

    assert pen.has_segments is True
    assert pen._last == (2.0, 2.0)  # noqa: SLF001
