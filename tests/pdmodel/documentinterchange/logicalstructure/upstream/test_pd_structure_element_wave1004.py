from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDAttributeObject,
    PDStructureElement,
    Revisions,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.pdmodel.documentinterchange.logicalstructure.upstream.test_pd_structure_element import (
    _check_element,
)


def test_check_element_returns_for_non_dictionary_leaf() -> None:
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()

    _check_element(COSName.get_pdf_name("NotADictionary"), attribute_set, None, class_set)

    assert attribute_set == []
    assert class_set == set()


def test_check_element_recurses_from_page_element_kids() -> None:
    page = PDPage()
    parent = PDStructureElement(structure_type="Div")
    parent.set_page(page)
    child = PDStructureElement(structure_type="P")
    child.set_page(page)
    parent.append_kid(child)
    attribute_set: list[Revisions[PDAttributeObject]] = []
    class_set: set[str] = set()

    _check_element(parent.get_cos_object(), attribute_set, None, class_set)

    assert len(attribute_set) == 2
    assert class_set == set()
