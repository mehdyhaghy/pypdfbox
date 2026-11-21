"""PDFBOX-6170: ``PDDocument.add_font_for_subsetting``."""

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class _FakeFont:
    def __init__(self, subset: bool) -> None:
        self._subset = subset

    def will_be_subset(self) -> bool:
        return self._subset

    def get_name(self) -> str:
        return "Fake"


def test_add_font_for_subsetting_queues_subset_font() -> None:
    with PDDocument() as doc:
        font = _FakeFont(True)
        doc.add_font_for_subsetting(font)
        assert font in doc.get_fonts_to_subset()


def test_add_font_for_subsetting_rejects_non_subset_font() -> None:
    with PDDocument() as doc:
        with pytest.raises(ValueError, match="The font Fake doesn't support subsetting"):
            doc.add_font_for_subsetting(_FakeFont(False))
        assert not doc.get_fonts_to_subset()


def test_add_font_for_subsetting_rejects_standard14_font() -> None:
    with PDDocument() as doc:
        font = PDType1Font(FontName.HELVETICA)
        with pytest.raises(ValueError, match="doesn't support subsetting"):
            doc.add_font_for_subsetting(font)


def test_set_font_routes_through_add_font_for_subsetting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        calls: list[object] = []
        monkeypatch.setattr(doc, "add_font_for_subsetting", calls.append)
        font = PDType1Font(FontName.HELVETICA)
        monkeypatch.setattr(font, "will_be_subset", lambda: True)
        with PDPageContentStream(doc, page) as cs:
            cs.set_font(font, 12)
        assert calls == [font]
