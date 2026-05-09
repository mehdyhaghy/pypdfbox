from __future__ import annotations

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    PDFAExtensionSchema,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
    XMPSchema,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave847_unqualified_bag_reader_returns_none_for_foreign_object() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:wave847", prefix="w")
    schema.set_property("Bagish", object())

    assert schema.get_unqualified_bag_value_list("Bagish") is None
    assert schema.get_unqualified_array_list("Bagish") is None


def test_wave847_photoshop_integer_reader_returns_none_when_text_fallback_absent() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_property(PhotoshopSchema.URGENCY, {"not": "text"})

    assert schema.get_urgency() is None


def test_wave847_pdfa_extension_malformed_schema_storage_reads_empty_list() -> None:
    schema = PDFAExtensionSchema(_metadata())
    raw = ("parser", "placeholder")
    schema.set_property(PDFAExtensionSchema.SCHEMAS, raw)

    assert schema.get_extension_schemas() == []
    assert schema.get_schemas_element() == raw


def test_wave847_adobe_pdf_known_properties_extracts_text_type_value() -> None:
    metadata = _metadata()
    schema = AdobePDFSchema(metadata)
    keywords = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.KEYWORDS,
        "alpha beta",
    )
    schema.set_property(AdobePDFSchema.KEYWORDS, keywords)

    assert schema.get_known_properties() == {AdobePDFSchema.KEYWORDS: "alpha beta"}
