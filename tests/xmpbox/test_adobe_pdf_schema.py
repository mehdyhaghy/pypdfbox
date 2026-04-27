from __future__ import annotations

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    DomXmpParser,
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
