import logging
from typing import Any

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSObject
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import PDDestination

_A = COSName.get_pdf_name("A")
_ANNOTS = COSName.get_pdf_name("Annots")
_BYTE_RANGE = COSName.get_pdf_name("ByteRange")
_D = COSName.get_pdf_name("D")
_DEST = COSName.get_pdf_name("Dest")
_FT = COSName.get_pdf_name("FT")
_K = COSName.get_pdf_name("K")
_OBJ = COSName.get_pdf_name("Obj")
_PARENT = COSName.get_pdf_name("Parent")
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_TYPE = COSName.get_pdf_name("Type")
_V = COSName.get_pdf_name("V")


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def _close_all(src: PDDocument, chunks: list[PDDocument]) -> None:
    for chunk in chunks:
        chunk.close()
    src.close()


def _dest_array(page_dict: COSDictionary) -> COSArray:
    dest = COSArray()
    dest.add(page_dict)
    dest.add(COSName.get_pdf_name("Fit"))
    return dest


def test_wave387_configuration_predicates_and_fluent_setters() -> None:
    splitter = Splitter()

    assert splitter.get_split_at_page() == Splitter.DEFAULT_SPLIT_LENGTH
    assert splitter.get_start_page() == Splitter.START_PAGE_DEFAULT
    assert splitter.get_end_page() == Splitter.END_PAGE_DEFAULT
    assert not splitter.has_start_page()
    assert not splitter.has_end_page()
    assert not splitter.has_stream_cache_create_function()
    assert not splitter.has_memory_usage_setting()

    def make_cache() -> object:
        return object()

    setting = object()
    assert splitter.set_split(3) is splitter
    assert splitter.set_start_page(2) is splitter
    assert splitter.set_end_page(7) is splitter
    assert splitter.set_stream_cache_create_function(make_cache) is splitter
    assert splitter.set_memory_usage_setting(setting) is splitter
    assert splitter.get_split_at_page() == 3
    assert splitter.has_start_page()
    assert splitter.has_end_page()
    assert splitter.has_stream_cache_create_function()
    assert splitter.has_memory_usage_setting()


def test_wave387_post_pass_exceptions_are_logged_and_do_not_abort(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ResilientSplitter(Splitter):
        def _clone_structure_tree(self, destination_document: PDDocument) -> None:
            raise RuntimeError("struct boom")

        def _fix_destinations(self, destination_document: PDDocument) -> None:
            raise RuntimeError("dest boom")

    src = _make_doc(1)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.splitter"):
        chunks = ResilientSplitter().split(src)

    assert len(chunks) == 1
    messages = [record.getMessage() for record in caplog.records]
    assert any("structure-tree clone failed" in message for message in messages)
    assert any("destination fix-up failed" in message for message in messages)
    _close_all(src, chunks)


def _page_with_link(link: PDAnnotationLink) -> PDPage:
    page = PDPage()
    annots = COSArray()
    annots.add(link.get_cos_object())
    page.get_cos_object().set_item(_ANNOTS, annots)
    return page


def _cloned_link(page: PDPage) -> COSDictionary:
    return page.get_cos_object().get_dictionary_object(_ANNOTS).get_object(0)


def test_wave387_process_annotations_removes_bad_direct_destination() -> None:
    link = PDAnnotationLink()
    link.get_cos_object().set_item(_DEST, COSInteger.get(4))
    page = _page_with_link(link)
    splitter = Splitter()
    splitter._current_page_number = 4

    splitter._process_annotations(page)

    cloned = _cloned_link(page)
    assert cloned is not link.get_cos_object()
    assert not cloned.contains_key(_DEST)
    # the source annotation is untouched
    assert link.get_cos_object().contains_key(_DEST)
    assert splitter._dest_to_fix == []


def test_wave387_process_annotations_removes_bad_goto_action() -> None:
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, COSInteger.get(4))
    link = PDAnnotationLink()
    link.set_action(action)
    page = _page_with_link(link)
    splitter = Splitter()

    splitter._process_annotations(page)

    assert not _cloned_link(page).contains_key(_A)
    assert link.get_cos_object().contains_key(_A)
    assert splitter._dest_to_fix == []


def test_wave387_named_destinations_are_left_untouched() -> None:
    link = PDAnnotationLink()
    link.set_destination(COSName.get_pdf_name("ChapterOne"))
    page = _page_with_link(link)
    splitter = Splitter()

    splitter._process_annotations(page)

    assert _cloned_link(page).get_dictionary_object(_DEST) == COSName.get_pdf_name(
        "ChapterOne"
    )
    assert splitter._dest_to_fix == []


def test_wave387_goto_action_destination_gets_shallow_cloned() -> None:
    page_dict = COSDictionary()
    action = PDActionGoTo()
    action.set_destination(_dest_array(page_dict))
    link = PDAnnotationLink()
    link.set_action(action)
    page = _page_with_link(link)
    splitter = Splitter()

    splitter._process_annotations(page)

    staged = splitter._dest_to_fix
    assert len(staged) == 1
    assert staged[0][1] is page.get_cos_object()
    cloned_action = _cloned_link(page).get_dictionary_object(_A)
    assert isinstance(cloned_action, COSDictionary)
    assert cloned_action is not action.get_cos_object()
    cloned_dest = cloned_action.get_dictionary_object(_D)
    assert cloned_dest is staged[0][0].get_cos_object()
    assert cloned_dest is not action.get_cos_object().get_dictionary_object(_D)
    assert cloned_dest.get_object(0) is page_dict


def test_wave387_fix_destinations_skips_missing_hosts_and_non_page_targets() -> None:
    src = _make_doc(1)
    chunk = _make_doc(1)
    host = COSDictionary()
    missing_host_dest = _dest_array(COSDictionary())
    integer_target_dest = COSArray()
    integer_target_dest.add(COSInteger.get(0))
    integer_target_dest.add(COSName.get_pdf_name("Fit"))

    splitter = Splitter()
    splitter._dest_to_fix = [
        (PDDestination.create(missing_host_dest), COSDictionary()),
        (PDDestination.create(integer_target_dest), host),
    ]
    splitter._page_dict_map = {id(host): chunk.get_page(0).get_cos_object()}

    splitter._fix_destinations(chunk)

    assert missing_host_dest.get_object(0) is not COSNull.NULL
    assert integer_target_dest.get_object(0).int_value() == 0
    _close_all(src, [chunk])


def test_wave387_cosobject_and_array_struct_helpers_preserve_holes() -> None:
    splitter = Splitter()
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("P"))
    # like upstream createClone, an unresolved reference is returned as is
    wrapped = COSObject(10, resolved=child)
    assert splitter._k_create_clone(wrapped, parent, parent, object()) is wrapped

    cloned = splitter._k_create_clone(child, parent, parent, object())
    assert isinstance(cloned, COSDictionary)
    assert splitter._k_create_clone(COSInteger.get(3), parent, parent, object()).int_value() == 3
    assert splitter._has_mcids(COSInteger.get(0))

    parent_tree_value = COSArray()
    parent_tree_value.add(child)
    parent_tree_value.add(COSDictionary())
    dst_numbers: dict[int, Any] = {}
    splitter._clone_tree_element({5: parent_tree_value}, dst_numbers, 5)

    cloned_array = dst_numbers[5]
    assert isinstance(cloned_array, COSArray)
    assert cloned_array.get_object(0) is cloned
    assert cloned_array.get(1) is COSNull.NULL


def test_wave387_orphan_annotation_without_page_annots_is_removed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    splitter = Splitter()
    src_obj = COSDictionary()
    src_obj.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    src_dict = COSDictionary()
    host_page = COSDictionary()
    src_dict.set_item(_PG, host_page)
    dst = COSDictionary()
    dst.set_item(_OBJ, src_obj)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.splitter"):
        splitter._remove_possible_orphan_annotation(
            src_obj, src_dict, None, dst
        )

    assert not dst.contains_key(_OBJ)
    assert "isn't in the page" in caplog.text
