from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------- helpers ----------


def _seed_page_contents(page: PDPage, body: bytes = b"q\n1 0 0 1 0 0 cm Q\n") -> None:
    stream = COSStream()
    stream.set_raw_data(body)
    page.set_contents(stream)


def _build_doc(num_pages: int, body: bytes = b"q Q\n") -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage()
        _seed_page_contents(page, body)
        doc.add_page(page)
    return doc


def _save_to_path(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


# ---------- destination configuration ----------


def test_merge_documents_requires_destination(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    _save_to_path(_build_doc(1), a)
    util = PDFMergerUtility()
    util.add_source(str(a))
    with pytest.raises(ValueError):
        util.merge_documents()


def test_merge_documents_no_sources_is_a_noop(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    util = PDFMergerUtility()
    util.set_destination_file_name(str(out))
    util.merge_documents()  # no sources => silent no-op
    assert not out.exists()


# ---------- happy path ----------


def test_two_pdf_page_tree_merge(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(2, body=b"q 1 0 0 1 0 0 cm Q\n"), a)
    _save_to_path(_build_doc(3, body=b"q 2 0 0 2 0 0 cm Q\n"), b)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    assert out.exists() and out.stat().st_size > 0
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 5


def test_three_pdf_page_tree_merge_preserves_order(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1, body=b"% A\n"), a)
    _save_to_path(_build_doc(2, body=b"% B\n"), b)
    _save_to_path(_build_doc(4, body=b"% C\n"), c)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b), str(c)])
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 1 + 2 + 4


def test_merge_to_destination_stream(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    _save_to_path(_build_doc(1), a)
    _save_to_path(_build_doc(1), b)

    sink = io.BytesIO()
    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_stream(sink)
    util.merge_documents()
    payload = sink.getvalue()
    assert payload.startswith(b"%PDF-")
    sink.seek(0)
    with PDDocument.load(payload) as merged:
        assert merged.get_number_of_pages() == 2


def test_merge_with_open_pddocument_source_keeps_caller_doc_open(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    src_b = _build_doc(2)
    util = PDFMergerUtility()
    util.add_source(src_a)
    util.add_source(src_b)
    util.set_destination_file_name(str(out))
    util.merge_documents()
    # Caller-provided open PDDocuments must NOT be closed by the utility.
    assert not src_a.is_closed()
    assert not src_b.is_closed()
    src_a.close()
    src_b.close()
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 3


# ---------- shared font / resource cloning ----------


def test_shared_font_resource_cloned_per_source(tmp_path: Path) -> None:
    """Two sources each carrying an identically-named /F1 font must end up
    with the merged document holding TWO distinct font subgraphs (one per
    source) — the cloner should not collapse equally-named-but-different
    indirect resources."""
    out = tmp_path / "out.pdf"

    def _build_with_font(font_basefont: str) -> PDDocument:
        doc = PDDocument()
        page = PDPage()
        _seed_page_contents(page)
        # Attach a /Resources /Font /F1 font dict to the page so each source
        # has its own /F1 referenced under the same logical key.
        font = COSDictionary()
        font.set_name("Type", "Font")
        font.set_name("Subtype", "Type1")
        font.set_name("BaseFont", font_basefont)
        font_map = COSDictionary()
        font_map.set_item(COSName.get_pdf_name("F1"), font)
        resources = COSDictionary()
        resources.set_item(COSName.get_pdf_name("Font"), font_map)
        page.get_cos_object().set_item(COSName.get_pdf_name("Resources"), resources)
        doc.add_page(page)
        return doc

    a_path = tmp_path / "a.pdf"
    b_path = tmp_path / "b.pdf"
    _save_to_path(_build_with_font("Helvetica"), a_path)
    _save_to_path(_build_with_font("Times-Roman"), b_path)

    util = PDFMergerUtility()
    util.add_source(str(a_path))
    util.add_source(str(b_path))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2
        page0 = merged.get_page(0)
        page1 = merged.get_page(1)
        font0 = (
            page0.get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("Resources"))
            .get_dictionary_object(COSName.get_pdf_name("Font"))
            .get_dictionary_object(COSName.get_pdf_name("F1"))
        )
        font1 = (
            page1.get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("Resources"))
            .get_dictionary_object(COSName.get_pdf_name("Font"))
            .get_dictionary_object(COSName.get_pdf_name("F1"))
        )
        assert font0.get_name("BaseFont") == "Helvetica"
        assert font1.get_name("BaseFont") == "Times-Roman"
        # And they're truly distinct dicts in the merged doc.
        assert font0 is not font1


# ---------- AcroForm field-name uniquification ----------


def _build_doc_with_acroform(field_name: str, partial_value: str = "v") -> PDDocument:
    """Build a 1-page PDDocument with an AcroForm carrying one text field
    of fully-qualified name ``field_name``."""
    doc = PDDocument()
    page = PDPage()
    _seed_page_contents(page)
    doc.add_page(page)

    field_dict = COSDictionary()
    field_dict.set_name("FT", "Tx")  # text field
    field_dict.set_string(COSName.get_pdf_name("T"), field_name)
    field_dict.set_string(COSName.get_pdf_name("V"), partial_value)

    fields_array = COSArray()
    fields_array.add(field_dict)

    acro_form = COSDictionary()
    acro_form.set_item(COSName.get_pdf_name("Fields"), fields_array)

    doc.get_document_catalog().get_cos_object().set_item(
        COSName.get_pdf_name("AcroForm"), acro_form
    )
    return doc


def test_acroform_field_name_uniquification(tmp_path: Path) -> None:
    """Two sources, each with a /T = 'name' text field, must collide and
    the second copy gets renamed to dummyFieldName1 (legacy mode)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc_with_acroform("Name", "alice"), a)
    _save_to_path(_build_doc_with_acroform("Name", "bob"), b)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        assert form is not None
        names = sorted(f.get_partial_name() for f in form.get_fields())
        assert "Name" in names
        # dummyFieldName1 from collision uniquification.
        assert any(n.startswith("dummyFieldName") for n in names if n is not None)


def test_acroform_no_collision_keeps_names_intact(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc_with_acroform("FieldA"), a)
    _save_to_path(_build_doc_with_acroform("FieldB"), b)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        names = sorted(f.get_partial_name() for f in form.get_fields())
        assert names == ["FieldA", "FieldB"]


def test_acroform_only_in_source_is_carried_over(tmp_path: Path) -> None:
    """Destination has no AcroForm; source's AcroForm must be cloned
    wholesale into destination."""
    a = tmp_path / "a.pdf"  # plain
    b = tmp_path / "b.pdf"  # has form
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    _save_to_path(_build_doc_with_acroform("OnlyField"), b)

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.add_source(str(b))
    util.set_destination_file_name(str(out))
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        form = merged.get_document_catalog().get_acro_form()
        assert form is not None
        names = [f.get_partial_name() for f in form.get_fields()]
        assert names == ["OnlyField"]


# ---------- enums / properties ----------


def test_default_modes() -> None:
    util = PDFMergerUtility()
    assert util.get_document_merge_mode() == DocumentMergeMode.PDFBOX_LEGACY_MODE
    assert util.get_acro_form_merge_mode() == AcroFormMergeMode.PDFBOX_LEGACY_MODE


def test_property_setters() -> None:
    util = PDFMergerUtility()
    util.document_merge_mode_property = DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    assert (
        util.document_merge_mode_property == DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    )
    util.acro_form_merge_mode_property = AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    assert (
        util.acro_form_merge_mode_property
        == AcroFormMergeMode.JOIN_FORM_FIELDS_MODE
    )


def test_optimize_resources_mode_falls_back_to_legacy(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    _save_to_path(_build_doc(1), b)
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()  # must not crash; legacy fallback path
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2


def test_destination_document_information_overrides(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    src_a.get_document_information().set_title("source-a")
    _save_to_path(src_a, a)
    _save_to_path(_build_doc(1), b)

    from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation

    info = PDDocumentInformation()
    info.set_title("merged-title")

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.set_destination_document_information(info)
    util.merge_documents()

    with PDDocument.load(str(out)) as merged:
        assert merged.get_document_information().get_title() == "merged-title"


# ---------- stream-cache / compress-parameters parity ----------


def test_stream_cache_create_function_default_is_none() -> None:
    util = PDFMergerUtility()
    assert util.get_stream_cache_create_function() is None


def test_stream_cache_create_function_setter_round_trip() -> None:
    util = PDFMergerUtility()

    def fake_factory() -> object:
        return object()

    util.set_stream_cache_create_function(fake_factory)
    assert util.get_stream_cache_create_function() is fake_factory


def test_compress_parameters_default_is_none() -> None:
    util = PDFMergerUtility()
    assert util.get_compress_parameters() is None


def test_compress_parameters_setter_round_trip() -> None:
    util = PDFMergerUtility()
    sentinel = object()
    util.set_compress_parameters(sentinel)
    assert util.get_compress_parameters() is sentinel


def test_merge_documents_kwargs_stage_setter_values(tmp_path: Path) -> None:
    """Passing ``stream_cache_create_function`` / ``compress_parameters``
    to :meth:`merge_documents` stages them on the instance, mirroring
    upstream's overloaded ``mergeDocuments`` signatures."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)

    sc_fn = lambda: object()  # noqa: E731 — test sentinel
    compress_sentinel = object()

    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents(
        stream_cache_create_function=sc_fn,
        compress_parameters=compress_sentinel,
    )
    assert util.get_stream_cache_create_function() is sc_fn
    assert util.get_compress_parameters() is compress_sentinel
    assert out.exists()


def test_merge_documents_random_access_read_kwargs_stage_setter_values(
    tmp_path: Path,
) -> None:
    """The :class:`RandomAccessRead` overload threads the same parity
    kwargs through to :meth:`merge_documents`."""
    from pypdfbox.io import RandomAccessReadBuffer

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    sc_fn = lambda: object()  # noqa: E731 — test sentinel
    compress_sentinel = object()

    util = PDFMergerUtility()
    util.set_destination_file_name(str(out))
    util.merge_documents_random_access_read(
        [RandomAccessReadBuffer(a.read_bytes())],
        stream_cache_create_function=sc_fn,
        compress_parameters=compress_sentinel,
    )
    assert util.get_stream_cache_create_function() is sc_fn
    assert util.get_compress_parameters() is compress_sentinel
    assert out.exists()


# ---------- public-named upstream-parity helpers ----------


def test_public_merge_into_proxies_underscore_helper() -> None:
    """``merge_into`` is the public-named mirror of ``_merge_into`` and
    must produce identical state on the destination dict."""
    from pypdfbox.cos import COSInteger
    from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility

    util = PDFMergerUtility()
    dest = PDDocument()
    cloner = PDFCloneUtility(dest)
    src = COSDictionary()
    src.set_item(COSName.get_pdf_name("X"), COSInteger.get(1))
    dst = COSDictionary()
    util.merge_into(src, dst, cloner, frozenset())
    assert dst.contains_key(COSName.get_pdf_name("X"))
    dest.close()


def test_public_is_dynamic_xfa_proxy() -> None:
    class Form:
        def xfa_is_dynamic(self) -> bool:
            return True

    util = PDFMergerUtility()
    assert util.is_dynamic_xfa(Form()) is True
    assert util.is_dynamic_xfa(None) is False


def test_public_has_only_documents_or_parts_proxy() -> None:
    util = PDFMergerUtility()
    arr = COSArray()
    doc = COSDictionary()
    doc.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Document"))
    arr.add(doc)
    assert util.has_only_documents_or_parts(arr) is True


def test_public_update_struct_parent_entries_proxy() -> None:
    """The public proxy must shift /StructParents by the offset, exactly
    like the underscore-prefixed helper."""
    from pypdfbox.cos import COSInteger

    util = PDFMergerUtility()
    page = COSDictionary()
    page.set_item(COSName.get_pdf_name("StructParents"), COSInteger.get(2))
    util.update_struct_parent_entries(page, 5)
    sp = page.get_dictionary_object(COSName.get_pdf_name("StructParents"))
    assert sp.int_value() == 7


def test_public_update_parent_entry_proxy() -> None:
    util = PDFMergerUtility()
    parent = COSDictionary()
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Document"))
    arr = COSArray()
    arr.add(child)
    util.update_parent_entry(arr, parent, COSName.get_pdf_name("Part"))
    assert child.get_dictionary_object(COSName.get_pdf_name("P")) is parent
    assert child.get_name(COSName.get_pdf_name("S")) == "Part"


def test_update_page_references_dispatch_dict_array_and_map() -> None:
    """``update_page_references`` is the public unified dispatcher for
    upstream's three ``updatePageReferences`` overloads."""
    from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility

    util = PDFMergerUtility()
    dest = PDDocument()
    cloner = PDFCloneUtility(dest)

    old_page = COSDictionary()
    new_page = COSDictionary()
    obj_map = {id(old_page): new_page}

    leaf = COSDictionary()
    leaf.set_item(COSName.get_pdf_name("Pg"), old_page)
    util.update_page_references(cloner, leaf, obj_map)
    assert leaf.get_dictionary_object(COSName.get_pdf_name("Pg")) is new_page

    arr_leaf = COSDictionary()
    arr_leaf.set_item(COSName.get_pdf_name("Pg"), old_page)
    arr = COSArray()
    arr.add(arr_leaf)
    util.update_page_references(cloner, arr, obj_map)
    assert arr_leaf.get_dictionary_object(COSName.get_pdf_name("Pg")) is new_page

    map_leaf = COSDictionary()
    map_leaf.set_item(COSName.get_pdf_name("Pg"), old_page)
    util.update_page_references(cloner, {1: map_leaf}, obj_map)
    assert map_leaf.get_dictionary_object(COSName.get_pdf_name("Pg")) is new_page

    with pytest.raises(TypeError):
        util.update_page_references(cloner, 42, obj_map)
    dest.close()


def test_merge_language_carries_when_dest_blank() -> None:
    util = PDFMergerUtility()
    dest = PDDocument()
    src = PDDocument()
    src.get_document_catalog().set_language("fr-CA")
    util.merge_language(dest.get_document_catalog(), src.get_document_catalog())
    assert dest.get_document_catalog().get_language() == "fr-CA"
    dest.close()
    src.close()


def test_merge_language_preserves_dest_when_set() -> None:
    util = PDFMergerUtility()
    dest = PDDocument()
    src = PDDocument()
    dest.get_document_catalog().set_language("en-US")
    src.get_document_catalog().set_language("fr-CA")
    util.merge_language(dest.get_document_catalog(), src.get_document_catalog())
    assert dest.get_document_catalog().get_language() == "en-US"
    dest.close()
    src.close()


def test_merge_mark_info_marks_destination() -> None:
    util = PDFMergerUtility()
    dest = PDDocument()
    src = PDDocument()
    util.merge_mark_info(dest.get_document_catalog(), src.get_document_catalog())
    info = dest.get_document_catalog().get_mark_info()
    assert info is not None
    assert info.is_marked() is True
    dest.close()
    src.close()


def test_merge_viewer_preferences_or_merges_booleans() -> None:
    from pypdfbox.multipdf.pdf_clone_utility import PDFCloneUtility
    from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences

    util = PDFMergerUtility()
    dest = PDDocument()
    src = PDDocument()
    src_prefs = PDViewerPreferences()
    src_prefs.set_hide_toolbar(True)
    src_prefs.set_center_window(True)
    src.get_document_catalog().set_viewer_preferences(src_prefs)
    util.merge_viewer_preferences(
        dest.get_document_catalog(),
        src.get_document_catalog(),
        PDFCloneUtility(dest),
    )
    dest_prefs = dest.get_document_catalog().get_viewer_preferences()
    assert dest_prefs is not None
    assert dest_prefs.get_hide_toolbar() is True
    assert dest_prefs.get_center_window() is True
    dest.close()
    src.close()


def test_optimized_merge_documents_falls_back_to_legacy(tmp_path: Path) -> None:
    """``optimized_merge_documents`` records params via setters and runs
    the legacy merge path."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    sentinel_sc = object()
    sentinel_cp = object()
    util.optimized_merge_documents(sentinel_sc, sentinel_cp)
    assert out.exists()
    assert util.get_stream_cache_create_function() is sentinel_sc
    assert util.get_compress_parameters() is sentinel_cp


def test_legacy_merge_documents_records_params(tmp_path: Path) -> None:
    """The public ``legacy_merge_documents`` mirrors upstream's
    ``legacyMergeDocuments(StreamCacheCreateFunction, CompressParameters)``
    signature and stages params via setters."""
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(2), a)
    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    sentinel_sc = object()
    sentinel_cp = object()
    util.legacy_merge_documents(sentinel_sc, sentinel_cp)
    assert out.exists()
    assert util.get_stream_cache_create_function() is sentinel_sc
    assert util.get_compress_parameters() is sentinel_cp
