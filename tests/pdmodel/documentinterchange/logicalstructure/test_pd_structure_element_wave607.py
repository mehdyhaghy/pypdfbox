from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")


def test_wave607_add_attribute_sets_back_pointer_and_current_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(7)
    attr = PDAttributeObject()
    attr.set_owner("Layout")

    elem.add_attribute(attr)

    revs = elem.get_attributes()
    assert revs.size() == 1
    assert revs.get_object_at(0) is attr.get_cos_object()
    assert revs.get_revision_number_at(0) == 7
    assert attr.get_structure_element() is elem
    assert isinstance(elem.get_cos_object().get_dictionary_object(_A), COSArray)


def test_wave607_remove_attribute_clears_slot_and_back_pointer_only_when_present() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    missing = PDAttributeObject()
    missing.set_owner("Table")
    missing.set_structure_element(elem)
    elem.add_attribute(attr)

    elem.remove_attribute(missing)

    assert missing.get_structure_element() is elem
    assert elem.get_attributes().size() == 1

    elem.remove_attribute(attr)

    assert attr.get_structure_element() is None
    assert elem.get_attributes().is_empty()
    assert elem.get_cos_object().get_dictionary_object(_A) is None


def test_wave607_attribute_changed_tracks_structure_element_revision() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    elem.add_attribute(attr)
    elem.set_revision_number(4)

    attr.notify_change()

    assert elem.get_attributes().get_revision_number_at(0) == 4


def test_wave607_class_name_maintenance_uses_current_revision_and_compacts() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(2)

    elem.add_class_name("Emphasis")
    elem.add_class_name(None)

    assert elem.get_class_names_as_strings() == ["Emphasis"]
    assert elem.get_class_names().get_revision_number_at(0) == 2
    assert isinstance(elem.get_cos_object().get_dictionary_object(_C), COSArray)

    elem.set_revision_number(5)
    elem.class_name_changed("Emphasis")
    elem.class_name_changed(None)
    elem.class_name_changed("Missing")

    assert elem.get_class_names().get_revision_number_at(0) == 5

    elem.remove_class_name("Missing")
    assert elem.get_class_names_as_strings() == ["Emphasis"]

    elem.remove_class_name("Emphasis")
    elem.remove_class_name(None)
    assert elem.get_class_names().is_empty()
    assert elem.get_cos_object().get_dictionary_object(_C) is None
