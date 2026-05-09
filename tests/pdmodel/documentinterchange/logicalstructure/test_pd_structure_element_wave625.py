from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDMarkedContentReference,
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave625_role_map_resolution_drives_standard_category_predicates() -> None:
    root = COSDictionary()
    role_map = COSDictionary()
    role_map.set_item(_name("Sidebar"), _name("Sect"))
    role_map.set_item(_name("FancyCaption"), _name("Caption"))
    root.set_name(_name("Type"), "StructTreeRoot")
    root.set_item(_name("RoleMap"), role_map)

    section = PDStructureElement(structure_type="Sidebar")
    section.set_parent(root)
    caption = PDStructureElement(structure_type="FancyCaption")
    caption.set_parent(root)
    figure = PDStructureElement(structure_type=PDStructureElement.FIGURE)

    assert section.get_role_map() == {
        "Sidebar": "Sect",
        "FancyCaption": "Caption",
    }
    assert section.get_standard_structure_type_name() == "Sect"
    assert section.is_resolved_structure_type_standard() is True
    assert section.is_grouping_level() is True
    assert section.is_block_level() is False
    assert caption.is_grouping_level() is True
    assert figure.is_illustration_level() is True
    assert PDStructureElement.is_standard_structure_type("MadeUp") is False
    assert PDStructureElement.is_standard_structure_type(None) is False


def test_wave625_typed_kid_filters_and_marked_content_reference_collection() -> None:
    elem = PDStructureElement(structure_type="P")
    child = PDStructureElement(structure_type="Span")
    mcr = PDMarkedContentReference()
    mcr.set_mcid(9)
    objr = PDObjectReference()

    elem.append_kid_element(child)
    elem.append_kid_mcid(3)
    elem.append_kid_marked_content(mcr)
    elem.append_kid_object_reference(objr)

    assert elem.count_kids() == 4
    assert list(elem.iter_kid_elements())[0].get_cos_object() is child.get_cos_object()
    assert list(elem.iter_object_references())[0].get_cos_object() is objr.get_cos_object()
    marked_refs = elem.get_marked_content_references()
    assert marked_refs[0] == 3
    assert marked_refs[1].get_cos_object() is mcr.get_cos_object()
    assert child.get_parent() is elem.get_cos_object()

    assert elem.remove_kid_element(PDStructureElement(structure_type="Span")) is False
    assert elem.remove_kid_object_reference(None) is False
    assert elem.remove_kid_marked_content(None) is False

    elem.clear_kids()
    assert elem.count_kids() == 0
    assert elem.get_marked_content_references() == []


def test_wave625_set_standard_structure_type_rejects_none_and_writes_s() -> None:
    elem = PDStructureElement()

    elem.set_standard_structure_type(PDStructureElement.H1)

    assert elem.get_structure_type() == "H1"
    assert elem.is_block_level() is True

    try:
        elem.set_standard_structure_type(None)  # type: ignore[arg-type]
    except ValueError as exc:
        assert "shall not be null" in str(exc)
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("set_standard_structure_type(None) should fail")
