from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import (
    SUBTYPE_XML,
    TYPE_METADATA,
    PDMetadata,
)
from pypdfbox.pdmodel.pd_document import PDDocument


_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_FILTER = COSName.FILTER  # type: ignore[attr-defined]
_FLATE = COSName.FLATE_DECODE  # type: ignore[attr-defined]


# ---------- constructor variants ----------


def test_default_constructor_tags_metadata_and_xml() -> None:
    meta = PDMetadata()
    cos = meta.get_cos_object()
    assert isinstance(cos, COSStream)
    type_value = cos.get_dictionary_object(_TYPE)
    subtype_value = cos.get_dictionary_object(_SUBTYPE)
    assert isinstance(type_value, COSName)
    assert isinstance(subtype_value, COSName)
    assert type_value.get_name() == "Metadata"
    assert subtype_value.get_name() == "XML"


def test_default_get_metadata_as_string_returns_empty() -> None:
    meta = PDMetadata()
    assert meta.get_metadata_as_string() == ""


def test_constructor_with_pddocument_tags_metadata() -> None:
    doc = PDDocument()
    try:
        meta = PDMetadata(doc)
        cos = meta.get_cos_object()
        assert cos.get_dictionary_object(_TYPE).get_name() == "Metadata"
        assert cos.get_dictionary_object(_SUBTYPE).get_name() == "XML"
    finally:
        doc.close()


def test_constructor_with_pddocument_and_input_imports_packet() -> None:
    doc = PDDocument()
    try:
        packet = b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>"
        meta = PDMetadata(doc, packet)
        assert meta.export_xmp_metadata() == packet
        assert meta.get_cos_object().get_dictionary_object(_TYPE).get_name() == "Metadata"
    finally:
        doc.close()


def test_constructor_with_existing_cos_stream_does_not_set_type() -> None:
    cos = COSStream()
    meta = PDMetadata(cos)
    assert meta.get_cos_object() is cos
    # PDMetadata(COSStream) explicitly does NOT tag — mirrors upstream
    assert cos.get_dictionary_object(_TYPE) is None
    assert cos.get_dictionary_object(_SUBTYPE) is None


def test_constructor_with_cos_stream_and_input_data_raises() -> None:
    with pytest.raises(TypeError):
        PDMetadata(COSStream(), b"data")


def test_constructor_with_bytes_round_trips_via_export() -> None:
    packet = b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>"
    meta = PDMetadata(packet)
    assert meta.export_xmp_metadata() == packet
    assert meta.get_metadata_as_string() == packet.decode("utf-8")
    # tagging is preserved
    assert meta.get_cos_object().get_dictionary_object(_TYPE).get_name() == "Metadata"
    assert meta.get_cos_object().get_dictionary_object(_SUBTYPE).get_name() == "XML"


def test_constructor_with_str_round_trips_as_utf8() -> None:
    packet = "<xmp>héllo wörld</xmp>"  # non-ASCII forces UTF-8 path
    meta = PDMetadata(packet)
    assert meta.get_metadata_as_string() == packet
    assert meta.export_xmp_metadata() == packet.encode("utf-8")


def test_unknown_argument_type_raises() -> None:
    with pytest.raises(TypeError):
        PDMetadata(12345)  # type: ignore[arg-type]


# ---------- import / export round-trips ----------


def test_import_then_export_round_trip() -> None:
    meta = PDMetadata()
    payload = b"<rdf:RDF/>"
    meta.import_xmp_metadata(payload)
    assert meta.export_xmp_metadata() == payload


def test_import_accepts_str_and_encodes_utf8() -> None:
    meta = PDMetadata()
    meta.import_xmp_metadata("<x>" + "é" + "</x>")
    assert meta.export_xmp_metadata() == "<x>é</x>".encode()


def test_import_accepts_binary_file_like() -> None:
    meta = PDMetadata()
    meta.import_xmp_metadata(io.BytesIO(b"<rdf:RDF/>"))
    assert meta.export_xmp_metadata() == b"<rdf:RDF/>"


def test_import_accepts_text_file_like_encodes_utf8() -> None:
    meta = PDMetadata()
    meta.import_xmp_metadata(io.StringIO("<x>é</x>"))
    assert meta.export_xmp_metadata() == "<x>é</x>".encode("utf-8")


def test_import_rejects_unknown_argument_type() -> None:
    meta = PDMetadata()
    with pytest.raises(TypeError):
        meta.import_xmp_metadata(12345)  # type: ignore[arg-type]


def test_import_replaces_existing_body() -> None:
    meta = PDMetadata(b"old")
    meta.import_xmp_metadata(b"new")
    assert meta.export_xmp_metadata() == b"new"


# ---------- create_input_stream / get_cos_object ----------


def test_create_input_stream_reads_packet() -> None:
    meta = PDMetadata(b"abc")
    with meta.create_input_stream() as src:
        assert src.read() == b"abc"


def test_create_input_stream_on_empty_returns_empty_bytes() -> None:
    meta = PDMetadata()
    with meta.create_input_stream() as src:
        assert src.read() == b""


def test_get_cos_object_returns_cos_stream() -> None:
    meta = PDMetadata()
    assert isinstance(meta.get_cos_object(), COSStream)


# ---------- set_filters (inherited from PDStream) ----------


def test_set_filters_records_flate_filter_on_dictionary() -> None:
    meta = PDMetadata()
    meta.set_filters(_FLATE)
    filters = meta.get_filters()
    assert len(filters) == 1
    assert filters[0].get_name() == "FlateDecode"


def test_set_filters_clears_when_none() -> None:
    meta = PDMetadata()
    meta.set_filters(_FLATE)
    meta.set_filters(None)
    assert meta.get_filters() == []
    assert meta.is_filter_undefined()


# ---------- /Type and /Subtype accessors ----------


def test_module_constants_match_pdf_spec_values() -> None:
    # Constants should match the literal strings upstream stamps onto
    # /Type and /Subtype for document-level XMP metadata streams.
    assert TYPE_METADATA == "Metadata"
    assert SUBTYPE_XML == "XML"


def test_get_type_returns_metadata_string_after_default_construction() -> None:
    meta = PDMetadata()
    assert meta.get_type() == TYPE_METADATA


def test_get_subtype_returns_xml_string_after_default_construction() -> None:
    meta = PDMetadata()
    assert meta.get_subtype() == SUBTYPE_XML


def test_get_type_and_subtype_are_none_for_untagged_cos_stream() -> None:
    meta = PDMetadata(COSStream())
    assert meta.get_type() is None
    assert meta.get_subtype() is None


def test_is_metadata_stream_true_for_tagged_default() -> None:
    assert PDMetadata().is_metadata_stream() is True


def test_is_metadata_stream_false_for_untagged_cos_stream() -> None:
    assert PDMetadata(COSStream()).is_metadata_stream() is False


def test_is_metadata_stream_false_when_only_type_present() -> None:
    cos = COSStream()
    cos.set_name(_TYPE, "Metadata")
    assert PDMetadata(cos).is_metadata_stream() is False


def test_is_metadata_stream_false_when_subtype_is_unexpected() -> None:
    cos = COSStream()
    cos.set_name(_TYPE, "Metadata")
    cos.set_name(_SUBTYPE, "Other")
    assert PDMetadata(cos).is_metadata_stream() is False


# ---------- export_xmp_metadata_as_input_stream ----------


def test_export_as_input_stream_returns_file_like_with_packet() -> None:
    meta = PDMetadata(b"<rdf:RDF/>")
    with meta.export_xmp_metadata_as_input_stream() as src:
        assert src.read() == b"<rdf:RDF/>"


def test_export_as_input_stream_on_empty_returns_empty() -> None:
    meta = PDMetadata()
    with meta.export_xmp_metadata_as_input_stream() as src:
        assert src.read() == b""


# ---------- set_metadata_from_string ----------


def test_set_metadata_from_string_round_trips_via_get() -> None:
    meta = PDMetadata()
    packet = "<x:xmpmeta>héllo</x:xmpmeta>"
    meta.set_metadata_from_string(packet)
    assert meta.get_metadata_as_string() == packet
    assert meta.export_xmp_metadata() == packet.encode("utf-8")


def test_set_metadata_from_string_replaces_existing_body() -> None:
    meta = PDMetadata(b"old")
    meta.set_metadata_from_string("new")
    assert meta.export_xmp_metadata() == b"new"


def test_set_metadata_from_string_rejects_non_string() -> None:
    meta = PDMetadata()
    with pytest.raises(TypeError):
        meta.set_metadata_from_string(b"bytes-not-allowed")  # type: ignore[arg-type]


# ---------- is_empty / get_metadata_size ----------


def test_is_empty_true_for_fresh_metadata() -> None:
    meta = PDMetadata()
    assert meta.is_empty() is True


def test_is_empty_false_after_import() -> None:
    meta = PDMetadata(b"<rdf:RDF/>")
    assert meta.is_empty() is False


def test_is_empty_true_after_construction_from_empty_cos_stream() -> None:
    """A ``PDMetadata`` wrapped around a fresh empty ``COSStream`` is
    empty (no body), even though it isn't tagged with /Type or /Subtype."""
    meta = PDMetadata(COSStream())
    assert meta.is_empty() is True


def test_get_metadata_size_zero_for_empty() -> None:
    meta = PDMetadata()
    assert meta.get_metadata_size() == 0


def test_get_metadata_size_matches_byte_length() -> None:
    packet = b"<rdf:RDF/>"
    meta = PDMetadata(packet)
    assert meta.get_metadata_size() == len(packet)


def test_get_metadata_size_matches_utf8_byte_length() -> None:
    """Non-ASCII XMP packets must report the encoded byte length, not
    the codepoint count."""
    packet = "<x>héllo</x>"  # 'é' is 2 bytes in UTF-8
    meta = PDMetadata(packet)
    assert meta.get_metadata_size() == len(packet.encode("utf-8"))
