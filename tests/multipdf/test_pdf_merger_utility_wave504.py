from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_DESTS = COSName.get_pdf_name("Dests")
_FIELDS = COSName.get_pdf_name("Fields")
_K = COSName.get_pdf_name("K")
_NAMES = COSName.get_pdf_name("Names")
_OBJ = COSName.get_pdf_name("Obj")
_OPEN_ACTION = COSName.get_pdf_name("OpenAction")
_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")
_P = COSName.get_pdf_name("P")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_PG = COSName.get_pdf_name("Pg")
_S = COSName.get_pdf_name("S")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_T = COSName.get_pdf_name("T")


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
    def __init__(self, catalog_dict: COSDictionary | None = None) -> None:
        self._dict = catalog_dict if catalog_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def _pdf_bytes(page_count: int) -> bytes:
    doc = PDDocument()
    try:
        for _ in range(page_count):
            doc.add_page(PDPage())
        sink = io.BytesIO()
        doc.save(sink)
        return sink.getvalue()
    finally:
        doc.close()


def test_wave504_legacy_merge_logs_owned_source_close_failure(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = PDDocument.load(_pdf_bytes(1))

    def broken_close() -> None:
        raise OSError("close failed")

    monkeypatch.setattr(source, "close", broken_close)
    monkeypatch.setattr(PDFMergerUtility, "_open_source", staticmethod(lambda _src: (source, True)))

    util = PDFMergerUtility()
    util.add_source(object())  # type: ignore[arg-type]
    util.set_destination_stream(io.BytesIO())

    try:
        with caplog.at_level(
            logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"
        ):
            util.merge_documents()
    finally:
        source._document.close()  # noqa: SLF001

    assert "error closing source PDDocument" in caplog.text


def test_wave504_open_source_accepts_binary_stream_payload() -> None:
    opened, owns = PDFMergerUtility._open_source(io.BytesIO(_pdf_bytes(2)))  # noqa: SLF001

    try:
        assert owns is True
        assert opened.get_number_of_pages() == 2
    finally:
        opened.close()


def test_wave504_append_document_rejects_dynamic_xfa_before_merge_work() -> None:
    class DynamicXfa:
        def xfa_is_dynamic(self) -> bool:
            return True

    class Catalog:
        def get_acro_form(self) -> DynamicXfa:
            return DynamicXfa()

    class Source:
        def is_closed(self) -> bool:
            return False

        def get_document_catalog(self) -> Catalog:
            return Catalog()

    destination = PDDocument()
    try:
        with pytest.raises(OSError, match="dynamic XFA"):
            PDFMergerUtility().append_document(destination, Source())  # type: ignore[arg-type]
    finally:
        destination.close()


def test_wave504_append_document_bumps_destination_version() -> None:
    source = PDDocument()
    destination = PDDocument()
    try:
        source.set_version(1.7)
        destination.set_version(1.4)

        PDFMergerUtility().append_document(destination, source)

        assert destination.get_version() == 1.7
    finally:
        source.close()
        destination.close()


def test_wave504_legacy_acroform_skips_bad_fqn_and_advances_dummy_suffix() -> None:
    class Field:
        def __init__(self, name: str | None, raises: bool = False) -> None:
            self._name = name
            self._raises = raises
            self._dict = COSDictionary()
            if name is not None:
                self._dict.set_string(_T, name)

        def get_partial_name(self) -> str | None:
            return self._name

        def get_fully_qualified_name(self) -> str | None:
            if self._raises:
                raise RuntimeError("bad fqn")
            return self._name

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class Form:
        def __init__(self, fields: list[Field], tree: list[Field] | None = None) -> None:
            self._fields = fields
            self._tree = tree if tree is not None else fields
            self._dict = COSDictionary()

        def get_fields(self) -> list[Field]:
            return self._fields

        def get_field_tree(self) -> list[Field]:
            return self._tree

        def get_field(self, name: str) -> Field | None:
            return Field(name) if name == "Name" else None

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    dest_form = Form([], [Field("dummyFieldName7")])
    src_form = Form([Field("Name"), Field("Ignored", raises=True)])

    PDFMergerUtility()._acro_form_legacy_mode(  # noqa: SLF001
        _IdentityCloner(), dest_form, src_form
    )

    fields = dest_form.get_cos_object().get_dictionary_object(_FIELDS)
    assert isinstance(fields, COSArray)
    assert fields.get_object(0).get_string(_T) == "dummyFieldName8"
    assert fields.get_object(1).get_string(_T) == "Ignored"


def test_wave504_merge_helpers_append_into_existing_destinations() -> None:
    src_dict = COSDictionary()
    dest_dict = COSDictionary()
    src_names = COSDictionary()
    dest_names = COSDictionary()
    src_dests = COSDictionary()
    dest_dests = COSDictionary()
    src_output_intents = COSArray()
    dest_output_intents = COSArray()
    src_names.set_string(COSName.get_pdf_name("FromSource"), "name")
    src_dests.set_string(COSName.get_pdf_name("Chapter"), "dest")
    src_output_intents.add(COSString("intent"))
    src_dict.set_item(_NAMES, src_names)
    src_dict.set_item(_DESTS, src_dests)
    src_dict.set_item(_OUTPUT_INTENTS, src_output_intents)
    dest_dict.set_item(_NAMES, dest_names)
    dest_dict.set_item(_DESTS, dest_dests)
    dest_dict.set_item(_OUTPUT_INTENTS, dest_output_intents)

    util = PDFMergerUtility()
    cloner = _IdentityCloner()
    util._merge_names(cloner, _Catalog(src_dict), _Catalog(dest_dict))  # noqa: SLF001
    util._merge_output_intents(cloner, _Catalog(src_dict), _Catalog(dest_dict))  # noqa: SLF001

    assert dest_names.get_string(COSName.get_pdf_name("FromSource")) == "name"
    assert dest_dests.get_string(COSName.get_pdf_name("Chapter")) == "dest"
    assert dest_output_intents.size() == 1
    assert dest_output_intents.get_object(0).get_string() == "intent"


def test_wave504_page_labels_without_nums_creates_empty_destination_nums() -> None:
    source = PDDocument()
    destination = PDDocument()
    try:
        labels = COSDictionary()
        source.get_document_catalog().get_cos_object().set_item(_PAGE_LABELS, labels)

        PDFMergerUtility()._merge_page_labels(  # noqa: SLF001
            _IdentityCloner(), source, destination
        )

        dest_labels = destination.get_document_catalog().get_cos_object().get_dictionary_object(
            _PAGE_LABELS
        )
        assert isinstance(dest_labels, COSDictionary)
        assert isinstance(dest_labels.get_dictionary_object(COSName.get_pdf_name("Nums")), COSArray)
    finally:
        source.close()
        destination.close()


def test_wave504_open_action_is_copied_only_when_destination_missing() -> None:
    source_action = COSDictionary()
    source_catalog = _Catalog()
    dest_catalog = _Catalog()
    source_catalog.get_cos_object().set_item(_OPEN_ACTION, source_action)

    PDFMergerUtility()._merge_open_action(  # noqa: SLF001
        _IdentityCloner(), source_catalog, dest_catalog
    )

    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is source_action

    replacement = COSDictionary()
    other_source = _Catalog()
    other_source.get_cos_object().set_item(_OPEN_ACTION, replacement)
    PDFMergerUtility()._merge_open_action(  # noqa: SLF001
        _IdentityCloner(), other_source, dest_catalog
    )
    assert dest_catalog.get_cos_object().get_dictionary_object(_OPEN_ACTION) is source_action


def test_wave504_struct_helpers_cover_none_nested_dicts_and_arrays() -> None:
    page = COSDictionary()
    page.set_item(_STRUCT_PARENTS, COSInteger.get(2))
    page.set_item(_STRUCT_PARENT, COSInteger.get(99))
    PDFMergerUtility._strip_struct_parent_from_annots(page)  # noqa: SLF001
    assert page.get_dictionary_object(_STRUCT_PARENT).int_value() == 99

    util = PDFMergerUtility()
    old_page = COSDictionary()
    new_page = COSDictionary()
    leaf = COSDictionary()
    leaf.set_item(_PG, old_page)
    parent = COSDictionary()
    parent.set_item(_K, leaf)
    nested_array = COSArray()
    nested_array.add(COSArray([parent]))

    util._update_page_references_map(_IdentityCloner(), {1: None, 2: nested_array}, {id(old_page): new_page})  # noqa: SLF001,E501

    assert leaf.get_dictionary_object(_PG) is new_page


def test_wave504_merge_k_entries_handles_array_source_and_empty_source() -> None:
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("P"))
    src_k = COSArray()
    src_k.add(child)
    src_root = COSDictionary()
    src_root.set_item(_K, src_k)
    dest_root = COSDictionary()

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(), _Root(src_root), _Root(dest_root)
    )

    merged = dest_root.get_dictionary_object(_K)
    assert isinstance(merged, COSArray)
    assert merged.get_object(0) is child
    assert child.get_dictionary_object(_P) is dest_root

    unchanged = COSDictionary()
    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(), _Root(COSDictionary()), _Root(unchanged)
    )
    assert not unchanged.contains_key(_K)


def test_wave504_merge_id_tree_skips_none_source_values() -> None:
    class IdTree:
        def get_names(self) -> dict[str, object | None]:
            return {"skip": None}

        def get_kids(self) -> None:
            return None

    class StructRoot(_Root):
        def __init__(self, tree: object | None) -> None:
            super().__init__(COSDictionary())
            self._tree = tree
            self.installed: object | None = None

        def get_id_tree(self) -> object | None:
            return self._tree

        def set_id_tree(self, tree: object) -> None:
            self.installed = tree

    dest_root = StructRoot(None)

    PDFMergerUtility()._merge_id_tree(  # noqa: SLF001
        _IdentityCloner(), StructRoot(IdTree()), dest_root
    )

    assert dest_root.installed is not None
