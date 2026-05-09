from __future__ import annotations

import io
from xml.etree import ElementTree as ET

import pytest

from pypdfbox.xmpbox import DomXmpParser, DublinCoreSchema, XMPMetadata, XMPSchema
from pypdfbox.xmpbox.dom_xmp_parser import XmpParsingException

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def test_wave744_parse_describe_element_allocates_default_accumulator() -> None:
    desc = ET.fromstring(
        f"""
        <rdf:Description
            xmlns:rdf="{RDF_NS}"
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            rdf:about="urn:doc">
          <dc:format>application/pdf</dc:format>
        </rdf:Description>
        """
    )

    parsed = DomXmpParser().parse_describe_element(desc, XMPMetadata.create_xmp_metadata())

    schema = parsed[DublinCoreSchema.NAMESPACE]
    assert isinstance(schema, DublinCoreSchema)
    assert schema.get_about() == "urn:doc"
    assert schema.get_format() == "application/pdf"


def test_wave744_parse_accepts_text_streams_that_return_str() -> None:
    packet = io.StringIO(
        f"""
        <rdf:RDF xmlns:rdf="{RDF_NS}"
                 xmlns:dc="http://purl.org/dc/elements/1.1/">
          <rdf:Description rdf:about="">
            <dc:identifier>urn:doc:text-stream</dc:identifier>
          </rdf:Description>
        </rdf:RDF>
        """
    )

    metadata = DomXmpParser().parse(packet)  # type: ignore[arg-type]

    dc = metadata.get_dublin_core_schema()
    assert isinstance(dc, DublinCoreSchema)
    assert dc.get_identifier() == "urn:doc:text-stream"


def test_wave744_parser_skips_rdf_children_inside_description() -> None:
    packet = (
        f'<rdf:RDF xmlns:rdf="{RDF_NS}" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<rdf:Description rdf:about="">'
        "<rdf:value>ignored</rdf:value>"
        "<dc:format>application/pdf</dc:format>"
        "</rdf:Description></rdf:RDF>"
    )

    metadata = DomXmpParser().parse(packet)

    dc = metadata.get_dublin_core_schema()
    assert isinstance(dc, DublinCoreSchema)
    assert dc.get_format() == "application/pdf"


def test_wave744_parse_property_returns_rdf_resource_value() -> None:
    prop = ET.fromstring(
        f"""
        <custom:Related
            xmlns:custom="http://example.com/custom/"
            xmlns:rdf="{RDF_NS}"
            rdf:resource="urn:related-doc" />
        """
    )

    assert DomXmpParser().parse_property(prop) == "urn:related-doc"


def test_wave744_parse_property_prefers_text_when_resource_has_children() -> None:
    prop = ET.fromstring(
        f"""
        <custom:Related
            xmlns:custom="http://example.com/custom/"
            xmlns:rdf="{RDF_NS}"
            rdf:resource="urn:related-doc">fallback<custom:Nested /></custom:Related>
        """
    )

    assert DomXmpParser().parse_property(prop) == "fallback"


def test_wave744_unknown_namespace_without_prefix_hint_uses_ns0() -> None:
    desc = ET.fromstring(
        f"""
        <rdf:Description xmlns:rdf="{RDF_NS}" rdf:about="urn:doc">
          <VendorProperty xmlns="http://example.com/default-vendor/">value</VendorProperty>
        </rdf:Description>
        """
    )

    parsed = DomXmpParser().parse_describe_element(desc, XMPMetadata.create_xmp_metadata())

    schema = parsed["http://example.com/default-vendor/"]
    assert type(schema) is XMPSchema
    assert schema.get_prefix() == "ns0"
    assert schema.get_unqualified_text_property_value("VendorProperty") == "value"


@pytest.mark.parametrize(
    ("packet", "expected"),
    [
        (b"<not-xml", XmpParsingException.ErrorType.FORMAT),
        (b"<root />", XmpParsingException.ErrorType.NO_ROOT_ELEMENT),
    ],
)
def test_wave744_parse_errors_keep_specific_error_types(
    packet: bytes,
    expected: XmpParsingException.ErrorType,
) -> None:
    with pytest.raises(XmpParsingException) as info:
        DomXmpParser().parse(packet)

    assert info.value.error_type is expected


def test_wave744_parse_property_alt_defaults_missing_xml_lang() -> None:
    prop = ET.fromstring(
        f"""
        <dc:title
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:rdf="{RDF_NS}">
          <rdf:Alt>
            <rdf:li>Default</rdf:li>
            <rdf:li xml:lang="fr">Bonjour</rdf:li>
          </rdf:Alt>
        </dc:title>
        """
    )

    assert DomXmpParser().parse_property(prop) == {
        "x-default": "Default",
        "fr": "Bonjour",
    }
