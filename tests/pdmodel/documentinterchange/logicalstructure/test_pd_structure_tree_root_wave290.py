from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
    PDStructureTreeRoot,
)


def test_wave290_malformed_tree_entries_report_absent() -> None:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("RoleMap"), COSString("bad"))
    dictionary.set_item(COSName.get_pdf_name("ClassMap"), COSString("bad"))
    dictionary.set_item(COSName.get_pdf_name("ParentTree"), COSName.get_pdf_name("bad"))
    dictionary.set_item(COSName.get_pdf_name("IDTree"), COSString("bad"))

    root = PDStructureTreeRoot(dictionary)

    assert root.get_role_map() == {}
    assert root.get_class_map() is None
    assert root.get_parent_tree() is None
    assert root.get_id_tree() is None
    assert root.has_role_map() is False
    assert root.has_class_map() is False
    assert root.has_parent_tree() is False
    assert root.has_id_tree() is False

