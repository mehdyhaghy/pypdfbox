from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    ArrayProperty,
    Cardinality,
    IntegerType,
    LayerType,
    PhotoshopSchema,
    RationalType,
    TextType,
    TiffSchema,
    URIType,
    XMPMetadata,
)


def _metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_photoshop_typed_getter_rewraps_cross_type_simple_property() -> None:
    metadata = _metadata()
    schema = PhotoshopSchema(metadata)
    schema._properties[PhotoshopSchema.ANCESTORID] = TextType(
        metadata,
        PhotoshopSchema.NAMESPACE,
        "photoshop",
        PhotoshopSchema.ANCESTORID,
        "uuid:parent",
    )

    prop = schema.get_ancestor_id_property()

    assert isinstance(prop, URIType)
    assert prop.get_property_name() == PhotoshopSchema.ANCESTORID
    assert prop.get_string_value() == "uuid:parent"


def test_photoshop_integer_getter_handles_plain_and_typed_invalid_values() -> None:
    metadata = _metadata()
    schema = PhotoshopSchema(metadata)

    schema._properties[PhotoshopSchema.URGENCY] = " 7 "
    assert schema.get_urgency() == 7

    schema._properties[PhotoshopSchema.URGENCY] = "not-an-int"
    assert schema.get_urgency() is None


def test_photoshop_set_integer_rejects_bool_and_string_form_stays_typed() -> None:
    schema = PhotoshopSchema(_metadata())

    with pytest.raises(TypeError, match="got bool"):
        schema.set_color_mode(False)

    schema.set_color_mode("3")
    prop = schema.get_color_mode_property()
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 3


def test_photoshop_text_layers_replace_non_array_storage_and_skip_bad_children() -> None:
    metadata = _metadata()
    schema = PhotoshopSchema(metadata)
    schema._properties[PhotoshopSchema.TEXT_LAYERS] = "not-an-array"
    layer = LayerType(metadata)
    layer.set_layer_name("Title")
    layer.set_layer_text("Hello")

    schema.add_text_layer(layer)
    seq = schema.get_text_layers_property()
    assert isinstance(seq, ArrayProperty)
    assert seq.get_array_type() == Cardinality.Seq

    seq.add_property(
        TextType(
            metadata,
            PhotoshopSchema.NAMESPACE,
            "photoshop",
            PhotoshopSchema.TEXT_LAYERS,
            "ignored",
        )
    )
    assert schema.get_text_layers() == [layer]


def test_photoshop_set_document_ancestors_from_plain_list_then_remove_missing() -> None:
    schema = PhotoshopSchema(_metadata())
    schema.set_document_ancestors(["uuid:a", "uuid:b"])

    bag = schema.get_document_ancestors_property()
    assert isinstance(bag, ArrayProperty)
    assert [child.get_string_value() for child in bag.get_all_properties()] == [
        "uuid:a",
        "uuid:b",
    ]

    schema.remove_document_ancestor("uuid:missing")
    assert schema.get_document_ancestors() == ["uuid:a", "uuid:b"]


def test_tiff_lang_alt_property_returns_none_for_absent_empty_or_non_dict_storage() -> None:
    schema = TiffSchema(_metadata())

    assert schema.get_copyright_property() is None
    schema._properties[TiffSchema.COPYRIGHT] = {}
    assert schema.get_copyright_property() is None
    schema._properties[TiffSchema.COPYRIGHT] = "plain"
    assert schema.get_copyright_property() is None


@pytest.mark.parametrize(
    "adder,getter,values",
    [
        (TiffSchema.add_bits_per_sample, TiffSchema.get_bits_per_sample, [8, "16"]),
        (
            TiffSchema.add_y_cb_cr_sub_sampling,
            TiffSchema.get_y_cb_cr_sub_sampling,
            [2, "1"],
        ),
        (
            TiffSchema.add_transfer_function,
            TiffSchema.get_transfer_function,
            [0, "255"],
        ),
        (TiffSchema.add_white_point, TiffSchema.get_white_point, ["1/1", "2/1"]),
        (
            TiffSchema.add_primary_chromaticities,
            TiffSchema.get_primary_chromaticities,
            ["64/100", "33/100"],
        ),
        (
            TiffSchema.add_y_cb_cr_coefficients,
            TiffSchema.get_y_cb_cr_coefficients,
            ["299/1000", "587/1000"],
        ),
        (
            TiffSchema.add_reference_black_white,
            TiffSchema.get_reference_black_white,
            ["0/1", "255/1"],
        ),
    ],
)
def test_tiff_sequence_accessors_append_stringified_values(
    adder,
    getter,
    values: list[int | str],
) -> None:
    schema = TiffSchema(_metadata())

    for value in values:
        adder(schema, value)

    assert getter(schema) == [str(value) for value in values]


def test_tiff_rational_property_wraps_plain_string_and_none_clears() -> None:
    schema = TiffSchema(_metadata())
    schema.set_x_resolution("300/1")

    prop = schema.get_x_resolution_property()
    assert isinstance(prop, RationalType)
    assert prop.get_property_name() == TiffSchema.XRESOLUTION
    assert prop.as_fraction() is not None

    schema.set_x_resolution(None)
    assert schema.get_x_resolution() is None
    assert schema.get_x_resolution_property() is None


def test_tiff_typed_set_renames_property_and_text_getter_reads_typed_value() -> None:
    metadata = _metadata()
    schema = TiffSchema(metadata)
    prop = TextType(
        metadata,
        TiffSchema.NAMESPACE,
        "tiff",
        "WrongName",
        "Digest",
    )

    schema.set_native_digest_property(prop)

    assert prop.get_property_name() == TiffSchema.NATIVE_DIGEST
    assert schema.get_native_digest() == "Digest"
