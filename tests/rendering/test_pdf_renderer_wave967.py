from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave521 as wave521


class _FakeDocument:
    def __init__(self) -> None:
        self.removed_indexes: list[int] = []
        self._pages: list[Any] = [object()]

    def get_number_of_pages(self) -> int:
        return len(self._pages)

    def get_pages(self) -> list[Any]:
        return self._pages

    def remove_page(self, index: int) -> None:
        self.removed_indexes.append(index)
        del self._pages[index]

    def add_page(self, page: Any) -> None:
        self._pages.append(page)

    def close(self) -> None:
        pass


def test_wave521_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    monkeypatch.setattr(wave521, "PDDocument", _FakeDocument)

    doc, page = wave521._make_doc()  # noqa: SLF001

    assert isinstance(doc, _FakeDocument)
    assert doc.removed_indexes == [0]
    assert doc.get_pages() == [page]


def test_wave521_render_setup_removes_existing_pages(monkeypatch: Any) -> None:
    monkeypatch.setattr(wave521, "PDDocument", _FakeDocument)

    wave521.test_render_setup_uses_media_box_origin_in_device_ctm(monkeypatch)
