from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.common import PDMatrix, PDMetadata, PDStringNameTreeNode
from pypdfbox.pdmodel.common.pdfdoc_encoding import decode_bytes


def test_matrix_number_at_rejects_non_number_entry() -> None:
    arr = COSArray([COSName.A])

    with pytest.raises(TypeError, match="matrix index 0"):
        PDMatrix._number_at(arr, 0)


def test_metadata_none_constructor_imports_optional_input_data() -> None:
    meta = PDMetadata(None, b"<rdf:RDF/>")

    assert meta.export_xmp_metadata() == b"<rdf:RDF/>"
    assert meta.is_metadata_stream() is True


def test_string_name_tree_rejects_non_string_leaf_value() -> None:
    tree = PDStringNameTreeNode()

    with pytest.raises(OSError, match="Expected COSString"):
        tree.convert_cos_to_value(COSName.A)


def test_string_name_tree_converts_string_leaf_value() -> None:
    tree = PDStringNameTreeNode()

    assert tree.convert_cos_to_value(COSString("payload")) == "payload"


def test_pdfdoc_decode_uses_question_mark_for_out_of_table_integer() -> None:
    assert decode_bytes([300]) == "?"  # type: ignore[arg-type]
