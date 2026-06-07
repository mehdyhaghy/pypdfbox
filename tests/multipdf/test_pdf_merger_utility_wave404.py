from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import DocumentMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage

_DESTS = COSName.get_pdf_name("Dests")
_LANG = COSName.get_pdf_name("Lang")
_METADATA = COSName.get_pdf_name("Metadata")
_OC_PROPERTIES = COSName.get_pdf_name("OCProperties")
_OUTPUT_INTENTS = COSName.get_pdf_name("OutputIntents")
_PAGE_LAYOUT = COSName.get_pdf_name("PageLayout")
_PAGE_MODE = COSName.get_pdf_name("PageMode")
_THREADS = COSName.get_pdf_name("Threads")
_VIEWER_PREFS = COSName.get_pdf_name("ViewerPreferences")


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


def _make_doc(page_count: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(page_count):
        doc.add_page(PDPage())
    return doc


def _pdf_bytes(page_count: int) -> bytes:
    buffer = io.BytesIO()
    doc = _make_doc(page_count)
    try:
        doc.save(buffer)
    finally:
        doc.close()
    return buffer.getvalue()


def test_wave404_add_sources_rejects_single_source_like_values(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(_pdf_bytes(1))

    for value in (str(pdf_path), pdf_path, b"%PDF", bytearray(b"%PDF"), io.BytesIO()):
        with pytest.raises(TypeError, match="expected an iterable of sources"):
            PDFMergerUtility().add_sources(value)  # type: ignore[arg-type]


def test_wave404_add_sources_appends_iterable_and_get_sources_returns_copy() -> None:
    first = b"one"
    second = memoryview(b"two")
    util = PDFMergerUtility()

    util.add_sources([first, second])
    sources = util.get_sources()
    sources.append(b"mutated")

    assert util.get_sources() == [first, second]


def test_wave404_merge_with_sources_requires_destination() -> None:
    util = PDFMergerUtility()
    util.add_source(_make_doc(1))

    with pytest.raises(ValueError, match="Either set_destination_file_name"):
        util.merge_documents()

    source = util.get_sources()[0]
    assert isinstance(source, PDDocument)
    source.close()


def test_wave404_merge_without_sources_is_noop_even_without_destination() -> None:
    PDFMergerUtility().merge_documents()


def test_wave404_merge_documents_stages_overload_arguments_under_optimize(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``merge_documents`` stages overload arguments via the setters; in
    OPTIMIZE_RESOURCES_MODE the real (no-fallback) optimised path runs,
    so no legacy-fallback info log is emitted."""
    util = PDFMergerUtility()
    cache_factory = object()
    compress_parameters = object()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)

    with caplog.at_level(
        logging.INFO, logger="pypdfbox.multipdf.pdf_merger_utility"
    ):
        util.merge_documents(
            stream_cache_create_function=cache_factory,
            compress_parameters=compress_parameters,
        )

    assert util.get_stream_cache_create_function() is cache_factory
    assert util.get_compress_parameters() is compress_parameters
    assert "falling back to PDFBOX_LEGACY_MODE" not in caplog.text


def test_wave404_merge_to_stream_from_bytes_and_bytearray_sources() -> None:
    output = io.BytesIO()
    util = PDFMergerUtility()
    util.add_source(_pdf_bytes(1))
    util.add_source(bytearray(_pdf_bytes(2)))
    util.set_destination_stream(output)

    util.merge_documents()

    with PDDocument.load(output.getvalue()) as merged:
        assert merged.get_number_of_pages() == 3


def test_wave404_catalog_scalar_merge_matches_upstream_gating() -> None:
    """Wave 1506: upstream ``appendDocument`` carries /PageMode first-source-wins
    OUTSIDE the structure-tree block, but merges /Lang and /ViewerPreferences
    ONLY inside the ``if (mergeStructTree)`` block (alongside /MarkInfo), and
    never merges /PageLayout at all (oracle-confirmed: a non-tagged two-source
    merge leaves Lang / ViewerPreferences / PageLayout absent on the
    destination). These sources are plain (untagged) → no structure-tree merge →
    Lang / ViewerPreferences / PageLayout are NOT carried; only the existing
    dest /PageMode survives."""
    source = _make_doc(1)
    destination = _make_doc(1)
    src_catalog = source.get_document_catalog().get_cos_object()
    dest_catalog = destination.get_document_catalog().get_cos_object()
    src_catalog.set_item(_PAGE_MODE, COSName.get_pdf_name("UseOutlines"))
    src_catalog.set_item(_PAGE_LAYOUT, COSName.get_pdf_name("TwoColumnLeft"))
    src_catalog.set_string(_LANG, "en-US")
    viewer_prefs = COSDictionary()
    viewer_prefs.set_item(COSName.get_pdf_name("HideToolbar"), COSBoolean.TRUE)
    src_catalog.set_item(_VIEWER_PREFS, viewer_prefs)
    dest_catalog.set_item(_PAGE_MODE, COSName.get_pdf_name("UseNone"))

    PDFMergerUtility().append_document(destination, source)

    # /PageMode is merged outside the struct block (first-source-wins): the
    # destination already had UseNone, so the source's UseOutlines is ignored.
    assert dest_catalog.get_dictionary_object(_PAGE_MODE) == COSName.get_pdf_name(
        "UseNone"
    )
    # No structure-tree merge → these three are NOT carried, matching upstream.
    assert dest_catalog.get_dictionary_object(_PAGE_LAYOUT) is None
    assert dest_catalog.get_string(_LANG) is None
    assert dest_catalog.get_dictionary_object(_VIEWER_PREFS) is None
    source.close()
    destination.close()


def test_wave404_merge_helpers_install_missing_catalog_arrays_and_dicts() -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    threads = COSArray()
    threads.add(COSDictionary())
    dests = COSDictionary()
    dests.set_string(COSName.get_pdf_name("Chapter"), "target")
    oc_properties = COSDictionary()
    oc_properties.set_string(COSName.get_pdf_name("Config"), "on")
    output_intents = COSArray()
    output_intents.add(COSDictionary())
    src_catalog.get_cos_object().set_item(_THREADS, threads)
    src_catalog.get_cos_object().set_item(_DESTS, dests)
    src_catalog.get_cos_object().set_item(_OC_PROPERTIES, oc_properties)
    src_catalog.get_cos_object().set_item(_OUTPUT_INTENTS, output_intents)

    util = PDFMergerUtility()
    cloner = _IdentityCloner()
    util._merge_threads(cloner, src_catalog, dest_catalog)  # noqa: SLF001
    util._merge_names(cloner, src_catalog, dest_catalog)  # noqa: SLF001
    util._merge_oc_properties(cloner, src_catalog, dest_catalog)  # noqa: SLF001
    util._merge_output_intents(cloner, src_catalog, dest_catalog)  # noqa: SLF001

    merged = dest_catalog.get_cos_object()
    assert merged.get_dictionary_object(_THREADS) is threads
    assert merged.get_dictionary_object(_DESTS) is dests
    assert merged.get_dictionary_object(_OC_PROPERTIES) is oc_properties
    assert merged.get_dictionary_object(_OUTPUT_INTENTS) is output_intents


def test_wave404_metadata_is_copied_only_when_destination_is_missing() -> None:
    src_catalog = _Catalog()
    dest_catalog = _Catalog()
    src_metadata = COSStream()
    existing_metadata = COSStream()
    src_catalog.get_cos_object().set_item(_METADATA, src_metadata)
    dest_catalog.get_cos_object().set_item(_METADATA, existing_metadata)

    destination = _make_doc(0)
    try:
        PDFMergerUtility()._merge_metadata(  # noqa: SLF001
            _IdentityCloner(), src_catalog, dest_catalog, destination
        )
    finally:
        destination.close()

    assert dest_catalog.get_cos_object().get_dictionary_object(_METADATA) is (
        existing_metadata
    )
