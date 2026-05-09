from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.xmpbox import DateType, ExifSchema, IntegerType, TextType, XMPMetadata
from pypdfbox.xmpbox.type import AbstractSimpleProperty, GPSCoordinateType, RationalType


def _exif() -> ExifSchema:
    return ExifSchema(XMPMetadata.create_xmp_metadata())


class _NonStringSimpleProperty(AbstractSimpleProperty):
    def set_value(self, value: Any) -> None:
        self._value = value

    def get_string_value(self) -> Any:
        return self._value

    def get_value(self) -> Any:
        return self._value


@pytest.mark.parametrize(
    ("getter", "setter", "typed_getter", "typed_setter"),
    [
        (
            "get_exif_version",
            "set_exif_version",
            "get_exif_version_property",
            "set_exif_version_property",
        ),
        (
            "get_flashpix_version",
            "set_flashpix_version",
            "get_flashpix_version_property",
            "set_flashpix_version_property",
        ),
        (
            "get_related_sound_file",
            "set_related_sound_file",
            "get_related_sound_file_property",
            "set_related_sound_file_property",
        ),
        (
            "get_spectral_sensitivity",
            "set_spectral_sensitivity",
            "get_spectral_sensitivity_property",
            "set_spectral_sensitivity_property",
        ),
        (
            "get_image_unique_id",
            "set_image_unique_id",
            "get_image_unique_id_property",
            "set_image_unique_id_property",
        ),
        (
            "get_gps_version_id",
            "set_gps_version_id",
            "get_gps_version_id_property",
            "set_gps_version_id_property",
        ),
        (
            "get_gps_satellites",
            "set_gps_satellites",
            "get_gps_satellites_property",
            "set_gps_satellites_property",
        ),
        (
            "get_gps_status",
            "set_gps_status",
            "get_gps_status_property",
            "set_gps_status_property",
        ),
        (
            "get_gps_measure_mode",
            "set_gps_measure_mode",
            "get_gps_measure_mode_property",
            "set_gps_measure_mode_property",
        ),
        (
            "get_gps_map_datum",
            "set_gps_map_datum",
            "get_gps_map_datum_property",
            "set_gps_map_datum_property",
        ),
        (
            "get_gps_speed_ref",
            "set_gps_speed_ref",
            "get_gps_speed_ref_property",
            "set_gps_speed_ref_property",
        ),
        (
            "get_gps_track_ref",
            "set_gps_track_ref",
            "get_gps_track_ref_property",
            "set_gps_track_ref_property",
        ),
        (
            "get_gps_img_direction_ref",
            "set_gps_img_direction_ref",
            "get_gps_img_direction_ref_property",
            "set_gps_img_direction_ref_property",
        ),
        (
            "get_gps_dest_bearing_ref",
            "set_gps_dest_bearing_ref",
            "get_gps_dest_bearing_ref_property",
            "set_gps_dest_bearing_ref_property",
        ),
        (
            "get_gps_dest_distance_ref",
            "set_gps_dest_distance_ref",
            "get_gps_dest_distance_ref_property",
            "set_gps_dest_distance_ref_property",
        ),
        (
            "get_gps_processing_method",
            "set_gps_processing_method",
            "get_gps_processing_method_property",
            "set_gps_processing_method_property",
        ),
        (
            "get_gps_area_information",
            "set_gps_area_information",
            "get_gps_area_information_property",
            "set_gps_area_information_property",
        ),
    ],
)
def test_wave390_text_property_accessors_share_simple_storage(
    getter: str, setter: str, typed_getter: str, typed_setter: str
) -> None:
    schema = _exif()
    metadata = schema.get_metadata()

    getattr(schema, setter)("raw-text")
    fabricated = getattr(schema, typed_getter)()
    assert isinstance(fabricated, TextType)
    assert fabricated.get_string_value() == "raw-text"

    prop = TextType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "typed")
    getattr(schema, typed_setter)(prop)
    assert getattr(schema, typed_getter)() is prop
    assert prop.get_property_name() != "tmp"
    assert getattr(schema, getter)() == "typed"

    getattr(schema, typed_setter)(None)
    assert getattr(schema, getter)() is None
    assert getattr(schema, typed_getter)() is None


@pytest.mark.parametrize(
    ("getter", "setter", "typed_getter", "typed_setter"),
    [
        (
            "get_color_space",
            "set_color_space",
            "get_color_space_property",
            "set_color_space_property",
        ),
        (
            "get_pixel_x_dimension",
            "set_pixel_x_dimension",
            "get_pixel_x_dimension_property",
            "set_pixel_x_dimension_property",
        ),
        (
            "get_pixel_y_dimension",
            "set_pixel_y_dimension",
            "get_pixel_y_dimension_property",
            "set_pixel_y_dimension_property",
        ),
        (
            "get_exposure_program",
            "set_exposure_program",
            "get_exposure_program_property",
            "set_exposure_program_property",
        ),
        (
            "get_metering_mode",
            "set_metering_mode",
            "get_metering_mode_property",
            "set_metering_mode_property",
        ),
        (
            "get_light_source",
            "set_light_source",
            "get_light_source_property",
            "set_light_source_property",
        ),
        (
            "get_focal_plane_resolution_unit",
            "set_focal_plane_resolution_unit",
            "get_focal_plane_resolution_unit_property",
            "set_focal_plane_resolution_unit_property",
        ),
        (
            "get_sensing_method",
            "set_sensing_method",
            "get_sensing_method_property",
            "set_sensing_method_property",
        ),
        (
            "get_file_source",
            "set_file_source",
            "get_file_source_property",
            "set_file_source_property",
        ),
        (
            "get_scene_type",
            "set_scene_type",
            "get_scene_type_property",
            "set_scene_type_property",
        ),
        (
            "get_custom_rendered",
            "set_custom_rendered",
            "get_custom_rendered_property",
            "set_custom_rendered_property",
        ),
        (
            "get_white_balance",
            "set_white_balance",
            "get_white_balance_property",
            "set_white_balance_property",
        ),
        (
            "get_exposure_mode",
            "set_exposure_mode",
            "get_exposure_mode_property",
            "set_exposure_mode_property",
        ),
        (
            "get_focal_length_in_35mm_film",
            "set_focal_length_in_35mm_film",
            "get_focal_length_in_35mm_film_property",
            "set_focal_length_in_35mm_film_property",
        ),
        (
            "get_scene_capture_type",
            "set_scene_capture_type",
            "get_scene_capture_type_property",
            "set_scene_capture_type_property",
        ),
        (
            "get_gain_control",
            "set_gain_control",
            "get_gain_control_property",
            "set_gain_control_property",
        ),
        ("get_contrast", "set_contrast", "get_contrast_property", "set_contrast_property"),
        (
            "get_saturation",
            "set_saturation",
            "get_saturation_property",
            "set_saturation_property",
        ),
        (
            "get_sharpness",
            "set_sharpness",
            "get_sharpness_property",
            "set_sharpness_property",
        ),
        (
            "get_subject_distance_range",
            "set_subject_distance_range",
            "get_subject_distance_range_property",
            "set_subject_distance_range_property",
        ),
        (
            "get_gps_altitude_ref",
            "set_gps_altitude_ref",
            "get_gps_altitude_ref_property",
            "set_gps_altitude_ref_property",
        ),
        (
            "get_gps_differential",
            "set_gps_differential",
            "get_gps_differential_property",
            "set_gps_differential_property",
        ),
    ],
)
def test_wave390_integer_property_accessors_share_simple_storage(
    getter: str, setter: str, typed_getter: str, typed_setter: str
) -> None:
    schema = _exif()
    metadata = schema.get_metadata()

    getattr(schema, setter)("42")
    assert getattr(schema, getter)() == 42
    fabricated = getattr(schema, typed_getter)()
    assert isinstance(fabricated, IntegerType)
    assert fabricated.get_value() == 42

    prop = IntegerType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 7)
    getattr(schema, typed_setter)(prop)
    assert getattr(schema, typed_getter)() is prop
    assert prop.get_property_name() != "tmp"
    assert getattr(schema, getter)() == 7

    getattr(schema, typed_setter)(None)
    assert getattr(schema, getter)() is None
    assert getattr(schema, typed_getter)() is None


@pytest.mark.parametrize(
    ("getter", "setter", "typed_getter", "typed_setter"),
    [
        (
            "get_date_time_original",
            "set_date_time_original",
            "get_date_time_original_property",
            "set_date_time_original_property",
        ),
        (
            "get_date_time_digitized",
            "set_date_time_digitized",
            "get_date_time_digitized_property",
            "set_date_time_digitized_property",
        ),
        (
            "get_gps_time_stamp",
            "set_gps_time_stamp",
            "get_gps_time_stamp_property",
            "set_gps_time_stamp_property",
        ),
    ],
)
def test_wave390_date_property_accessors_share_simple_storage(
    getter: str, setter: str, typed_getter: str, typed_setter: str
) -> None:
    schema = _exif()
    metadata = schema.get_metadata()

    getattr(schema, setter)("2026-05-08T12:34:56Z")
    fabricated = getattr(schema, typed_getter)()
    assert isinstance(fabricated, DateType)
    assert fabricated.get_string_value() == "2026-05-08T12:34:56+00:00"

    prop = DateType(
        metadata,
        schema.get_namespace(),
        schema.get_prefix(),
        "tmp",
        "2026-05-08T01:02:03Z",
    )
    getattr(schema, typed_setter)(prop)
    assert getattr(schema, typed_getter)() is prop
    assert prop.get_property_name() != "tmp"
    assert getattr(schema, getter)() == "2026-05-08T01:02:03+00:00"

    getattr(schema, typed_setter)(None)
    assert getattr(schema, getter)() is None


def test_wave390_integer_getter_uses_generic_text_fallback_for_sequences() -> None:
    schema = _exif()

    schema.set_property(ExifSchema.COLOR_SPACE, 23)
    assert schema.get_color_space() == 23

    schema.set_property(ExifSchema.COLOR_SPACE, [" 12 "])
    assert schema.get_color_space() == 12

    schema.set_property(ExifSchema.COLOR_SPACE, ["not-an-int"])
    assert schema.get_color_space() is None

    schema.set_property(ExifSchema.COLOR_SPACE, object())
    assert schema.get_color_space() is None


def test_wave390_non_string_simple_properties_are_ignored_by_string_getters() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    raw = _NonStringSimpleProperty(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 123
    )

    schema.set_property(ExifSchema.COLOR_SPACE, raw)
    assert schema.get_color_space() is None

    schema.set_property(ExifSchema.IMAGE_UNIQUE_ID, raw)
    assert schema.get_image_unique_id() is None
    assert schema.get_image_unique_id_property() is None

    schema.set_property(ExifSchema.FOCAL_LENGTH, raw)
    assert schema.get_focal_length() is None
    assert schema.get_focal_length_property() is None

    schema.set_property(ExifSchema.GPS_LATITUDE, raw)
    assert schema.get_gps_latitude() is None
    assert schema.get_gps_latitude_property() is None


def test_wave390_typed_getters_reject_invalid_raw_strings() -> None:
    schema = _exif()

    schema.set_text_property_value(ExifSchema.GPS_TIME_STAMP, "")
    schema.set_property(ExifSchema.GPS_ALTITUDE, 7)
    schema.set_property(ExifSchema.GPS_LATITUDE, 7)

    assert schema.get_gps_time_stamp_property() is None
    assert schema.get_gps_altitude() is None
    assert schema.get_gps_altitude_property() is None
    assert schema.get_gps_latitude() is None
    assert schema.get_gps_latitude_property() is None


def test_wave390_typed_setters_accept_subclasses() -> None:
    schema = _exif()
    metadata = schema.get_metadata()

    rational = RationalType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "3/4"
    )
    coordinate = GPSCoordinateType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "1,2,3N"
    )

    schema.set_gps_dop_property(rational)
    schema.set_gps_dest_longitude_property(coordinate)

    assert schema.get_gps_dop_property() is rational
    assert schema.get_gps_dop() == "3/4"
    assert schema.get_gps_dest_longitude_property() is coordinate
    assert schema.get_gps_dest_longitude() == "1,2,3N"
