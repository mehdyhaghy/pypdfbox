from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata


_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


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


def test_constructor_with_existing_cos_stream_does_not_set_type() -> None:
    cos = COSStream()
    meta = PDMetadata(cos)
    assert meta.get_cos_object() is cos
    # PDMetadata(COSStream) explicitly does NOT tag — mirrors upstream
    assert cos.get_dictionary_object(_TYPE) is None
    assert cos.get_dictionary_object(_SUBTYPE) is None


def test_import_then_export_round_trip() -> None:
    meta = PDMetadata()
    payload = b"<rdf:RDF/>"
    meta.import_xmp_metadata(payload)
    assert meta.export_xmp_metadata() == payload


def test_import_accepts_str_and_encodes_utf8() -> None:
    meta = PDMetadata()
    meta.import_xmp_metadata("<x>" + "é" + "</x>")
    assert meta.export_xmp_metadata() == "<x>é</x>".encode()


def test_create_input_stream_reads_packet() -> None:
    meta = PDMetadata(b"abc")
    with meta.create_input_stream() as src:
        assert src.read() == b"abc"


def test_unknown_argument_type_raises() -> None:
    with pytest.raises(TypeError):
        PDMetadata(12345)  # type: ignore[arg-type]
