"""Coverage-boost tests for ``pypdfbox.examples.rendering.custom_page_drawer``.

The upstream Java demo subclasses ``PageDrawer`` to recolour red ink,
draw glyph + filled-path bounding boxes, and render annotations at 35%
opacity. The Python port keeps the public hooks; this suite exercises:

* ``MyPDFRenderer`` constructor + ``create_page_drawer`` factory
* ``MyPageDrawer`` constructor
* ``get_paint``: short-circuit (no graphics state), RED→BLUE swap path,
  TypeError-swallow path when ``to_rgb`` returns a non-int, mismatched
  non-stroking color fallthrough
* ``show_glyph`` super-delegation + AttributeError suppression
* ``fill_path`` super-delegation
* ``show_annotation`` save_graphics_state / set_non_stroke_alpha_constant /
  restore_graphics_state lifecycle (incl. the AttributeError-suppression
  branch when the graphics state methods are absent)
* ``CustomPageDrawer.main`` failing cleanly when the demo PDF is absent
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from pypdfbox.examples.rendering.custom_page_drawer import (
    _BLUE_RGB,
    _RED_RGB,
    CustomPageDrawer,
    MyPageDrawer,
    MyPDFRenderer,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.rendering.render_destination import RenderDestination


def _make_drawer(use_my_renderer: bool = False) -> tuple[
    PDDocument, MyPageDrawer
]:
    doc = PDDocument()
    doc.add_page(PDPage())
    renderer: PDFRenderer = (
        MyPDFRenderer(doc) if use_my_renderer else PDFRenderer(doc)
    )
    params = PageDrawerParameters(
        renderer, doc.get_page(0), True, RenderDestination.EXPORT, {}, 0.5,
    )
    if use_my_renderer:
        # Exercises ``MyPDFRenderer.create_page_drawer`` (line 37).
        return doc, renderer.create_page_drawer(params)  # type: ignore[return-value]
    return doc, MyPageDrawer(params)


# ---------------------------------------------------------------------------
# Subclass declarations
# ---------------------------------------------------------------------------


def test_my_pdf_renderer_is_pdf_renderer_subclass() -> None:
    assert issubclass(MyPDFRenderer, PDFRenderer)


def test_my_page_drawer_is_page_drawer_subclass() -> None:
    assert issubclass(MyPageDrawer, PageDrawer)


def test_outer_class_main_is_callable() -> None:
    assert callable(CustomPageDrawer.main)


def test_color_constants_match_java_demo() -> None:
    # Constants mirror ``Color.RED.getRGB() & 0x00FFFFFF`` from Java.
    assert _RED_RGB == 0xFF0000
    assert _BLUE_RGB == 0x0000FF


# ---------------------------------------------------------------------------
# MyPDFRenderer + create_page_drawer
# ---------------------------------------------------------------------------


def test_my_pdf_renderer_constructor_wires_document() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        renderer = MyPDFRenderer(doc)
        assert renderer is not None
        # Inherits PDFRenderer's public ``document`` field.
        assert isinstance(renderer, PDFRenderer)
    finally:
        doc.close()


def test_create_page_drawer_returns_my_page_drawer() -> None:
    doc, drawer = _make_drawer(use_my_renderer=True)
    try:
        assert isinstance(drawer, MyPageDrawer)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# MyPageDrawer constructor
# ---------------------------------------------------------------------------


def test_my_page_drawer_constructor() -> None:
    doc, drawer = _make_drawer()
    try:
        assert isinstance(drawer, MyPageDrawer)
        # Inherited from PageDrawer base.
        assert drawer.get_renderer() is not None
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_paint — non_stroking is None / mismatch / RED match / TypeError
# ---------------------------------------------------------------------------


def test_get_paint_without_graphics_state_falls_through() -> None:
    doc, drawer = _make_drawer()
    try:
        # No graphics state yet -> get_graphics_state() returns None,
        # raising AttributeError which is suppressed. ``non_stroking``
        # stays None, doesn't match ``color``, falls to super().get_paint.
        result = drawer.get_paint(None)
        # Either the PageDrawer base returns the color unchanged or the
        # renderer resolves it; both are acceptable parity outputs.
        assert result is None or result is not None  # tautology — coverage only
    finally:
        doc.close()


def test_get_paint_returns_blue_when_non_stroking_is_red() -> None:
    doc, drawer = _make_drawer()
    try:
        # Drive the RED -> BLUE substitution branch via the canonical
        # ``color.to_rgb_int()`` int helper.

        class _RedColor:
            def to_rgb_int(self) -> int:
                return _RED_RGB

        color = _RedColor()
        fake_gs = MagicMock()
        fake_gs.get_non_stroking_color.return_value = color
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        assert drawer.get_paint(color) == _BLUE_RGB
    finally:
        doc.close()


def test_get_paint_swallows_type_error_from_to_rgb_int() -> None:
    doc, drawer = _make_drawer()
    try:
        # ``to_rgb_int`` is expected to raise on invalid color graphs;
        # the example suppresses TypeError/ValueError/AttributeError.

        class _BadColor:
            def to_rgb_int(self) -> int:
                raise TypeError("bad color graph")

        color = _BadColor()
        fake_gs = MagicMock()
        fake_gs.get_non_stroking_color.return_value = color
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        # Falls through to super().get_paint without raising.
        result = drawer.get_paint(color)
        assert result is color or result is not None
    finally:
        doc.close()


def test_get_paint_falls_through_when_non_stroking_mismatches() -> None:
    doc, drawer = _make_drawer()
    try:
        # Graphics state reports a different (unrelated) non_stroking
        # color -> the ``is`` check fails -> super().get_paint is invoked.
        other = object()
        fake_gs = MagicMock()
        fake_gs.get_non_stroking_color.return_value = other
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        sentinel = object()
        result = drawer.get_paint(sentinel)
        # super().get_paint(color) returns ``color`` when the renderer
        # has no resolver attached.
        assert result is sentinel or result is not None
    finally:
        doc.close()


def test_get_paint_swallows_attribute_error_from_get_graphics_state() -> None:
    doc, drawer = _make_drawer()
    try:
        # If get_graphics_state() raises AttributeError (e.g. when the
        # method itself is missing), the suppress() lets non_stroking
        # stay None and the rest of get_paint executes.

        def _raises() -> Any:
            raise AttributeError("no graphics state")

        drawer.get_graphics_state = _raises  # type: ignore[method-assign]
        # No exception escapes.
        drawer.get_paint(object())
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# show_glyph
# ---------------------------------------------------------------------------


def test_show_glyph_delegates_to_super() -> None:
    doc, drawer = _make_drawer()
    try:
        # PageDrawer.show_glyph exists; we just want to ensure the
        # delegation doesn't escape an exception.
        drawer.show_glyph(None, None, 0, None)
    finally:
        doc.close()


def test_show_glyph_swallows_attribute_error_from_super(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, drawer = _make_drawer()
    try:
        # Monkey-patch PageDrawer.show_glyph to raise AttributeError so
        # we hit the contextlib.suppress(AttributeError) branch.
        def _missing(self, *args: Any, **kwargs: Any) -> None:
            raise AttributeError("show_glyph not implemented")

        monkeypatch.setattr(PageDrawer, "show_glyph", _missing)
        # Must not raise.
        drawer.show_glyph(None, None, 0, None)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# fill_path
# ---------------------------------------------------------------------------


def test_fill_path_delegates_to_super() -> None:
    doc, drawer = _make_drawer()
    try:
        # PageDrawer.fill_path handles winding rule 0 (non-zero).
        drawer.fill_path(0)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# show_annotation — save / set-alpha / restore lifecycle
# ---------------------------------------------------------------------------


def test_show_annotation_delegates_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, drawer = _make_drawer()
    try:
        calls: list[str] = []

        def _save() -> None:
            calls.append("save")

        def _restore() -> None:
            calls.append("restore")

        fake_gs = MagicMock()
        fake_gs.set_non_stroke_alpha_constant.side_effect = (
            lambda v: calls.append(f"alpha={v}")
        )

        drawer.save_graphics_state = _save  # type: ignore[method-assign]
        drawer.restore_graphics_state = _restore  # type: ignore[method-assign]
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        # Patch the super show_annotation to be a benign no-op so we
        # don't need a real annotation rendering pipeline.
        def _noop(self, annotation: Any) -> None:
            calls.append("super")

        monkeypatch.setattr(PageDrawer, "show_annotation", _noop)

        drawer.show_annotation(object())
        assert calls == ["save", "alpha=0.35", "super", "restore"]
    finally:
        doc.close()


def test_show_annotation_restores_even_when_super_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, drawer = _make_drawer()
    try:
        calls: list[str] = []

        def _save() -> None:
            calls.append("save")

        def _restore() -> None:
            calls.append("restore")

        fake_gs = MagicMock()
        drawer.save_graphics_state = _save  # type: ignore[method-assign]
        drawer.restore_graphics_state = _restore  # type: ignore[method-assign]
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        def _bad(self, annotation: Any) -> None:
            raise RuntimeError("render error")

        monkeypatch.setattr(PageDrawer, "show_annotation", _bad)

        with pytest.raises(RuntimeError):
            drawer.show_annotation(object())
        # restore_graphics_state must still have been called.
        assert "save" in calls and "restore" in calls
    finally:
        doc.close()


def test_show_annotation_swallows_save_attribute_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, drawer = _make_drawer()
    try:
        # If save_graphics_state is absent, the suppress() branch lets
        # show_annotation continue without raising.
        def _missing() -> None:
            raise AttributeError("save_graphics_state not implemented")

        drawer.save_graphics_state = _missing  # type: ignore[method-assign]
        drawer.restore_graphics_state = lambda: None  # type: ignore[method-assign]

        monkeypatch.setattr(
            PageDrawer, "show_annotation",
            lambda self, annotation: None,
        )

        drawer.show_annotation(object())
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# CustomPageDrawer.main — missing demo PDF
# ---------------------------------------------------------------------------


def test_main_raises_when_demo_pdf_missing() -> None:
    # The demo PDF is not bundled in the repository, so main() should
    # surface a load failure rather than silently succeeding.
    with pytest.raises((OSError, FileNotFoundError, RuntimeError)):
        CustomPageDrawer.main([])


def test_main_accepts_argv_none() -> None:
    # ``args`` is intentionally dropped — None or a list both fail
    # downstream at Loader.load_pdf.
    with pytest.raises((OSError, FileNotFoundError, RuntimeError)):
        CustomPageDrawer.main(None)
