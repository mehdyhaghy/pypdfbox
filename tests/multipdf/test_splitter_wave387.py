from __future__ import annotations

import logging
from typing import Any

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSNull, COSObject
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import PDAnnotationLink

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

        def _scrub_acroform(self, destination_document: PDDocument) -> None:
            raise RuntimeError("acro boom")

    src = _make_doc(1)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.splitter"):
        chunks = ResilientSplitter().split(src)

    assert len(chunks) == 1
    messages = [record.getMessage() for record in caplog.records]
    assert any("structure-tree clone failed" in message for message in messages)
    assert any("destination fix-up failed" in message for message in messages)
    assert any("AcroForm scrub failed" in message for message in messages)
    _close_all(src, chunks)


def test_wave387_stage_link_destination_removes_bad_direct_destination() -> None:
    class BadDestinationLink:
        destination_cleared = False

        def get_destination(self) -> object:
            raise OSError("bad dest")

        def set_destination(self, value: object) -> None:
            self.destination_cleared = value is None

    splitter = Splitter()
    splitter._current_page_number = 4  # noqa: SLF001
    link = BadDestinationLink()

    splitter._stage_link_destination(link, COSDictionary())  # noqa: SLF001

    assert link.destination_cleared
    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave387_stage_link_destination_removes_bad_goto_action() -> None:
    class BadAction(PDActionGoTo):
        def get_destination(self) -> object:
            raise OSError("bad action destination")

    class LinkWithBadAction:
        def __init__(self) -> None:
            self.action: object | None = BadAction()

        def get_destination(self) -> None:
            return None

        def get_action(self) -> object | None:
            return self.action

        def set_action(self, value: object | None) -> None:
            self.action = value

    link = LinkWithBadAction()
    splitter = Splitter()

    splitter._stage_link_destination(link, COSDictionary())  # noqa: SLF001

    assert link.action is None
    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave387_named_destinations_are_left_untouched() -> None:
    link = PDAnnotationLink()
    link.set_destination(COSName.get_pdf_name("ChapterOne"))
    splitter = Splitter()

    splitter._stage_link_destination(link, COSDictionary())  # noqa: SLF001

    assert link.get_cos_object().get_dictionary_object(_DEST) == COSName.get_pdf_name(
        "ChapterOne"
    )
    assert splitter._dest_to_fix == []  # noqa: SLF001


def test_wave387_goto_action_destination_gets_shallow_cloned() -> None:
    page_dict = COSDictionary()
    action = PDActionGoTo()
    action.set_destination(_dest_array(page_dict))
    link = PDAnnotationLink()
    link.set_action(action)
    splitter = Splitter()

    splitter._stage_link_destination(link, COSDictionary())  # noqa: SLF001

    staged = splitter._dest_to_fix  # noqa: SLF001
    assert len(staged) == 1
    cloned_action = link.get_cos_object().get_dictionary_object(_A)
    assert isinstance(cloned_action, COSDictionary)
    assert cloned_action is not action.get_cos_object()
    cloned_dest = cloned_action.get_dictionary_object(_D)
    assert cloned_dest is staged[0][0]
    assert cloned_dest is not action.get_cos_object().get_dictionary_object(_D)


def test_wave387_fix_destinations_skips_missing_hosts_and_non_page_targets() -> None:
    src = _make_doc(1)
    chunk = _make_doc(1)
    host = COSDictionary()
    missing_host_dest = _dest_array(COSDictionary())
    integer_target_dest = COSArray()
    integer_target_dest.add(COSInteger.get(0))
    integer_target_dest.add(COSName.get_pdf_name("Fit"))

    splitter = Splitter()
    splitter._dest_to_fix = [  # noqa: SLF001
        (missing_host_dest, COSDictionary()),
        (integer_target_dest, host),
    ]
    splitter._page_dict_map = {id(host): chunk.get_page(0).get_cos_object()}  # noqa: SLF001

    splitter._fix_destinations(chunk)  # noqa: SLF001

    assert missing_host_dest.get_object(0) is not COSNull.NULL
    assert integer_target_dest.get_object(0).int_value() == 0
    _close_all(src, [chunk])


def test_wave387_signature_widget_detects_byte_range_value() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    signature_value = COSDictionary()
    signature_value.set_item(_BYTE_RANGE, COSArray())
    widget.set_item(_V, signature_value)

    assert Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave387_signature_widget_non_sig_parent_stops_parent_walk() -> None:
    widget = COSDictionary()
    widget.set_item(_SUBTYPE, COSName.get_pdf_name("Widget"))
    parent = COSDictionary()
    parent.set_item(_FT, COSName.get_pdf_name("Tx"))
    widget.set_item(_PARENT, parent)

    assert not Splitter._is_signature_widget(widget)  # noqa: SLF001


def test_wave387_cosobject_and_array_struct_helpers_preserve_holes() -> None:
    splitter = Splitter()
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("P"))
    wrapped = COSObject(10, resolved=child)

    cloned = splitter._k_create_clone(wrapped, parent, parent, object())  # noqa: SLF001
    assert isinstance(cloned, COSDictionary)
    assert splitter._k_create_clone(COSInteger.get(3), parent, parent, object()).int_value() == 3  # noqa: SLF001,E501
    assert splitter._has_mcids(COSInteger.get(0))  # noqa: SLF001

    parent_tree_value = COSArray()
    parent_tree_value.add(child)
    parent_tree_value.add(COSDictionary())
    dst_numbers: dict[int, Any] = {}
    splitter._clone_tree_element({5: parent_tree_value}, dst_numbers, 5)  # noqa: SLF001

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
        splitter._remove_possible_orphan_annotation(  # noqa: SLF001
            src_obj, src_dict, None, dst
        )

    assert not dst.contains_key(_OBJ)
    assert "isn't in the page" in caplog.text


def test_wave387_number_and_id_tree_walkers_recurse_and_swallow_bad_nodes() -> None:
    class BadNode:
        def get_numbers(self) -> object:
            raise RuntimeError("numbers unavailable")

        def get_names(self) -> object:
            raise RuntimeError("names unavailable")

        def get_kids(self) -> object:
            raise RuntimeError("kids unavailable")

    class NumberLeaf:
        def __init__(self, value: COSDictionary) -> None:
            self.value = value

        def get_numbers(self) -> dict[int, COSDictionary]:
            return {2: self.value}

        def get_kids(self) -> None:
            return None

    class IdLeaf:
        def __init__(self, value: COSDictionary) -> None:
            self.value = value

        def get_names(self) -> dict[str, COSDictionary]:
            return {"id": self.value}

        def get_kids(self) -> None:
            return None

    class Parent:
        def __init__(self, child: object) -> None:
            self.child = child

        def get_numbers(self) -> None:
            return None

        def get_names(self) -> None:
            return None

        def get_kids(self) -> list[object]:
            return [BadNode(), self.child]

    number_value = COSDictionary()
    id_value = COSDictionary()

    assert Splitter._get_number_tree_as_map(Parent(NumberLeaf(number_value))) == {  # noqa: SLF001
        2: number_value
    }
    assert Splitter._get_id_tree_as_map(Parent(IdLeaf(id_value))) == {  # noqa: SLF001
        "id": id_value
    }
