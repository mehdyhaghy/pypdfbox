"""Tests for the new public dispatch methods on :class:`PagePane`.

Covers the promotion of ``_start_rendering`` → :py:meth:`PagePane.start_rendering`
and the freshly-ported :py:meth:`PagePane.start_extracting`. These mirror
upstream ``startRendering()`` / ``startExtracting()`` (PDFBox 3.0).
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.cos import COSStream
from pypdfbox.debugger.pagepane.page_pane import PagePane
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def _make_one_page_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 60.0, 60.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 12 Tf 5 10 Td (x) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)
    return doc


def test_start_rendering_is_public_alias_of_underscore(tk_root: tk.Tk) -> None:
    """``_start_rendering`` should be the underscore back-compat alias."""
    assert PagePane._start_rendering is PagePane.start_rendering  # noqa: SLF001


def test_start_rendering_places_image_on_canvas(tk_root: tk.Tk) -> None:
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()
        # Re-invoke the public method directly — it should be idempotent
        # (clearing the canvas tag and creating a new image item).
        pane.start_rendering()
        canvas = pane._canvas  # noqa: SLF001
        assert canvas is not None
        items = canvas.find_withtag("rendered_page")
        assert items, "expected a rendered page image after start_rendering()"
    finally:
        doc.close()


def test_start_extracting_invokes_stripper_and_dialog(
    tk_root: tk.Tk, monkeypatch
) -> None:
    """``start_extracting`` should drive PDFTextStripper + TextDialog.

    We don't depend on the real stripper / dialog — both are
    monkeypatched so the test works headlessly and asserts only the
    dispatch path.
    """
    doc = _make_one_page_doc()
    try:
        page_dict = doc.get_page(0).get_cos_object()
        pane = PagePane(tk_root, doc, page_dict, statuslabel=None)
        pane.init()

        captured: dict[str, object] = {}

        class _FakeStripper:
            def __init__(self) -> None:
                captured["constructed"] = True

            def set_start_page(self, n: int) -> None:
                captured["start"] = n

            def set_end_page(self, n: int) -> None:
                captured["end"] = n

            def set_sort_by_position(self, flag: bool) -> None:
                captured["sorted"] = flag

            def get_text(self, document: PDDocument) -> str:
                captured["doc"] = document
                return "extracted-text-payload"

        class _FakeDialog:
            text: str = ""
            visible: bool = False

            @classmethod
            def instance(cls) -> _FakeDialog:
                return cls()

            def set_text(self, value: str) -> None:
                captured["dialog_text"] = value

            def set_visible(self, visible: bool) -> None:
                captured["dialog_visible"] = visible

        import pypdfbox.text.pdf_text_stripper as stripper_mod
        import pypdfbox.debugger.ui.text_dialog as dialog_mod

        monkeypatch.setattr(stripper_mod, "PDFTextStripper", _FakeStripper)
        monkeypatch.setattr(dialog_mod, "TextDialog", _FakeDialog)

        pane.start_extracting()
        assert captured.get("constructed") is True
        assert captured.get("start") == 1
        assert captured.get("end") == 1
        assert captured.get("dialog_text") == "extracted-text-payload"
        assert captured.get("dialog_visible") is True
    finally:
        doc.close()


def test_start_extracting_no_op_when_orphan_page(tk_root: tk.Tk) -> None:
    """An orphan page (pageIndex < 0) should short-circuit, matching upstream."""
    doc = _make_one_page_doc()
    try:
        orphan = PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0))
        pane = PagePane(tk_root, doc, orphan.get_cos_object(), statuslabel=None)
        pane.init()
        # Should not raise even though no TextDialog is wired up.
        pane.start_extracting()
    finally:
        doc.close()
