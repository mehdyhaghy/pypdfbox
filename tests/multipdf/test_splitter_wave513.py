from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull
from pypdfbox.multipdf import Splitter

_ACROFORM = COSName.get_pdf_name("AcroForm")
_ANNOTS = COSName.get_pdf_name("Annots")
_B = COSName.get_pdf_name("B")
_FIELDS = COSName.get_pdf_name("Fields")
_FIT = COSName.get_pdf_name("Fit")
_FT = COSName.get_pdf_name("FT")
_PARENT = COSName.get_pdf_name("Parent")
_SIG_FLAGS = COSName.get_pdf_name("SigFlags")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _field(field_type: str) -> COSDictionary:
    field = COSDictionary()
    field.set_item(_FT, COSName.get_pdf_name(field_type))
    return field


def _dest_array(page_dict: COSDictionary) -> COSArray:
    dest = COSArray()
    dest.add(page_dict)
    dest.add(_FIT)
    return dest


def test_wave513_scrub_acroform_keeps_non_signature_fields() -> None:
    doc = PDDocument()
    acroform = COSDictionary()
    acroform.set_int(_SIG_FLAGS, 3)
    fields = COSArray()
    sig_field = _field("Sig")
    text_field = _field("Tx")
    fields.add(sig_field)
    fields.add(text_field)
    acroform.set_item(_FIELDS, fields)
    doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)

    try:
        Splitter()._scrub_acroform(doc)  # noqa: SLF001

        assert not acroform.contains_key(_SIG_FLAGS)
        kept_fields = acroform.get_dictionary_object(_FIELDS)
        assert isinstance(kept_fields, COSArray)
        assert kept_fields.size() == 1
        assert kept_fields.get_object(0) is text_field
        assert doc.get_document_catalog().get_cos_object().contains_key(_ACROFORM)
    finally:
        doc.close()


def test_wave513_scrub_acroform_removes_empty_signature_only_form() -> None:
    doc = PDDocument()
    acroform = COSDictionary()
    acroform.set_item(_TYPE, COSName.get_pdf_name("AcroForm"))
    fields = COSArray()
    fields.add(_field("Sig"))
    acroform.set_item(_FIELDS, fields)
    doc.get_document_catalog().get_cos_object().set_item(_ACROFORM, acroform)

    try:
        Splitter()._scrub_acroform(doc)  # noqa: SLF001

        assert not doc.get_document_catalog().get_cos_object().contains_key(_ACROFORM)
    finally:
        doc.close()


def test_wave513_fix_destinations_nulls_target_outside_chunk() -> None:
    source = _make_doc(2)
    chunk = _make_doc(1)
    source_pages = list(source.get_pages())
    dest = _dest_array(source_pages[1].get_cos_object())
    splitter = Splitter()
    splitter._dest_to_fix = [(dest, source_pages[0].get_cos_object())]  # noqa: SLF001
    splitter._page_dict_map = {  # noqa: SLF001
        id(source_pages[0].get_cos_object()): chunk.get_page(0).get_cos_object()
    }

    try:
        splitter._fix_destinations(chunk)  # noqa: SLF001

        assert dest.get(0) is COSNull.NULL
    finally:
        source.close()
        chunk.close()


def test_wave513_process_annotations_drops_widget_parent_on_clone() -> None:
    source_page = PDPage()
    imported = PDPage()
    parent = COSDictionary()
    parent.set_item(_FT, COSName.get_pdf_name("Tx"))
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    widget.set_item(_PARENT, parent)
    annots = COSArray()
    annots.add(widget)
    imported.get_cos_object().set_item(_ANNOTS, annots)

    Splitter()._process_annotations(source_page, imported)  # noqa: SLF001

    cloned_annots = imported.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    cloned_widget = cloned_annots.get_object(0)
    assert isinstance(cloned_widget, COSDictionary)
    assert cloned_widget is not widget
    assert not cloned_widget.contains_key(_PARENT)
    assert widget.get_dictionary_object(_PARENT) is parent


def test_wave513_process_page_removes_beads_from_imported_page() -> None:
    source = _make_doc(1)
    source.get_page(0).get_cos_object().set_item(_B, COSArray())
    splitter = Splitter()
    splitter._source_document = source  # noqa: SLF001

    try:
        splitter.process_page(source.get_page(0))

        imported = splitter.get_destination_document().get_page(0)
        assert not imported.get_cos_object().contains_key(_B)
    finally:
        for chunk in splitter._destination_documents:  # noqa: SLF001
            chunk.close()
        source.close()
