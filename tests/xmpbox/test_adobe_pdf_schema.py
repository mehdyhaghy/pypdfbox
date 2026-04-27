from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    DomXmpParser,
    TextType,
    XMPMetadata,
)


def _adobe() -> AdobePDFSchema:
    return AdobePDFSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _adobe()
    assert AdobePDFSchema.NAMESPACE == "http://ns.adobe.com/pdf/1.3/"
    assert AdobePDFSchema.PREFERRED_PREFIX == "pdf"
    assert schema.get_namespace() == "http://ns.adobe.com/pdf/1.3/"
    assert schema.get_prefix() == "pdf"


def test_local_name_constants_match_upstream() -> None:
    assert AdobePDFSchema.KEYWORDS == "Keywords"
    assert AdobePDFSchema.PDF_VERSION == "PDFVersion"
    assert AdobePDFSchema.PRODUCER == "Producer"


def test_default_accessors_return_none() -> None:
    schema = _adobe()
    assert schema.get_keywords() is None
    assert schema.get_pdf_version() is None
    assert schema.get_producer() is None


def test_round_trip_each_accessor() -> None:
    schema = _adobe()
    schema.set_keywords("kw1 kw2 kw3")
    schema.set_pdf_version("1.4")
    schema.set_producer("testcase")
    assert schema.get_keywords() == "kw1 kw2 kw3"
    assert schema.get_pdf_version() == "1.4"
    assert schema.get_producer() == "testcase"

    schema.set_keywords(None)
    schema.set_pdf_version(None)
    schema.set_producer(None)
    assert schema.get_keywords() is None
    assert schema.get_pdf_version() is None
    assert schema.get_producer() is None


def test_constructor_with_own_prefix() -> None:
    schema = AdobePDFSchema(XMPMetadata.create_xmp_metadata(), own_prefix="myPdf")
    assert schema.get_prefix() == "myPdf"
    assert schema.get_namespace() == "http://ns.adobe.com/pdf/1.3/"


def test_xmp_metadata_get_adobe_pdf_schema_returns_typed_wrapper() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_adobe_pdf_schema() is None
    assert metadata.get_pdf_schema() is None
    schema = metadata.add_adobe_pdf_schema()
    assert isinstance(schema, AdobePDFSchema)
    # Idempotent — repeat add returns the same instance.
    assert metadata.add_adobe_pdf_schema() is schema
    assert metadata.get_adobe_pdf_schema() is schema
    assert metadata.get_pdf_schema() is schema
    # Upstream-named aliases.
    assert metadata.create_and_add_adobe_pdf_schema() is schema
    assert metadata.add_pdf_basic_schema() is schema


def test_dom_parser_dispatches_pdf_namespace_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:pdf='http://ns.adobe.com/pdf/1.3/'"
        b" pdf:Keywords='alpha beta'"
        b" pdf:PDFVersion='1.7'"
        b" pdf:Producer='ProducerOne'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(AdobePDFSchema)
    assert isinstance(schema, AdobePDFSchema)
    assert schema.get_keywords() == "alpha beta"
    assert schema.get_pdf_version() == "1.7"
    assert schema.get_producer() == "ProducerOne"
    assert metadata.get_adobe_pdf_schema() is schema
    assert metadata.get_pdf_schema() is schema


def test_dom_parser_get_namespace_table_includes_pdf() -> None:
    table = DomXmpParser().get_namespace_table()
    assert table.get("pdf") == "http://ns.adobe.com/pdf/1.3/"


# --- typed-property accessors ------------------------------------------


def _build_text(metadata: XMPMetadata, name: str, value: str) -> TextType:
    return TextType(metadata, AdobePDFSchema.NAMESPACE, "pdf", name, value)


def test_typed_property_round_trip_keywords() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    prop = _build_text(metadata, AdobePDFSchema.KEYWORDS, "kw1 kw2 kw3")
    schema.set_keywords_property(prop)

    # Typed-form retrieval returns the same instance handed in.
    assert schema.get_keywords_property() is prop
    assert isinstance(schema.get_keywords_property(), TextType)
    assert schema.get_keywords_property().get_value() == "kw1 kw2 kw3"
    # String-form retrieval sees the same value.
    assert schema.get_keywords() == "kw1 kw2 kw3"


def test_typed_property_round_trip_pdf_version() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    prop = _build_text(metadata, AdobePDFSchema.PDF_VERSION, "1.7")
    schema.set_pdf_version_property(prop)

    assert schema.get_pdf_version_property() is prop
    assert schema.get_pdf_version_property().get_value() == "1.7"
    assert schema.get_pdf_version() == "1.7"


def test_typed_property_round_trip_producer() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    prop = _build_text(metadata, AdobePDFSchema.PRODUCER, "ProducerOne")
    schema.set_producer_property(prop)

    assert schema.get_producer_property() is prop
    assert schema.get_producer_property().get_value() == "ProducerOne"
    assert schema.get_producer() == "ProducerOne"


def test_typed_getters_return_none_when_unset() -> None:
    schema = _adobe()
    assert schema.get_keywords_property() is None
    assert schema.get_pdf_version_property() is None
    assert schema.get_producer_property() is None


def test_typed_setter_with_none_clears_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    schema.set_keywords_property(_build_text(metadata, AdobePDFSchema.KEYWORDS, "x"))
    schema.set_keywords_property(None)
    assert schema.get_keywords_property() is None
    assert schema.get_keywords() is None


def test_string_form_setter_after_typed_returns_rehydrated_text_type() -> None:
    """``set_keywords(str)`` after ``set_keywords_property(TextType)`` must
    invalidate the typed cache; subsequent typed reads hand back a fresh
    ``TextType`` reflecting the new string value."""
    metadata = XMPMetadata.create_xmp_metadata()
    schema = AdobePDFSchema(metadata)
    prop = _build_text(metadata, AdobePDFSchema.KEYWORDS, "first")
    schema.set_keywords_property(prop)
    assert schema.get_keywords_property() is prop

    schema.set_keywords("second")
    rehydrated = schema.get_keywords_property()
    assert rehydrated is not prop
    assert isinstance(rehydrated, TextType)
    assert rehydrated.get_value() == "second"
    assert schema.get_keywords() == "second"


def test_string_form_first_then_typed_getter_lazily_constructs_text_type() -> None:
    """A schema populated only via the string-form setter must still respond
    to the typed getter — upstream ``getKeywordsProperty()`` synthesizes a
    field from the underlying value when none is explicitly attached."""
    schema = _adobe()
    schema.set_keywords("alpha beta")
    prop = schema.get_keywords_property()
    assert isinstance(prop, TextType)
    assert prop.get_value() == "alpha beta"
    assert prop.get_property_name() == AdobePDFSchema.KEYWORDS
    assert prop.get_namespace() == AdobePDFSchema.NAMESPACE
    assert prop.get_prefix() == "pdf"


def test_typed_setter_rejects_non_text_type() -> None:
    schema = _adobe()
    with pytest.raises(TypeError):
        schema.set_keywords_property("not-a-text-type")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        schema.set_pdf_version_property(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        schema.set_producer_property(123)  # type: ignore[arg-type]
