from __future__ import annotations

import io
import logging

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.multipdf.pdf_merger_utility import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage

_FIELDS = COSName.get_pdf_name("Fields")
_K = COSName.get_pdf_name("K")
_METADATA = COSName.get_pdf_name("Metadata")
_OC_PROPERTIES = COSName.get_pdf_name("OCProperties")
_OBJ = COSName.get_pdf_name("Obj")
_PAGE_LABELS = COSName.get_pdf_name("PageLabels")
_PART = COSName.get_pdf_name("Part")
_PG = COSName.get_pdf_name("Pg")
_ROLE_MAP = COSName.get_pdf_name("RoleMap")
_S = COSName.get_pdf_name("S")
_STRUCT_PARENT = COSName.get_pdf_name("StructParent")
_STRUCT_PARENTS = COSName.get_pdf_name("StructParents")
_T = COSName.get_pdf_name("T")
_THREADS = COSName.get_pdf_name("Threads")


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


class _BrokenCloner(_IdentityCloner):
    def clone_for_new_document(self, value: object) -> object:
        raise OSError("cannot clone")


class _Catalog:
    def __init__(self, catalog_dict: COSDictionary | None = None) -> None:
        self._dict = catalog_dict if catalog_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _Field:
    def __init__(self, name: str) -> None:
        self._dict = COSDictionary()
        self._dict.set_string(_T, name)
        self._name = name

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_partial_name(self) -> str:
        return self._name

    def get_fully_qualified_name(self) -> str:
        return self._name


class _Form:
    def __init__(self, fields: list[_Field], existing: COSArray | None = None) -> None:
        self._fields = fields
        self._dict = COSDictionary()
        if existing is not None:
            self._dict.set_item(_FIELDS, existing)

    def get_fields(self) -> list[_Field]:
        return self._fields

    # Legacy-mode AcroForm merge (which JOIN delegates to in PDFBox 3.0.x)
    # walks the destination's field tree and looks up by FQ name to detect
    # collisions. These destinations carry no existing fields, so no rename.
    def get_field_tree(self) -> list[_Field]:
        return []

    def get_field(self, _name: str) -> None:
        return None

    def get_cos_object(self) -> COSDictionary:
        return self._dict


class _Root:
    def __init__(self, root_dict: COSDictionary | None = None) -> None:
        self._dict = root_dict if root_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def _pdf_bytes(page_count: int = 1) -> bytes:
    doc = PDDocument()
    try:
        for _ in range(page_count):
            doc.add_page(PDPage())
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()


def test_wave536_merge_documents_without_sources_does_not_require_destination() -> None:
    PDFMergerUtility().merge_documents()


def test_wave536_merge_documents_records_stream_cache_and_compress_parameters() -> None:
    util = PDFMergerUtility()
    cache_factory = object()
    compress = object()

    util.merge_documents(
        stream_cache_create_function=cache_factory,
        compress_parameters=compress,
    )

    assert util.get_stream_cache_create_function() is cache_factory
    assert util.get_compress_parameters() is compress


def test_wave536_optimize_mode_no_legacy_fallback_log_for_valid_input(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """OPTIMIZE_RESOURCES_MODE now performs a real cross-document
    resource-deduplicating merge; the legacy-fallback info log must not
    fire for an empty-sources no-op call."""
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)

    with caplog.at_level(logging.INFO, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util.merge_documents()

    assert "OPTIMIZE_RESOURCES_MODE not yet implemented" not in caplog.text
    assert "falling back to PDFBOX_LEGACY_MODE" not in caplog.text


def test_wave536_merge_random_access_read_rejects_non_random_access_source() -> None:
    util = PDFMergerUtility()

    with pytest.raises(TypeError, match="RandomAccessRead"):
        util.merge_documents_random_access_read([object()])  # type: ignore[list-item]

    assert util.get_sources() == []


def test_wave536_merge_random_access_read_keeps_caller_source_open() -> None:
    source = RandomAccessReadBuffer(_pdf_bytes())
    util = PDFMergerUtility()
    util.set_destination_stream(io.BytesIO())

    util.merge_documents_random_access_read([source])

    assert source.is_closed() is False
    source.close()


def test_wave536_open_source_rejects_stream_reading_text() -> None:
    class TextStream:
        def read(self) -> str:
            return "not-bytes"

    with pytest.raises(TypeError, match="read\\(\\) must return bytes"):
        PDFMergerUtility._open_source(TextStream())  # noqa: SLF001


def test_wave536_join_fields_mode_appends_fields_into_existing_array() -> None:
    existing = COSArray()
    dest_form = _Form([], existing)
    src_form = _Form([_Field("A"), _Field("B")])

    PDFMergerUtility()._acro_form_join_fields_mode(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        dest_form,
        src_form,
    )

    assert dest_form.get_cos_object().get_dictionary_object(_FIELDS) is existing
    assert existing.size() == 2
    assert existing.get_object(0).get_string(_T) == "A"
    assert existing.get_object(1).get_string(_T) == "B"


def test_wave536_join_fields_mode_noops_without_source_fields() -> None:
    dest_form = _Form([])

    PDFMergerUtility()._acro_form_join_fields_mode(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        dest_form,
        _Form([]),
    )

    assert dest_form.get_cos_object().get_dictionary_object(_FIELDS) is None


def test_wave536_merge_threads_installs_or_appends_threads() -> None:
    source_threads = COSArray([COSString("a"), COSString("b")])
    src_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_THREADS, source_threads)
    dest_catalog = _Catalog()

    util = PDFMergerUtility()
    util._merge_threads(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001
    assert dest_catalog.get_cos_object().get_dictionary_object(_THREADS) is source_threads

    more_threads = COSArray([COSString("c")])
    second_source = _Catalog()
    second_source.get_cos_object().set_item(_THREADS, more_threads)
    util._merge_threads(_IdentityCloner(), second_source, dest_catalog)  # noqa: SLF001
    assert source_threads.size() == 3
    assert source_threads.get_object(2).get_string() == "c"


def test_wave536_page_labels_bad_index_rolls_back_destination_additions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = PDDocument()
    destination = PDDocument()
    try:
        destination.add_page(PDPage())
        dest_labels = COSDictionary()
        dest_nums = COSArray([COSInteger.get(0), COSDictionary()])
        dest_labels.set_item(COSName.get_pdf_name("Nums"), dest_nums)
        destination.get_document_catalog().get_cos_object().set_item(
            _PAGE_LABELS, dest_labels
        )

        src_labels = COSDictionary()
        src_nums = COSArray([COSInteger.get(0), COSDictionary(), COSString("bad")])
        src_nums.add(COSDictionary())
        src_labels.set_item(COSName.get_pdf_name("Nums"), src_nums)
        source.get_document_catalog().get_cos_object().set_item(
            _PAGE_LABELS, src_labels
        )

        with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
            PDFMergerUtility()._merge_page_labels(  # noqa: SLF001
                _IdentityCloner(),  # type: ignore[arg-type]
                source,
                destination,
            )

        assert dest_nums.size() == 2
        assert "page labels ignored" in caplog.text
    finally:
        source.close()
        destination.close()


def test_wave536_metadata_clone_failure_is_logged_and_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    metadata = COSStream()
    metadata.set_raw_data(b"xmp")
    src_catalog.get_cos_object().set_item(_METADATA, metadata)

    with caplog.at_level(logging.ERROR, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_metadata(  # noqa: SLF001
            _BrokenCloner(),  # type: ignore[arg-type]
            src_catalog,
            dest_catalog,
            PDDocument(),
        )

    assert dest_catalog.get_cos_object().get_dictionary_object(_METADATA) is None
    assert "Metadata skipped" in caplog.text


def test_wave536_oc_properties_merge_installs_then_merges_existing_dict() -> None:
    src_oc = COSDictionary()
    src_oc.set_string(COSName.get_pdf_name("One"), "1")
    src_catalog = _Catalog()
    src_catalog.get_cos_object().set_item(_OC_PROPERTIES, src_oc)
    dest_catalog = _Catalog()

    util = PDFMergerUtility()
    util._merge_oc_properties(_IdentityCloner(), src_catalog, dest_catalog)  # noqa: SLF001
    installed = dest_catalog.get_cos_object().get_dictionary_object(_OC_PROPERTIES)
    assert installed is src_oc

    second_oc = COSDictionary()
    second_oc.set_string(COSName.get_pdf_name("Two"), "2")
    second_source = _Catalog()
    second_source.get_cos_object().set_item(_OC_PROPERTIES, second_oc)
    util._merge_oc_properties(_IdentityCloner(), second_source, dest_catalog)  # noqa: SLF001
    assert src_oc.get_string(COSName.get_pdf_name("Two")) == "2"


def test_wave536_update_struct_parent_entries_offsets_only_non_negative_numbers() -> None:
    page = COSDictionary()
    page.set_item(_STRUCT_PARENTS, COSInteger.get(-1))
    keep = COSDictionary()
    keep.set_item(_STRUCT_PARENT, COSInteger.get(-2))
    bump = COSDictionary()
    bump.set_item(_STRUCT_PARENT, COSInteger.get(3))
    annots = COSArray([keep, bump, COSString("skip")])
    page.set_item(COSName.get_pdf_name("Annots"), annots)

    PDFMergerUtility._update_struct_parent_entries(page, 10)  # noqa: SLF001

    assert page.get_dictionary_object(_STRUCT_PARENTS).int_value() == -1
    assert keep.get_dictionary_object(_STRUCT_PARENT).int_value() == -2
    assert bump.get_dictionary_object(_STRUCT_PARENT).int_value() == 13


def test_wave536_update_page_references_clones_orphan_object() -> None:
    orphan = COSDictionary()
    orphan.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    entry = COSDictionary()
    entry.set_item(_OBJ, orphan)
    clone = COSDictionary()

    class Cloner(_IdentityCloner):
        def clone_for_new_document(self, value: object) -> object:
            assert value is orphan
            return clone

    PDFMergerUtility()._update_page_references_dict(  # noqa: SLF001
        Cloner(),  # type: ignore[arg-type]
        entry,
        {},
    )

    assert entry.get_dictionary_object(_OBJ) is clone


def test_wave536_merge_k_entries_wraps_existing_and_source_under_document() -> None:
    existing = COSDictionary()
    existing.set_item(_S, COSName.get_pdf_name("Sect"))
    source = COSDictionary()
    source.set_item(_S, COSName.get_pdf_name("Document"))
    src_root = COSDictionary()
    src_root.set_item(_K, source)
    dest_root = COSDictionary()
    dest_root.set_item(_K, existing)

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _Root(src_root),
        _Root(dest_root),
    )

    wrapper = dest_root.get_dictionary_object(_K)
    assert isinstance(wrapper, COSDictionary)
    assert wrapper.get_name(_S) == "Document"
    merged_children = wrapper.get_dictionary_object(_K)
    assert isinstance(merged_children, COSArray)
    assert merged_children.size() == 2
    assert existing.get_dictionary_object(COSName.get_pdf_name("P")) is wrapper
    assert source.get_dictionary_object(COSName.get_pdf_name("P")) is wrapper


def test_wave536_merge_k_entries_appends_documents_to_existing_document() -> None:
    child = COSDictionary()
    child.set_item(_S, COSName.get_pdf_name("Document"))
    existing_children = COSArray([child])
    top = COSDictionary()
    top.set_item(_S, COSName.get_pdf_name("Document"))
    top.set_item(_K, existing_children)
    dest_root = COSDictionary()
    dest_root.set_item(_K, top)

    source_child = COSDictionary()
    source_child.set_item(_S, COSName.get_pdf_name("Document"))
    src_root = COSDictionary()
    src_root.set_item(_K, source_child)

    PDFMergerUtility()._merge_k_entries(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        _Root(src_root),
        _Root(dest_root),
    )

    assert existing_children.size() == 2
    assert source_child.get_dictionary_object(COSName.get_pdf_name("P")) is top
    assert source_child.get_dictionary_object(_S) == _PART


def test_wave536_merge_role_map_destination_wins_on_conflicts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = COSName.get_pdf_name("Custom")
    src_role_map = COSDictionary()
    src_role_map.set_item(key, COSName.get_pdf_name("SourceRole"))
    dest_role_map = COSDictionary()
    dest_role_map.set_item(key, COSName.get_pdf_name("DestRole"))
    src_root = COSDictionary()
    src_root.set_item(_ROLE_MAP, src_role_map)
    dest_root = COSDictionary()
    dest_root.set_item(_ROLE_MAP, dest_role_map)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        PDFMergerUtility()._merge_role_map(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            _Root(src_root),
            _Root(dest_root),
        )

    assert dest_role_map.get_dictionary_object(key) == COSName.get_pdf_name("DestRole")
    assert "already exists in destination RoleMap" in caplog.text


def test_wave536_acro_form_errors_can_be_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenCatalog(_Catalog):
        def get_acro_form(self) -> object:
            raise RuntimeError("bad form")

    util = PDFMergerUtility()
    util.set_ignore_acro_form_errors(True)

    with caplog.at_level(logging.WARNING, logger="pypdfbox.multipdf.pdf_merger_utility"):
        util._merge_acro_form(  # noqa: SLF001
            _IdentityCloner(),  # type: ignore[arg-type]
            BrokenCatalog(),
            BrokenCatalog(),
        )

    assert "AcroForm merge error ignored" in caplog.text


def test_wave536_acro_form_join_mode_dispatches_to_join_fields() -> None:
    class Catalog(_Catalog):
        def __init__(self, form: _Form) -> None:
            super().__init__()
            self._form = form

        def get_acro_form(self) -> _Form:
            return self._form

    dest_form = _Form([])
    src_form = _Form([_Field("Joined")])
    util = PDFMergerUtility()
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)

    util._merge_acro_form(  # noqa: SLF001
        _IdentityCloner(),  # type: ignore[arg-type]
        Catalog(dest_form),
        Catalog(src_form),
    )

    fields = dest_form.get_cos_object().get_dictionary_object(_FIELDS)
    assert isinstance(fields, COSArray)
    assert fields.get_object(0).get_string(_T) == "Joined"
