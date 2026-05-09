from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
)
from pypdfbox.pdmodel import PDPage
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page import _unwrap_page_dict


def test_wave646_user_unit_defaults_validates_and_ignores_malformed_values() -> None:
    page = PDPage()

    assert page.get_user_unit() == 1.0

    page.set_user_unit(2.5)
    assert page.get_user_unit() == 2.5

    page.get_cos_object().set_item("UserUnit", COSInteger.get(0))
    assert page.get_user_unit() == 1.0

    page.get_cos_object().set_item("UserUnit", COSName.get_pdf_name("Bad"))
    assert page.get_user_unit() == 1.0

    with pytest.raises(ValueError, match="user_unit must be positive"):
        page.set_user_unit(0)


def test_wave646_annotations_clear_reject_wrong_type_and_ignore_malformed_source() -> None:
    page = PDPage()
    text = PDAnnotationText()

    page.set_annotations([text])
    assert page.has_annotations() is True

    page.set_annotations(None)
    assert page.has_annotations() is False
    assert page.get_annotations() == []

    page.get_cos_object().set_item("Annots", COSDictionary())
    assert page.get_annotations() == []

    with pytest.raises(TypeError, match="set_annotations entries"):
        page.set_annotations([object()])  # type: ignore[list-item]


def test_wave646_thread_beads_preserve_malformed_slots_and_clear() -> None:
    page = PDPage()
    bead = PDThreadBead()

    assert page.get_thread_beads() == []

    page.set_thread_beads([bead])
    assert page.has_thread_beads() is True
    assert page.get_thread_beads()[0].get_cos_object() is bead.get_cos_object()

    page.get_cos_object().set_item(
        "B",
        COSArray([bead.get_cos_object(), COSName.get_pdf_name("Bad")]),
    )
    beads = page.get_thread_beads()
    assert beads[0].get_cos_object() is bead.get_cos_object()
    assert beads[1] is None

    page.set_thread_beads(None)
    assert page.has_thread_beads() is False

    with pytest.raises(TypeError, match="set_thread_beads entries"):
        page.set_thread_beads([object()])  # type: ignore[list-item]


def test_wave646_page_presence_and_clear_helpers_remove_direct_entries() -> None:
    page = PDPage()

    page.get_cos_object().set_item("Metadata", COSDictionary())
    page.get_cos_object().set_item("Thumb", COSDictionary())
    page.get_cos_object().set_item("Trans", COSDictionary())
    page.get_cos_object().set_item("Group", COSDictionary())
    page.set_tab_order(PDPage.TAB_ORDER_ROW)
    page.set_duration(3)

    assert page.has_metadata() is True
    assert page.has_thumb() is True
    assert page.has_transition() is True
    assert page.has_group() is True
    assert page.has_tab_order() is True
    assert page.has_duration() is True
    assert page.get_tab_order() == PDPage.TAB_ORDER_ROW
    assert page.get_duration() == 3.0

    page.clear_metadata()
    page.clear_thumb()
    page.clear_transition()
    page.clear_group()
    page.clear_tab_order()
    page.clear_duration()

    assert page.has_metadata() is False
    assert page.has_thumb() is False
    assert page.has_transition() is False
    assert page.has_group() is False
    assert page.has_tab_order() is False
    assert page.has_duration() is False


def test_wave646_struct_parents_float_equality_repr_and_unwrap_page_dict() -> None:
    page = PDPage()
    same = PDPage(page.get_cos_object())
    other = PDPage()

    page.get_cos_object().set_item("StructParents", COSFloat(6.9))

    assert page.get_struct_parents() == 6
    assert page == same
    assert page != other
    assert hash(page) == id(page.get_cos_object())
    assert "PDPage(media_box=" in repr(page)
    assert _unwrap_page_dict(page) is page.get_cos_object()
    assert _unwrap_page_dict(page.get_cos_object()) is page.get_cos_object()
    assert _unwrap_page_dict(COSObject(1, resolved=page.get_cos_object())) is page.get_cos_object()

    with pytest.raises(TypeError, match="does not resolve"):
        _unwrap_page_dict(COSObject(2, resolved=COSInteger.get(1)))

    with pytest.raises(TypeError, match="expected PDPage"):
        _unwrap_page_dict(object())  # type: ignore[arg-type]
