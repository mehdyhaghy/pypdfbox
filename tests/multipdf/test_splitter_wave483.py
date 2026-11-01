from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.multipdf import Splitter

_ACROFORM = COSName.get_pdf_name("AcroForm")
_ANNOTS = COSName.get_pdf_name("Annots")
_FIELDS = COSName.get_pdf_name("Fields")
_FT = COSName.get_pdf_name("FT")
_SIG_FLAGS = COSName.get_pdf_name("SigFlags")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _annotation(subtype: str) -> COSDictionary:
    annot = COSDictionary()
    annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annot.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return annot


def _close_all(source: PDDocument, chunks: list[PDDocument]) -> None:
    for chunk in chunks:
        chunk.close()
    source.close()


def test_wave483_process_page_exposes_source_and_destination_to_subclasses() -> None:
    class InspectingSplitter(Splitter):
        def process_page(self, page: PDPage) -> None:
            assert self.get_source_document() is source
            super().process_page(page)
            assert self.get_destination_document() is self._current_destination_document
            seen_destinations.append(self.get_destination_document())

    source = _make_doc(2)
    seen_destinations: list[PDDocument] = []

    chunks = InspectingSplitter().set_split_at_page(2).split(source)

    assert seen_destinations == [chunks[0], chunks[0]]
    assert chunks[0].get_number_of_pages() == 2
    _close_all(source, chunks)
