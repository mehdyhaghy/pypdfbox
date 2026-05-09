from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave592 as wave592


def test_wave592_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
    class FakeDocument:
        def __init__(self) -> None:
            self.removed_indexes: list[int] = []
            self.added_pages: list[Any] = []
            self._remaining_pages = 2

        def get_number_of_pages(self) -> int:
            return self._remaining_pages

        def remove_page(self, index: int) -> None:
            self.removed_indexes.append(index)
            self._remaining_pages -= 1

        def add_page(self, page: Any) -> None:
            self.added_pages.append(page)

    monkeypatch.setattr(wave592, "PDDocument", FakeDocument)

    doc, page = wave592._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0, 0]
    assert doc.added_pages == [page]


def test_wave592_tiling_stub_accessors_are_exercised(monkeypatch: Any) -> None:
    def render_cell_stub(
        _renderer: Any,
        pattern: Any,
        *,
        bbox: Any,
        tile_size: tuple[int, int],
    ) -> None:
        assert tile_size == (2, 2)
        pattern.get_resources()
        bbox.get_lower_left_x()
        bbox.get_lower_left_y()
        return None

    monkeypatch.setattr(wave592.PDFRenderer, "_render_tiling_cell", render_cell_stub)

    wave592.test_render_tiling_cell_rejects_non_stream_and_degenerate_bbox()
