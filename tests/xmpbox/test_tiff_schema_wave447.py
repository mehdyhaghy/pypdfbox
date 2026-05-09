from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    DateType,
    IntegerType,
    RationalType,
    TextType,
    TiffSchema,
    XMPMetadata,
)


def _tiff() -> TiffSchema:
    return TiffSchema(XMPMetadata.create_xmp_metadata())


def test_integer_getter_rejects_bool_and_unparseable_typed_values() -> None:
    schema = _tiff()

    schema._properties[TiffSchema.IMAGE_WIDTH] = True
    assert schema.get_image_width() is None

    schema._properties[TiffSchema.IMAGE_WIDTH] = TextType(
        schema._metadata,
        TiffSchema.NAMESPACE,
        "tiff",
        TiffSchema.IMAGE_WIDTH,
        "wide",
    )
    assert schema.get_image_width() is None
    assert schema.get_image_width_property() is None


def test_integer_setter_rejects_bool_despite_int_subclassing() -> None:
    schema = _tiff()

    with pytest.raises(TypeError, match="got bool"):
        schema.set_orientation(True)

    assert schema.get_orientation() is None


@pytest.mark.parametrize(
    "setter,getter,prop_getter,local_name",
    [
        (
            TiffSchema.set_image_length,
            TiffSchema.get_image_length,
            TiffSchema.get_image_length_property,
            TiffSchema.IMAGE_LENGTH,
        ),
        (
            TiffSchema.set_compression,
            TiffSchema.get_compression,
            TiffSchema.get_compression_property,
            TiffSchema.COMPRESSION,
        ),
        (
            TiffSchema.set_photometric_interpretation,
            TiffSchema.get_photometric_interpretation,
            TiffSchema.get_photometric_interpretation_property,
            TiffSchema.PHOTOMETRIC_INTERPRETATION,
        ),
        (
            TiffSchema.set_samples_per_pixel,
            TiffSchema.get_samples_per_pixel,
            TiffSchema.get_samples_per_pixel_property,
            TiffSchema.SAMPLES_PER_PIXEL,
        ),
        (
            TiffSchema.set_planar_configuration,
            TiffSchema.get_planar_configuration,
            TiffSchema.get_planar_configuration_property,
            TiffSchema.PLANAR_CONFIGURATION,
        ),
        (
            TiffSchema.set_y_cb_cr_positioning,
            TiffSchema.get_y_cb_cr_positioning,
            TiffSchema.get_y_cb_cr_positioning_property,
            TiffSchema.YCB_CR_POSITIONING,
        ),
        (
            TiffSchema.set_resolution_unit,
            TiffSchema.get_resolution_unit,
            TiffSchema.get_resolution_unit_property,
            TiffSchema.RESOLUTION_UNIT,
        ),
    ],
)
def test_remaining_integer_accessors_share_text_and_typed_storage(
    setter,
    getter,
    prop_getter,
    local_name: str,
) -> None:
    schema = _tiff()

    setter(schema, "42")
    assert getter(schema) == 42
    prop = prop_getter(schema)
    assert isinstance(prop, IntegerType)
    assert prop.get_value() == 42

    prop.set_property_name("Renamed")
    schema._typed_set(local_name, prop)
    assert prop.get_property_name() == local_name

    setter(schema, None)
    assert getter(schema) is None
    assert prop_getter(schema) is None


def test_text_and_date_typed_getters_do_not_escape_invalid_raw_values() -> None:
    schema = _tiff()

    schema._properties[TiffSchema.NATIVE_DIGEST] = object()
    schema._properties[TiffSchema.DATE_TIME] = TextType(
        schema._metadata,
        TiffSchema.NAMESPACE,
        "tiff",
        TiffSchema.DATE_TIME,
        "definitely-not-a-date",
    )

    assert schema.get_native_digest_property() is None
    assert schema.get_date_time_property() is None
    assert isinstance(schema.get_date_time(), str)


def test_y_resolution_typed_property_round_trips_and_clears() -> None:
    schema = _tiff()
    prop = RationalType(
        schema._metadata,
        TiffSchema.NAMESPACE,
        "tiff",
        TiffSchema.YRESOLUTION,
        "72/1",
    )

    schema.set_y_resolution_property(prop)
    assert schema.get_y_resolution() == "72/1"
    assert schema.get_y_resolution_property() is prop

    schema.set_y_resolution_property(None)
    assert schema.get_y_resolution() is None
    assert schema.get_y_resolution_property() is None


def test_rational_string_getter_ignores_non_text_raw_value() -> None:
    schema = _tiff()
    schema._properties[TiffSchema.XRESOLUTION] = 300

    assert schema.get_x_resolution() is None
    assert schema.get_x_resolution_property() is None


def test_lang_alt_property_skips_non_string_language_slots() -> None:
    schema = _tiff()

    schema.set_image_description("Default")
    schema._properties[TiffSchema.IMAGE_DESCRIPTION]["fr"] = object()

    lang_alt = schema.get_image_description_property()
    assert lang_alt is not None
    assert lang_alt.get_language_value("x-default") == "Default"
    assert lang_alt.get_language_value("fr") is None


def test_typed_setters_for_text_date_and_rational_clear_with_none() -> None:
    schema = _tiff()
    schema.set_native_digest("abc")
    schema.set_date_time("2026-05-08T12:00:00Z")
    schema.set_x_resolution("300/1")

    schema.set_native_digest_property(None)
    schema.set_date_time_property(None)
    schema.set_x_resolution_property(None)

    assert schema.get_native_digest() is None
    assert schema.get_date_time() is None
    assert schema.get_x_resolution() is None
    assert schema.get_native_digest_property() is None
    assert schema.get_date_time_property() is None
    assert schema.get_x_resolution_property() is None


def test_date_property_can_be_reinstalled_after_clear() -> None:
    schema = _tiff()
    schema.set_date_time_property(None)

    schema.set_date_time_property(
        DateType(
            schema._metadata,
            TiffSchema.NAMESPACE,
            "tiff",
            TiffSchema.DATE_TIME,
            "2026-05-08T10:11:12Z",
        )
    )

    fetched = schema.get_date_time_property()
    assert isinstance(fetched, DateType)
    assert fetched.get_string_value().startswith("2026-05-08T10:11:12")
