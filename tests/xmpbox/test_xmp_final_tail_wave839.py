from __future__ import annotations

from pypdfbox.xmpbox import (
    AdobePDFSchema,
    ArrayProperty,
    Cardinality,
    LayerType,
    PDFAExtensionSchema,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
    XMPSchema,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_wave839_xmp_schema_array_reader_preserves_string_scalar_shape() -> None:
    schema = XMPSchema(_metadata(), namespace_uri="urn:test", prefix="t")

    schema.set_property("Subjects", "single")

    assert schema.get_unqualified_bag_value_list("Subjects") == ["single"]
    assert schema.get_unqualified_array_list("Subjects") == ["single"]


def test_wave839_photoshop_add_text_layers_replaces_non_array_storage() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_property(PhotoshopSchema.TEXT_LAYERS, "stale parser value")

    schema.add_text_layers("headline", "Visible layer text")

    prop = schema.get_text_layers_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_property_name() == PhotoshopSchema.TEXT_LAYERS
    assert prop.get_array_type() is Cardinality.Seq
    layers = schema.get_text_layers()
    assert layers is not None
    assert len(layers) == 1
    assert layers[0].get_layer_name() == "headline"
    assert layers[0].get_layer_text() == "Visible layer text"


def test_wave839_photoshop_text_layers_skip_non_layer_children() -> None:
    metadata = _metadata()
    schema = PhotoshopSchema(metadata)
    seq = ArrayProperty(
        metadata,
        PhotoshopSchema.NAMESPACE,
        PhotoshopSchema.PREFERRED_PREFIX,
        PhotoshopSchema.TEXT_LAYERS,
        Cardinality.Seq,
    )
    layer = LayerType(metadata)
    layer.set_layer_name("kept")
    layer.set_layer_text("text")
    seq.add_property(TextType(metadata, "urn:test", "t", "Other", "ignored"))
    seq.add_property(layer)

    schema.set_text_layers_property(seq)

    assert schema.get_text_layers() == [layer]


def test_wave839_adobe_pdf_typed_getter_drops_stale_cache_for_non_text_storage() -> None:
    metadata = _metadata()
    schema = AdobePDFSchema(metadata)
    prop = TextType(
        metadata,
        AdobePDFSchema.NAMESPACE,
        AdobePDFSchema.PREFERRED_PREFIX,
        AdobePDFSchema.KEYWORDS,
        "first",
    )
    schema.set_keywords_property(prop)

    schema.set_property(AdobePDFSchema.KEYWORDS, {"unexpected": "shape"})

    assert schema.get_keywords_property() is None
    assert schema.get_known_properties() == {
        AdobePDFSchema.KEYWORDS: "{'unexpected': 'shape'}"
    }


def test_wave839_pdfa_extension_mixed_list_is_raw_but_not_normalized() -> None:
    schema = PDFAExtensionSchema(_metadata())
    raw = [
        {
            PDFAExtensionSchema.SCHEMA: "Demo",
            PDFAExtensionSchema.NAMESPACE_URI: "urn:demo",
            PDFAExtensionSchema.PREFIX: "demo",
        },
        "not a struct",
    ]

    schema.set_property(PDFAExtensionSchema.SCHEMAS, raw)

    assert schema.get_extension_schemas() == []
    assert schema.get_schemas_property() is raw
    assert schema.get_count() == 2
