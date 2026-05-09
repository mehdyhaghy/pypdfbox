from __future__ import annotations

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    ArrayProperty,
    Cardinality,
    PDFAExtensionSchema,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
    XMPSchema,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave829_xmp_schema_typed_array_add_and_remove_round_trip() -> None:
    metadata = _metadata()
    schema = XMPSchema(metadata, namespace_uri="urn:test", prefix="t")
    bag = ArrayProperty(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        "Subjects",
        Cardinality.Bag,
    )
    bag.add_property(
        TextType(metadata, schema.get_namespace(), schema.get_prefix(), "li", "alpha")
    )
    schema.set_property("Subjects", bag)

    schema.add_qualified_bag_value("Subjects", "beta")
    schema.remove_unqualified_bag_value("Subjects", "alpha")

    assert schema.get_metadata() is metadata
    assert schema.get_unqualified_bag_value_list("Subjects") == ["beta"]


def test_wave829_xmp_schema_lang_alt_noops_on_non_dict_storage() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:test", prefix="t")
    schema.set_property("Title", "plain title")

    schema.remove_unqualified_language_property_value("Title", "en-US")

    assert schema.get_property("Title") == "plain title"
    assert schema.get_unqualified_language_property_languages_value("Title") is None


def test_wave829_photoshop_integer_reader_ignores_unusable_dict_values() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_property(PhotoshopSchema.URGENCY, {"x-default": object()})

    assert schema.get_urgency() is None


def test_wave829_adobe_pdf_known_properties_unwraps_direct_text_type() -> None:
    metadata = _metadata()
    schema = AdobePDFSchema(metadata)
    keywords = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.KEYWORDS,
        "one, two",
    )
    schema.set_property(AdobePDFSchema.KEYWORDS, keywords)

    assert schema.get_known_properties() == {AdobePDFSchema.KEYWORDS: "one, two"}


def test_wave829_pdfa_extension_non_list_storage_is_counted_as_empty() -> None:
    schema = PDFAExtensionSchema(_metadata())
    schema.set_property(PDFAExtensionSchema.SCHEMAS, ("unexpected", "shape"))

    assert schema.get_extension_schemas() == []
    assert schema.get_schemas_property() == ("unexpected", "shape")
    assert schema.get_count() == 0
