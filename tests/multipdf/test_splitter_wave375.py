from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.multipdf import Splitter

_A = COSName.get_pdf_name("A")
_B = COSName.get_pdf_name("B")
_D = COSName.get_pdf_name("D")
_POPUP = COSName.get_pdf_name("Popup")
_RESOURCES = COSName.get_pdf_name("Resources")
_S = COSName.get_pdf_name("S")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TITLE = COSName.get_pdf_name("Title")
_TYPE = COSName.get_pdf_name("Type")


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def _close_all(src: PDDocument, chunks: list[PDDocument]) -> None:
    for chunk in chunks:
        chunk.close()
    src.close()


def _annotation(subtype: str) -> COSDictionary:
    annot = COSDictionary()
    annot.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    annot.set_item(_SUBTYPE, COSName.get_pdf_name(subtype))
    return annot


def test_wave375_process_page_copies_inherited_resources_and_removes_beads() -> None:
    src = _make_doc(1)
    page = src.get_page(0)

    resources = COSDictionary()
    proc_set = COSArray()
    proc_set.add(COSName.get_pdf_name("PDF"))
    resources.set_item(COSName.get_pdf_name("ProcSet"), proc_set)
    parent = page.get_cos_parent()
    assert parent is not None
    parent.set_item(_RESOURCES, resources)
    page.get_cos_object().set_item(_B, COSArray())
    assert not page.get_cos_object().contains_key(_RESOURCES)

    chunks = Splitter().split(src)

    imported_dict = chunks[0].get_page(0).get_cos_object()
    assert imported_dict.get_dictionary_object(_RESOURCES) is resources
    assert not imported_dict.contains_key(_B)
    _close_all(src, chunks)


def test_wave375_popup_annotation_reference_is_rewritten_to_cloned_popup() -> None:
    source_page = PDPage()
    imported = PDPage()
    popup = _annotation("Popup")
    text = _annotation("Text")
    text.set_item(_POPUP, popup)
    annots = COSArray()
    annots.add(text)
    annots.add(popup)
    imported.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    Splitter()._process_annotations(source_page, imported)  # noqa: SLF001

    cloned_annots = (
        imported.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    )
    assert isinstance(cloned_annots, COSArray)
    cloned_text = cloned_annots.get_object(0)
    cloned_popup = cloned_annots.get_object(1)
    assert isinstance(cloned_text, COSDictionary)
    assert isinstance(cloned_popup, COSDictionary)
    assert cloned_text.get_dictionary_object(_POPUP) is cloned_popup
    assert cloned_popup is not popup


def test_wave375_goto_action_destination_is_rewritten_to_cloned_page() -> None:
    src = _make_doc(2)
    pages = list(src.get_pages())

    dest_array = COSArray()
    dest_array.add(pages[1].get_cos_object())
    dest_array.add(COSName.get_pdf_name("XYZ"))

    action = COSDictionary()
    action.set_item(_S, COSName.get_pdf_name("GoTo"))
    action.set_item(_D, dest_array)

    link = _annotation("Link")
    link.set_item(_A, action)
    annots = COSArray()
    annots.add(link)
    pages[0].get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)

    cloned_pages = list(chunks[0].get_pages())
    cloned_annots = cloned_pages[0].get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Annots")
    )
    assert isinstance(cloned_annots, COSArray)
    cloned_link = cloned_annots.get_object(0)
    assert isinstance(cloned_link, COSDictionary)
    cloned_action = cloned_link.get_dictionary_object(_A)
    assert isinstance(cloned_action, COSDictionary)
    cloned_dest = cloned_action.get_dictionary_object(_D)
    assert isinstance(cloned_dest, COSArray)
    assert cloned_dest.get_object(0) is cloned_pages[1].get_cos_object()
    assert cloned_action is not action
    _close_all(src, chunks)


def test_wave375_create_new_document_skips_nested_info_entries() -> None:
    src = _make_doc(1)
    info = src.get_document_information()
    info.set_title("kept")
    info.get_cos_object().set_item(_TYPE, COSName.get_pdf_name("Info"))
    nested = COSDictionary()
    nested.set_string(COSName.get_pdf_name("Value"), "dropped")
    info.get_cos_object().set_item(COSName.get_pdf_name("Nested"), nested)

    chunks = Splitter().split(src)

    copied = chunks[0].get_document_information().get_cos_object()
    assert copied.get_string(_TITLE) == "kept"
    assert not copied.contains_key(_TYPE)
    assert not copied.contains_key(COSName.get_pdf_name("Nested"))
    _close_all(src, chunks)
