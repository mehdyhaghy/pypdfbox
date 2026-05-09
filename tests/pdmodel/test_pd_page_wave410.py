from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDRectangle
from pypdfbox.pdmodel.common import PDMetadata
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page import _unwrap_page_dict


def test_set_contents_accepts_stream_wrapper_and_rejects_bad_wrappers() -> None:
    class StreamWrapper:
        def __init__(self, cos: object) -> None:
            self._cos = cos

        def get_cos_object(self) -> object:
            return self._cos

    page = PDPage()
    stream = COSStream()
    stream.set_raw_data(b"wrapped")

    page.set_contents([StreamWrapper(stream)])

    assert page.get_contents() == b"wrapped"
    with pytest.raises(TypeError, match="must wrap a COSStream"):
        page.set_contents([StreamWrapper(COSDictionary())])
    with pytest.raises(TypeError, match="COSStream-like"):
        page.set_contents([object()])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="expected None, COSStream"):
        page.set_contents("bad")  # type: ignore[arg-type]


def test_content_helpers_ignore_malformed_contents_entries() -> None:
    page = PDPage()
    page.get_cos_object().set_item(COSName.CONTENTS, COSDictionary())  # type: ignore[attr-defined]
    assert page.get_contents() == b""
    assert page.get_content_streams() == []
    assert page.has_contents() is False

    arr = COSArray()
    arr.add(COSDictionary())
    stream = COSStream()
    stream.set_raw_data(b"ok")
    arr.add(stream)
    page.get_cos_object().set_item(COSName.CONTENTS, arr)  # type: ignore[attr-defined]
    assert page.get_contents() == b"ok"
    assert len(page.get_content_streams()) == 1
    assert page.has_contents() is True


def test_box_setters_accept_cos_array_and_none_removes_entries() -> None:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 300.0))
    crop = PDRectangle(10.0, 20.0, 150.0, 250.0).to_cos_array()
    bleed = PDRectangle(0.0, 0.0, 210.0, 310.0).to_cos_array()
    trim = PDRectangle(1.0, 2.0, 3.0, 4.0).to_cos_array()
    art = PDRectangle(5.0, 6.0, 7.0, 8.0).to_cos_array()

    page.set_crop_box(crop)
    page.set_bleed_box(bleed)
    page.set_trim_box(trim)
    page.set_art_box(art)

    assert page.get_crop_box().lower_left_x == 10.0
    assert page.get_bleed_box().upper_right_x == 200.0
    assert page.get_trim_box().lower_left_y == 2.0
    assert page.get_art_box().upper_right_y == 8.0

    page.set_media_box(None)
    page.set_crop_box(None)
    page.set_bleed_box(None)
    page.set_trim_box(None)
    page.set_art_box(None)

    assert page.get_media_box().width == 612.0
    assert page.get_crop_box().width == 612.0
    assert page.get_cos_object().get_dictionary_object("BleedBox") is None
    assert page.get_cos_object().get_dictionary_object("TrimBox") is None
    assert page.get_cos_object().get_dictionary_object("ArtBox") is None


def test_user_unit_rejects_non_positive_and_ignores_malformed_values() -> None:
    page = PDPage()
    with pytest.raises(ValueError, match="positive"):
        page.set_user_unit(0)

    page.get_cos_object().set_item("UserUnit", COSInteger.get(-2))
    assert page.get_user_unit() == 1.0
    page.get_cos_object().set_item("UserUnit", COSFloat(0.0))
    assert page.get_user_unit() == 1.0
    page.get_cos_object().set_name("UserUnit", "Two")
    assert page.get_user_unit() == 1.0


def test_annotations_setter_removes_and_rejects_non_annotations() -> None:
    page = PDPage()
    with pytest.raises(TypeError, match="PDAnnotation"):
        page.set_annotations([object()])  # type: ignore[list-item]

    page.get_cos_object().set_item("Annots", COSArray())
    page.set_annotations(None)
    assert page.has_annotations() is False


def test_thread_beads_round_trip_malformed_slots_and_clear() -> None:
    page = PDPage()
    bead = PDThreadBead()
    page.set_thread_beads([bead])
    page.get_cos_object().get_dictionary_object("B").add(COSName.get_pdf_name("Bad"))  # type: ignore[union-attr]

    resolved = page.get_thread_beads()

    assert resolved[0].get_cos_object() is bead.get_cos_object()
    assert resolved[1] is None
    with pytest.raises(TypeError, match="PDThreadBead"):
        page.set_thread_beads([object()])  # type: ignore[list-item]
    page.set_thread_beads(None)
    assert page.get_thread_beads() == []


def test_metadata_group_tab_duration_and_actions_clear_paths() -> None:
    page = PDPage()
    metadata = PDMetadata(b"<x:xmpmeta/>")
    group = COSDictionary()

    page.set_metadata(metadata)
    page.set_group(group)
    page.set_tab_order(PDPage.TAB_ORDER_WIDGETS)
    page.set_duration(1.25)
    page.get_actions()

    assert page.get_metadata().get_cos_object() is metadata.get_cos_object()
    assert page.get_group() is group
    assert page.get_tab_order() == "W"
    assert page.has_duration() is True
    assert page.has_actions() is True

    page.set_metadata(None)
    page.set_group(None)
    page.clear_tab_order()
    page.clear_duration()
    page.clear_actions()

    assert page.get_metadata() is None
    assert page.get_group() is None
    assert page.get_tab_order() is None
    assert page.get_duration() is None
    assert page.has_actions() is False


def test_set_group_rejects_non_dictionary_wrappers() -> None:
    class BadGroup:
        def get_cos_object(self) -> COSName:
            return COSName.get_pdf_name("NotADict")

    page = PDPage()
    with pytest.raises(TypeError, match="set_group expected COSDictionary"):
        page.set_group(BadGroup())


def test_getters_return_none_or_empty_for_malformed_optional_entries() -> None:
    page = PDPage()
    page.get_cos_object().set_name("Thumb", "NoStream")
    page.get_cos_object().set_name("Trans", "NoDict")
    page.get_cos_object().set_name("Metadata", "NoStream")
    page.get_cos_object().set_name("Group", "NoDict")
    page.get_cos_object().set_name("VP", "NoArray")
    page.get_cos_object().set_name("B", "NoArray")
    page.get_cos_object().set_item("StructParents", COSFloat(3.8))

    assert page.get_thumb() is None
    assert page.get_transition() is None
    assert page.get_metadata() is None
    assert page.get_group() is None
    assert page.get_viewports() is None
    assert page.get_thread_beads() == []
    assert page.get_struct_parents() == 3


def test_equality_hash_repr_and_unwrap_page_dict() -> None:
    raw = COSDictionary()
    page = PDPage(raw)
    same = PDPage(raw)
    other = PDPage()
    indirect = COSObject(12, resolved=raw)

    assert page == same
    assert page != other
    assert hash(page) == id(raw)
    assert "PDPage(media_box=" in repr(page)
    assert _unwrap_page_dict(page) is raw
    assert _unwrap_page_dict(raw) is raw
    assert _unwrap_page_dict(indirect) is raw

    with pytest.raises(TypeError, match="does not resolve"):
        _unwrap_page_dict(COSObject(13, resolved=COSName.get_pdf_name("Bad")))
    with pytest.raises(TypeError, match="expected PDPage"):
        _unwrap_page_dict(object())  # type: ignore[arg-type]
