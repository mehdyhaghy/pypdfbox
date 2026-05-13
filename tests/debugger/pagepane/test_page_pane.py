"""Tests for :class:`PagePane`.

The widget needs a Tk root (``tk_root`` fixture from conftest) and is
exercised against a single synthetic PDF page.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import (
    PagePane,
    _resolve_allow_subsampling,
    _resolve_image_type,
    _resolve_render_destination,
    _resolve_rotation,
    _resolve_zoom_scale,
    _safe_call,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.image_type import ImageType
from pypdfbox.rendering.render_destination import RenderDestination


@pytest.fixture()
def _reset_menus() -> Iterator[None]:
    """Reset every menu singleton this module touches before and after.

    Each menu owns global selection state. Tests that assert specific
    selections must not leak state into neighbouring tests, so we wipe
    the singletons on both ends of the test.
    """
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu
    from pypdfbox.debugger.ui.text_stripper_menu import TextStripperMenu
    from pypdfbox.debugger.ui.view_menu import ViewMenu
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    def _wipe() -> None:
        ZoomMenu._reset_instance()  # noqa: SLF001
        RotationMenu._reset_instance()  # noqa: SLF001
        RenderDestinationMenu._reset_instance()  # noqa: SLF001
        ViewMenu._reset_instance()  # noqa: SLF001
        ImageTypeMenu._reset_for_testing()  # noqa: SLF001
        TextStripperMenu._reset_for_testing()  # noqa: SLF001

    _wipe()
    try:
        yield
    finally:
        _wipe()


def _make_one_page_doc(content: bytes | None = b"BT /F0 12 Tf 10 50 Td (x) Tj ET") -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 60.0, 60.0))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_page_pane_constructs_and_returns_frame(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert pane.get_panel() is not None
        assert pane._initialized is True  # noqa: SLF001 — internal flag
        # Page label widget mentions the 1-based page number.
        assert pane._page_label_widget is not None  # noqa: SLF001
        assert "Page 1" in pane._page_label_widget.cget("text")  # noqa: SLF001
    finally:
        doc.close()


def test_page_pane_orphan_page_label(tk_root: tk.Tk) -> None:
    """A page whose dictionary isn't in the document tree shows the orphan label."""
    doc = _make_one_page_doc(content=None)
    try:
        orphan = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
        pane = PagePane(tk_root, doc, orphan.get_cos_object(), statuslabel=None)
        pane.init()
        label = pane._page_label_widget  # noqa: SLF001
        assert label is not None
        assert "orphan" in label.cget("text")
    finally:
        doc.close()


def test_page_pane_render_places_image_on_canvas(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # After init() ran, the canvas should have one image item with
        # tag "rendered_page".
        canvas = pane._canvas  # noqa: SLF001
        assert canvas is not None
        items = canvas.find_withtag("rendered_page")
        assert items, "expected at least one rendered page image on the canvas"
        assert pane.get_image() is not None
    finally:
        doc.close()


def test_page_pane_set_page_swaps_rendered_image(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc()
    second = PDPage(PDRectangle(0.0, 0.0, 80.0, 40.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 10 Tf 5 20 Td (y) Tj ET")
    second.set_contents(stream)
    doc.add_page(second)
    try:
        first_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, first_dict, statuslabel=None)
        pane.init()
        before = pane.get_image()
        pane.set_page(doc.get_page(1))
        after = pane.get_image()
        assert after is not None
        # Image size after the swap should reflect the second page.
        assert after.size == (80, 40)
        # And the image instance should have changed.
        assert before is not after
    finally:
        doc.close()


def test_page_pane_status_label_updates_on_mouse_motion(tk_root: tk.Tk) -> None:
    """Sanity check that the mouse handler writes to the status widget."""
    from tkinter import ttk

    doc = _make_one_page_doc()
    try:
        status = ttk.Label(tk_root, text="")
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=status)
        pane.init()
        # Synthesize a motion event by directly invoking the handler.
        event = tk.Event()
        event.x = 10
        event.y = 10
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert status.cget("text").startswith("x: ")
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Helper-function tests (no Tk required)
# ---------------------------------------------------------------------------


def test_resolve_zoom_scale_returns_float() -> None:
    value = _resolve_zoom_scale()
    assert isinstance(value, float)
    assert value > 0


def test_resolve_rotation_returns_int() -> None:
    value = _resolve_rotation()
    assert isinstance(value, int)


def test_safe_call_returns_default_when_target_is_none() -> None:
    assert _safe_call(None, "missing", default=42) == 42


def test_safe_call_returns_method_result() -> None:
    class _T:
        def value(self) -> int:
            return 7

    assert _safe_call(_T(), "value", default=0) == 7


def test_safe_call_returns_default_when_method_missing() -> None:
    assert _safe_call(object(), "no_such", default="fallback") == "fallback"


def test_safe_call_returns_default_when_method_raises() -> None:
    class _T:
        def boom(self) -> None:
            raise RuntimeError("nope")

    assert _safe_call(_T(), "boom", default="ok") == "ok"


# ---------------------------------------------------------------------------
# Menu-singleton wiring (Wave 1295)
# ---------------------------------------------------------------------------


def test_resolve_zoom_scale_reads_zoom_menu_static_selection(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    """``_resolve_zoom_scale`` returns the currently-selected zoom percent."""
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ZoomMenu.get_instance(master=tk_root).change_zoom_selection(2.0)
    assert _resolve_zoom_scale() == pytest.approx(2.0)


def test_resolve_rotation_reads_rotation_menu_selection(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu

    menu = RotationMenu.get_instance(master=tk_root)
    menu.set_rotation_selection(RotationMenu.ROTATE_180_DEGREES)
    assert _resolve_rotation() == 180


def test_resolve_image_type_returns_none_when_menu_uninstantiated(
    _reset_menus: None,
) -> None:
    assert _resolve_image_type() is None


def test_resolve_image_type_reads_menu_selection(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu

    menu = ImageTypeMenu.get_instance(master=tk_root)
    menu.set_image_type_selection(ImageTypeMenu.IMAGETYPE_GRAY)
    assert _resolve_image_type() is ImageType.GRAY


def test_resolve_render_destination_reads_menu_selection(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu

    menu = RenderDestinationMenu.get_instance(master=tk_root)
    menu.set_render_destination_selection(
        RenderDestinationMenu.RENDER_DESTINATION_PRINT
    )
    assert _resolve_render_destination() is RenderDestination.PRINT


def test_resolve_allow_subsampling_reflects_view_menu_state(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    from pypdfbox.debugger.ui.view_menu import ViewMenu

    instance = ViewMenu.get_instance(master=tk_root)
    # Toggle via the underlying BooleanVar; matches how the checkbutton
    # would update it in a live UI.
    instance._allow_subsampling_var.set(True)  # noqa: SLF001
    assert _resolve_allow_subsampling() is True
    instance._allow_subsampling_var.set(False)  # noqa: SLF001
    assert _resolve_allow_subsampling() is False


def test_page_pane_renders_at_zoom_menu_scale(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    """A 2x zoom selection doubles the rendered image's pixel dimensions."""
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ZoomMenu.get_instance(master=tk_root).change_zoom_selection(2.0)
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        image = pane.get_image()
        assert image is not None
        # Page is 60x60 user-space units; 2x scale → 120x120 pixels.
        assert image.size == (120, 120)
    finally:
        doc.close()


def test_page_pane_uses_image_type_menu_mode(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    """Selecting Gray flips the rendered image's Pillow mode to ``L``."""
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu

    menu = ImageTypeMenu.get_instance(master=tk_root)
    menu.set_image_type_selection(ImageTypeMenu.IMAGETYPE_GRAY)
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        image = pane.get_image()
        assert image is not None
        assert image.mode == "L"
    finally:
        doc.close()


def test_page_pane_propagates_render_destination_to_renderer(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_render_image`` should thread the enum selected on
    ``RenderDestinationMenu`` straight through to ``render_image`` via
    the ``destination=`` kwarg (mirrors upstream's four-arg
    ``renderImage(int, float, ImageType, RenderDestination)``). We
    hijack the renderer class via monkeypatch to inspect what the page
    pane wired in.
    """
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu

    RenderDestinationMenu.get_instance(
        master=tk_root
    ).set_render_destination_selection(
        RenderDestinationMenu.RENDER_DESTINATION_PRINT
    )

    seen: dict[str, object] = {}

    import pypdfbox.rendering as rendering_module

    real_renderer_cls = rendering_module.PDFRenderer

    class _SpyRenderer(real_renderer_cls):  # type: ignore[misc, valid-type]
        def render_image(  # type: ignore[override]
            self,
            page_index,
            scale=1.0,
            image_type=None,
            destination=None,
        ):
            seen["destination"] = destination
            return super().render_image(
                page_index,
                scale=scale,
                image_type=image_type,
                destination=destination,
            )

    monkeypatch.setattr(rendering_module, "PDFRenderer", _SpyRenderer)

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert seen.get("destination") is RenderDestination.PRINT
    finally:
        doc.close()


def test_page_pane_propagates_allow_subsampling_to_renderer(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ViewMenu.is_allow_subsampling()`` should be forwarded to the
    renderer via ``set_subsampling_allowed`` when present.
    """
    from pypdfbox.debugger.ui.view_menu import ViewMenu

    ViewMenu.get_instance(master=tk_root)._allow_subsampling_var.set(True)  # noqa: SLF001

    seen: dict[str, object] = {}

    import pypdfbox.rendering as rendering_module

    real_renderer_cls = rendering_module.PDFRenderer

    class _SpyRenderer(real_renderer_cls):  # type: ignore[misc, valid-type]
        def set_subsampling_allowed(self, allowed):  # type: ignore[override]
            seen["subsampling"] = bool(allowed)

    monkeypatch.setattr(rendering_module, "PDFRenderer", _SpyRenderer)

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert seen.get("subsampling") is True
    finally:
        doc.close()


@pytest.mark.parametrize(
    "label, expected_uri",
    [("URI: https://example.com", "https://example.com"), ("Field name: foo, value: bar", "")],
)
def test_page_pane_currrent_uri_after_motion_over_rect(
    tk_root: tk.Tk, label: str, expected_uri: str
) -> None:
    """When the cursor sits over a URI rect, ``_current_uri`` is populated."""
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Inject a fake rectangle that contains any point.
        class _AlwaysContains:
            def contains(self, _x: float, _y: float) -> bool:
                return True

        pane._rect_map[_AlwaysContains()] = label  # noqa: SLF001
        event = tk.Event()
        event.x = 5
        event.y = 5
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert pane._current_uri == expected_uri  # noqa: SLF001
    finally:
        doc.close()
