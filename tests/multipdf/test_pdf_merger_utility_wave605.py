from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.multipdf.pdf_merger_utility import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)

_ID_TREE = COSName.get_pdf_name("IDTree")
_K = COSName.get_pdf_name("K")
_NAMES = COSName.get_pdf_name("Names")
_OBJ = COSName.get_pdf_name("Obj")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")


class _IdentityCloner:
    def clone_for_new_document(self, value: object) -> object:
        return value

    def _clone_merge_cos_base(
        self,
        src: COSDictionary,
        dst: COSDictionary,
        exclude: set[COSName],
    ) -> None:
        for key, value in src.entry_set():
            if key not in exclude:
                dst.set_item(key, value)


class _Catalog:
    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _StructRoot:
    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        self.parent_tree: object | None = None
        self.parent_tree_next_key: int | None = None

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_id_tree(self) -> None:
        return None

    def set_parent_tree(self, parent_tree: object) -> None:
        self.parent_tree = parent_tree

    def set_parent_tree_next_key(self, value: int) -> None:
        self.parent_tree_next_key = value


def test_wave605_config_aliases_destinations_and_sources_round_trip() -> None:
    util = PDFMergerUtility()
    stream = io.BytesIO()

    util.document_merge_mode_property = DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    util.acro_form_merge_mode_property = AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    util.set_destination(stream)
    util.add_sources([b"one", bytearray(b"two")])

    assert util.get_document_merge_mode() is DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    assert util.document_merge_mode_property is DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    assert util.get_acro_form_merge_mode() is AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    assert util.acro_form_merge_mode_property is AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    assert util.get_destination_stream() is stream
    assert util.get_destination_file_name() is None
    assert util.get_sources() == [b"one", bytearray(b"two")]

    with pytest.raises(TypeError, match="expected an iterable of sources"):
        util.add_sources(b"single")
    with pytest.raises(TypeError, match="unsupported destination type"):
        util.set_destination(object())  # type: ignore[arg-type]


def test_wave605_merge_with_source_requires_destination() -> None:
    util = PDFMergerUtility()
    util.add_source(b"%PDF-1.4\n")

    with pytest.raises(ValueError, match="Either set_destination_file_name"):
        util.merge_documents()


def test_wave605_merge_names_removes_misplaced_id_tree_from_destination(
    caplog: pytest.LogCaptureFixture,
) -> None:
    names = COSDictionary()
    names.set_item(_ID_TREE, COSDictionary())
    source = _Catalog()
    source.get_cos_object().set_item(_NAMES, names)
    destination = _Catalog()

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_names(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            source,
            destination,
        )

    installed = destination.get_cos_object().get_dictionary_object(_NAMES)
    assert isinstance(installed, COSDictionary)
    assert installed.get_dictionary_object(_ID_TREE) is None
    assert "Removed /IDTree" in caplog.text


def test_wave605_finish_struct_tree_merge_rekeys_parent_tree_entries() -> None:
    src_leaf = COSDictionary()
    dest_leaf = COSDictionary()
    src_root = _StructRoot()
    dest_root = _StructRoot()

    PDFMergerUtility()._finish_struct_tree_merge(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        src_root,
        dest_root,
        {0: src_leaf},
        {7: dest_leaf},
        10,
        {},
    )

    assert dest_root.parent_tree_next_key == 11
    assert dest_root.parent_tree is not None
    numbers = dest_root.parent_tree.get_numbers()  # type: ignore[attr-defined]
    assert numbers[7] is dest_leaf
    assert numbers[10] is src_leaf


def test_wave605_update_page_references_recurses_through_nested_arrays() -> None:
    old_page = COSDictionary()
    new_page = COSDictionary()
    old_obj = COSDictionary()
    new_obj = COSDictionary()
    nested = COSDictionary()
    nested.set_item(_PG, old_page)
    nested.set_item(_OBJ, old_obj)
    parent_tree_value = COSArray([COSString("skip"), COSArray([nested])])

    PDFMergerUtility()._update_page_references_map(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        {0: parent_tree_value},
        {id(old_page): new_page, id(old_obj): new_obj},
    )

    assert nested.get_dictionary_object(_PG) is new_page
    assert nested.get_dictionary_object(_OBJ) is new_obj


def test_wave605_role_map_installs_when_destination_missing() -> None:
    source_role_map = COSDictionary()
    source_role_map.set_item(COSName.get_pdf_name("Custom"), COSName.get_pdf_name("P"))
    src_root_dict = COSDictionary()
    src_root_dict.set_item(_ROLE_MAP, source_role_map)
    dest_root_dict = COSDictionary()

    PDFMergerUtility()._merge_role_map(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _StructRoot(src_root_dict),
        _StructRoot(dest_root_dict),
    )

    assert dest_root_dict.get_dictionary_object(_ROLE_MAP) is source_role_map


def test_wave605_has_only_documents_or_parts_rejects_malformed_entries() -> None:
    assert PDFMergerUtility._has_only_documents_or_parts(  # noqa: SLF001
        COSArray([COSInteger.get(1)])
    ) is False
