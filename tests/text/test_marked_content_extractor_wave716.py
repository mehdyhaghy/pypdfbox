from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFMarkedContentExtractor


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


class RecordingMarkedContentExtractor(PDFMarkedContentExtractor):
    def __init__(self) -> None:
        super().__init__()
        self.points: list[tuple[str | None, COSDictionary | None]] = []

    def marked_content_point(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        self.points.append((tag.get_name() if tag is not None else None, properties))


def test_mp_operator_dispatches_marked_content_point_without_opening_sequence() -> None:
    doc = PDDocument()
    try:
        page = _make_page_with_stream(doc, b"/Span MP\n")
        extractor = RecordingMarkedContentExtractor()

        assert extractor.process_page(page) == ""

        assert extractor.points == [("Span", None)]
        assert extractor.get_marked_contents() == []
    finally:
        doc.close()


def test_resolve_bdc_properties_tolerates_missing_or_non_dictionary_operands() -> None:
    extractor = PDFMarkedContentExtractor()

    assert extractor._resolve_bdc_properties([COSName.get_pdf_name("P")]) is None
    assert (
        extractor._resolve_bdc_properties(
            [COSName.get_pdf_name("P"), COSInteger.get(7)]
        )
        is None
    )


def test_resolve_bdc_properties_swallows_broken_resource_lookup() -> None:
    class BrokenPage:
        def get_resources(self) -> Any:
            raise RuntimeError("broken resources")

    extractor = PDFMarkedContentExtractor()
    extractor._active_page = BrokenPage()

    assert (
        extractor._resolve_bdc_properties(
            [COSName.get_pdf_name("P"), COSName.get_pdf_name("Props")]
        )
        is None
    )
