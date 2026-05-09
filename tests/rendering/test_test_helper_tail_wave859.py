from __future__ import annotations

import tests.rendering.test_pdf_renderer_shading_type1 as shading_helpers
from pypdfbox.cos import COSArray, COSFloat, COSName


class _DocumentWithInitialPage:
    def __init__(self) -> None:
        self._page_count = 1
        self.removed_indices: list[int] = []
        self.pages: list[object] = []

    def get_number_of_pages(self) -> int:
        return self._page_count

    def remove_page(self, index: int) -> None:
        self.removed_indices.append(index)
        self._page_count = 0

    def add_page(self, page: object) -> None:
        self.pages.append(page)


def test_wave859_shading_make_doc_clears_existing_placeholder_page(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shading_helpers, "PDDocument", _DocumentWithInitialPage)

    doc, page = shading_helpers._make_doc(25.0, 30.0)

    assert doc.removed_indices == [0]
    assert doc.pages == [page]


def test_wave859_type4_function_helper_populates_stream_dictionary() -> None:
    function = shading_helpers._type4_postscript_function(
        [0.0, 1.0],
        [0.0, 1.0, 0.0, 1.0],
        b"dup",
    )

    assert function.get_int(COSName.get_pdf_name("FunctionType")) == 4
    assert function.get_raw_data() == b"dup"

    domain = function.get_dictionary_object(COSName.get_pdf_name("Domain"))
    range_ = function.get_dictionary_object(COSName.get_pdf_name("Range"))

    assert isinstance(domain, COSArray)
    assert isinstance(range_, COSArray)
    assert [domain.get_object(i) for i in range(domain.size())] == [
        COSFloat(0.0),
        COSFloat(1.0),
    ]
    assert [range_.get_object(i) for i in range(range_.size())] == [
        COSFloat(0.0),
        COSFloat(1.0),
        COSFloat(0.0),
        COSFloat(1.0),
    ]
