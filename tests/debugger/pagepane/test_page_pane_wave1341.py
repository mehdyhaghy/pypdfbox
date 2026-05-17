"""Wave-1341 coverage-boost tests for
:mod:`pypdfbox.debugger.pagepane.page_pane`.

Targets the residual ImportError/exception fallback branches:

* ``collect_link_locations`` — ``PDAnnotationLink`` import failure
  (lines 172-173);
* ``collect_link_location`` — primary import block failure with the
  URI-only retry succeeding (lines 206-217), plus the
  ``PDActionGoTo is None or PDPageDestination is None`` short-circuit
  for actions that aren't ``PDActionURI`` (line 227);
* ``start_extracting`` — missing text-extraction dependency
  (lines 336-338) and the ``PDFTextStripper`` raising ``OSError``
  (lines 356-358);
* :class:`RenderWorker.do_in_background` — rotation branch when
  ``ImageUtil.get_rotated_image`` raises ``ValueError``
  (lines 789-790).
"""

from __future__ import annotations

import importlib
import sys
import tkinter as tk
from collections.abc import Iterator
from typing import Any

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import (
    PagePane,
    RenderWorker,
    _resolve_rotation,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc(
    content: bytes | None = b"BT /F0 12 Tf 10 50 Td (x) Tj ET",
) -> PDDocument:
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


def _force_module_import_error(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Force ``import name`` to raise ``ImportError`` for the duration of
    the test. Removes any cached entry and installs a sentinel that
    triggers ModuleNotFoundError via Python's import machinery."""
    if name in sys.modules:
        monkeypatch.setitem(sys.modules, name, None)
    else:
        monkeypatch.setitem(sys.modules, name, None)


# ---------- collect_link_locations: PDAnnotationLink import fallback -----


def test_collect_link_locations_swallows_link_import_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the inline import of ``PDAnnotationLink`` raises ImportError,
    ``collect_link_locations`` returns silently (lines 172-173)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        _force_module_import_error(
            monkeypatch,
            "pypdfbox.pdmodel.interactive.annotation.pd_annotation_link",
        )
        pane.collect_link_locations()  # must not raise
    finally:
        doc.close()


# ---------- collect_link_location: primary-import fallback w/ URI retry --


def test_collect_link_location_primary_import_fallback_uri_retry(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the four-module primary import block fails (e.g. PDActionGoTo
    is unavailable), the URI-only retry import succeeds and the
    ``PDActionGoTo is None`` guard short-circuits non-URI actions
    (lines 206-211, 213-215, 218-227)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Force the primary import to fail by blocking PDActionGoTo only.
        _force_module_import_error(
            monkeypatch,
            "pypdfbox.pdmodel.interactive.action.pd_action_go_to",
        )

        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(0.0, 0.0, 10.0, 10.0))

        # Wire a non-URI action so the action isinstance(PDActionURI)
        # branch on line 222 is skipped, exercising the
        # ``PDActionGoTo is None`` short-circuit at line 226-227.
        sentinel_action = object()

        def _get_action() -> object:
            return sentinel_action

        link.get_action = _get_action  # type: ignore[method-assign]
        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(link)
        # No /URI nor /GoTo handler available → map unchanged.
        assert dict(pane._rect_map) == before  # noqa: SLF001
    finally:
        doc.close()


def test_collect_link_location_primary_and_uri_both_unavailable_returns(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both the primary import block and the URI-only retry raise
    ImportError, the helper returns silently (lines 216-217)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Force BOTH the primary block (via pd_action_go_to) and the
        # inner URI-only retry to fail.
        _force_module_import_error(
            monkeypatch,
            "pypdfbox.pdmodel.interactive.action.pd_action_go_to",
        )
        _force_module_import_error(
            monkeypatch,
            "pypdfbox.pdmodel.interactive.action.pd_action_uri",
        )

        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(0.0, 0.0, 10.0, 10.0))
        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(link)  # must not raise
        assert dict(pane._rect_map) == before  # noqa: SLF001
    finally:
        doc.close()


# ---------- start_extracting: ImportError + OSError paths ----------------


def test_start_extracting_handles_text_stripper_import_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If text extraction dependencies are missing,
    ``start_extracting`` logs and returns (lines 336-338)."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        _force_module_import_error(
            monkeypatch, "pypdfbox.text.pdf_text_stripper"
        )
        pane.start_extracting()  # must not raise
    finally:
        doc.close()


def test_start_extracting_handles_text_strip_oserror(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch, _reset_menus: None,
) -> None:
    """If ``PDFTextStripper.get_text`` raises ``OSError``, the helper
    logs and returns (lines 356-358)."""
    from pypdfbox.text import pdf_text_stripper

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Patch the stripper class's get_text to raise OSError. Use the
        # actual class object so the import-side of the call resolves to
        # the monkeypatched method.
        def _boom(self: Any, document: Any) -> str:  # noqa: ARG001
            raise OSError("simulated I/O failure")

        monkeypatch.setattr(
            pdf_text_stripper.PDFTextStripper, "get_text", _boom
        )
        pane.start_extracting()  # must not raise
    finally:
        doc.close()


# ---------- RenderWorker rotation: ImageUtil ValueError swallowed -------


def test_render_worker_swallows_rotation_value_error(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch, _reset_menus: None,
) -> None:
    """When ``ImageUtil.get_rotated_image`` raises ``ValueError`` (e.g.
    unsupported rotation angle), :meth:`RenderWorker.do_in_background`
    swallows it and returns the un-rotated image (lines 789-790)."""
    from pypdfbox.debugger.ui import image_util
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu

    RotationMenu.get_instance(master=tk_root).set_rotation_selection(
        RotationMenu.ROTATE_90_DEGREES
    )
    assert _resolve_rotation() != 0

    def _boom(image: Any, angle: int) -> Any:  # noqa: ARG001
        raise ValueError("simulated rotation failure")

    monkeypatch.setattr(image_util.ImageUtil, "get_rotated_image", _boom)

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        worker = RenderWorker(pane)
        image = worker.do_in_background()
        # Falls through to return the un-rotated image.
        assert image is not None
    finally:
        doc.close()


# Silence the unused-import warning for the monkeypatch helper.
_ = importlib  # noqa: F841
