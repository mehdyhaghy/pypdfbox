from __future__ import annotations

import logging

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull
from pypdfbox.multipdf import Splitter

_ANNOTS = COSName.get_pdf_name("Annots")
_OBJ = COSName.get_pdf_name("Obj")
_PARENT = COSName.get_pdf_name("Parent")
_POPUP = COSName.get_pdf_name("Popup")
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


def test_wave453_create_new_document_sanitizes_info_dictionary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = _make_doc(1)
    info_dict = source.get_document_information().get_cos_object()
    info_dict.set_item(_TYPE, COSName.get_pdf_name("ShouldNotCopy"))
    info_dict.set_string(COSName.get_pdf_name("Title"), "kept title")
    info_dict.set_item(COSName.get_pdf_name("Nested"), COSDictionary())

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        chunks = Splitter().split(source)

    chunk_info = chunks[0].get_document_information().get_cos_object()
    assert chunk_info.get_string(COSName.get_pdf_name("Title")) == "kept title"
    assert not chunk_info.contains_key(_TYPE)
    assert not chunk_info.contains_key(COSName.get_pdf_name("Nested"))
    assert "Nested entry for key 'Nested' skipped" in caplog.text

    chunks[0].close()
    source.close()


def test_wave453_process_annotations_clones_popup_reference_without_source_alias() -> None:
    source_page = PDPage()
    imported = PDPage()
    popup = _annotation("Popup")
    markup = _annotation("Text")
    markup.set_item(_POPUP, popup)
    annots = COSArray()
    annots.add(markup)
    annots.add(popup)
    imported.get_cos_object().set_item(_ANNOTS, annots)

    Splitter()._process_annotations(source_page, imported)  # noqa: SLF001

    cloned_annots = imported.get_cos_object().get_dictionary_object(_ANNOTS)
    assert isinstance(cloned_annots, COSArray)
    cloned_markup = cloned_annots.get_object(0)
    cloned_popup = cloned_annots.get_object(1)
    assert isinstance(cloned_markup, COSDictionary)
    assert isinstance(cloned_popup, COSDictionary)
    assert cloned_markup is not markup
    assert cloned_popup is not popup
    assert cloned_markup.get_dictionary_object(_POPUP) is cloned_popup


def test_wave453_clone_tree_element_logs_missing_dict_and_unsupported_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    splitter = Splitter()
    missing_struct = COSDictionary()
    dst_numbers: dict[int, object] = {}

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        splitter._clone_tree_element({2: missing_struct, 3: COSInteger.get(7)}, dst_numbers, 2)  # noqa: SLF001,E501
        splitter._clone_tree_element({2: missing_struct, 3: COSInteger.get(7)}, dst_numbers, 3)  # noqa: SLF001,E501

    assert dst_numbers == {}
    assert "ParentTree index 2 dictionary not found in /K" in caplog.text
    assert "tree element neither dictionary nor array" in caplog.text


def test_wave453_objr_clone_drops_annotation_not_present_on_host_page(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class PageTree:
        def index_of(self, page_dict: COSDictionary) -> int:
            return 0 if page_dict is host_page else -1

    splitter = Splitter()
    host_page = COSDictionary()
    splitter._page_dict_map = {id(host_page): host_page}  # noqa: SLF001
    host_page.set_item(_ANNOTS, COSArray())
    orphan_annotation = _annotation("Link")
    objr = COSDictionary()
    objr.set_item(_TYPE, COSName.get_pdf_name("OBJR"))
    objr.set_item(_OBJ, orphan_annotation)
    objr.set_item(COSName.get_pdf_name("Pg"), host_page)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        cloned = splitter._k_create_clone(objr, COSDictionary(), None, PageTree())  # noqa: SLF001

    assert cloned is None
    assert "An annotation OBJ that isn't in the page" in caplog.text


def test_wave453_fix_destinations_rewrites_in_chunk_target() -> None:
    source = _make_doc(2)
    chunk = _make_doc(2)
    source_pages = list(source.get_pages())
    chunk_pages = list(chunk.get_pages())
    dest = COSArray()
    dest.add(source_pages[1].get_cos_object())
    dest.add(COSName.get_pdf_name("Fit"))

    splitter = Splitter()
    splitter._dest_to_fix = [(dest, source_pages[0].get_cos_object())]  # noqa: SLF001
    splitter._page_dict_map = {  # noqa: SLF001
        id(source_pages[0].get_cos_object()): chunk_pages[0].get_cos_object(),
        id(source_pages[1].get_cos_object()): chunk_pages[1].get_cos_object(),
    }

    splitter._fix_destinations(chunk)  # noqa: SLF001

    assert dest.get_object(0) is chunk_pages[1].get_cos_object()
    assert dest.get(0) is not COSNull.NULL
    source.close()
    chunk.close()
