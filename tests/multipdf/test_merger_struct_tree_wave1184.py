"""Coverage cleanup for ``tests.multipdf.test_merger_struct_tree`` helpers."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from tests.multipdf.test_merger_struct_tree import _build_minimal_struct_doc


def test_build_minimal_struct_doc_accepts_raw_role_map_dict() -> None:
    role_map = COSDictionary()
    role_map.set_item(COSName.get_pdf_name("Custom"), COSName.get_pdf_name("P"))

    doc = _build_minimal_struct_doc(extra_role_map_dict=role_map)
    try:
        root = doc.get_document_catalog().get_struct_tree_root()
        assert root.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("RoleMap")
        ) is role_map
    finally:
        doc.close()
