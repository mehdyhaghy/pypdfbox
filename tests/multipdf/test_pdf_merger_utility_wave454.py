from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_ANNOTS = COSName.get_pdf_name("Annots")
_FIELDS = COSName.get_pdf_name("Fields")
_K = COSName.get_pdf_name("K")
_NUMS = COSName.get_pdf_name("Nums")
_P = COSName.get_pdf_name("P")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_T = COSName.get_pdf_name("T")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def test_wave454_open_source_rejects_binary_stream_returning_text() -> None:
    with pytest.raises(TypeError, match="binary stream source read"):
        PDFMergerUtility._open_source(io.StringIO("%PDF-1.7"))  # type: ignore[arg-type]  # noqa: SLF001,E501


def test_wave454_acroform_legacy_mode_empty_source_fields_is_noop() -> None:
    class Form:
        def __init__(self, fields: list[object]) -> None:
            self._fields = fields
            self._dict = COSDictionary()

        def get_fields(self) -> list[object]:
            return self._fields

        def get_field_tree(self) -> list[object]:
            return []

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    dest_form = Form([])

    PDFMergerUtility()._acro_form_legacy_mode(  # noqa: SLF001
        _IdentityCloner(), dest_form, Form([])
    )

    assert not dest_form.get_cos_object().contains_key(_FIELDS)


def test_wave454_join_fields_mode_empty_source_fields_leaves_destination() -> None:
    class Form:
        def __init__(self, fields: list[object]) -> None:
            self._fields = fields
            self._dict = COSDictionary()

        def get_fields(self) -> list[object]:
            return self._fields

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    dest_form = Form([])

    PDFMergerUtility()._acro_form_join_fields_mode(  # noqa: SLF001
        _IdentityCloner(), dest_form, Form([])
    )

    assert not dest_form.get_cos_object().contains_key(_FIELDS)


def test_wave454_page_labels_invalid_index_rolls_back_partial_append(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = _make_doc(1)
    destination = _make_doc(2)
    src_nums = COSArray()
    src_nums.add(COSInteger.get(0))
    first_label = COSDictionary()
    first_label.set_string(_P, "A-")
    src_nums.add(first_label)
    src_nums.add(COSName.get_pdf_name("BadIndex"))
    src_nums.add(COSDictionary())
    src_labels = COSDictionary()
    src_labels.set_item(_NUMS, src_nums)
    source.get_document_catalog().get_cos_object().set_item(_PAGE_LABELS, src_labels)

    dest_nums = COSArray()
    existing_label = COSDictionary()
    dest_nums.add(COSInteger.get(0))
    dest_nums.add(existing_label)
    dest_labels = COSDictionary()
    dest_labels.set_item(_NUMS, dest_nums)
    destination.get_document_catalog().get_cos_object().set_item(
        _PAGE_LABELS, dest_labels
    )

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_page_labels(  # noqa: SLF001
            _IdentityCloner(), source, destination
        )

    assert dest_nums.size() == 2
    assert dest_nums.get_object(1) is existing_label
    assert "page labels ignored" in caplog.text
    source.close()
    destination.close()


def test_wave454_update_struct_parent_entries_offsets_non_negative_values() -> None:
    page = COSDictionary()
    page.set_item(_STRUCT_PARENTS, COSInteger.get(4))
    shifted_annot = COSDictionary()
    shifted_annot.set_item(_STRUCT_PARENT, COSInteger.get(1))
    negative_annot = COSDictionary()
    negative_annot.set_item(_STRUCT_PARENT, COSInteger.get(-1))
    annots = COSArray()
    annots.add(shifted_annot)
    annots.add(negative_annot)
    annots.add(COSName.get_pdf_name("NotADict"))
    page.set_item(_ANNOTS, annots)

    PDFMergerUtility._update_struct_parent_entries(page, 10)  # noqa: SLF001

    assert page.get_dictionary_object(_STRUCT_PARENTS).int_value() == 14
    assert shifted_annot.get_dictionary_object(_STRUCT_PARENT).int_value() == 11
    assert negative_annot.get_dictionary_object(_STRUCT_PARENT).int_value() == -1


def test_wave454_merge_k_entries_installs_source_k_when_destination_empty() -> None:
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("P"))
    src_root = COSDictionary()
    src_root.set_item(_K, child)
    dest_root = COSDictionary()

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(), _Root(src_root), _Root(dest_root)
    )

    merged = dest_root.get_dictionary_object(_K)
    assert isinstance(merged, COSArray)
    assert merged.size() == 1
    assert merged.get_object(0) is child
    assert child.get_dictionary_object(_P) is dest_root


def test_wave454_merge_role_map_installs_missing_destination_map() -> None:
    src_role_map = COSDictionary()
    src_role_map.set_item(COSName.get_pdf_name("Heading"), COSName.get_pdf_name("H1"))
    src_root = COSDictionary()
    src_root.set_item(_ROLE_MAP, src_role_map)
    dest_root = COSDictionary()

    PDFMergerUtility()._merge_role_map(  # noqa: SLF001
        _IdentityCloner(), _Root(src_root), _Root(dest_root)
    )

    assert dest_root.get_dictionary_object(_ROLE_MAP) is src_role_map


def test_wave454_mode_setters_round_trip_join_fields_mode() -> None:
    util = PDFMergerUtility()

    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)

    assert util.get_acro_form_merge_mode() is AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
