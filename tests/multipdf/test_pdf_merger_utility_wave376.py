from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_ANNOTS = COSName.get_pdf_name("Annots")
_DESTS = COSName.get_pdf_name("Dests")
_ID_TREE = COSName.get_pdf_name("IDTree")
_NAMES = COSName.get_pdf_name("Names")
_NUMS = COSName.get_pdf_name("Nums")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_P = COSName.get_pdf_name("P")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")


def _build_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def _save_to_path(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _catalog_dict(doc: PDDocument) -> COSDictionary:
    return doc.get_document_catalog().get_cos_object()


def test_wave376_add_source_accepts_memoryview(tmp_path: Path) -> None:
    source_path = tmp_path / "source.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(2), source_path)

    util = PDFMergerUtility()
    util.add_source(memoryview(source_path.read_bytes()))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2


def test_wave376_open_source_rejects_text_stream_payload() -> None:
    class TextStream:
        def read(self) -> str:
            return "not bytes"

    with pytest.raises(TypeError, match=r"read\(\) must return bytes"):
        PDFMergerUtility._open_source(TextStream())  # noqa: SLF001


def test_wave376_append_document_rejects_closed_source() -> None:
    util = PDFMergerUtility()
    destination = _build_doc(1)
    source = _build_doc(1)
    source.close()

    with pytest.raises(OSError, match="source PDF is closed"):
        util.append_document(destination, source)

    destination.close()


def test_wave376_append_document_rejects_closed_destination() -> None:
    util = PDFMergerUtility()
    destination = _build_doc(1)
    source = _build_doc(1)
    destination.close()

    with pytest.raises(OSError, match="destination PDF is closed"):
        util.append_document(destination, source)

    source.close()


def test_wave376_misplaced_id_tree_is_removed_from_names_dictionary() -> None:
    destination = _build_doc(1)
    source = _build_doc(1)
    names = COSDictionary()
    bogus_id_tree = COSDictionary()
    bogus_id_tree.set_item(_NAMES, COSArray())
    names.set_item(_ID_TREE, bogus_id_tree)
    _catalog_dict(source).set_item(_NAMES, names)

    PDFMergerUtility().append_document(destination, source)

    merged_names = _catalog_dict(destination).get_dictionary_object(_NAMES)
    assert isinstance(merged_names, COSDictionary)
    assert not merged_names.contains_key(_ID_TREE)
    source.close()
    destination.close()


def test_wave376_legacy_dests_merge_into_existing_destination_dictionary() -> None:
    destination = _build_doc(1)
    dest_dests = COSDictionary()
    dest_dests.set_string(COSName.get_pdf_name("A"), "dest")
    _catalog_dict(destination).set_item(_DESTS, dest_dests)

    source = _build_doc(1)
    src_dests = COSDictionary()
    src_dests.set_string(COSName.get_pdf_name("B"), "source")
    _catalog_dict(source).set_item(_DESTS, src_dests)

    PDFMergerUtility().append_document(destination, source)

    merged_dests = _catalog_dict(destination).get_dictionary_object(_DESTS)
    assert isinstance(merged_dests, COSDictionary)
    assert merged_dests.get_string(COSName.get_pdf_name("A")) == "dest"
    assert merged_dests.get_string(COSName.get_pdf_name("B")) == "source"
    source.close()
    destination.close()


def test_wave376_invalid_page_label_index_rolls_back_partial_append() -> None:
    destination = _build_doc(1)
    dest_nums = COSArray()
    dest_nums.add(COSInteger.get(0))
    dest_label = COSDictionary()
    dest_label.set_string(_P, "D-")
    dest_nums.add(dest_label)
    dest_labels = COSDictionary()
    dest_labels.set_item(_NUMS, dest_nums)
    _catalog_dict(destination).set_item(_PAGE_LABELS, dest_labels)

    source = _build_doc(1)
    src_nums = COSArray()
    src_nums.add(COSName.get_pdf_name("BadIndex"))
    src_label = COSDictionary()
    src_label.set_string(_P, "S-")
    src_nums.add(src_label)
    src_labels = COSDictionary()
    src_labels.set_item(_NUMS, src_nums)
    _catalog_dict(source).set_item(_PAGE_LABELS, src_labels)

    PDFMergerUtility().append_document(destination, source)

    merged_nums = (
        _catalog_dict(destination)
        .get_dictionary_object(_PAGE_LABELS)
        .get_dictionary_object(_NUMS)
    )
    assert isinstance(merged_nums, COSArray)
    assert merged_nums.size() == 2
    assert merged_nums.get_object(0).int_value() == 0
    assert merged_nums.get_object(1).get_string(_P) == "D-"
    source.close()
    destination.close()


def test_wave376_update_struct_parent_entries_leaves_negative_sentinels() -> None:
    page_dict = COSDictionary()
    page_dict.set_item(_STRUCT_PARENTS, COSInteger.get(-1))
    annot = COSDictionary()
    annot.set_item(_STRUCT_PARENT, COSInteger.get(-1))
    annots = COSArray()
    annots.add(annot)
    annots.add(COSName.get_pdf_name("NonDictionaryEntry"))
    page_dict.set_item(_ANNOTS, annots)

    PDFMergerUtility._update_struct_parent_entries(page_dict, 10)  # noqa: SLF001

    assert page_dict.get_dictionary_object(_STRUCT_PARENTS).int_value() == -1
    assert annot.get_dictionary_object(_STRUCT_PARENT).int_value() == -1
