from __future__ import annotations

from fractions import Fraction

import pytest

from pypdfbox.xmpbox import (
    DateType,
    ExifSchema,
    GPSCoordinateType,
    IntegerType,
    LangAlt,
    RationalType,
    TextType,
    XMPMetadata,
)
from pypdfbox.xmpbox.type.lang_alt import LANG_ATTR_NAME


def _exif() -> ExifSchema:
    return ExifSchema(XMPMetadata.create_xmp_metadata())


def test_wave366_integer_getter_handles_bool_text_and_bad_typed_values() -> None:
    schema = _exif()
    metadata = schema.get_metadata()

    schema.set_property(ExifSchema.COLOR_SPACE, True)
    assert schema.get_color_space() is None
    assert schema.get_color_space_property() is None

    raw_text = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.COLOR_SPACE,
        " 7 ",
    )
    schema.set_property(ExifSchema.COLOR_SPACE, raw_text)
    assert schema.get_color_space() == 7
    assert schema.get_color_space_property() is None

    schema.set_text_property_value(ExifSchema.COLOR_SPACE, "junk")
    assert schema.get_color_space() is None
    assert schema.get_color_space_property() is None

    with pytest.raises(TypeError):
        schema.set_color_space(True)


def test_wave366_typed_setters_pin_names_and_clear() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    pixel_y = IntegerType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 3024)
    status = TextType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "A")
    timestamp = DateType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        "tmp",
        "2026-05-08T09:10:11Z",
    )

    schema.set_pixel_y_dimension_property(pixel_y)
    schema.set_gps_status_property(status)
    schema.set_gps_time_stamp_property(timestamp)

    assert pixel_y.get_property_name() == ExifSchema.PIXEL_Y_DIMENSION
    assert status.get_property_name() == ExifSchema.GPS_STATUS
    assert timestamp.get_property_name() == ExifSchema.GPS_TIME_STAMP
    assert schema.get_pixel_y_dimension() == 3024
    assert schema.get_gps_status() == "A"
    assert schema.get_gps_time_stamp() == "2026-05-08T09:10:11+00:00"

    schema.set_pixel_y_dimension_property(None)
    schema.set_gps_status_property(None)
    schema.set_gps_time_stamp_property(None)

    assert schema.get_pixel_y_dimension_property() is None
    assert schema.get_gps_status_property() is None
    assert schema.get_gps_time_stamp_property() is None


def test_wave366_user_comment_property_orders_default_and_filters_non_strings() -> None:
    schema = _exif()
    schema.set_property(
        ExifSchema.USER_COMMENT,
        {"fr": "Bonjour", "x-default": "Default", "raw": object()},
    )

    lang_alt = schema.get_user_comment_property()

    assert isinstance(lang_alt, LangAlt)
    assert lang_alt.get_language_value("x-default") == "Default"
    assert lang_alt.get_language_value("fr") == "Bonjour"
    assert lang_alt.get_languages() == ["x-default", "fr"]
    first_attr = lang_alt.get_all_properties()[0].get_attribute(LANG_ATTR_NAME)
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"


def test_wave366_sequence_adders_preserve_string_values() -> None:
    schema = _exif()

    schema.add_components_configuration("01")
    schema.add_iso_speed_ratings("0200")
    schema.add_subject_area("center")
    schema.add_subject_location("1512")

    assert schema.get_components_configuration() == ["01"]
    assert schema.get_iso_speed_ratings() == ["0200"]
    assert schema.get_subject_area() == ["center"]
    assert schema.get_subject_location() == ["1512"]


def test_wave366_rational_and_gps_getters_reject_incompatible_raw_values() -> None:
    schema = _exif()

    schema.set_property(ExifSchema.FOCAL_LENGTH, 50)
    schema.set_property(ExifSchema.GPS_LATITUDE, object())

    assert schema.get_focal_length() is None
    assert schema.get_focal_length_property() is None
    assert schema.get_gps_latitude() is None
    assert schema.get_gps_latitude_property() is None


def test_wave366_typed_getters_rewrap_cross_type_simple_properties() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    raw_integer = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.COLOR_SPACE,
        "9",
    )
    raw_rational = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.GPS_ALTITUDE,
        "33/2",
    )
    raw_coordinate = TextType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        ExifSchema.GPS_DEST_LATITUDE,
        "48,51,30N",
    )

    schema.set_property(ExifSchema.COLOR_SPACE, raw_integer)
    schema.set_property(ExifSchema.GPS_ALTITUDE, raw_rational)
    schema.set_property(ExifSchema.GPS_DEST_LATITUDE, raw_coordinate)

    color_space = schema.get_color_space_property()
    altitude = schema.get_gps_altitude_property()
    coordinate = schema.get_gps_dest_latitude_property()

    assert isinstance(color_space, IntegerType)
    assert color_space is not raw_integer
    assert color_space.get_value() == 9
    assert isinstance(altitude, RationalType)
    assert altitude is not raw_rational
    assert altitude.as_fraction() == Fraction(33, 2)
    assert isinstance(coordinate, GPSCoordinateType)
    assert coordinate is not raw_coordinate
    assert coordinate.parse() == (48, 51.0, 30.0, "N")
