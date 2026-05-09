from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    IntegerType,
    LayerType,
    PhotoshopSchema,
    TextType,
    XMPMetadata,
)


def _schema() -> PhotoshopSchema:
    return PhotoshopSchema(XMPMetadata.create_xmp_metadata())


def _layer(metadata: XMPMetadata, name: str, text: str) -> LayerType:
    layer = LayerType(metadata)
    layer.set_layer_name(name)
    layer.set_layer_text(text)
    return layer


def test_integer_accessors_reject_bool_storage_and_bool_setter() -> None:
    schema = _schema()

    schema._properties[PhotoshopSchema.URGENCY] = True
    assert schema.get_urgency() is None

    with pytest.raises(TypeError, match="expects int or str"):
        schema.set_urgency(False)


def test_integer_accessors_trim_decimal_strings_and_ignore_invalid_typed_value() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)

    schema.set_color_mode(" 9 ")
    assert schema.get_color_mode() == 9

    schema.set_color_mode_property(
        TextType(
            metadata,
            PhotoshopSchema.NAMESPACE,
            "photoshop",
            PhotoshopSchema.COLOR_MODE,
            "not-an-int",
        )
    )
    assert schema.get_color_mode() is None


def test_cross_type_typed_getter_rewraps_existing_simple_property() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    schema.set_ancestor_id_property(
        TextType(
            metadata,
            PhotoshopSchema.NAMESPACE,
            "photoshop",
            PhotoshopSchema.ANCESTORID,
            "uuid:from-text",
        )
    )

    ancestor = schema.get_ancestor_id_property()

    assert ancestor is not None
    assert ancestor.get_string_value() == "uuid:from-text"
    assert ancestor.get_property_name() == PhotoshopSchema.ANCESTORID


def test_typed_setter_renames_field_to_upstream_local_name() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    field = TextType(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        "WrongName",
        "Paris",
    )

    schema.set_city_property(field)

    assert field.get_property_name() == PhotoshopSchema.CITY
    assert schema.get_property(PhotoshopSchema.CITY) is field
    assert schema.get_city() == "Paris"


def test_document_ancestors_property_view_ignores_non_string_list_items() -> None:
    schema = _schema()
    schema._properties[PhotoshopSchema.DOCUMENT_ANCESTORS] = ["uuid:ok", 42]

    bag = schema.get_document_ancestors_property()

    assert isinstance(bag, ArrayProperty)
    assert bag.get_array_type() == Cardinality.Bag
    children = bag.get_all_properties()
    assert len(children) == 1
    assert isinstance(children[0], TextType)
    assert children[0].get_string_value() == "uuid:ok"


def test_text_layers_skip_non_layer_children_and_clear_existing_container() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = PhotoshopSchema(metadata)
    seq = ArrayProperty(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        PhotoshopSchema.TEXT_LAYERS,
        Cardinality.Seq,
    )
    seq.add_property(_layer(metadata, "visible", "kept"))
    seq.add_property(
        TextType(
            metadata,
            PhotoshopSchema.NAMESPACE,
            "photoshop",
            "li",
            "ignored",
        )
    )
    schema.set_text_layers_property(seq)

    layers = schema.get_text_layers()
    assert layers is not None
    assert [layer.get_layer_name() for layer in layers] == ["visible"]

    schema.clear_text_layers()
    assert schema.get_text_layers() == []
    assert schema.get_text_layers_property() is seq


def test_text_layers_helpers_handle_absent_or_malformed_storage() -> None:
    schema = _schema()
    schema.clear_text_layers()
    assert schema.get_text_layers() is None

    schema._properties[PhotoshopSchema.TEXT_LAYERS] = "not-an-array"
    assert schema.get_text_layers() is None
    assert schema.get_text_layers_property() is None
    schema.add_text_layers("rebuilt", "text")

    layers = schema.get_text_layers()
    assert layers is not None
    assert len(layers) == 1
    assert layers[0].get_layer_name() == "rebuilt"


def test_set_text_layers_empty_list_keeps_empty_seq_property() -> None:
    schema = _schema()

    schema.set_text_layers([])

    assert schema.get_text_layers() == []
    prop = schema.get_text_layers_property()
    assert isinstance(prop, ArrayProperty)
    assert prop.get_array_type() == Cardinality.Seq
    assert prop.get_all_properties() == []


def test_integer_property_getter_wraps_plain_int_storage() -> None:
    schema = _schema()
    schema._properties[PhotoshopSchema.URGENCY] = 7

    urgency = schema.get_urgency_property()

    assert isinstance(urgency, IntegerType)
    assert urgency.get_value() == 7
