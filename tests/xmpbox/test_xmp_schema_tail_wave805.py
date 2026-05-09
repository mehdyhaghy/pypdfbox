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


def test_wave805_xmp_schema_bag_reader_ignores_non_array_storage() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:test", prefix="t")
    schema.set_property("Bagish", object())

    assert schema.get_unqualified_bag_value_list("Bagish") is None
    assert schema.get_unqualified_array_list("Bagish") is None


def test_wave805_photoshop_integer_reader_returns_none_for_non_text_container() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_property(PhotoshopSchema.COLOR_MODE, [object()])

    assert schema.get_color_mode() is None


def test_wave805_pdfa_extension_unrecognized_schema_storage_stays_opaque() -> None:
    schema = PDFAExtensionSchema(_metadata())
    schema.set_property(PDFAExtensionSchema.SCHEMAS, {"unexpected": "shape"})

    assert schema.get_extension_schemas() == []
    assert schema.get_schemas_element() == {"unexpected": "shape"}
    assert schema.get_count() == 0


def test_wave805_adobe_pdf_known_properties_reads_text_type_storage() -> None:
    metadata = _metadata()
    schema = AdobePDFSchema(metadata)
    producer = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.PRODUCER,
        "typed producer",
    )
    schema.set_property(AdobePDFSchema.PRODUCER, producer)

    assert schema.get_known_properties() == {AdobePDFSchema.PRODUCER: "typed producer"}
