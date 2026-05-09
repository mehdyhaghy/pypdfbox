from __future__ import annotations

import pytest

from pypdfbox.xmpbox import IntegerType, TiffSchema, XMPMetadata


def _tiff() -> TiffSchema:
    return TiffSchema(XMPMetadata.create_xmp_metadata())


def _integer_property(schema: TiffSchema, local_name: str, value: int) -> IntegerType:
    return IntegerType(
        schema._metadata,
        TiffSchema.NAMESPACE,
        TiffSchema.PREFERRED_PREFIX,
        local_name,
        value,
    )


def test_integer_getter_accepts_raw_int_storage_without_treating_bool_as_int() -> None:
    schema = _tiff()
    schema._properties[TiffSchema.IMAGE_WIDTH] = 640

    assert schema.get_image_width() == 640


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (["512"], 512),
        (["wide"], None),
        ([], None),
    ],
)
def test_integer_getter_falls_back_to_best_effort_text_values(
    raw: list[str],
    expected: int | None,
) -> None:
    schema = _tiff()
    schema._properties[TiffSchema.IMAGE_WIDTH] = raw

    assert schema.get_image_width() == expected


@pytest.mark.parametrize(
    ("setter", "getter", "prop_getter", "local_name", "value"),
    [
        (
            TiffSchema.set_image_length_property,
            TiffSchema.get_image_length,
            TiffSchema.get_image_length_property,
            TiffSchema.IMAGE_LENGTH,
            301,
        ),
        (
            TiffSchema.set_compression_property,
            TiffSchema.get_compression,
            TiffSchema.get_compression_property,
            TiffSchema.COMPRESSION,
            5,
        ),
        (
            TiffSchema.set_photometric_interpretation_property,
            TiffSchema.get_photometric_interpretation,
            TiffSchema.get_photometric_interpretation_property,
            TiffSchema.PHOTOMETRIC_INTERPRETATION,
            2,
        ),
        (
            TiffSchema.set_samples_per_pixel_property,
            TiffSchema.get_samples_per_pixel,
            TiffSchema.get_samples_per_pixel_property,
            TiffSchema.SAMPLES_PER_PIXEL,
            3,
        ),
        (
            TiffSchema.set_planar_configuration_property,
            TiffSchema.get_planar_configuration,
            TiffSchema.get_planar_configuration_property,
            TiffSchema.PLANAR_CONFIGURATION,
            1,
        ),
        (
            TiffSchema.set_y_cb_cr_positioning_property,
            TiffSchema.get_y_cb_cr_positioning,
            TiffSchema.get_y_cb_cr_positioning_property,
            TiffSchema.YCB_CR_POSITIONING,
            1,
        ),
        (
            TiffSchema.set_resolution_unit_property,
            TiffSchema.get_resolution_unit,
            TiffSchema.get_resolution_unit_property,
            TiffSchema.RESOLUTION_UNIT,
            2,
        ),
    ],
)
def test_remaining_integer_property_setters_store_and_rename_property(
    setter,
    getter,
    prop_getter,
    local_name: str,
    value: int,
) -> None:
    schema = _tiff()
    prop = _integer_property(schema, "WrongName", value)

    setter(schema, prop)

    assert prop.get_property_name() == local_name
    assert getter(schema) == value
    assert prop_getter(schema) is prop
