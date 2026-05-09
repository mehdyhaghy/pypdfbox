from __future__ import annotations

import io
from xml.etree import ElementTree as ET

from pypdfbox.xmpbox import (
    ColorantType,
    DomXmpParser,
    FontType,
    IntegerType,
    PDFAIdentificationSchema,
    PDFUAIdentificationSchema,
    TextType,
    XMPageTextSchema,
    XMPMetadata,
)


def _pdfa() -> PDFAIdentificationSchema:
    return PDFAIdentificationSchema(XMPMetadata.create_xmp_metadata())


def _pdfua() -> PDFUAIdentificationSchema:
    return PDFUAIdentificationSchema(XMPMetadata.create_xmp_metadata())


def test_pdfa_integer_reads_abstract_simple_and_unknown_storage() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(metadata)
    text_part = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        PDFAIdentificationSchema.PART,
        "3",
    )

    schema.set_property(PDFAIdentificationSchema.PART, text_part)
    assert schema.get_part() == 3

    schema.set_property(PDFAIdentificationSchema.PART, object())
    assert schema.get_part() is None


def test_pdfa_typed_get_rehydrates_from_abstract_simple_and_rejects_bad_raw() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PDFAIdentificationSchema(metadata)
    schema.set_property(
        PDFAIdentificationSchema.PART,
        TextType(
            metadata,
            schema.get_namespace(),
            schema.get_prefix(),
            PDFAIdentificationSchema.PART,
            "4",
        ),
    )

    part = schema.get_part_property()
    assert isinstance(part, IntegerType)
    assert part.get_value() == 4

    schema.set_property(PDFAIdentificationSchema.PART, "not-an-int")
    assert schema.get_part_property() is None


def test_pdfa_set_rev_value_with_int_alias() -> None:
    schema = _pdfa()
    schema.set_rev_value_with_int(2020)
    assert schema.get_rev() == 2020
    assert schema.get_revision() == "2020"


def test_pdfua_part_fallback_reads_text_list_and_rejects_bad_fallback() -> None:
    schema = _pdfua()
    schema.set_property(PDFUAIdentificationSchema.PART, ["2"])
    assert schema.get_part() == 2

    schema.set_property(PDFUAIdentificationSchema.PART, [])
    assert schema.get_part() is None

    schema.set_property(PDFUAIdentificationSchema.PART, ["not-an-int"])
    assert schema.get_part() is None


def test_pdfua_revision_stringifies_integer_storage() -> None:
    schema = _pdfua()
    schema.set_property(PDFUAIdentificationSchema.REV, 2024)
    assert schema.get_revision() == "2024"
    assert schema.get_rev() == "2024"


def test_dom_parser_parse_describe_element_builds_accumulator_when_omitted() -> None:
    desc = ET.fromstring(
        b"<rdf:Description"
        b" xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'"
        b" xmlns:dc='http://purl.org/dc/elements/1.1/'"
        b" rdf:about='urn:test'>"
        b"<rdf:value>ignored</rdf:value>"
        b"<dc:format>application/pdf</dc:format>"
        b"</rdf:Description>"
    )

    per_ns = DomXmpParser().parse_describe_element(
        desc,
        XMPMetadata.create_xmp_metadata(),
    )

    schema = per_ns["http://purl.org/dc/elements/1.1/"]
    assert schema.get_about() == "urn:test"
    assert schema.get_unqualified_text_property_value("format") == "application/pdf"


def test_dom_parser_accepts_text_stream_and_resource_property_alias() -> None:
    packet = (
        "<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'"
        " xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        "<rdf:Description rdf:about=''><dc:format>application/pdf</dc:format>"
        "</rdf:Description></rdf:RDF>"
    )
    metadata = DomXmpParser().parse(io.StringIO(packet))
    assert metadata.get_dublin_core_schema() is not None

    resource = ET.fromstring(
        b"<xmp:BaseURL"
        b" xmlns:xmp='http://ns.adobe.com/xap/1.0/'"
        b" xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'"
        b" rdf:resource='https://example.test/base'/>"
    )
    assert DomXmpParser().parse_property(resource) == "https://example.test/base"


def test_paged_text_reads_primitive_scalar_storage_shapes() -> None:
    schema = XMPageTextSchema(XMPMetadata.create_xmp_metadata())
    schema.set_property(XMPageTextSchema.N_PAGES, 12)
    assert schema.get_n_pages() == 12
    assert XMPageTextSchema._coerce_boolean(True) is True


def test_paged_text_raw_singletons_are_wrapped_or_filtered() -> None:
    schema = XMPageTextSchema(XMPMetadata.create_xmp_metadata())
    schema.set_property(XMPageTextSchema.COLORANTS, "PANTONE 185 C")
    assert schema.get_colorants() == ["PANTONE 185 C"]
    assert schema.get_colorant_properties() == []

    spot = ColorantType(schema.get_metadata())
    schema.set_property(XMPageTextSchema.COLORANTS, spot)
    assert schema.get_colorant_properties() == [spot]

    schema.set_property(XMPageTextSchema.FONTS, "Helvetica")
    assert schema.get_fonts() == ["Helvetica"]
    assert schema.get_font_properties() == []

    font = FontType(schema.get_metadata())
    schema.set_property(XMPageTextSchema.FONTS, font)
    assert schema.get_font_properties() == [font]
