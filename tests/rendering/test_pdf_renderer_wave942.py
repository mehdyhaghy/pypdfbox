from __future__ import annotations

from typing import Any

from tests.rendering import test_pdf_renderer_wave682 as wave682


def test_wave682_make_doc_removes_existing_pages(monkeypatch: Any) -> None:
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

    monkeypatch.setattr(wave682, "PDDocument", FakeDocument)

    doc, page = wave682._make_doc()  # noqa: SLF001

    assert isinstance(doc, FakeDocument)
    assert doc.removed_indexes == [0, 0]
    assert doc.added_pages == [page]


def test_wave682_bad_ttf_units_stub_is_exercised(monkeypatch: Any) -> None:
    def draw_glyph_stub(
        _renderer: Any,
        _font: object,
        _code: int,
        ttf: Any | None,
        _glyph_set: Any | None,
        *,
        type1_units_per_em: int | None = None,
    ) -> float:
        if ttf is not None:
            assert ttf.get_units_per_em() == 1000
            return 500.0
        assert type1_units_per_em == 1000
        return 333.0

    monkeypatch.setattr(wave682.PDFRenderer, "_draw_glyph", draw_glyph_stub)

    wave682.test_draw_glyph_ttf_and_type1_failures_fall_back_cleanly(monkeypatch)
