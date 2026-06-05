from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.multipdf import AcroFormMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_ANNOTS = COSName.get_pdf_name("Annots")
_K = COSName.get_pdf_name("K")
_NAMES = COSName.get_pdf_name("Names")
_NUMS = COSName.get_pdf_name("Nums")
_OBJ = COSName.get_pdf_name("Obj")
_OC_PROPERTIES = COSName.get_pdf_name("OCProperties")
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")
_P = COSName.get_pdf_name("P")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_PART = COSName.get_pdf_name("Part")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_THREADS = COSName.get_pdf_name("Threads")
_TYPE = COSName.get_pdf_name("Type")


class _IdentityCloner:
    def clone_for_new_document(self, value: Any) -> Any:
        return value

    def _clone_merge_cos_base(
        self,
        src: COSDictionary,
        dst: COSDictionary,
        exclude: set[COSName],
    ) -> None:
        for key, value in src.entry_set():
            if key not in exclude and not dst.contains_key(key):
                dst.set_item(key, value)


class _Catalog:
    def __init__(self) -> None:
        self._dict = COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict or COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def _build_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(n_pages):
        doc.add_page(PDPage())
    return doc


def _save_doc(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def test_wave388_destination_accessors_route_path_stream_and_reject_bad_type(
    tmp_path: Path,
) -> None:
    util = PDFMergerUtility()
    out = tmp_path / "merged.pdf"
    sink = io.BytesIO()
    info = object()
    metadata = object()

    util.set_destination(out)
    assert util.get_destination_file_name() == out
    util.set_destination(sink)
    assert util.get_destination_stream() is sink
    util.set_destination_document_information(info)
    util.set_destination_metadata(metadata)
    util.set_ignore_acro_form_errors(1)

    assert util.get_destination_document_information() is info
    assert util.get_destination_metadata() is metadata
    assert util.is_ignore_acro_form_errors()
    with pytest.raises(TypeError, match="unsupported destination type"):
        util.set_destination(123)  # type: ignore[arg-type]


def test_wave388_random_access_read_overload_rejects_non_random_access() -> None:
    util = PDFMergerUtility()

    with pytest.raises(TypeError, match="RandomAccessRead instance"):
        util.merge_documents_random_access_read([b"%PDF-1.7\n"])  # type: ignore[list-item]

    assert util.get_sources() == []


def test_wave388_open_source_returns_open_document_without_taking_ownership() -> None:
    doc = _build_doc(1)

    opened, owns = PDFMergerUtility._open_source(doc)  # noqa: SLF001

    assert opened is doc
    assert owns is False
    doc.close()


def test_wave388_open_source_rejects_unsupported_source_type() -> None:
    with pytest.raises(TypeError, match="unsupported source type"):
        PDFMergerUtility._open_source(object())  # type: ignore[arg-type]  # noqa: SLF001


def test_wave388_random_access_sources_remain_caller_owned(tmp_path: Path) -> None:
    from pypdfbox.io import RandomAccessReadBuffer

    src_path = tmp_path / "src.pdf"
    out = tmp_path / "out.pdf"
    _save_doc(_build_doc(1), src_path)
    rar = RandomAccessReadBuffer(src_path.read_bytes())

    util = PDFMergerUtility()
    util.set_destination_file_name(str(out))
    util.merge_documents_random_access_read([rar])

    assert out.exists()
    assert not rar.is_closed()
    rar.close()


def test_wave388_dynamic_xfa_helper_handles_true_false_and_raises() -> None:
    class Dynamic:
        def xfa_is_dynamic(self) -> bool:
            return True

    class Static:
        def xfa_is_dynamic(self) -> bool:
            return False

    class Broken:
        def xfa_is_dynamic(self) -> bool:
            raise RuntimeError("unreadable")

    assert PDFMergerUtility._is_dynamic_xfa(Dynamic())  # noqa: SLF001
    assert not PDFMergerUtility._is_dynamic_xfa(Static())  # noqa: SLF001
    assert not PDFMergerUtility._is_dynamic_xfa(Broken())  # noqa: SLF001
    assert not PDFMergerUtility._is_dynamic_xfa(object())  # noqa: SLF001


def test_wave388_merge_into_respects_exclude_and_existing_destination() -> None:
    src = COSDictionary()
    dst = COSDictionary()
    keep = COSName.get_pdf_name("Keep")
    skip = COSName.get_pdf_name("Skip")
    existing = COSName.get_pdf_name("Existing")
    src.set_string(keep, "copied")
    src.set_string(skip, "excluded")
    src.set_string(existing, "source")
    dst.set_string(existing, "dest")

    PDFMergerUtility._merge_into(src, dst, _IdentityCloner(), {skip})  # noqa: SLF001

    assert dst.get_string(keep) == "copied"
    assert dst.get_string(existing) == "dest"
    assert not dst.contains_key(skip)


def test_wave388_acroform_join_mode_appends_verbatim_fields() -> None:
    class Field:
        def __init__(self, name: str) -> None:
            self._dict = COSDictionary()
            self._dict.set_string(COSName.get_pdf_name("T"), name)
            self._name = name

        def get_cos_object(self) -> COSDictionary:
            return self._dict

        def get_partial_name(self) -> str:
            return self._name

        def get_fully_qualified_name(self) -> str:
            return self._name

    class Form:
        def __init__(self, fields: list[Field]) -> None:
            self._fields = fields
            self._dict = COSDictionary()

        def get_fields(self) -> list[Field]:
            return self._fields

        # JOIN delegates to legacy mode in PDFBox 3.0.x; legacy mode walks
        # the destination field tree and looks up by FQ name for collisions.
        def get_field_tree(self) -> list[Field]:
            return []

        def get_field(self, _name: str) -> None:
            return None

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    util = PDFMergerUtility()
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    dest_form = Form([])
    src_fields = [Field("A"), Field("B")]

    # No collision (dest empty) → both fields appended verbatim under both modes.
    util._acro_form_join_fields_mode(_IdentityCloner(), dest_form, Form(src_fields))  # noqa: SLF001

    fields = dest_form.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Fields"))
    assert isinstance(fields, COSArray)
    assert fields.size() == 2
    assert fields.get_object(0) is src_fields[0].get_cos_object()
    assert fields.get_object(1) is src_fields[1].get_cos_object()


def test_wave388_acroform_merge_errors_can_be_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenCatalog:
        def get_acro_form(self) -> object:
            raise RuntimeError("cannot inspect form")

    util = PDFMergerUtility()
    util.set_ignore_acro_form_errors(True)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util._merge_acro_form(_IdentityCloner(), BrokenCatalog(), BrokenCatalog())  # noqa: SLF001

    assert "AcroForm merge error ignored" in caplog.text


def test_wave388_threads_append_into_existing_destination_array() -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    src_threads = COSArray()
    dest_threads = COSArray()
    src_thread = COSDictionary()
    dest_thread = COSDictionary()
    src_threads.add(src_thread)
    dest_threads.add(dest_thread)
    src_catalog.get_cos_object().set_item(_THREADS, src_threads)
    dest_catalog.get_cos_object().set_item(_THREADS, dest_threads)

    PDFMergerUtility()._merge_threads(  # noqa: SLF001
        _IdentityCloner(), src_catalog, dest_catalog
    )

    assert dest_threads.size() == 2
    assert dest_threads.get_object(0) is dest_thread
    assert dest_threads.get_object(1) is src_thread


def test_wave388_page_labels_create_destination_nums_when_missing() -> None:
    source = _build_doc(1)
    destination = _build_doc(2)
    src_nums = COSArray()
    src_nums.add(COSInteger.get(0))
    label = COSDictionary()
    label.set_string(COSName.get_pdf_name("P"), "S-")
    src_nums.add(label)
    src_labels = COSDictionary()
    src_labels.set_item(_NUMS, src_nums)
    source.get_document_catalog().get_cos_object().set_item(_PAGE_LABELS, src_labels)

    PDFMergerUtility()._merge_page_labels(  # noqa: SLF001
        _IdentityCloner(), source, destination
    )

    merged_nums = (
        destination.get_document_catalog()
        .get_cos_object()
        .get_dictionary_object(_PAGE_LABELS)
        .get_dictionary_object(_NUMS)
    )
    assert isinstance(merged_nums, COSArray)
    assert merged_nums.get_object(0).int_value() == 2
    assert merged_nums.get_object(1) is label
    source.close()
    destination.close()


def test_wave388_catalog_array_and_dictionary_merges_append_or_overlay() -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    oc_src = COSDictionary()
    oc_dst = COSDictionary()
    oc_src.set_string(COSName.get_pdf_name("SourceOnly"), "yes")
    oc_dst.set_string(COSName.get_pdf_name("DestOnly"), "yes")
    src_catalog.get_cos_object().set_item(_OC_PROPERTIES, oc_src)
    dest_catalog.get_cos_object().set_item(_OC_PROPERTIES, oc_dst)
    output_src = COSArray()
    output_dst = COSArray()
    output_src_item = COSDictionary()
    output_dst_item = COSDictionary()
    output_src.add(output_src_item)
    output_dst.add(output_dst_item)
    src_catalog.get_cos_object().set_item(_OUTPUT_INTENTS, output_src)
    dest_catalog.get_cos_object().set_item(_OUTPUT_INTENTS, output_dst)

    util = PDFMergerUtility()
    util._merge_oc_properties(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001
    util._merge_output_intents(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001

    assert oc_dst.get_string(COSName.get_pdf_name("DestOnly")) == "yes"
    assert oc_dst.get_string(COSName.get_pdf_name("SourceOnly")) == "yes"
    assert output_dst.size() == 2
    assert output_dst.get_object(1) is output_src_item


def test_wave388_open_action_is_first_source_wins() -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    first = COSDictionary()
    second = COSDictionary()
    src_catalog.get_cos_object().set_item(_OPEN_ACTION, first)

    util = PDFMergerUtility()
    util._merge_open_action(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001
    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is first

    src_catalog.get_cos_object().set_item(_OPEN_ACTION, second)
    util._merge_open_action(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001
    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is first


def test_wave388_strip_struct_parent_from_annotations_only_touches_dict_entries() -> None:
    page_dict = COSDictionary()
    annot = COSDictionary()
    annot.set_item(_STRUCT_PARENT, COSInteger.get(4))
    annots = COSArray()
    annots.add(annot)
    annots.add(COSName.get_pdf_name("NotADict"))
    page_dict.set_item(_ANNOTS, annots)

    PDFMergerUtility._strip_struct_parent_from_annots(page_dict)  # noqa: SLF001

    assert not annot.contains_key(_STRUCT_PARENT)


def test_wave388_tree_map_helpers_recurse_and_unwrap_cos_objects() -> None:
    class Wrapper:
        def __init__(self, value: COSDictionary) -> None:
            self.value = value

        def get_cos_object(self) -> COSDictionary:
            return self.value

    class Leaf:
        def __init__(self, key: object, value: COSDictionary) -> None:
            self.key = key
            self.value = value

        def get_numbers(self) -> dict[object, Wrapper]:
            return {self.key: Wrapper(self.value)}

        def get_names(self) -> dict[object, Wrapper]:
            return {self.key: Wrapper(self.value)}

        def get_kids(self) -> None:
            return None

    class Parent:
        def __init__(self, child: Leaf) -> None:
            self.child = child

        def get_numbers(self) -> None:
            return None

        def get_names(self) -> None:
            return None

        def get_kids(self) -> list[Leaf]:
            return [self.child]

    number_value = COSDictionary()
    id_value = COSDictionary()

    assert PDFMergerUtility.get_number_tree_as_map(Parent(Leaf("4", number_value))) == {
        4: number_value
    }
    assert PDFMergerUtility.get_id_tree_as_map(Parent(Leaf(7, id_value))) == {
        "7": id_value
    }


def test_wave388_prepare_struct_tree_bootstrap_strips_stale_parent_keys() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
        PDStructureTreeRoot,
    )

    source = _build_doc(1)
    destination = _build_doc(1)
    source.get_document_catalog().set_struct_tree_root(PDStructureTreeRoot())
    dest_page = destination.get_page(0)
    dest_page.get_cos_object().set_item(_STRUCT_PARENTS, COSInteger.get(9))
    annot = COSDictionary()
    annot.set_item(_STRUCT_PARENT, COSInteger.get(8))
    annots = COSArray()
    annots.add(annot)
    dest_page.get_cos_object().set_item(_ANNOTS, annots)

    result = PDFMergerUtility()._prepare_struct_tree_merge(  # noqa: SLF001
        source.get_document_catalog(),
        destination.get_document_catalog(),
        destination,
    )

    assert result[0] is False
    assert destination.get_document_catalog().get_struct_tree_root() is not None
    assert not dest_page.get_cos_object().contains_key(_STRUCT_PARENTS)
    assert not annot.contains_key(_STRUCT_PARENT)
    source.close()
    destination.close()


def test_wave388_update_page_references_handles_nested_arrays_and_orphans() -> None:
    page_old = COSDictionary()
    page_new = COSDictionary()
    obj_old = COSDictionary()
    obj_new = COSDictionary()
    orphan = COSDictionary()
    orphan.set_item(_TYPE, COSName.get_pdf_name("Annot"))
    nested = COSDictionary()
    nested.set_item(_PG, page_old)
    nested.set_item(_OBJ, orphan)
    entry = COSDictionary()
    entry.set_item(_PG, page_old)
    entry.set_item(_OBJ, obj_old)
    child_array = COSArray()
    child_array.add(nested)
    entry.set_item(_K, child_array)

    PDFMergerUtility()._update_page_references_map(  # noqa: SLF001
        _IdentityCloner(),
        {0: entry},
        {id(page_old): page_new, id(obj_old): obj_new},
    )

    assert entry.get_dictionary_object(_PG) is page_new
    assert entry.get_dictionary_object(_OBJ) is obj_new
    assert nested.get_dictionary_object(_PG) is page_new
    assert nested.get_dictionary_object(_OBJ) is orphan


def test_wave388_merge_k_entries_wraps_mixed_existing_and_source_kids() -> None:
    dest_child = COSDictionary()
    dest_child.set_item(_S, COSName.get_pdf_name("P"))
    src_child = COSDictionary()
    src_child.set_item(_S, COSName.get_pdf_name("Span"))
    src_root_dict = COSDictionary()
    src_root_dict.set_item(_K, src_child)
    dest_root_dict = COSDictionary()
    dest_root_dict.set_item(_K, dest_child)

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(), _Root(src_root_dict), _Root(dest_root_dict)
    )

    wrapper = dest_root_dict.get_dictionary_object(_K)
    assert isinstance(wrapper, COSDictionary)
    merged = wrapper.get_dictionary_object(_K)
    assert isinstance(merged, COSArray)
    assert merged.size() == 2
    assert dest_child.get_dictionary_object(_P) is wrapper
    assert src_child.get_dictionary_object(_P) is wrapper


def test_wave388_merge_k_entries_appends_under_document_when_children_are_parts() -> None:
    doc_child = COSDictionary()
    doc_child.set_item(_S, COSName.get_pdf_name("Document"))
    part_child = COSDictionary()
    part_child.set_item(_S, _PART)
    level_one = COSArray()
    level_one.add(doc_child)
    top = COSDictionary()
    top.set_item(_S, COSName.get_pdf_name("Document"))
    top.set_item(_K, level_one)
    dest_root = COSDictionary()
    dest_root.set_item(_K, top)
    src_root = COSDictionary()
    src_root.set_item(_K, part_child)

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(), _Root(src_root), _Root(dest_root)
    )

    assert level_one.size() == 2
    assert doc_child.get_dictionary_object(_P) is top
    assert part_child.get_dictionary_object(_P) is top
    assert doc_child.get_name(_S) == "Part"


def test_wave388_has_only_documents_or_parts_rejects_non_dictionary_and_roles() -> None:
    good = COSArray()
    part = COSDictionary()
    part.set_item(_S, _PART)
    good.add(part)
    bad_type = COSArray()
    bad_type.add(COSInteger.get(1))
    bad_role = COSArray()
    role = COSDictionary()
    role.set_item(_S, COSName.get_pdf_name("P"))
    bad_role.add(role)

    assert PDFMergerUtility._has_only_documents_or_parts(good)  # noqa: SLF001
    assert not PDFMergerUtility._has_only_documents_or_parts(bad_type)  # noqa: SLF001
    assert not PDFMergerUtility._has_only_documents_or_parts(bad_role)  # noqa: SLF001


def test_wave388_merge_role_map_keeps_equal_conflicts_and_adds_new_entries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    src_role_map = COSDictionary()
    dest_role_map = COSDictionary()
    same = COSName.get_pdf_name("Same")
    conflict = COSName.get_pdf_name("Conflict")
    new_key = COSName.get_pdf_name("New")
    src_role_map.set_item(same, COSName.get_pdf_name("P"))
    src_role_map.set_item(conflict, COSName.get_pdf_name("H1"))
    src_role_map.set_item(new_key, COSName.get_pdf_name("Span"))
    dest_role_map.set_item(same, COSName.get_pdf_name("P"))
    dest_role_map.set_item(conflict, COSName.get_pdf_name("P"))
    src_root = COSDictionary()
    dest_root = COSDictionary()
    src_root.set_item(_ROLE_MAP, src_role_map)
    dest_root.set_item(_ROLE_MAP, dest_role_map)

    with caplog.at_level(
        logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        PDFMergerUtility()._merge_role_map(  # noqa: SLF001
            _IdentityCloner(), _Root(src_root), _Root(dest_root)
        )

    assert dest_role_map.get_dictionary_object(same) == COSName.get_pdf_name("P")
    assert dest_role_map.get_dictionary_object(conflict) == COSName.get_pdf_name("P")
    assert dest_role_map.get_dictionary_object(new_key) == COSName.get_pdf_name("Span")
    assert "already exists in destination RoleMap" in caplog.text


def test_wave388_metadata_clone_exceptions_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenCloner:
        def clone_for_new_document(self, value: object) -> object:
            raise RuntimeError("metadata unreadable")

    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_NAMES, COSDictionary())
    src_catalog.get_cos_object().set_item(COSName.get_pdf_name("Metadata"), COSStream())

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_metadata(  # noqa: SLF001
            BrokenCloner(), src_catalog, dest_catalog, _build_doc(0)
        )

    assert "Metadata skipped" in caplog.text
