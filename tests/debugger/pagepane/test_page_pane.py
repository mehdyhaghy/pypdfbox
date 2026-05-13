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


# ---------------------------------------------------------------------------
# Mouse handler edge cases (Wave 1299)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page_rotation, menu_rotation, event_xy, expected_substring",
    [
        # Rotation 90: x = (60 - event_y - offset_x) etc. We don't pin the
        # exact coords, only that the handler produces *some* status text.
        (90, 0, (10, 20), "x: "),
        (180, 0, (10, 20), "x: "),
        (270, 0, (10, 20), "x: "),
        # Composite menu+page rotation that wraps to 0 — exercises the
        # ``else`` arm.
        (0, 0, (10, 20), "x: "),
    ],
)
def test_on_mouse_moved_rotation_branches(
    tk_root: tk.Tk,
    page_rotation: int,
    menu_rotation: int,
    event_xy: tuple[int, int],
    expected_substring: str,
) -> None:
    """Exercise the four rotation branches inside ``_on_mouse_moved``.

    We rotate the page itself (via ``set_rotation``) so we don't have to
    bring up the live RotationMenu singleton.
    """
    from tkinter import ttk

    doc = _make_one_page_doc(content=None)
    try:
        doc.get_page(0).set_rotation(page_rotation)
        status = ttk.Label(tk_root, text="")
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=status)
        pane.init()
        event = tk.Event()
        event.x, event.y = event_xy
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert expected_substring in status.cget("text")
    finally:
        doc.close()


def test_on_mouse_moved_treats_zero_zoom_scale_as_one(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``_resolve_zoom_scale`` returns ``0`` the handler falls back
    to ``1.0`` instead of dividing by zero."""
    import pypdfbox.debugger.pagepane.page_pane as page_pane_mod

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Only patch *after* init so the renderer doesn't see scale=0.
        monkeypatch.setattr(page_pane_mod, "_resolve_zoom_scale", lambda: 0.0)
        event = tk.Event()
        event.x = 5
        event.y = 5
        pane._on_mouse_moved(event)  # noqa: SLF001
        # No exception is sufficient — division-by-zero would have raised.
    finally:
        doc.close()


def test_on_mouse_moved_skips_rect_with_bad_contains(tk_root: tk.Tk) -> None:
    """A rect whose ``contains`` raises ``AttributeError`` / ``TypeError``
    is silently skipped — ``_current_uri`` stays empty."""
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        class _BoomRect:
            def contains(self, _x: float, _y: float) -> bool:
                raise AttributeError("not a rect")

        pane._rect_map[_BoomRect()] = "URI: https://oops"  # noqa: SLF001
        event = tk.Event()
        event.x = 1
        event.y = 1
        pane._on_mouse_moved(event)  # noqa: SLF001
        assert pane._current_uri == ""  # noqa: SLF001
    finally:
        doc.close()


def test_on_mouse_clicked_opens_uri(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_on_mouse_clicked`` should hand the cached URI to webbrowser.open."""
    import pypdfbox.debugger.pagepane.page_pane as page_pane_mod

    seen: dict[str, str] = {}

    def _fake_open(url: str) -> bool:
        seen["url"] = url
        return True

    monkeypatch.setattr(page_pane_mod.webbrowser, "open", _fake_open)

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        pane._current_uri = "https://example.com/foo"  # noqa: SLF001
        pane._on_mouse_clicked(tk.Event())  # noqa: SLF001
        assert seen.get("url") == "https://example.com/foo"
    finally:
        doc.close()


def test_on_mouse_clicked_noop_when_no_uri(tk_root: tk.Tk) -> None:
    """No URI cached → ``_on_mouse_clicked`` returns immediately."""
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        pane._current_uri = ""  # noqa: SLF001
        # Smoke: doesn't raise.
        pane._on_mouse_clicked(tk.Event())  # noqa: SLF001
    finally:
        doc.close()


def test_on_mouse_exited_resets_status_label(tk_root: tk.Tk) -> None:
    """``_on_mouse_exited`` writes ``_label_text`` back to the status widget."""
    from tkinter import ttk

    doc = _make_one_page_doc(content=None)
    try:
        status = ttk.Label(tk_root, text="initial")
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=status)
        pane.init()
        pane._label_text = "Page 1"  # noqa: SLF001
        pane._on_mouse_exited(tk.Event())  # noqa: SLF001
        assert status.cget("text") == "Page 1"
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Rect map collection edge paths (Wave 1299)
# ---------------------------------------------------------------------------


def test_collect_link_locations_records_uri_rect(tk_root: tk.Tk) -> None:
    """A real link annotation with a /URI action should populate the rect_map."""
    from pypdfbox.pdmodel import PDRectangle
    from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = _make_one_page_doc(content=None)
    try:
        page = doc.get_page(0)
        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(10.0, 10.0, 50.0, 30.0))
        action = PDActionURI()
        action.set_uri("https://link.example.com")
        link.set_action(action)
        page.set_annotations([link])
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("URI: https://link.example.com" in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_link_locations_swallows_annotation_attribute_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``page.get_annotations`` itself raises ``AttributeError`` the
    collector returns silently (rect map untouched)."""
    from pypdfbox.pdmodel.pd_page import PDPage as _PDPage

    def _boom(self) -> list:  # type: ignore[no-untyped-def]
        raise AttributeError("no annotations")

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        monkeypatch.setattr(_PDPage, "get_annotations", _boom)
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # rect_map stays empty (no link / field discovery succeeded).
        assert pane._rect_map == {}  # noqa: SLF001
    finally:
        doc.close()


def test_collect_field_locations_records_field_label(tk_root: tk.Tk) -> None:
    """A widget annotation paired with an AcroForm field surfaces a label."""
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel import PDRectangle
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    doc = _make_one_page_doc(content=None)
    try:
        # Build an AcroForm with one text field; the field dict is also
        # the widget annotation (single-widget shortcut, PDF spec).
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        field_dict = COSDictionary()
        field_dict.set_name(COSName.get_pdf_name("FT"), "Tx")
        field_dict.set_string(COSName.get_pdf_name("T"), "my_field")
        field_dict.set_string(COSName.get_pdf_name("V"), "hello")
        field_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
        rect = PDRectangle(5.0, 5.0, 25.0, 15.0)
        field_dict.set_item(COSName.get_pdf_name("Rect"), rect.get_cos_object())
        field = PDTextField(acroform, field_dict, None)
        acroform.set_fields([field])
        catalog.set_acro_form(acroform)

        page = doc.get_page(0)
        # The page references the widget annotation (sharing the field's
        # underlying dictionary) so the field collector matches it.
        page.set_annotations([PDAnnotationWidget(field_dict)])
        page_dict = page.get_cos_object()

        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("Field name: my_field" in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_skips_when_no_acroform(tk_root: tk.Tk) -> None:
    """``acroform is None`` short-circuits the field collector."""
    doc = _make_one_page_doc(content=None)
    try:
        # No AcroForm set on the catalog (default state).
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # No field labels in the rect map.
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_swallows_catalog_attribute_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``get_document_catalog`` raises ``AttributeError`` the collector
    bails out without touching the rect map.
    """
    from pypdfbox.pdmodel.pd_document import PDDocument as _PDDoc

    def _boom(self):  # type: ignore[no-untyped-def]
        raise AttributeError("no catalog")

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        monkeypatch.setattr(_PDDoc, "get_document_catalog", _boom)
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert pane._rect_map == {}  # noqa: SLF001
    finally:
        doc.close()


def test_init_rect_map_logs_on_oserror(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``OSError`` raised by the inner collectors is logged and swallowed."""
    from pypdfbox.debugger.pagepane import page_pane as page_pane_mod

    def _boom(self):  # type: ignore[no-untyped-def]
        raise OSError("simulated")

    monkeypatch.setattr(page_pane_mod.PagePane, "_collect_link_locations", _boom)
    doc = _make_one_page_doc(content=None)
    try:
        with caplog.at_level("ERROR"):
            page_dict = doc.get_page(0).get_cos_object()
            pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
            pane.init()
        assert any("collecting rect map failed" in rec.message for rec in caplog.records)
    finally:
        doc.close()


def test_set_page_handles_unknown_page(tk_root: tk.Tk) -> None:
    """``set_page`` with an orphan page resets ``_page_index`` to ``-1``."""
    from pypdfbox.pdmodel import PDPage, PDRectangle

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        orphan = PDPage(PDRectangle(0.0, 0.0, 30.0, 30.0))
        pane.set_page(orphan)
        assert pane._page_index == -1  # noqa: SLF001
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Rendering edge paths (Wave 1299)
# ---------------------------------------------------------------------------


def test_start_rendering_logs_and_returns_on_render_failure(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``OSError`` / ``RuntimeError`` raised by ``_render_image`` is logged."""
    import pypdfbox.debugger.pagepane.page_pane as page_pane_mod

    def _boom(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated render fail")

    monkeypatch.setattr(page_pane_mod.PagePane, "_render_image", _boom)
    doc = _make_one_page_doc()
    try:
        with caplog.at_level("ERROR"):
            page_dict = doc.get_page(0).get_cos_object()
            pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
            pane.init()
        assert any("page render failed" in rec.message for rec in caplog.records)
        assert pane.get_image() is None
    finally:
        doc.close()


def test_draw_debug_overlays_paints_when_view_menu_flags_set(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the view menu reports any of the four show-* flags as ``True``
    ``_draw_debug_overlays`` should construct a ``DebugTextOverlay`` and
    call ``render_to``. We spy on the overlay by patching the class
    inside the page-pane module.
    """
    import pypdfbox.debugger.pagepane.page_pane as page_pane_mod
    from pypdfbox.debugger.ui.view_menu import ViewMenu

    # Bring the singleton up and stub the flag accessors so the
    # ``any(...)`` guard inside ``_draw_debug_overlays`` is satisfied.
    instance = ViewMenu.get_instance(master=tk_root)

    class _StubViewMenu:
        @staticmethod
        def is_show_text_stripper() -> bool:
            return True

        @staticmethod
        def is_show_text_stripper_beads() -> bool:
            return False

        @staticmethod
        def is_show_font_bbox() -> bool:
            return False

        @staticmethod
        def is_show_glyph_bounds() -> bool:
            return False

    monkeypatch.setattr(
        page_pane_mod, "_safe_get_view_menu", lambda: _StubViewMenu()
    )

    seen: dict[str, bool] = {}

    real_overlay_cls = page_pane_mod.DebugTextOverlay

    class _SpyOverlay(real_overlay_cls):  # type: ignore[misc, valid-type]
        def render_to(self, draw):  # type: ignore[no-untyped-def]
            seen["rendered"] = True
            return super().render_to(draw)

    monkeypatch.setattr(page_pane_mod, "DebugTextOverlay", _SpyOverlay)

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert seen.get("rendered") is True
    finally:
        doc.close()
        del instance


def test_present_image_rotates_when_rotation_nonzero(
    tk_root: tk.Tk, _reset_menus: None
) -> None:
    """A non-zero rotation selection runs the image through
    ``ImageUtil.get_rotated_image`` so a portrait page becomes landscape.
    """
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu
    from pypdfbox.pdmodel import PDPage, PDRectangle

    # Use a clearly non-square page so rotation flips dims.
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 80.0, 40.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 10 Tf 5 20 Td (y) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)
    try:
        menu = RotationMenu.get_instance(master=tk_root)
        menu.set_rotation_selection(RotationMenu.ROTATE_90_DEGREES)
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        image = pane.get_image()
        assert image is not None
        # A 90 rotation flips (80,40) into (40,80).
        assert image.size == (40, 80)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Resolver helpers — ImportError / failure paths (Wave 1299)
# ---------------------------------------------------------------------------


def test_resolve_zoom_scale_returns_default_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``zoom_menu`` can't be imported the resolver returns ``1.0``."""
    monkeypatch.setitem(__import__("sys").modules, "pypdfbox.debugger.ui.zoom_menu", None)
    assert _resolve_zoom_scale() == 1.0


def test_resolve_zoom_scale_static_getter_raises_then_instance_fallback(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``ZoomMenu.get_zoom_scale`` raises and the singleton's
    instance accessor returns a value, the resolver picks the instance
    fallback.
    """
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    instance = ZoomMenu.get_instance(master=tk_root)
    # ``_page_zoom_scale`` is an explicit instance field — distinct from
    # the menu's selected percent — and is what the fallback path reads.
    instance.set_page_zoom_scale(1.5)

    def _boom_static() -> float:
        raise RuntimeError("static getter failed")

    monkeypatch.setattr(ZoomMenu, "get_zoom_scale", _boom_static)
    assert _resolve_zoom_scale() == pytest.approx(1.5)


def test_resolve_zoom_scale_instance_get_page_zoom_scale_raises(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When *both* the static getter and the instance accessor raise the
    resolver falls back to ``1.0``."""
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ZoomMenu.get_instance(master=tk_root)

    def _boom_static() -> float:
        raise RuntimeError("nope")

    def _boom_inst(self) -> float:  # type: ignore[no-untyped-def]
        raise RuntimeError("inst nope")

    monkeypatch.setattr(ZoomMenu, "get_zoom_scale", _boom_static)
    monkeypatch.setattr(ZoomMenu, "get_page_zoom_scale", _boom_inst)
    assert _resolve_zoom_scale() == 1.0


def test_resolve_zoom_scale_instance_falsy_value_falls_back(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A falsy ``get_page_zoom_scale()`` result triggers the ``or 1.0``
    fallback inside the resolver."""
    from pypdfbox.debugger.ui.zoom_menu import ZoomMenu

    ZoomMenu.get_instance(master=tk_root)

    def _boom_static() -> float:
        raise RuntimeError("nope")

    monkeypatch.setattr(ZoomMenu, "get_zoom_scale", _boom_static)
    monkeypatch.setattr(
        ZoomMenu, "get_page_zoom_scale", lambda self: 0.0  # type: ignore[no-untyped-def]
    )
    assert _resolve_zoom_scale() == 1.0


def test_resolve_rotation_returns_zero_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        __import__("sys").modules, "pypdfbox.debugger.ui.rotation_menu", None
    )
    assert _resolve_rotation() == 0


def test_resolve_rotation_returns_zero_when_static_getter_raises(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu

    RotationMenu.get_instance(master=tk_root)

    def _boom() -> int:
        raise RuntimeError("nope")

    monkeypatch.setattr(RotationMenu, "get_rotation_degrees", _boom)
    assert _resolve_rotation() == 0


def test_resolve_image_type_returns_none_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        __import__("sys").modules, "pypdfbox.debugger.ui.image_type_menu", None
    )
    assert _resolve_image_type() is None


def test_resolve_image_type_returns_none_when_getter_raises_runtime(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu

    def _boom() -> object:
        raise RuntimeError("uninstantiated")

    monkeypatch.setattr(ImageTypeMenu, "get_image_type", _boom)
    assert _resolve_image_type() is None


def test_resolve_image_type_returns_none_when_getter_raises_arbitrary(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any unexpected exception path also resolves to ``None``."""
    from pypdfbox.debugger.ui.image_type_menu import ImageTypeMenu

    def _boom() -> object:
        raise KeyError("dropped")

    monkeypatch.setattr(ImageTypeMenu, "get_image_type", _boom)
    assert _resolve_image_type() is None


def test_resolve_render_destination_returns_none_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        __import__("sys").modules,
        "pypdfbox.debugger.ui.render_destination_menu",
        None,
    )
    assert _resolve_render_destination() is None


def test_resolve_render_destination_returns_none_when_getter_raises(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pypdfbox.debugger.ui.render_destination_menu import RenderDestinationMenu

    def _boom() -> object:
        raise RuntimeError("nope")

    monkeypatch.setattr(RenderDestinationMenu, "get_render_destination", _boom)
    assert _resolve_render_destination() is None


def test_resolve_render_destination_returns_none_when_getter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the menu module is loadable but lacks ``get_render_destination``
    the resolver returns ``None`` (the ``getter is None`` short-circuit).
    """
    import pypdfbox.debugger.ui.render_destination_menu as menu_mod

    monkeypatch.delattr(
        menu_mod.RenderDestinationMenu, "get_render_destination", raising=False
    )
    assert _resolve_render_destination() is None


def test_resolve_image_type_returns_none_when_getter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.debugger.ui.image_type_menu as menu_mod

    monkeypatch.delattr(
        menu_mod.ImageTypeMenu, "get_image_type", raising=False
    )
    assert _resolve_image_type() is None


def test_resolve_allow_subsampling_returns_false_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        __import__("sys").modules, "pypdfbox.debugger.ui.view_menu", None
    )
    assert _resolve_allow_subsampling() is False


def test_resolve_allow_subsampling_returns_false_when_getter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.debugger.ui.view_menu as menu_mod

    monkeypatch.delattr(
        menu_mod.ViewMenu, "is_allow_subsampling", raising=False
    )
    assert _resolve_allow_subsampling() is False


def test_resolve_allow_subsampling_returns_false_when_getter_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.debugger.ui.view_menu as menu_mod

    def _boom() -> bool:
        raise RuntimeError("nope")

    monkeypatch.setattr(menu_mod.ViewMenu, "is_allow_subsampling", _boom)
    assert _resolve_allow_subsampling() is False


def test_safe_get_view_menu_returns_none_on_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.debugger.pagepane.page_pane import _safe_get_view_menu

    monkeypatch.setitem(
        __import__("sys").modules, "pypdfbox.debugger.ui.view_menu", None
    )
    assert _safe_get_view_menu() is None


# ---------------------------------------------------------------------------
# Additional defensive-path coverage (Wave 1299)
# ---------------------------------------------------------------------------


def test_page_pane_ctor_orphan_when_index_of_raises(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``index_of`` raising ``AttributeError`` resolves to orphan label."""
    from pypdfbox.pdmodel.pd_page_tree import PDPageTree

    def _boom(self, _page):  # type: ignore[no-untyped-def]
        raise AttributeError("legacy doc")

    monkeypatch.setattr(PDPageTree, "index_of", _boom)
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        assert pane._page_index == -1  # noqa: SLF001
        assert "orphan" in pane._page_label_widget.cget("text")  # noqa: SLF001
    finally:
        doc.close()


def test_set_page_swallows_index_of_attribute_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``set_page`` when ``index_of`` raises ``AttributeError`` falls back
    to ``-1`` (mirrors the constructor's defensive arm).
    """
    from pypdfbox.pdmodel import PDPage, PDRectangle
    from pypdfbox.pdmodel.pd_page_tree import PDPageTree

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        def _boom(self, _page):  # type: ignore[no-untyped-def]
            raise AttributeError("legacy doc")

        monkeypatch.setattr(PDPageTree, "index_of", _boom)
        pane.set_page(PDPage(PDRectangle(0.0, 0.0, 10.0, 10.0)))
        assert pane._page_index == -1  # noqa: SLF001
    finally:
        doc.close()


def test_collect_link_locations_skips_link_without_rectangle(
    tk_root: tk.Tk,
) -> None:
    """A link annotation with no /Rect entry is silently skipped."""
    from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = _make_one_page_doc(content=None)
    try:
        page = doc.get_page(0)
        link = PDAnnotationLink()
        action = PDActionURI()
        action.set_uri("https://no-rect.example.com")
        link.set_action(action)
        # Deliberately do NOT call ``link.set_rectangle(...)`` so the
        # collector hits the ``if rect is None: continue`` arm.
        page.set_annotations([link])
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # No URI label was recorded for this rectangle-less annotation.
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("https://no-rect.example.com" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_link_locations_returns_when_action_import_fails(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the action/annotation submodules can't be imported the link
    collector exits without touching the rect map.
    """
    sys_modules = __import__("sys").modules
    monkeypatch.setitem(
        sys_modules,
        "pypdfbox.pdmodel.interactive.action.pd_action_uri",
        None,
    )
    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # rect_map untouched by the link collector (still possibly
        # populated by the field collector).
        assert all(not lbl.startswith("URI:") for lbl in pane._rect_map.values())  # noqa: SLF001
    finally:
        doc.close()


def test_collect_field_locations_field_with_no_widgets(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A field whose ``get_widgets`` raises ``AttributeError`` is skipped
    cleanly. We patch ``PDAcroForm.get_field_tree`` at the class level so
    every fresh wrapper picks up our stub tree.
    """
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    class _BareField:
        """Stub field whose accessors trip the AttributeError defensive arms."""

    class _StubTree:
        def __iter__(self):
            return iter([_BareField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page = doc.get_page(0)
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_widget_with_no_cos_object(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Widgets without ``get_cos_object`` are skipped via ``AttributeError``."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    class _BareWidget:
        """No ``get_cos_object`` → hits the inner AttributeError arm."""

    class _StubField:
        def get_widgets(self):
            return [_BareWidget()]

    class _StubTree:
        def __iter__(self):
            return iter([_StubField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_widget_not_in_annotations(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A widget whose dict is *not* in the page's /Annots set is skipped
    (the ``widget_dict not in dictionary_set`` arm).
    """
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    class _StubWidget:
        def __init__(self) -> None:
            self._dict = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class _StubField:
        def get_widgets(self):
            return [_StubWidget()]

    class _StubTree:
        def __iter__(self):
            return iter([_StubField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert labels == [] or all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_widget_without_rectangle(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matched widget whose ``get_rectangle`` returns ``None`` is skipped
    (the ``if rect is None: continue`` arm).
    """
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    widget_dict = COSDictionary()
    widget_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    widget_annot = PDAnnotationWidget(widget_dict)

    class _StubWidgetNoRect:
        def get_cos_object(self):
            return widget_dict

        def get_rectangle(self):
            return None

    class _StubField:
        def get_widgets(self):
            return [_StubWidgetNoRect()]

    class _StubTree:
        def __iter__(self):
            return iter([_StubField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page = doc.get_page(0)
        page.set_annotations([widget_annot])
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_field_name_accessor_raises(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matched widget whose owning field raises ``AttributeError`` for
    ``get_fully_qualified_name`` falls back to the placeholder label.
    """
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel import PDRectangle
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
        PDAnnotationWidget,
    )
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    widget_dict = COSDictionary()
    widget_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    widget_annot = PDAnnotationWidget(widget_dict)
    rect_obj = PDRectangle(1.0, 2.0, 3.0, 4.0)

    class _StubWidget:
        def get_cos_object(self):
            return widget_dict

        def get_rectangle(self):
            return rect_obj

    class _StubField:
        def get_widgets(self):
            return [_StubWidget()]

        # No ``get_fully_qualified_name`` / ``get_value_as_string`` →
        # AttributeError swallowed.

    class _StubTree:
        def __iter__(self):
            return iter([_StubField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page = doc.get_page(0)
        page.set_annotations([widget_annot])
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        # ``<field>`` is the placeholder fallback name baked into the
        # page pane when the accessors raise.
        assert any("Field name: <field>" in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_page_get_annotations_raises(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``page.get_annotations`` raising ``AttributeError`` lands on the
    fallback ``annotations = []`` arm; without a populated dict-set the
    field collector skips every widget.
    """
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel import PDRectangle
    from pypdfbox.pdmodel.interactive.form import PDAcroForm
    from pypdfbox.pdmodel.pd_page import PDPage as _PDPage

    widget_dict = COSDictionary()
    widget_dict.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    rect_obj = PDRectangle(1.0, 2.0, 3.0, 4.0)

    class _StubWidget:
        def get_cos_object(self):
            return widget_dict

        def get_rectangle(self):
            return rect_obj

    class _StubField:
        def get_widgets(self):
            return [_StubWidget()]

    class _StubTree:
        def __iter__(self):
            return iter([_StubField()])

    monkeypatch.setattr(PDAcroForm, "get_field_tree", lambda self: _StubTree())

    # ``_init_rect_map`` calls field then link collector. The field
    # collector's *second* call to ``get_annotations`` should land on
    # the defensive arm — but the field collector itself calls
    # ``get_annotations`` first, before the link collector even runs. We
    # raise on the very first call so the field-collector ``except``
    # arm fires.
    counter = {"n": 0}

    def _maybe_raise(self):  # type: ignore[no-untyped-def]
        counter["n"] += 1
        if counter["n"] == 1:
            raise AttributeError("field-collector path")
        return []

    monkeypatch.setattr(_PDPage, "get_annotations", _maybe_raise)

    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Widget dict isn't in the empty annotations set, so no Field
        # label is recorded; the test exists to drive the
        # ``annotations = []`` fallback arm.
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_collect_field_locations_acroform_without_field_tree(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An AcroForm-like object missing ``get_field_tree`` short-circuits."""
    from pypdfbox.pdmodel.interactive.form import PDAcroForm

    def _boom(self):  # type: ignore[no-untyped-def]
        raise AttributeError("no field tree")

    monkeypatch.setattr(PDAcroForm, "get_field_tree", _boom)
    doc = _make_one_page_doc(content=None)
    try:
        catalog = doc.get_document_catalog()
        acroform = PDAcroForm(doc)
        catalog.set_acro_form(acroform)
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert all("Field name" not in lbl for lbl in labels)
    finally:
        doc.close()


def test_present_image_swallows_image_util_value_error(
    tk_root: tk.Tk, _reset_menus: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ``ImageUtil.get_rotated_image`` raises ``ValueError`` the page
    pane swallows it and keeps the un-rotated image."""
    from pypdfbox.debugger.ui.image_util import ImageUtil
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu

    RotationMenu.get_instance(master=tk_root).set_rotation_selection(
        RotationMenu.ROTATE_90_DEGREES
    )

    def _boom(_image, _rotation):  # type: ignore[no-untyped-def]
        raise ValueError("simulated")

    monkeypatch.setattr(ImageUtil, "get_rotated_image", staticmethod(_boom))

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # The image is still present (unrotated) — error path didn't
        # bubble up.
        assert pane.get_image() is not None
    finally:
        doc.close()


def test_present_image_returns_when_canvas_is_none(tk_root: tk.Tk) -> None:
    """``_present_image`` short-circuits when ``self._canvas`` is ``None``."""
    from PIL import Image

    doc = _make_one_page_doc(content=None)
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        pane._canvas = None  # noqa: SLF001
        # ``_present_image`` returns early; ``_image`` stays as whatever
        # was set before (None in this case) but no exception is raised.
        before = pane.get_image()
        pane._present_image(Image.new("RGB", (5, 5), "white"))  # noqa: SLF001
        assert pane.get_image() is before
    finally:
        doc.close()
