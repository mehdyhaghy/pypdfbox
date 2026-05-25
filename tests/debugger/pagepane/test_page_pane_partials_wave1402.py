"""Wave 1402 — branch-coverage round-out for ``PagePane``.

Targets the residual partial branches on
``pypdfbox/debugger/pagepane/page_pane.py``:

* 240->244 — destination resolver missing on the catalog.
* 344->347 — ``TextStripperMenu.is_sorted`` missing.
* 348->355 — ``TextStripperMenu.is_ignore_spaces`` missing.
* 364->367 — ``TextDialog.set_text`` setter missing.
* 368->exit — ``TextDialog.set_visible`` setter missing.
* 385->388 — renderer has no ``set_subsampling_allowed`` method.
* 529->524 — rect.contains returns False ⇒ continue to next iter.
* 535->538 — pane has no ``_canvas`` to update.
* 733->738 — ``ZoomMenu.get_zoom_scale`` static getter missing.
* 762->767 — ``RotationMenu.get_rotation_degrees`` static getter missing.

Uses the shared ``tk_root`` fixture from ``tests/debugger/pagepane/conftest.py``.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import (
    PagePane,
    _resolve_rotation,
    _resolve_zoom_scale,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


@pytest.fixture()
def _reset_menus() -> Iterator[None]:
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


def _make_one_page_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 60.0, 60.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 12 Tf 10 50 Td (x) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


# ----------------------------------------------------------------------
# 240->244 — find_named_destination_page missing on the catalog
# ----------------------------------------------------------------------


def test_collect_link_location_catalog_without_named_destination_resolver(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """240->244 — destination is a ``PDNamedDestination`` but the
    catalog has no ``find_named_destination_page`` resolver ⇒ skip
    the assignment branch.

    Constructed via the else-arm of line 230 (action is not
    ``PDActionGoTo``), routing through ``link_annotation.get_destination()``
    so we control the typed return.
    """
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: E501
        PDNamedDestination,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        named = PDNamedDestination()

        class _NonGoToAction:
            """Action that is NEITHER PDActionURI NOR PDActionGoTo so
            we hit the else-arm of line 230."""

        action = _NonGoToAction()

        class _FakeLink:
            def get_action(self) -> Any:
                return action

            def get_destination(self) -> Any:
                # The else-branch reaches into link_annotation directly.
                return named

            def get_rectangle(self) -> Any:
                return PDRectangle(0.0, 0.0, 10.0, 10.0)

        # Strip the resolver method off the real catalog so getattr
        # returns None at line 239.
        from pypdfbox.pdmodel import pd_document_catalog as _cat_mod

        monkeypatch.delattr(
            _cat_mod.PDDocumentCatalog,
            "find_named_destination_page",
            raising=False,
        )
        pane.collect_link_location(_FakeLink())
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 344->347 — TextStripperMenu has no `is_sorted` classmethod
# ----------------------------------------------------------------------


def test_start_extracting_when_text_stripper_menu_has_no_is_sorted(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """344->347 — ``sorted_getter`` is None ⇒ skip the
    ``set_sort_by_position`` step."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        from pypdfbox.debugger.ui import text_stripper_menu as _tsm

        # Hide both classmethods so the branches at 344 and 348 BOTH
        # collapse to None.
        monkeypatch.delattr(
            _tsm.TextStripperMenu, "is_sorted", raising=False
        )
        monkeypatch.delattr(
            _tsm.TextStripperMenu, "is_ignore_spaces", raising=False
        )
        # We don't care whether extraction succeeds — we only care that
        # the branches at 344 / 348 are exercised.
        pane.start_extracting()
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 364->367, 368->exit — TextDialog setters missing
# ----------------------------------------------------------------------


def test_start_extracting_when_text_dialog_has_no_set_text(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """364->367, 368->exit — ``set_text`` / ``set_visible`` getters
    return None ⇒ skip both branches."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)

        # Stub out the import so we control the dialog object handed
        # back by ``TextDialog.instance()``.
        class _BlankDialog:
            # Neither ``set_text`` nor ``set_visible`` ⇒ both branches
            # collapse to None and skip the body.
            pass

        from pypdfbox.debugger.ui import text_dialog as _td

        monkeypatch.setattr(
            _td.TextDialog, "instance", classmethod(lambda cls: _BlankDialog())
        )
        # Stripper extraction itself does not need to succeed.
        pane.start_extracting()
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 385->388 — renderer has no `set_subsampling_allowed` setter
# ----------------------------------------------------------------------


def test_render_image_renderer_without_subsampling_setter(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """385->388 — ``setter is None`` ⇒ skip the subsampling step."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)

        from pypdfbox import rendering as _r

        class _SubsamplinglessRenderer:
            def __init__(self, _doc: Any) -> None:
                pass

            # No `set_subsampling_allowed` method — that's the False arm.
            def render_image(self, _idx: int, **_kw: Any) -> Any:
                from PIL import Image

                return Image.new("RGB", (10, 10))

        monkeypatch.setattr(_r, "PDFRenderer", _SubsamplinglessRenderer)
        # Should succeed without invoking the missing setter.
        image = pane._render_image()  # noqa: SLF001
        assert image is not None
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 529->524 — mouse hover continues past a non-hit rect
# ----------------------------------------------------------------------


def test_on_mouse_moved_continues_past_non_hit_rect(
    tk_root: tk.Tk,
) -> None:
    """529->524 — first rect does not contain the cursor ⇒ ``hit`` is
    False, the loop continues to the second rect."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Force a Tk canvas so the canvas-config branch on the same call
        # is also covered.
        pane._canvas = tk.Canvas(tk_root)  # noqa: SLF001

        class _Rect:
            def __init__(self, hit: bool) -> None:
                self._hit = hit

            def contains(self, _x: float, _y: float) -> bool:
                return self._hit

        # Two rects: first NOT a hit ⇒ continue, second IS a hit ⇒ break.
        pane._rect_map = {  # noqa: SLF001
            _Rect(False): "Far rect",
            _Rect(True): "URI: https://example.com",
        }

        # Build a minimal event.
        class _Evt:
            x = 5
            y = 5

        pane._on_mouse_moved(_Evt())  # type: ignore[arg-type]  # noqa: SLF001
        assert pane._current_uri == "https://example.com"  # noqa: SLF001
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 535->538 — _canvas is None ⇒ skip canvas.configure
# ----------------------------------------------------------------------


def test_on_mouse_moved_skips_canvas_when_canvas_none(
    tk_root: tk.Tk,
) -> None:
    """535->538 — ``_canvas`` is ``None`` ⇒ skip the configure step but
    still call ``_set_status``."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Force canvas back to None for this branch.
        pane._canvas = None  # noqa: SLF001
        pane._rect_map = {}  # noqa: SLF001

        class _Evt:
            x = 1
            y = 1

        # Should not raise even though canvas is missing.
        pane._on_mouse_moved(_Evt())  # type: ignore[arg-type]  # noqa: SLF001
    finally:
        doc.close()


# ----------------------------------------------------------------------
# 733->738 — ZoomMenu.get_zoom_scale missing
# ----------------------------------------------------------------------


def test_resolve_zoom_scale_when_static_getter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """733->738 — ``static_getter is None`` ⇒ fall through to the
    instance lookup."""
    from pypdfbox.debugger.ui import zoom_menu as _zm

    monkeypatch.delattr(_zm.ZoomMenu, "get_zoom_scale", raising=False)
    # _instance is None on a fresh module ⇒ ultimate fallback to 1.0.
    monkeypatch.setattr(_zm.ZoomMenu, "_instance", None, raising=False)
    assert _resolve_zoom_scale() == 1.0


# ----------------------------------------------------------------------
# 762->767 — RotationMenu.get_rotation_degrees missing
# ----------------------------------------------------------------------


def test_resolve_rotation_when_static_getter_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """762->767 — ``static_getter is None`` ⇒ fall through to the 0
    default."""
    from pypdfbox.debugger.ui import rotation_menu as _rm

    # Force a non-None _instance so we get past the first guard.
    monkeypatch.setattr(_rm.RotationMenu, "_instance", MagicMock(), raising=False)
    monkeypatch.delattr(_rm.RotationMenu, "get_rotation_degrees", raising=False)
    assert _resolve_rotation() == 0
