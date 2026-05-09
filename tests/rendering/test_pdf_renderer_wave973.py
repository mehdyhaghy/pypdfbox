from __future__ import annotations

from tests.rendering import test_pdf_renderer_shading_mesh as mesh_tests


class _DocWithExistingPage:
    def __init__(self) -> None:
        self.removed_pages: list[int] = []
        self.added_pages: list[object] = [object()]

    def get_number_of_pages(self) -> int:
        return len(self.added_pages)

    def remove_page(self, index: int) -> None:
        self.removed_pages.append(index)
        self.added_pages.pop(index)

    def add_page(self, page: object) -> None:
        self.added_pages.append(page)


def test_wave973_make_doc_removes_default_pages(monkeypatch) -> None:
    doc = _DocWithExistingPage()
    monkeypatch.setattr(mesh_tests, "PDDocument", lambda: doc)

    made_doc, page = mesh_tests._make_doc(24.0, 36.0)

    assert made_doc is doc
    assert doc.removed_pages == [0]
    assert doc.added_pages == [page]
    assert page.get_media_box().get_width() == 24.0
    assert page.get_media_box().get_height() == 36.0


def test_wave973_is_close_uses_rgb_tolerance() -> None:
    assert mesh_tests._is_close((10, 20, 30), (22, 8, 40))
    assert not mesh_tests._is_close((10, 20, 30), (23, 8, 40))
