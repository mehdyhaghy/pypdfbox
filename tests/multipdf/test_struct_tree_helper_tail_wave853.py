from __future__ import annotations

import pytest

import tests.multipdf.test_pdf_merger_utility_struct_tree as struct_tree_tests
from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from tests.multipdf.test_pdf_merger_utility_struct_tree import _build_structured_doc


def test_wave853_structured_doc_helper_rejects_mismatched_parent_keys() -> None:
    with pytest.raises(ValueError, match="one entry per page"):
        _build_structured_doc(page_count=2, parent_tree_keys=[0])


def test_wave853_structured_doc_helper_builds_id_tree() -> None:
    doc = _build_structured_doc(
        page_count=2,
        parent_tree_keys=[0, 1],
        id_tree={"intro": "para-0", "body": "para-1"},
    )
    try:
        root = doc.get_document_catalog().get_struct_tree_root()
        assert root is not None

        id_tree = root.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("IDTree")
        )
        names = id_tree.get_dictionary_object(COSName.get_pdf_name("Names"))

        assert isinstance(names, COSArray)
        assert names.size() == 4
        intro = names.get_object(1)
        body = names.get_object(3)
        assert isinstance(intro, COSDictionary)
        assert isinstance(body, COSDictionary)
        assert intro.get_string(COSName.get_pdf_name("ID")) == "intro"
        assert body.get_string(COSName.get_pdf_name("T")) == "para-1"
    finally:
        doc.close()


def test_wave853_structured_doc_helper_rejects_missing_id_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs: list[PDDocument] = []

    class TrackingDocument(PDDocument):
        def __init__(self) -> None:
            super().__init__()
            docs.append(self)

    monkeypatch.setattr(struct_tree_tests, "PDDocument", TrackingDocument)

    with pytest.raises(ValueError, match="missing kid"):
        _build_structured_doc(
            page_count=1,
            parent_tree_keys=[0],
            id_tree={"missing": "para-9"},
        )

    for doc in docs:
        doc.close()
