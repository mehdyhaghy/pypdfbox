from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
    PDAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions

_A = COSName.get_pdf_name("A")
_C = COSName.get_pdf_name("C")
_K = COSName.get_pdf_name("K")
_O = COSName.get_pdf_name("O")
_P = COSName.get_pdf_name("P")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_TYPE = COSName.TYPE


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave647_single_attribute_dictionary_is_typed_and_owner_searchable() -> None:
    attr_dict = COSDictionary()
    attr_dict.set_name(_O, "Layout")
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_item(_A, attr_dict)

    revs = elem.get_attributes()
    objects = elem.get_attribute_objects()

    assert revs.size() == 1
    assert revs.get_object_at(0) is attr_dict
    assert revs.get_revision_number_at(0) == 0
    assert len(objects) == 1
    assert objects[0].get_cos_object() is attr_dict
    assert elem.has_attribute_owner("Layout") is True
    assert elem.has_attribute_owner("Table") is False
    assert elem.has_attribute_owner(None) is False  # type: ignore[arg-type]


def test_wave647_setters_remove_attributes_and_store_single_zero_revision_class_name() -> None:
    elem = PDStructureElement(structure_type="P")
    attr = PDAttributeObject()
    attr.set_owner("Layout")
    attr_revs: Revisions[PDAttributeObject] = Revisions()
    attr_revs.add_object(attr, 3)

    elem.set_attributes(attr_revs)
    assert isinstance(elem.get_cos_object().get_dictionary_object(_A), COSArray)

    elem.set_attributes(None)
    assert elem.get_attributes().is_empty()
    assert elem.get_cos_object().get_dictionary_object(_A) is None

    class_revs: Revisions[COSName] = Revisions()
    class_revs.add_object(_name("Emphasis"), 0)
    elem.set_class_names(class_revs)

    assert elem.get_cos_object().get_dictionary_object(_C) == _name("Emphasis")
    assert elem.get_class_names_as_strings() == ["Emphasis"]
    assert elem.has_class("Emphasis") is True
    assert elem.has_class("Missing") is False
    assert elem.has_class(None) is False

    elem.set_class_names(None)
    assert elem.get_class_names().is_empty()
    assert elem.get_cos_object().get_dictionary_object(_C) is None


def test_wave647_role_map_chains_cycles_and_non_name_values_are_handled() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    role_map = COSDictionary()
    role_map.set_item(_name("FancyParagraph"), _name("BodyText"))
    role_map.set_item(_name("BodyText"), _name("P"))
    role_map.set_item(_name("LoopA"), _name("LoopB"))
    role_map.set_item(_name("LoopB"), _name("LoopA"))
    role_map.set_item(_name("Ignored"), COSInteger.get(4))
    root.set_item(_ROLE_MAP, role_map)

    paragraph = PDStructureElement(structure_type="FancyParagraph")
    paragraph.set_parent(root)
    loop = PDStructureElement(structure_type="LoopA")
    loop.set_parent(root)

    assert paragraph.get_role_map() == {
        "FancyParagraph": "BodyText",
        "BodyText": "P",
        "LoopA": "LoopB",
        "LoopB": "LoopA",
    }
    assert paragraph.get_standard_structure_type() == "P"
    assert paragraph.is_block_level() is True
    assert loop.get_standard_structure_type() == "LoopA"
    assert loop.is_resolved_structure_type_standard() is False


def test_wave647_descendant_walk_skips_cycles_and_find_by_role_uses_resolved_type() -> None:
    root = COSDictionary()
    root.set_name(_TYPE, "StructTreeRoot")
    role_map = COSDictionary()
    role_map.set_item(_name("AsideLink"), _name("Link"))
    root.set_item(_ROLE_MAP, role_map)

    parent = PDStructureElement(structure_type="Sect")
    parent.set_parent(root)
    child = PDStructureElement(structure_type="AsideLink")
    child.set_parent(parent)
    grandchild = PDStructureElement(structure_type="Span")
    grandchild.set_parent(child)

    parent.get_cos_object().set_item(_K, COSArray())
    parent.get_cos_object().get_dictionary_object(_K).add(child.get_cos_object())
    child.get_cos_object().set_item(_K, COSArray())
    child.get_cos_object().get_dictionary_object(_K).add(grandchild.get_cos_object())
    child.get_cos_object().get_dictionary_object(_K).add(parent.get_cos_object())

    assert [node.get_structure_type() for node in parent.iter_descendants()] == [
        "AsideLink",
        "Span",
    ]
    assert parent.find_first_by_role("Link").get_cos_object() is child.get_cos_object()
    assert list(parent.find_by_role("Missing")) == []


def test_wave647_broken_parent_chain_does_not_look_like_attached_root() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.get_cos_object().set_item(_P, COSInteger.get(1))

    assert elem.get_parent() == COSInteger.get(1)
    assert elem.get_parent_node() is None
    assert elem.get_structure_tree_root() is None
    assert elem.is_root_attached() is False
