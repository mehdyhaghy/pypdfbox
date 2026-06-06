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


def test_wave607_remove_attribute_collapses_and_clears_back_pointer_upstream() -> None:
    # Upstream parity (PDStructureElement.java L258-L284, verified against
    # StructAttrMutateProbe): removeAttribute always clears the attribute's
    # back-pointer (line 283 is unconditional) AND, for the array form,
    # collapses [dict, 0] back to a bare dict whenever size()==2 &&
    # getInt(1)==0 — even when the removed attribute wasn't actually present
    # (the remove is a no-op but the collapse check still fires).
    from pypdfbox.cos import COSDictionary

    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    missing = PDAttributeObject()
    missing.set_owner("Table")
    missing.set_structure_element(elem)
    elem.add_attribute(attr)

    elem.remove_attribute(missing)

    # Back-pointer is cleared unconditionally (upstream line 283).
    assert missing.get_structure_element() is None
    # [Layout, 0] collapses to a bare Layout dict.
    collapsed = elem.get_cos_object().get_dictionary_object(_A)
    assert isinstance(collapsed, COSDictionary)
    assert elem.get_attributes().size() == 1

    elem.remove_attribute(attr)

    assert attr.get_structure_element() is None
    assert elem.get_attributes().is_empty()
    # Bare-dict form: a matching remove clears /A outright.
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
    # Upstream parity: removing the only class name from [name, rev] leaves
    # the orphan [rev] array; getClassNames() drops the orphan integer.
    leftover_c = elem.get_cos_object().get_dictionary_object(_C)
    assert isinstance(leftover_c, COSArray)
    assert leftover_c.size() == 1
