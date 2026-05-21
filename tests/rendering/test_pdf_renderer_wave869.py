from __future__ import annotations

from PIL import Image

import tests.rendering.test_pdf_renderer_wave512 as wave512


class _DocumentWithPage:
    def __init__(self) -> None:
        self.page_count = 1
        self.removed: list[int] = []
        self.pages: list[object] = []

    def get_number_of_pages(self) -> int:
        return self.page_count

    def remove_page(self, index: int) -> None:
        self.removed.append(index)
        self.page_count = 0

    def add_page(self, page: object) -> None:
        self.pages.append(page)


def test_wave869_make_doc_exercises_existing_page_removal(monkeypatch) -> None:
    monkeypatch.setattr(wave512, "PDDocument", _DocumentWithPage)

    doc, page = wave512._make_doc(4.0, 5.0)

    assert doc.removed == [0]
    assert doc.pages == [page]


def test_wave869_tiling_test_local_stubs_are_consumed(monkeypatch) -> None:
    def render_tiling_cell(  # noqa: ANN001
        self, pattern, *, bbox, tile_size, cell_size=None,
    ):
        assert bbox.get_width() == 1.0
        assert bbox.get_height() == 1.0
        assert bbox.get_lower_left_x() == 0.0
        assert bbox.get_lower_left_y() == 0.0
        assert pattern.get_resources() is None
        # Wave 1373: tiles are now RGBA with the gap pixels transparent.
        return Image.new("RGBA", tile_size, (0, 0, 0, 0))

    monkeypatch.setattr(wave512.PDFRenderer, "_render_tiling_cell", render_tiling_cell)

    wave512.test_render_tiling_cell_restores_resources_when_pattern_has_none()
