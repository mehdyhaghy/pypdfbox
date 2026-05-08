from __future__ import annotations

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.revisions import Revisions

_C = COSName.get_pdf_name("C")


def test_wave326_set_class_names_single_zero_revision_serializes_bare_name() -> None:
    elem = PDStructureElement(structure_type="P")
    elem.set_revision_number(9)
    class_names: Revisions[COSName] = Revisions()
    class_names.add_object(COSName.get_pdf_name("Body"))

    elem.set_class_names(class_names)

    stored = elem.get_cos_object().get_dictionary_object(_C)
    assert isinstance(stored, COSName)
    assert stored.get_name() == "Body"

    got = elem.get_class_names()
    assert got.size() == 1
    assert got.get_object_at(0) == COSName.get_pdf_name("Body")
    assert got.get_revision_number_at(0) == 0


def test_wave326_set_class_names_changed_revision_keeps_array_shape() -> None:
    elem = PDStructureElement(structure_type="P")
    class_names: Revisions[COSName] = Revisions()
    class_names.add_object(COSName.get_pdf_name("Body"), 4)

    elem.set_class_names(class_names)

    stored = elem.get_cos_object().get_dictionary_object(_C)
    assert isinstance(stored, COSArray)
    assert stored.size() == 2

    got = elem.get_class_names()
    assert got.size() == 1
    assert got.get_object_at(0) == COSName.get_pdf_name("Body")
    assert got.get_revision_number_at(0) == 4
