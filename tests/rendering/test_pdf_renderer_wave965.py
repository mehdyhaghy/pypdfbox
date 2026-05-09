from __future__ import annotations

from tests.rendering import test_pdf_renderer_wave662 as wave662


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


def test_wave662_make_doc_removes_existing_pages(monkeypatch) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(wave662, "PDDocument", lambda: doc)

    returned_doc, page = wave662._make_doc()

    assert returned_doc is doc
    assert doc._pages == 0
    assert doc.added_pages == [page]


def test_wave662_function_shading_get_function_returns_none() -> None:
    shading = wave662._FunctionShading(
        domain=wave662._Domain(0.0, 1.0, 0.0, 1.0),
    )

    assert shading.get_function() is None
