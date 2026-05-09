from __future__ import annotations

import logging
from typing import Any

from tests.rendering import test_pdf_renderer_wave531 as wave531


class _DocWithExistingPage:
    def __init__(self) -> None:
        self._pages = 1
        self.added_pages = []

    def get_number_of_pages(self) -> int:
        return self._pages

    def remove_page(self, index: int) -> None:
        assert index == 0
        self._pages -= 1

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)


def test_wave531_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(wave531, "PDDocument", lambda: doc)

    returned_doc, page = wave531._make_doc()

    assert returned_doc is doc
    assert doc._pages == 0
    assert doc.added_pages == [page]


def test_wave531_dispatch_test_restores_existing_handler(caplog: Any) -> None:
    def original_handler(
        _renderer: wave531.PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise AssertionError("should be restored, not called")

    previous = wave531.renderer_mod._DISPATCH.get("W531")  # noqa: SLF001
    wave531.renderer_mod._DISPATCH["W531"] = original_handler  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        wave531.test_process_operator_logs_and_swallows_handler_value_error(caplog)

        assert wave531.renderer_mod._DISPATCH["W531"] is original_handler  # noqa: SLF001
    finally:
        if previous is None:
            wave531.renderer_mod._DISPATCH.pop("W531", None)  # noqa: SLF001
        else:
            wave531.renderer_mod._DISPATCH["W531"] = previous  # noqa: SLF001
