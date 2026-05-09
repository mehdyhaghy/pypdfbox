from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
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


def test_wave483_sig_only_acroform_is_removed_from_split_chunk() -> None:
    class AcroFormCopyingSplitter(Splitter):
        def create_new_document(self) -> PDDocument:
            document = super().create_new_document()
            acroform = (
                self.get_source_document()
                .get_document_catalog()
                .get_cos_object()
                .get_dictionary_object(_ACROFORM)
            )
            document.get_document_catalog().get_cos_object().set_item(
                _ACROFORM, acroform
            )
            return document

    source = _make_doc(1)
    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    fields = COSArray()
    fields.add(sig_field)
    acroform = COSDictionary()
    acroform.set_item(_TYPE, COSName.get_pdf_name("AcroForm"))
    acroform.set_item(_SIG_FLAGS, COSInteger.get(3))
    acroform.set_item(_FIELDS, fields)
    source.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)

    widget = _annotation("Widget")
    widget.set_item(_FT, COSName.get_pdf_name("Sig"))
    annots = COSArray()
    annots.add(widget)
    source.get_page(0).get_cos_object().set_item(_ANNOTS, annots)

    chunks = AcroFormCopyingSplitter().split(source)

    catalog = chunks[0].get_document_catalog().get_cos_object()
    assert chunks[0].get_page(0).get_annotations() == []
    assert not catalog.contains_key(_ACROFORM)
    _close_all(source, chunks)
