from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature

_ANNOTS = COSName.get_pdf_name("Annots")
_CONTENTS = COSName.get_pdf_name("Contents")
_PARENT = COSName.get_pdf_name("Parent")
_RESOURCES = COSName.get_pdf_name("Resources")
_T = COSName.get_pdf_name("T")
_V = COSName.get_pdf_name("V")


def test_wave535_import_page_deep_copies_streams_arrays_and_drops_parent() -> None:
    source_page = PDPage()
    page_dict = source_page.get_cos_object()
    parent = COSDictionary()
    resources = COSDictionary()
    nested_array = COSArray()
    nested_array.add(COSString("nested"))
    stream = COSStream()
    stream.set_raw_data(b"stream-bytes")
    stream.set_item(COSName.get_pdf_name("Meta"), nested_array)

    page_dict.set_item(_PARENT, parent)
    page_dict.set_item(_RESOURCES, resources)
    page_dict.set_item(_CONTENTS, stream)

    destination = PDDocument()
    try:
        imported = destination.import_page(source_page)
        imported_dict = imported.get_cos_object()

        assert imported_dict is not page_dict
        assert imported_dict.get_dictionary_object(_PARENT) is not parent
        assert imported_dict.get_dictionary_object(_RESOURCES) is not resources

        imported_stream = imported_dict.get_dictionary_object(_CONTENTS)
        assert isinstance(imported_stream, COSStream)
        assert imported_stream is not stream
        assert imported_stream.get_raw_data() == b"stream-bytes"
        copied_meta = imported_stream.get_dictionary_object(COSName.get_pdf_name("Meta"))
        assert copied_meta is not nested_array
        assert destination.get_number_of_pages() == 1
    finally:
        destination.close()


def test_wave535_import_page_breaks_cycles_by_reusing_seen_object() -> None:
    cyclic = COSDictionary()
    cyclic.set_item(COSName.get_pdf_name("Self"), cyclic)
    page = PDPage()
    page.get_cos_object().set_item(COSName.get_pdf_name("Cycle"), cyclic)

    doc = PDDocument()
    try:
        imported = doc.import_page(page)

        copied_cycle = imported.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Cycle")
        )
        assert isinstance(copied_cycle, COSDictionary)
        assert copied_cycle is not cyclic
        assert copied_cycle.get_dictionary_object(COSName.get_pdf_name("Self")) is cyclic
    finally:
        doc.close()


def test_wave535_deep_copy_resolves_cos_object_references() -> None:
    target = COSDictionary()
    target.set_string(COSName.get_pdf_name("Name"), "resolved")
    ref = COSObject(7, resolved=target)
    page = PDPage()
    page.get_cos_object().set_item(COSName.get_pdf_name("Ref"), ref)

    doc = PDDocument()
    try:
        imported = doc.import_page(page)

        copied = imported.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Ref"))
        assert isinstance(copied, COSDictionary)
        assert copied is not target
        assert copied.get_string(COSName.get_pdf_name("Name")) == "resolved"
    finally:
        doc.close()


def test_wave535_write_bytes_to_random_access_write_buffer() -> None:
    sink = RandomAccessWriteBuffer()

    PDDocument._write_bytes_to_target(b"abc", sink)  # noqa: SLF001

    assert sink.to_bytes() == b"abc"


def test_wave535_splice_signature_rejects_blob_larger_than_placeholder() -> None:
    with pytest.raises(ValueError, match="larger than"):
        PDDocument._splice_signature(bytearray(b"<0000>"), (1, 5), b"\x00\x01\x02")  # noqa: SLF001


def test_wave535_extract_bracketed_concatenates_declared_slices() -> None:
    assert PDDocument._extract_bracketed(b"abcdefghi", [1, 3, 6, 2]) == b"bcdgh"  # noqa: SLF001


def test_wave535_add_signature_uses_next_available_signature_field_name() -> None:
    doc = PDDocument()
    try:
        existing_field = COSDictionary()
        existing_field.set_string(_T, "Signature1")
        fields = COSArray()
        fields.add(existing_field)

        catalog = doc.get_document_catalog()
        from pypdfbox.pdmodel.interactive.form import PDAcroForm

        acro_form = PDAcroForm(doc)
        acro_form.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)
        catalog.set_acro_form(acro_form)

        signature = PDSignature()
        doc.add_signature(signature)

        added_field = fields.get_object(1)
        assert isinstance(added_field, COSDictionary)
        assert added_field.get_string(_T) == "Signature2"
        assert added_field.get_dictionary_object(_V) is signature.get_cos_object()
    finally:
        doc.close()


def test_wave535_requires_full_save_reflects_loaded_dirty_object_state() -> None:
    src = PDDocument()
    src.add_page(PDPage())
    data = io.BytesIO()
    src.save(data)
    src.close()

    with PDDocument.load(data.getvalue()) as loaded:
        assert loaded.requires_full_save() is True

        loaded.get_document().get_objects()[0].set_needs_to_be_updated(True)
        assert loaded.requires_full_save() is False


def test_wave535_add_signature_attaches_widget_to_first_page_annots() -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        first_page = doc.get_page(0).get_cos_object()

        doc.add_signature(PDSignature())

        annots = first_page.get_dictionary_object(_ANNOTS)
        assert isinstance(annots, COSArray)
        widget = annots.get_object(0)
        assert isinstance(widget, COSDictionary)
        assert widget.get_dictionary_object(COSName.get_pdf_name("P")) is first_page
        assert first_page.is_needs_to_be_updated() is True
    finally:
        doc.close()


def test_wave535_set_version_below_1_4_updates_header() -> None:
    doc = PDDocument()
    try:
        doc.get_document().set_version(1.3)

        doc.set_version(1.4)

        assert doc.get_document().get_version() == pytest.approx(1.4)
    finally:
        doc.close()


def test_wave535_get_current_access_permission_uses_security_handler_once() -> None:
    class Handler:
        def __init__(self) -> None:
            self.calls = 0

        def get_current_access_permission(self) -> object:
            self.calls += 1
            return COSInteger.get(7)

    doc = PDDocument()
    handler = Handler()
    doc._security_handler = handler  # noqa: SLF001
    try:
        first = doc.get_current_access_permission()
        second = doc.get_current_access_permission()

        assert first is second
        assert first == COSInteger.get(7)
        assert handler.calls == 1
    finally:
        doc.close()
