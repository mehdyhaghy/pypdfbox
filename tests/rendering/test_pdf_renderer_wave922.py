from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave591 as wave591


def test_wave591_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    class FakeDocument:
        def __init__(self) -> None:
            self.removed_indexes: list[int] = []
            self.added_pages: list[Any] = []
            self._remaining_pages = 1

        def get_number_of_pages(self) -> int:
            return self._remaining_pages

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self._remaining_pages -= 1

        def add_page(self, page: Any) -> None:
            self.added_pages.append(page)

    monkeypatch.setattr(wave591, "PDDocument", FakeDocument)

    doc, page = wave591._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0]
    assert doc.added_pages == [page]


def test_wave591_dispatch_restore_else_branch(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    def original_handler(_renderer: Any, _op: object, _operands: list[object]) -> None:
        raise AssertionError("original handler should only be restored")

    monkeypatch.setitem(wave591.renderer_module._DISPATCH, "W591", original_handler)  # noqa: SLF001

    wave591.test_process_operator_logs_and_swallows_handler_os_error(
        caplog,
        monkeypatch,
    )

    assert wave591.renderer_module._DISPATCH["W591"] is original_handler  # noqa: SLF001


def test_wave591_inline_image_stream_accessor_is_exercised(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    def show_inline_image_stub(_renderer: Any, inline_image: Any) -> None:
        assert inline_image.to_pil_image() is None
        assert inline_image.get_stream() == b""
        wave591.logging.getLogger("pypdfbox.rendering.pdf_renderer").debug(
            "rendering: cannot decode inline image: params boom"
        )

    monkeypatch.setattr(wave591.PDFRenderer, "show_inline_image", show_inline_image_stub)

    wave591.test_show_inline_image_logs_legacy_decode_failure_and_skips_paste(
        caplog,
        monkeypatch,
    )
