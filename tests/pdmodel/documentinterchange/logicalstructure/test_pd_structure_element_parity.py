from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions

_S = COSName.get_pdf_name("S")
_ID = COSName.get_pdf_name("ID")
_R = COSName.get_pdf_name("R")
_T = COSName.T  # type: ignore[attr-defined]
_LANG = COSName.get_pdf_name("Lang")
_ALT = COSName.get_pdf_name("Alt")
_E = COSName.get_pdf_name("E")
_ACTUAL_TEXT = COSName.get_pdf_name("ActualText")
_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")


# ---------- /S structure type ----------


def test_structure_type_round_trip() -> None:
    elem = PDStructureElement()
    assert elem.get_structure_type() is None
    elem.set_structure_type("H1")
    assert elem.get_structure_type() == "H1"
    assert elem.get_cos_object().get_name(_S) == "H1"


def test_structure_type_constructor_sets_s() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_structure_type() == "P"


def test_structure_type_overwrite() -> None:
    elem = PDStructureElement(structure_type="H1")
    elem.set_structure_type("H2")
    assert elem.get_structure_type() == "H2"


# ---------- /ActualText ----------


def test_actual_text_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_actual_text() is None
    elem.set_actual_text("hello world")
    assert elem.get_actual_text() == "hello world"


def test_actual_text_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_actual_text("temporary")
    elem.set_actual_text(None)
    assert elem.get_actual_text() is None
    assert elem.get_cos_object().get_dictionary_object(_ACTUAL_TEXT) is None


# ---------- /E expanded form (upstream getExpandedForm) ----------


def test_expansion_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_expanded_form() is None
    elem.set_expanded_form("Acquired Immune Deficiency Syndrome")
    assert elem.get_expanded_form() == "Acquired Immune Deficiency Syndrome"


def test_expansion_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_expanded_form("AIDS")
    elem.set_expanded_form(None)
    assert elem.get_expanded_form() is None
    assert elem.get_cos_object().get_dictionary_object(_E) is None


# ---------- /Lang language ----------


def test_language_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_language() is None
    elem.set_language("en-US")
    assert elem.get_language() == "en-US"


def test_language_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_language("fr-CA")
    elem.set_language(None)
    assert elem.get_language() is None
    assert elem.get_cos_object().get_dictionary_object(_LANG) is None


# ---------- /T title ----------


def test_title_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_title() is None
    elem.set_title("Chapter 1")
    assert elem.get_title() == "Chapter 1"


def test_title_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_title("draft")
    elem.set_title(None)
    assert elem.get_title() is None
    assert elem.get_cos_object().get_dictionary_object(_T) is None


# ---------- /ID byte-string ----------


def test_id_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_id() is None
    elem.set_id("element-42")
    assert elem.get_id() == "element-42"


def test_id_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_id("doomed")
    elem.set_id(None)
    assert elem.get_id() is None
    assert elem.get_cos_object().get_dictionary_object(_ID) is None


# ---------- /R revision number ----------


def test_revision_number_default_is_zero() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_revision_number() == 0


def test_revision_number_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(3)
    assert elem.get_revision_number() == 3
    assert elem.get_cos_object().get_int(_R, -1) == 3


def test_revision_number_negative_rejected() -> None:
    elem = PDStructureElement(structure_type="P")
    with pytest.raises(ValueError):
        elem.set_revision_number(-1)


# ---------- /C class names ----------


def test_class_names_empty_when_unset() -> None:
    elem = PDStructureElement(structure_type="P")
    revs = elem.get_class_names()
    assert revs.size() == 0


def test_class_names_single_string_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    revs: Revisions[COSName] = Revisions()
    revs.add_object(COSName.get_pdf_name("MyClass"))
    elem.set_class_names(revs)

    got = elem.get_class_names()
    assert got.size() == 1
    val = got.get_object_at(0)
    # COSName equality vs python string
    assert (val.get_name() if isinstance(val, COSName) else val) == "MyClass"
    assert got.get_revision_number_at(0) == 0


def test_class_names_multiple_strings_round_trip() -> None:
    elem = PDStructureElement(structure_type="P")
    revs: Revisions[COSName] = Revisions()
    revs.add_object(COSName.get_pdf_name("Bold"), 0)
    revs.add_object(COSName.get_pdf_name("Italic"), 2)
    revs.add_object(COSName.get_pdf_name("Underline"), 5)
    elem.set_class_names(revs)

    got = elem.get_class_names()
    assert got.size() == 3
    names = [
        got.get_object_at(i).get_name()
        if isinstance(got.get_object_at(i), COSName)
        else got.get_object_at(i)
        for i in range(got.size())
    ]
    revisions = [got.get_revision_number_at(i) for i in range(got.size())]
    assert names == ["Bold", "Italic", "Underline"]
    assert revisions == [0, 2, 5]


def test_class_names_set_none_removes_c_entry() -> None:
    elem = PDStructureElement(structure_type="P")
    revs: Revisions[COSName] = Revisions()
    revs.add_object(COSName.get_pdf_name("Bold"))
    elem.set_class_names(revs)
    elem.set_class_names(None)
    assert elem.get_class_names().size() == 0
    assert elem.get_cos_object().get_dictionary_object(_C) is None


def test_class_names_bare_name_fallback() -> None:
    # Defensive: PDFs in the wild may store /C as a bare /Name (single
    # entry) rather than an array. Upstream wraps that into a
    # single-entry Revisions using revision 0.
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(7)
    elem.get_cos_object().set_item(_C, COSName.get_pdf_name("Bare"))

    got = elem.get_class_names()
    assert got.size() == 1
    val = got.get_object_at(0)
    assert (val.get_name() if isinstance(val, COSName) else val) == "Bare"
    assert got.get_revision_number_at(0) == 0


# ---------- /A attributes ----------


def test_attributes_empty_when_unset() -> None:
    elem = PDStructureElement(structure_type="P")
    assert elem.get_attributes().size() == 0


def test_attributes_round_trip_array() -> None:
    elem = PDStructureElement(structure_type="P")

    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    a2 = PDAttributeObject()
    a2.set_owner("List")

    revs: Revisions[PDAttributeObject] = Revisions()
    revs.add_object(a1, 0)
    revs.add_object(a2, 1)
    elem.set_attributes(revs)

    got = elem.get_attributes()
    assert got.size() == 2
    assert got.get_revision_number_at(0) == 0
    assert got.get_revision_number_at(1) == 1
    # /A in the dict is a COSArray
    assert isinstance(elem.get_cos_object().get_dictionary_object(_A), COSArray)


def test_attributes_set_none_removes_a_entry() -> None:
    elem = PDStructureElement(structure_type="P")
    a1 = PDAttributeObject()
    a1.set_owner("Layout")
    revs: Revisions[PDAttributeObject] = Revisions()
    revs.add_object(a1, 0)
    elem.set_attributes(revs)

    elem.set_attributes(None)
    assert elem.get_attributes().size() == 0
    assert elem.get_cos_object().get_dictionary_object(_A) is None


def test_attributes_bare_dict_fallback() -> None:
    # Defensive: /A may be a bare dict (single attribute object) rather
    # than an array. Upstream wraps as a single-entry Revisions using
    # the element's current /R.
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(4)
    bare = COSDictionary()
    bare.set_name(COSName.get_pdf_name("O"), "Layout")
    elem.get_cos_object().set_item(_A, bare)

    got = elem.get_attributes()
    assert got.size() == 1
    assert got.get_revision_number_at(0) == 4


# ---------- /Alt alternate description ----------


def test_alternate_description_round_trip() -> None:
    elem = PDStructureElement(structure_type="Figure")
    assert elem.get_alternate_description() is None
    elem.set_alternate_description("a red square")
    assert elem.get_alternate_description() == "a red square"


def test_alternate_description_clear_with_none() -> None:
    elem = PDStructureElement(structure_type="Figure")
    elem.set_alternate_description("temporary")
    elem.set_alternate_description(None)
    assert elem.get_alternate_description() is None
    assert elem.get_cos_object().get_dictionary_object(_ALT) is None
