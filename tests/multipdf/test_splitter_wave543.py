from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

_ANNOTS = COSName.get_pdf_name("Annots")
_CUSTOM = COSName.get_pdf_name("Custom")
_FIT = COSName.get_pdf_name("Fit")
_LABEL = COSName.get_pdf_name("Wave543Label")
_NESTED = COSName.get_pdf_name("Nested")
_POPUP = COSName.get_pdf_name("Popup")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")


def _make_labeled_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for index in range(page_count):
        page = PDPage()
        page.get_cos_object().set_string(_LABEL, f"page-{index + 1}")
        doc.add_page(page)
    return doc


def test_wave543_split_respects_start_end_range_and_split_alignment() -> None:
    source = _make_labeled_doc(6)
    splitter = Splitter().set_start_page(2).set_end_page(5).set_split_at_page(2)

    chunks = splitter.split(source)

    try:
        assert [chunk.get_number_of_pages() for chunk in chunks] == [2, 2]
        assert [
            chunk.get_page(index).get_cos_object().get_string(_LABEL)
            for chunk in chunks
            for index in range(chunk.get_number_of_pages())
        ] == ["page-2", "page-3", "page-4", "page-5"]
        assert splitter.get_source_document() is source
        assert splitter.get_destination_document() is chunks[-1]
    finally:
        for chunk in chunks:
            chunk.close()
        source.close()


def test_wave543_create_new_document_copies_sanitized_info_and_version() -> None:
    source = _make_labeled_doc(1)
    source.set_version(1.7)
    info_dict = COSDictionary()
    info_dict.set_string("Title", "Wave 543")
    info_dict.set_item(_TYPE, COSName.get_pdf_name("Info"))
    info_dict.set_item(_NESTED, COSDictionary())
    info_dict.set_string(_CUSTOM, "kept")
    source.set_document_information(PDDocumentInformation(info_dict))

    chunks = Splitter().split(source)

    try:
        assert len(chunks) == 1
        copied_info = chunks[0].get_document_information().get_cos_object()
        assert chunks[0].get_version() == 1.7
        assert copied_info.get_string("Title") == "Wave 543"
        assert copied_info.get_string(_CUSTOM) == "kept"
        assert not copied_info.contains_key(_TYPE)
        assert not copied_info.contains_key(_NESTED)
    finally:
        for chunk in chunks:
            chunk.close()
        source.close()


def test_wave543_process_annotations_rewrites_popup_to_cloned_popup() -> None:
    source_page = PDPage()
    imported = PDPage()
    markup = COSDictionary()
    markup.set_item(_SUBTYPE, COSName.get_pdf_name("Text"))
    popup = COSDictionary()
    popup.set_item(_SUBTYPE, COSName.get_pdf_name("Popup"))
    markup.set_item(_POPUP, popup)
    annots = COSArray()
    annots.add(markup)
    annots.add(popup)
    imported.get_cos_object().set_item(_ANNOTS, annots)

    splitter = Splitter()
    # Wave 1373: chunk-level deferred second pass; drain manually.
    splitter._pending_annot_passes = []  # noqa: SLF001
    splitter._process_annotations(source_page, imported)  # noqa: SLF001
    splitter._finalize_annotation_links()  # noqa: SLF001

    cloned_annots = imported.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    cloned_markup = cloned_annots.get_object(0)
    cloned_popup = cloned_annots.get_object(1)
    assert isinstance(cloned_markup, COSDictionary)
    assert isinstance(cloned_popup, COSDictionary)
    assert cloned_markup is not markup
    assert cloned_popup is not popup
    assert cloned_markup.get_dictionary_object(_POPUP) is cloned_popup
    assert markup.get_dictionary_object(_POPUP) is popup


def test_wave543_fix_destinations_ignores_non_page_targets() -> None:
    source = _make_labeled_doc(1)
    chunk = _make_labeled_doc(1)
    dest = COSArray()
    dest.add(COSName.get_pdf_name("NamedTarget"))
    dest.add(_FIT)
    splitter = Splitter()
    splitter._dest_to_fix = [(dest, source.get_page(0).get_cos_object())]  # noqa: SLF001
    splitter._page_dict_map = {  # noqa: SLF001
        id(source.get_page(0).get_cos_object()): chunk.get_page(0).get_cos_object()
    }

    try:
        splitter._fix_destinations(chunk)  # noqa: SLF001

        assert dest.get(0) is COSName.get_pdf_name("NamedTarget")
    finally:
        source.close()
        chunk.close()
