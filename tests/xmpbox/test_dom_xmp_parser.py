from __future__ import annotations

import io

import pytest

from pypdfbox.xmpbox import (
    DomXmpParser,
    DublinCoreSchema,
    XMPBasicSchema,
    XMPSchema,
    XmpParsingException,
)
from pypdfbox.xmpbox.dom_xmp_parser import parse as module_parse


SIMPLE_PACKET = b"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:xmp="http://ns.adobe.com/xap/1.0/">
  <rdf:Description rdf:about="">
    <dc:title>
      <rdf:Alt>
        <rdf:li xml:lang="x-default">Hello</rdf:li>
        <rdf:li xml:lang="fr">Bonjour</rdf:li>
      </rdf:Alt>
    </dc:title>
    <dc:creator>
      <rdf:Seq>
        <rdf:li>Alice</rdf:li>
        <rdf:li>Bob</rdf:li>
      </rdf:Seq>
    </dc:creator>
    <dc:subject>
      <rdf:Bag>
        <rdf:li>pdf</rdf:li>
        <rdf:li>xmp</rdf:li>
      </rdf:Bag>
    </dc:subject>
    <xmp:CreatorTool>pypdfbox</xmp:CreatorTool>
    <xmp:CreateDate>2026-04-25T12:00:00Z</xmp:CreateDate>
  </rdf:Description>
</rdf:RDF>
<?xpacket end="w"?>"""


def test_parse_packet_extracts_xpacket_attributes() -> None:
    meta = DomXmpParser().parse(SIMPLE_PACKET)
    assert meta.get_xpacket_id() == "W5M0MpCehiHzreSzNTczkc9d"
    assert meta.get_end_xpacket() == "w"


def test_parse_packet_dispatches_known_namespaces() -> None:
    meta = DomXmpParser().parse(SIMPLE_PACKET)
    dc = meta.get_dublin_core_schema()
    basic = meta.get_xmp_basic_schema()
    assert isinstance(dc, DublinCoreSchema)
    assert isinstance(basic, XMPBasicSchema)
    assert dc.get_title() == "Hello"
    assert dc.get_title("fr") == "Bonjour"
    assert dc.get_creators() == ["Alice", "Bob"]
    assert dc.get_subjects() == ["pdf", "xmp"]
    assert basic.get_creator_tool() == "pypdfbox"
    assert basic.get_create_date() == "2026-04-25T12:00:00Z"


def test_parse_accepts_string_input() -> None:
    meta = DomXmpParser().parse(SIMPLE_PACKET.decode("utf-8"))
    assert meta.get_dublin_core_schema() is not None


def test_parse_accepts_binary_stream() -> None:
    meta = DomXmpParser().parse(io.BytesIO(SIMPLE_PACKET))
    assert meta.get_dublin_core_schema() is not None


def test_module_level_parse_helper_matches_class() -> None:
    a = DomXmpParser().parse(SIMPLE_PACKET)
    b = module_parse(SIMPLE_PACKET)
    assert a.get_dublin_core_schema() is not None
    assert b.get_dublin_core_schema() is not None


def test_parse_attribute_form_properties() -> None:
    packet = (
        b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
        b'<rdf:Description rdf:about="" pdf:Producer="WeasyPrint 64.1"/>'
        b'</rdf:RDF><?xpacket end="r"?>'
    )
    meta = DomXmpParser().parse(packet)
    schema = meta.get_schema("http://ns.adobe.com/pdf/1.3/")
    assert schema is not None
    assert schema.get_unqualified_text_property_value("Producer") == "WeasyPrint 64.1"
    # Unknown namespace falls back to plain XMPSchema
    assert isinstance(schema, XMPSchema)


def test_parse_unknown_namespace_falls_back_to_plain_schema() -> None:
    packet = (
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:custom="http://example.com/custom#">'
        b'<rdf:Description rdf:about="">'
        b'<custom:Label>my-label</custom:Label>'
        b'</rdf:Description></rdf:RDF>'
    )
    meta = DomXmpParser().parse(packet)
    schema = meta.get_schema("http://example.com/custom#")
    assert schema is not None
    assert type(schema) is XMPSchema
    assert schema.get_unqualified_text_property_value("Label") == "my-label"


def test_parse_packet_without_xpacket_wrapper() -> None:
    # Some PDFs embed bare RDF without the processing instructions.
    packet = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:format>application/pdf</dc:format>'
        b'</rdf:Description></rdf:RDF>'
    )
    meta = DomXmpParser().parse(packet)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_format() == "application/pdf"


def test_parse_handles_x_xmpmeta_wrapper() -> None:
    packet = (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about="">'
        b'<dc:format>application/pdf</dc:format>'
        b'</rdf:Description></rdf:RDF></x:xmpmeta>'
    )
    meta = DomXmpParser().parse(packet)
    assert meta.get_dublin_core_schema() is not None
    assert meta.get_dublin_core_schema().get_format() == "application/pdf"


def test_parse_malformed_raises_xmp_parsing_exception() -> None:
    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(b"<rdf:RDF unclosed")


def test_parse_missing_rdf_root_raises() -> None:
    with pytest.raises(XmpParsingException):
        DomXmpParser().parse(b"<root><child/></root>")


def test_xmp_parsing_exception_default_error_type_is_undefined() -> None:
    """Single-message construction stays back-compat and reports UNDEFINED."""
    exc = XmpParsingException("some failure")
    assert exc.get_error_type() is XmpParsingException.ErrorType.UNDEFINED
    assert exc.error_type is XmpParsingException.ErrorType.UNDEFINED
    assert str(exc) == "some failure"


def test_xmp_parsing_exception_with_explicit_error_type() -> None:
    exc = XmpParsingException(
        XmpParsingException.ErrorType.NO_SCHEMA, "missing schema"
    )
    assert exc.get_error_type() is XmpParsingException.ErrorType.NO_SCHEMA
    assert str(exc) == "missing schema"


def test_xmp_parsing_exception_with_cause_chains_through() -> None:
    inner = ValueError("inner")
    exc = XmpParsingException(
        XmpParsingException.ErrorType.FORMAT, "wrapping", cause=inner
    )
    assert exc.__cause__ is inner
    assert exc.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_xmp_parsing_exception_error_type_enum_membership() -> None:
    # Mirror the upstream Java enum: every documented error type must exist
    # by upstream-Java name and resolve to a unique value.
    expected_names = {
        "Undefined",
        "Configuration",
        "XpacketBadStart",
        "XpacketBadEnd",
        "NoRootElement",
        "NoSchema",
        "InvalidPdfaSchema",
        "NoType",
        "InvalidType",
        "Format",
        "NoValueType",
        "RequiredProperty",
        "InvalidPrefix",
    }
    actual_names = {member.value for member in XmpParsingException.ErrorType}
    assert actual_names == expected_names


def test_parse_malformed_sets_format_error_type() -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse(b"<rdf:RDF unclosed")
    assert info.value.get_error_type() is XmpParsingException.ErrorType.FORMAT


def test_parse_missing_rdf_root_sets_no_root_element_error_type() -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse(b"<root><child/></root>")
    assert (
        info.value.get_error_type()
        is XmpParsingException.ErrorType.NO_ROOT_ELEMENT
    )


def test_multiple_descriptions_for_same_namespace_merge() -> None:
    # Mirrors the shape of upstream PDFBOX-5976: one schema's properties
    # spread across multiple rdf:Description blocks.
    packet = (
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
        b' xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description rdf:about=""><dc:format>application/pdf</dc:format></rdf:Description>'
        b'<rdf:Description rdf:about=""><dc:identifier>id-1</dc:identifier></rdf:Description>'
        b'</rdf:RDF>'
    )
    meta = DomXmpParser().parse(packet)
    dc = meta.get_dublin_core_schema()
    assert dc is not None
    assert dc.get_format() == "application/pdf"
    assert dc.get_identifier() == "id-1"
