"""Wave-1332 coverage-boost tests for ``pypdfbox.debugger.pagepane.page_pane``.

Pre-wave coverage was 88% (52 lines missing). The dropped lines fall in
three buckets:

* ``collect_link_location`` destination-action paths
  (``PDActionGoTo`` / ``PDNamedDestination`` / ``PDPageDestination``)
  and the ``get_action`` ``AttributeError`` swallow (206-217, 220-221,
  226-250);
* ``start_extracting`` import/error paths (336-338, 353-354, 356-358,
  362);
* :class:`RenderWorker` execute-failure + ``ImageUtil`` rotation
  branches (758-761, 783-790).

All tests honour ``PYPDFBOX_SKIP_TK=1`` via the existing ``tk_root``
fixture from the package conftest.
"""

from __future__ import annotations

import logging
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


# ---------- collect_link_location: action error + destination paths ------


def test_collect_link_location_swallows_get_action_attribute_error(
    tk_root: tk.Tk,
) -> None:
    """A link whose ``get_action`` raises ``AttributeError`` is skipped."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        before = dict(pane._rect_map)  # noqa: SLF001
        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(0.0, 0.0, 10.0, 10.0))

        def _boom() -> None:
            raise AttributeError("no action")

        link.get_action = _boom  # type: ignore[method-assign]
        pane.collect_link_location(link)
        # No new entries.
        assert pane._rect_map == before  # noqa: SLF001
    finally:
        doc.close()


def test_collect_link_location_with_pd_action_go_to_page_destination(
    tk_root: tk.Tk,
) -> None:
    """``PDActionGoTo`` -> ``PDPageDestination`` resolves to ``Page destination: N``."""
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
        PDPageFitDestination,
    )

    doc = _make_one_page_doc()
    try:
        page = doc.get_page(0)
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        destination = PDPageFitDestination()
        destination.set_page_number(2)
        # ``retrieve_page_number`` defers to the array; on a number-form
        # destination it returns 2 directly without needing a parent chain.

        class _FakeLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(5.0, 5.0, 25.0, 25.0)

            def get_action(self) -> Any:
                fake = PDActionGoTo()
                fake.get_destination = lambda: destination  # type: ignore[method-assign]
                return fake

        pane.collect_link_location(_FakeLink())
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("Page destination: 3" in label for label in labels)
    finally:
        doc.close()


def test_collect_link_location_named_destination_resolved_via_catalog(
    tk_root: tk.Tk,
) -> None:
    """A named destination -> catalog ``find_named_destination_page`` resolution."""
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: E501
        PDNamedDestination,
    )
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
        PDPageFitDestination,
    )

    doc = _make_one_page_doc()
    try:
        page = doc.get_page(0)
        catalog = doc.get_document_catalog()
        page_dict = page.get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Set up a named destination resolver on the catalog.
        named = PDNamedDestination("MyAnchor")
        resolved = PDPageFitDestination()
        resolved.set_page_number(0)

        def _resolver(named_dest: object) -> object:
            return resolved

        catalog.find_named_destination_page = _resolver  # type: ignore[method-assign]

        class _FakeLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(2.0, 2.0, 12.0, 12.0)

            def get_action(self) -> Any:
                fake = PDActionGoTo()
                fake.get_destination = lambda: named  # type: ignore[method-assign]
                return fake

        pane.collect_link_location(_FakeLink())
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("Page destination" in label for label in labels)
    finally:
        doc.close()


def test_collect_link_location_destination_resolution_error_is_logged(
    tk_root: tk.Tk, caplog: pytest.LogCaptureFixture,
) -> None:
    """If destination resolution raises ``OSError``, the failure is logged."""
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Build a fake link wrapper that returns a PDActionGoTo whose
        # ``get_destination`` raises OSError. We bypass PDAnnotationLink's
        # /A round-trip (which would lose our patched method) by returning
        # the action directly from ``get_action``.
        action = PDActionGoTo()

        def _boom() -> None:
            raise OSError("destination kaboom")

        action.get_destination = _boom  # type: ignore[method-assign]

        class _FakeLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(0.0, 0.0, 10.0, 10.0)

            def get_action(self) -> Any:
                return action

        with caplog.at_level(
            logging.ERROR, logger="pypdfbox.debugger.pagepane.page_pane"
        ):
            pane.collect_link_location(_FakeLink())
        assert any(
            "resolving link destination" in rec.message for rec in caplog.records
        )
    finally:
        doc.close()


def test_collect_link_location_page_destination_with_invalid_page_returns(
    tk_root: tk.Tk,
) -> None:
    """A ``PDPageDestination`` whose ``retrieve_page_number`` raises is skipped."""
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
        PDPageFitDestination,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        destination = PDPageFitDestination()

        def _kaboom() -> int:
            raise OSError("can't retrieve")

        destination.retrieve_page_number = _kaboom  # type: ignore[method-assign]

        class _FakeLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(0.0, 0.0, 10.0, 10.0)

            def get_action(self) -> Any:
                fake_action = PDActionGoTo()
                fake_action.get_destination = lambda: destination  # type: ignore[method-assign]
                return fake_action

        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(_FakeLink())
        # No new entry.
        assert pane._rect_map == before  # noqa: SLF001
    finally:
        doc.close()


def test_collect_link_location_non_goto_action_falls_back_to_link_get_destination(
    tk_root: tk.Tk,
) -> None:
    """When ``action`` is not a ``PDActionGoTo``, the link's own
    ``get_destination`` is consulted (parity with upstream's
    ``PDAnnotationLink.getDestination`` fallback)."""
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
        PDPageFitDestination,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        # Build a destination with page number 0 (i.e. label "Page destination: 1").
        destination = PDPageFitDestination()
        destination.set_page_number(0)

        class _LinkWithDestination:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(1.0, 1.0, 9.0, 9.0)

            def get_action(self) -> Any:
                # Some non-GoTo, non-URI action — falls into the
                # ``else`` branch that consults ``link.get_destination``.
                class _OtherAction:
                    pass

                return _OtherAction()

            def get_destination(self) -> Any:
                return destination

        pane.collect_link_location(_LinkWithDestination())
        labels = list(pane._rect_map.values())  # noqa: SLF001
        assert any("Page destination" in label for label in labels)
    finally:
        doc.close()


def test_collect_link_location_no_link_get_destination_returns_none(
    tk_root: tk.Tk,
) -> None:
    """When the link has no ``get_destination`` either, nothing is recorded."""

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        class _NoDestLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(0.0, 0.0, 4.0, 4.0)

            def get_action(self) -> Any:
                return object()  # neither PDActionGoTo nor PDActionURI

        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(_NoDestLink())
        assert pane._rect_map == before  # noqa: SLF001
    finally:
        doc.close()


def test_collect_link_location_page_destination_returning_negative_one_skipped(
    tk_root: tk.Tk,
) -> None:
    """``retrieve_page_number`` returning ``-1`` short-circuits without recording."""
    from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
    from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (  # noqa: E501
        PDPageFitDestination,
    )

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        destination = PDPageFitDestination()
        destination.retrieve_page_number = lambda: -1  # type: ignore[method-assign]

        class _FakeLink:
            def get_rectangle(self) -> PDRectangle:
                return PDRectangle(0.0, 0.0, 10.0, 10.0)

            def get_action(self) -> Any:
                fake_action = PDActionGoTo()
                fake_action.get_destination = lambda: destination  # type: ignore[method-assign]
                return fake_action

        before = dict(pane._rect_map)  # noqa: SLF001
        pane.collect_link_location(_FakeLink())
        assert pane._rect_map == before  # noqa: SLF001
    finally:
        doc.close()


# ---------- start_extracting ----------------------------------------------


def test_start_extracting_returns_early_for_orphan_page(tk_root: tk.Tk) -> None:
    """An orphan page (page_index < 0) short-circuits ``start_extracting``."""
    doc = _make_one_page_doc()
    try:
        orphan = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
        pane = PagePane(tk_root, doc, orphan.get_cos_object(), statuslabel=None)
        pane.init()
        # No raise.
        pane.start_extracting()
    finally:
        doc.close()


def test_start_extracting_runs_on_valid_page(
    tk_root: tk.Tk, _reset_menus: None,
) -> None:
    """A regular page exercises the text-strip + dialog instance lookup path."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # No raise; the path either finds no dialog instance (None) or
        # silently swallows the setter failure.
        pane.start_extracting()
    finally:
        doc.close()


# ---------- RenderWorker exception + rotation paths ----------------------


def test_render_worker_execute_swallows_oserror(tk_root: tk.Tk) -> None:
    """``RenderWorker.execute`` returns ``None`` when ``do_in_background`` raises."""

    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        worker = RenderWorker(pane)

        def _boom() -> Any:
            raise OSError("render failed")

        worker.do_in_background = _boom  # type: ignore[method-assign]
        assert worker.execute() is None
        assert worker.get() is None
    finally:
        doc.close()


def test_render_worker_applies_rotation_when_nonzero(
    tk_root: tk.Tk, _reset_menus: None,
) -> None:
    """A non-zero rotation triggers the ``ImageUtil.get_rotated_image`` branch."""
    from pypdfbox.debugger.ui.rotation_menu import RotationMenu

    RotationMenu.get_instance(master=tk_root).set_rotation_selection(
        RotationMenu.ROTATE_90_DEGREES
    )
    assert _resolve_rotation() != 0
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        worker = RenderWorker(pane)
        # Should render + rotate without raising.
        image = worker.do_in_background()
        assert image is not None
    finally:
        doc.close()


def test_render_worker_done_with_no_result_is_noop(tk_root: tk.Tk) -> None:
    """``done()`` is a no-op when no image has been produced."""
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        worker = RenderWorker(pane)
        # Must not raise even without execute() first.
        worker.done()
    finally:
        doc.close()
