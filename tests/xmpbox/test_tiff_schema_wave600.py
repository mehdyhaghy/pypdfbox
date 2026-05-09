from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pypdfbox.xmpbox import DateType, IntegerType, TiffSchema, XMPMetadata


def _tiff() -> TiffSchema:
    return TiffSchema(XMPMetadata.create_xmp_metadata())


def test_wave600_integer_string_setter_removes_and_rejects_bool() -> None:
    schema = _tiff()

    schema.set_orientation(" 6 ")
    assert schema.get_orientation() == 6

    with pytest.raises(TypeError, match="got bool"):
        schema.set_orientation(True)

    schema.set_orientation(None)
    assert schema.get_orientation() is None
    assert schema.get_orientation_property() is None


def test_wave600_integer_property_getter_returns_none_for_uncoercible_storage() -> None:
    schema = _tiff()
    schema._properties[TiffSchema.IMAGE_LENGTH] = "12.5"

    assert schema.get_image_length() is None
    assert schema.get_image_length_property() is None


def test_wave600_date_time_property_round_trips_typed_value_and_none_clears() -> None:
    schema = _tiff()
    prop = DateType(
        schema._metadata,
        TiffSchema.NAMESPACE,
        TiffSchema.PREFERRED_PREFIX,
        "WrongName",
        datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC),
    )

    schema.set_date_time_property(prop)

    assert prop.get_property_name() == TiffSchema.DATE_TIME
    assert schema.get_date_time_property() is prop
    assert schema.get_date_time() == "2024-03-04T05:06:07+00:00"

    schema.set_date_time_property(None)

    assert schema.get_date_time() is None
    assert schema.get_date_time_property() is None


def test_wave600_typed_getter_rewraps_string_integer_property() -> None:
    schema = _tiff()
    schema._properties[TiffSchema.RESOLUTION_UNIT] = "2"

    prop = schema.get_resolution_unit_property()

    assert isinstance(prop, IntegerType)
    assert prop.get_property_name() == TiffSchema.RESOLUTION_UNIT
    assert prop.get_value() == 2
