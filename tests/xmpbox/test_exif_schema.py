from __future__ import annotations

from fractions import Fraction

import pytest

from pypdfbox.xmpbox import (
    DateType,
    DomXmpParser,
    ExifSchema,
    GPSCoordinateType,
    IntegerType,
    LangAlt,
    RationalType,
    TextType,
    XMPMetadata,
)


def _exif() -> ExifSchema:
    return ExifSchema(XMPMetadata.create_xmp_metadata())


def test_namespace_and_prefix_match_upstream() -> None:
    schema = _exif()
    assert ExifSchema.NAMESPACE == "http://ns.adobe.com/exif/1.0/"
    assert ExifSchema.PREFERRED_PREFIX == "exif"
    assert schema.get_namespace() == "http://ns.adobe.com/exif/1.0/"
    assert schema.get_prefix() == "exif"


def test_local_name_constants_match_upstream() -> None:
    # Verify each upstream constant is mirrored verbatim.
    assert ExifSchema.USER_COMMENT == "UserComment"
    assert ExifSchema.EXIF_VERSION == "ExifVersion"
    assert ExifSchema.FLASH_PIX_VERSION == "FlashpixVersion"
    assert ExifSchema.COLOR_SPACE == "ColorSpace"
    assert ExifSchema.COMPONENTS_CONFIGURATION == "ComponentsConfiguration"
    assert ExifSchema.COMPRESSED_BPP == "CompressedBitsPerPixel"
    assert ExifSchema.PIXEL_X_DIMENSION == "PixelXDimension"
    assert ExifSchema.PIXEL_Y_DIMENSION == "PixelYDimension"
    assert ExifSchema.RELATED_SOUND_FILE == "RelatedSoundFile"
    assert ExifSchema.DATE_TIME_ORIGINAL == "DateTimeOriginal"
    assert ExifSchema.DATE_TIME_DIGITIZED == "DateTimeDigitized"
    assert ExifSchema.EXPOSURE_TIME == "ExposureTime"
    assert ExifSchema.F_NUMBER == "FNumber"
    assert ExifSchema.EXPOSURE_PROGRAM == "ExposureProgram"
    assert ExifSchema.SPECTRAL_SENSITIVITY == "SpectralSensitivity"
    assert ExifSchema.ISO_SPEED_RATINGS == "ISOSpeedRatings"
    assert ExifSchema.SHUTTER_SPEED_VALUE == "ShutterSpeedValue"
    assert ExifSchema.APERTURE_VALUE == "ApertureValue"
    assert ExifSchema.BRIGHTNESS_VALUE == "BrightnessValue"
    assert ExifSchema.EXPOSURE_BIAS_VALUE == "ExposureBiasValue"
    assert ExifSchema.MAX_APERTURE_VALUE == "MaxApertureValue"
    assert ExifSchema.SUBJECT_DISTANCE == "SubjectDistance"
    assert ExifSchema.METERING_MODE == "MeteringMode"
    assert ExifSchema.LIGHT_SOURCE == "LightSource"
    assert ExifSchema.FLASH_ENERGY == "FlashEnergy"
    assert ExifSchema.FOCAL_LENGTH == "FocalLength"
    assert ExifSchema.FOCAL_PLANE_XRESOLUTION == "FocalPlaneXResolution"
    assert ExifSchema.FOCAL_PLANE_YRESOLUTION == "FocalPlaneYResolution"
    assert ExifSchema.SUBJECT_AREA == "SubjectArea"
    assert ExifSchema.FOCAL_PLANE_RESOLUTION_UNIT == "FocalPlaneResolutionUnit"
    assert ExifSchema.SUBJECT_LOCATION == "SubjectLocation"
    assert ExifSchema.EXPOSURE_INDEX == "ExposureIndex"
    assert ExifSchema.SENSING_METHOD == "SensingMethod"
    assert ExifSchema.FILE_SOURCE == "FileSource"
    assert ExifSchema.SCENE_TYPE == "SceneType"
    assert ExifSchema.CUSTOM_RENDERED == "CustomRendered"
    assert ExifSchema.WHITE_BALANCE == "WhiteBalance"
    assert ExifSchema.EXPOSURE_MODE == "ExposureMode"
    assert ExifSchema.DIGITAL_ZOOM_RATIO == "DigitalZoomRatio"
    assert ExifSchema.FOCAL_LENGTH_IN_3_5MM_FILM == "FocalLengthIn35mmFilm"
    assert ExifSchema.SCENE_CAPTURE_TYPE == "SceneCaptureType"
    assert ExifSchema.GAIN_CONTROL == "GainControl"
    assert ExifSchema.CONTRAST == "Contrast"
    assert ExifSchema.SATURATION == "Saturation"
    assert ExifSchema.SHARPNESS == "Sharpness"
    assert ExifSchema.SUBJECT_DISTANCE_RANGE == "SubjectDistanceRange"
    assert ExifSchema.IMAGE_UNIQUE_ID == "ImageUniqueID"
    assert ExifSchema.GPSVERSION_ID == "GPSVersionID"
    assert ExifSchema.GPS_SATELLITES == "GPSSatellites"
    assert ExifSchema.GPS_STATUS == "GPSStatus"
    assert ExifSchema.GPS_MEASURE_MODE == "GPSMeasureMode"
    assert ExifSchema.GPS_MAP_DATUM == "GPSMapDatum"
    assert ExifSchema.GPS_SPEED_REF == "GPSSpeedRef"
    assert ExifSchema.GPS_TRACK_REF == "GPSTrackRef"
    assert ExifSchema.GPS_IMG_DIRECTION_REF == "GPSImgDirectionRef"
    assert ExifSchema.GPS_DEST_BEARING_REF == "GPSDestBearingRef"
    assert ExifSchema.GPS_DEST_DISTANCE_REF == "GPSDestDistanceRef"
    assert ExifSchema.GPS_PROCESSING_METHOD == "GPSProcessingMethod"
    assert ExifSchema.GPS_AREA_INFORMATION == "GPSAreaInformation"
    assert ExifSchema.GPS_ALTITUDE == "GPSAltitude"
    assert ExifSchema.GPS_DOP == "GPSDOP"
    assert ExifSchema.GPS_SPEED == "GPSSpeed"
    assert ExifSchema.GPS_TRACK == "GPSTrack"
    assert ExifSchema.GPS_IMG_DIRECTION == "GPSImgDirection"
    assert ExifSchema.GPS_DEST_BEARING == "GPSDestBearing"
    assert ExifSchema.GPS_DEST_DISTANCE == "GPSDestDistance"
    assert ExifSchema.GPS_ALTITUDE_REF == "GPSAltitudeRef"
    assert ExifSchema.GPS_DIFFERENTIAL == "GPSDifferential"
    assert ExifSchema.GPS_TIME_STAMP == "GPSTimeStamp"
    assert ExifSchema.OECF == "OECF"
    assert ExifSchema.SPATIAL_FREQUENCY_RESPONSE == "SpatialFrequencyResponse"
    assert ExifSchema.GPS_LATITUDE == "GPSLatitude"
    assert ExifSchema.GPS_LONGITUDE == "GPSLongitude"
    assert ExifSchema.GPS_DEST_LATITUDE == "GPSDestLatitude"
    assert ExifSchema.GPS_DEST_LONGITUDE == "GPSDestLongitude"
    assert ExifSchema.CFA_PATTERN == "CFAPattern"
    assert ExifSchema.FLASH == "Flash"
    assert ExifSchema.CFA_PATTERN_TYPE == "CFAPatternType"
    assert ExifSchema.DEVICE_SETTING_DESCRIPTION == "DeviceSettingDescription"


def test_default_accessors_return_none() -> None:
    schema = _exif()
    # LangAlt
    assert schema.get_user_comment() is None
    assert schema.get_user_comment_languages() is None
    # Text
    assert schema.get_exif_version() is None
    assert schema.get_flashpix_version() is None
    assert schema.get_related_sound_file() is None
    assert schema.get_spectral_sensitivity() is None
    assert schema.get_image_unique_id() is None
    assert schema.get_gps_version_id() is None
    assert schema.get_gps_satellites() is None
    assert schema.get_gps_status() is None
    assert schema.get_gps_measure_mode() is None
    assert schema.get_gps_map_datum() is None
    assert schema.get_gps_speed_ref() is None
    assert schema.get_gps_track_ref() is None
    assert schema.get_gps_img_direction_ref() is None
    assert schema.get_gps_dest_bearing_ref() is None
    assert schema.get_gps_dest_distance_ref() is None
    assert schema.get_gps_processing_method() is None
    assert schema.get_gps_area_information() is None
    # Date
    assert schema.get_date_time_original() is None
    assert schema.get_date_time_digitized() is None
    assert schema.get_gps_time_stamp() is None
    # Integer
    assert schema.get_color_space() is None
    assert schema.get_pixel_x_dimension() is None
    assert schema.get_pixel_y_dimension() is None
    assert schema.get_exposure_program() is None
    assert schema.get_metering_mode() is None
    assert schema.get_light_source() is None
    assert schema.get_focal_plane_resolution_unit() is None
    assert schema.get_sensing_method() is None
    assert schema.get_file_source() is None
    assert schema.get_scene_type() is None
    assert schema.get_custom_rendered() is None
    assert schema.get_white_balance() is None
    assert schema.get_exposure_mode() is None
    assert schema.get_focal_length_in_35mm_film() is None
    assert schema.get_scene_capture_type() is None
    assert schema.get_gain_control() is None
    assert schema.get_contrast() is None
    assert schema.get_saturation() is None
    assert schema.get_sharpness() is None
    assert schema.get_subject_distance_range() is None
    assert schema.get_gps_altitude_ref() is None
    assert schema.get_gps_differential() is None
    # Seq<Integer>
    assert schema.get_components_configuration() is None
    assert schema.get_iso_speed_ratings() is None
    assert schema.get_subject_area() is None
    assert schema.get_subject_location() is None


def test_text_property_round_trip_for_each_simple_text_accessor() -> None:
    schema = _exif()
    schema.set_exif_version("0220")
    schema.set_flashpix_version("0100")
    schema.set_related_sound_file("voice.wav")
    schema.set_spectral_sensitivity("ISO 100/21°")
    schema.set_image_unique_id("9876ABCD9876ABCD")
    schema.set_gps_version_id("2.2.0.0")
    schema.set_gps_satellites("12 of 24")
    schema.set_gps_status("A")
    schema.set_gps_measure_mode("3")
    schema.set_gps_map_datum("WGS-84")
    schema.set_gps_speed_ref("K")
    schema.set_gps_track_ref("T")
    schema.set_gps_img_direction_ref("M")
    schema.set_gps_dest_bearing_ref("T")
    schema.set_gps_dest_distance_ref("K")
    schema.set_gps_processing_method("GPS")
    schema.set_gps_area_information("Eiffel Tower")
    schema.set_date_time_original("2026-04-27T12:00:00Z")
    schema.set_date_time_digitized("2026-04-27T12:00:01Z")
    schema.set_gps_time_stamp("2026-04-27T12:00:02Z")

    assert schema.get_exif_version() == "0220"
    assert schema.get_flashpix_version() == "0100"
    assert schema.get_related_sound_file() == "voice.wav"
    assert schema.get_spectral_sensitivity() == "ISO 100/21°"
    assert schema.get_image_unique_id() == "9876ABCD9876ABCD"
    assert schema.get_gps_version_id() == "2.2.0.0"
    assert schema.get_gps_satellites() == "12 of 24"
    assert schema.get_gps_status() == "A"
    assert schema.get_gps_measure_mode() == "3"
    assert schema.get_gps_map_datum() == "WGS-84"
    assert schema.get_gps_speed_ref() == "K"
    assert schema.get_gps_track_ref() == "T"
    assert schema.get_gps_img_direction_ref() == "M"
    assert schema.get_gps_dest_bearing_ref() == "T"
    assert schema.get_gps_dest_distance_ref() == "K"
    assert schema.get_gps_processing_method() == "GPS"
    assert schema.get_gps_area_information() == "Eiffel Tower"
    assert schema.get_date_time_original() == "2026-04-27T12:00:00Z"
    assert schema.get_date_time_digitized() == "2026-04-27T12:00:01Z"
    assert schema.get_gps_time_stamp() == "2026-04-27T12:00:02Z"

    # set_*(None) clears the property.
    schema.set_exif_version(None)
    schema.set_flashpix_version(None)
    schema.set_related_sound_file(None)
    schema.set_spectral_sensitivity(None)
    schema.set_image_unique_id(None)
    schema.set_gps_version_id(None)
    schema.set_gps_satellites(None)
    schema.set_gps_status(None)
    schema.set_gps_measure_mode(None)
    schema.set_gps_map_datum(None)
    schema.set_gps_speed_ref(None)
    schema.set_gps_track_ref(None)
    schema.set_gps_img_direction_ref(None)
    schema.set_gps_dest_bearing_ref(None)
    schema.set_gps_dest_distance_ref(None)
    schema.set_gps_processing_method(None)
    schema.set_gps_area_information(None)
    schema.set_date_time_original(None)
    schema.set_date_time_digitized(None)
    schema.set_gps_time_stamp(None)

    assert schema.get_exif_version() is None
    assert schema.get_image_unique_id() is None
    assert schema.get_gps_time_stamp() is None


def test_user_comment_lang_alt_round_trip() -> None:
    schema = _exif()
    schema.set_user_comment("Default comment")
    assert schema.get_user_comment() == "Default comment"
    schema.add_user_comment("fr", "Commentaire")
    assert schema.get_user_comment("fr") == "Commentaire"
    langs = schema.get_user_comment_languages() or []
    assert "fr" in langs


def test_color_space_int_round_trip() -> None:
    schema = _exif()
    schema.set_color_space(1)
    assert schema.get_color_space() == 1
    # IntegerType serialises as the decimal string in upstream.
    assert schema.get_unqualified_text_property_value(ExifSchema.COLOR_SPACE) == "1"
    schema.set_color_space(None)
    assert schema.get_color_space() is None


def test_color_space_accepts_string_form_for_parser_round_trip() -> None:
    schema = _exif()
    # Parser stores attribute-form values as raw strings.
    schema.set_text_property_value(ExifSchema.COLOR_SPACE, "65535")
    assert schema.get_color_space() == 65535
    schema.set_text_property_value(ExifSchema.COLOR_SPACE, "junk")
    assert schema.get_color_space() is None


def test_pixel_dimensions_int_round_trip() -> None:
    schema = _exif()
    schema.set_pixel_x_dimension(4032)
    schema.set_pixel_y_dimension(3024)
    assert schema.get_pixel_x_dimension() == 4032
    assert schema.get_pixel_y_dimension() == 3024


def test_assorted_integer_accessors_round_trip() -> None:
    schema = _exif()
    schema.set_exposure_program(2)
    schema.set_metering_mode(5)
    schema.set_light_source(1)
    schema.set_focal_plane_resolution_unit(3)
    schema.set_sensing_method(2)
    schema.set_file_source(3)
    schema.set_scene_type(1)
    schema.set_custom_rendered(0)
    schema.set_white_balance(0)
    schema.set_exposure_mode(0)
    schema.set_focal_length_in_35mm_film(50)
    schema.set_scene_capture_type(0)
    schema.set_gain_control(0)
    schema.set_contrast(0)
    schema.set_saturation(0)
    schema.set_sharpness(0)
    schema.set_subject_distance_range(0)
    schema.set_gps_altitude_ref(0)
    schema.set_gps_differential(0)

    assert schema.get_exposure_program() == 2
    assert schema.get_metering_mode() == 5
    assert schema.get_light_source() == 1
    assert schema.get_focal_plane_resolution_unit() == 3
    assert schema.get_sensing_method() == 2
    assert schema.get_file_source() == 3
    assert schema.get_scene_type() == 1
    assert schema.get_custom_rendered() == 0
    assert schema.get_white_balance() == 0
    assert schema.get_exposure_mode() == 0
    assert schema.get_focal_length_in_35mm_film() == 50
    assert schema.get_scene_capture_type() == 0
    assert schema.get_gain_control() == 0
    assert schema.get_contrast() == 0
    assert schema.get_saturation() == 0
    assert schema.get_sharpness() == 0
    assert schema.get_subject_distance_range() == 0
    assert schema.get_gps_altitude_ref() == 0
    assert schema.get_gps_differential() == 0


def test_components_configuration_seq_round_trip() -> None:
    schema = _exif()
    schema.add_components_configuration(1)
    schema.add_components_configuration(2)
    schema.add_components_configuration(3)
    schema.add_components_configuration(0)
    assert schema.get_components_configuration() == ["1", "2", "3", "0"]


def test_iso_speed_ratings_seq_round_trip() -> None:
    schema = _exif()
    schema.add_iso_speed_ratings(100)
    schema.add_iso_speed_ratings(200)
    assert schema.get_iso_speed_ratings() == ["100", "200"]


def test_subject_area_seq_round_trip() -> None:
    schema = _exif()
    schema.add_subject_area(2016)
    schema.add_subject_area(1512)
    schema.add_subject_area(120)
    assert schema.get_subject_area() == ["2016", "1512", "120"]


def test_subject_location_seq_round_trip() -> None:
    schema = _exif()
    schema.add_subject_location(2016)
    schema.add_subject_location(1512)
    assert schema.get_subject_location() == ["2016", "1512"]


def test_xmp_metadata_add_exif_schema_idempotent() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    assert metadata.get_exif_schema() is None
    schema = metadata.add_exif_schema()
    assert isinstance(schema, ExifSchema)
    # Idempotent — repeat add returns the same instance.
    assert metadata.add_exif_schema() is schema
    assert metadata.get_exif_schema() is schema


def test_create_and_add_exif_schema_alias() -> None:
    metadata = XMPMetadata.create_xmp_metadata()
    schema = metadata.create_and_add_exif_schema()
    assert isinstance(schema, ExifSchema)
    # Alias is also idempotent through add_exif_schema.
    assert metadata.create_and_add_exif_schema() is schema


def test_dom_parser_dispatches_attribute_form_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:exif='http://ns.adobe.com/exif/1.0/'"
        b" exif:ExifVersion='0220'"
        b" exif:FlashpixVersion='0100'"
        b" exif:ColorSpace='1'"
        b" exif:PixelXDimension='4032'"
        b" exif:PixelYDimension='3024'"
        b" exif:DateTimeOriginal='2026-04-27T12:00:00Z'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(ExifSchema)
    assert isinstance(schema, ExifSchema)
    assert schema.get_exif_version() == "0220"
    assert schema.get_flashpix_version() == "0100"
    assert schema.get_color_space() == 1
    assert schema.get_pixel_x_dimension() == 4032
    assert schema.get_pixel_y_dimension() == 3024
    assert schema.get_date_time_original() == "2026-04-27T12:00:00Z"


def test_dom_parser_dispatches_iso_speed_ratings_seq_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:exif='http://ns.adobe.com/exif/1.0/'>"
        b"<exif:ISOSpeedRatings>"
        b"<rdf:Seq>"
        b"<rdf:li>100</rdf:li>"
        b"<rdf:li>200</rdf:li>"
        b"</rdf:Seq>"
        b"</exif:ISOSpeedRatings>"
        b"</rdf:Description>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(ExifSchema)
    assert isinstance(schema, ExifSchema)
    assert schema.get_iso_speed_ratings() == ["100", "200"]


def test_dom_parser_get_namespace_table_includes_exif() -> None:
    table = DomXmpParser().get_namespace_table()
    assert table.get("exif") == "http://ns.adobe.com/exif/1.0/"


# --- Typed *_property accessors --------------------------------------


def _meta() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_text_typed_property_round_trip_with_caching() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    prop = TextType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "0220")
    schema.set_exif_version_property(prop)
    # Typed setter caches the originating instance.
    assert schema.get_exif_version_property() is prop
    # String-form getter sees the same value.
    assert schema.get_exif_version() == "0220"
    # Setting None clears the property.
    schema.set_exif_version_property(None)
    assert schema.get_exif_version_property() is None
    assert schema.get_exif_version() is None


def test_text_typed_getter_fabricates_wrapper_from_raw_string() -> None:
    schema = _exif()
    schema.set_image_unique_id("9876ABCD")
    typed = schema.get_image_unique_id_property()
    assert isinstance(typed, TextType)
    assert typed.get_string_value() == "9876ABCD"


def test_integer_typed_property_round_trip() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    prop = IntegerType(metadata, schema.get_namespace(), schema.get_prefix(), "tmp", 1)
    schema.set_color_space_property(prop)
    assert schema.get_color_space_property() is prop
    assert schema.get_color_space() == 1
    # Fabricates from raw int when only the simple-form setter was called.
    schema.set_pixel_x_dimension(4032)
    typed = schema.get_pixel_x_dimension_property()
    assert isinstance(typed, IntegerType)
    assert typed.get_value() == 4032


def test_date_typed_property_round_trip() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    prop = DateType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "2026-04-27T12:00:00Z"
    )
    schema.set_date_time_original_property(prop)
    assert schema.get_date_time_original_property() is prop
    # Z is canonicalized to +00:00 on round-trip via datetime.isoformat()
    assert schema.get_date_time_original() == "2026-04-27T12:00:00+00:00"


def test_rational_property_string_round_trip() -> None:
    schema = _exif()
    schema.set_exposure_time("1/250")
    assert schema.get_exposure_time() == "1/250"
    assert schema.get_unqualified_text_property_value(ExifSchema.EXPOSURE_TIME) == "1/250"
    schema.set_exposure_time(None)
    assert schema.get_exposure_time() is None


def test_rational_typed_property_round_trip_with_caching() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    rt = RationalType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "1/8"
    )
    schema.set_f_number_property(rt)
    assert schema.get_f_number_property() is rt
    assert schema.get_f_number() == "1/8"
    typed = schema.get_f_number_property()
    assert isinstance(typed, RationalType)
    assert typed.as_fraction() == Fraction(1, 8)


def test_rational_typed_getter_fabricates_wrapper_from_raw_string() -> None:
    schema = _exif()
    schema.set_focal_length("50/1")
    typed = schema.get_focal_length_property()
    assert isinstance(typed, RationalType)
    assert typed.as_fraction() == Fraction(50, 1)


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_compressed_bits_per_pixel", "set_compressed_bits_per_pixel"),
        ("get_exposure_time", "set_exposure_time"),
        ("get_f_number", "set_f_number"),
        ("get_shutter_speed_value", "set_shutter_speed_value"),
        ("get_aperture_value", "set_aperture_value"),
        ("get_brightness_value", "set_brightness_value"),
        ("get_exposure_bias_value", "set_exposure_bias_value"),
        ("get_max_aperture_value", "set_max_aperture_value"),
        ("get_subject_distance", "set_subject_distance"),
        ("get_flash_energy", "set_flash_energy"),
        ("get_focal_length", "set_focal_length"),
        ("get_focal_plane_x_resolution", "set_focal_plane_x_resolution"),
        ("get_focal_plane_y_resolution", "set_focal_plane_y_resolution"),
        ("get_exposure_index", "set_exposure_index"),
        ("get_digital_zoom_ratio", "set_digital_zoom_ratio"),
        ("get_gps_altitude", "set_gps_altitude"),
        ("get_gps_dop", "set_gps_dop"),
        ("get_gps_speed", "set_gps_speed"),
        ("get_gps_track", "set_gps_track"),
        ("get_gps_img_direction", "set_gps_img_direction"),
        ("get_gps_dest_bearing", "set_gps_dest_bearing"),
        ("get_gps_dest_distance", "set_gps_dest_distance"),
    ],
)
def test_every_rational_string_accessor_round_trips(getter: str, setter: str) -> None:
    schema = _exif()
    assert getattr(schema, getter)() is None
    getattr(schema, setter)("3/2")
    assert getattr(schema, getter)() == "3/2"
    getattr(schema, setter)(None)
    assert getattr(schema, getter)() is None


@pytest.mark.parametrize(
    ("typed_getter", "typed_setter"),
    [
        ("get_compressed_bits_per_pixel_property", "set_compressed_bits_per_pixel_property"),
        ("get_exposure_time_property", "set_exposure_time_property"),
        ("get_f_number_property", "set_f_number_property"),
        ("get_shutter_speed_value_property", "set_shutter_speed_value_property"),
        ("get_aperture_value_property", "set_aperture_value_property"),
        ("get_brightness_value_property", "set_brightness_value_property"),
        ("get_exposure_bias_value_property", "set_exposure_bias_value_property"),
        ("get_max_aperture_value_property", "set_max_aperture_value_property"),
        ("get_subject_distance_property", "set_subject_distance_property"),
        ("get_flash_energy_property", "set_flash_energy_property"),
        ("get_focal_length_property", "set_focal_length_property"),
        ("get_focal_plane_x_resolution_property", "set_focal_plane_x_resolution_property"),
        ("get_focal_plane_y_resolution_property", "set_focal_plane_y_resolution_property"),
        ("get_exposure_index_property", "set_exposure_index_property"),
        ("get_digital_zoom_ratio_property", "set_digital_zoom_ratio_property"),
        ("get_gps_altitude_property", "set_gps_altitude_property"),
        ("get_gps_dop_property", "set_gps_dop_property"),
        ("get_gps_speed_property", "set_gps_speed_property"),
        ("get_gps_track_property", "set_gps_track_property"),
        ("get_gps_img_direction_property", "set_gps_img_direction_property"),
        ("get_gps_dest_bearing_property", "set_gps_dest_bearing_property"),
        ("get_gps_dest_distance_property", "set_gps_dest_distance_property"),
    ],
)
def test_every_rational_typed_accessor_round_trips(
    typed_getter: str, typed_setter: str
) -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    rt = RationalType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "7/16"
    )
    getattr(schema, typed_setter)(rt)
    assert getattr(schema, typed_getter)() is rt
    getattr(schema, typed_setter)(None)
    assert getattr(schema, typed_getter)() is None


# --- GPSCoordinate -----------------------------------------------------


def test_gps_coordinate_string_round_trip() -> None:
    schema = _exif()
    schema.set_gps_latitude("48,51,30N")
    schema.set_gps_longitude("2,17,40E")
    assert schema.get_gps_latitude() == "48,51,30N"
    assert schema.get_gps_longitude() == "2,17,40E"
    schema.set_gps_latitude(None)
    assert schema.get_gps_latitude() is None


def test_gps_coordinate_typed_property_round_trip_with_caching() -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    coord = GPSCoordinateType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "48,51,30N"
    )
    schema.set_gps_latitude_property(coord)
    # Cached identity preserved.
    assert schema.get_gps_latitude_property() is coord
    assert schema.get_gps_latitude() == "48,51,30N"
    # Parse helper splits into (D, M, S, hemi).
    parsed = coord.parse()
    assert parsed == (48, 51.0, 30.0, "N")


def test_gps_coordinate_typed_getter_fabricates_wrapper_from_raw_string() -> None:
    schema = _exif()
    schema.set_gps_dest_longitude("2,17.5W")
    typed = schema.get_gps_dest_longitude_property()
    assert isinstance(typed, GPSCoordinateType)
    parsed = typed.parse()
    assert parsed == (2, 17.5, 0.0, "W")


def test_gps_coordinate_format_helpers() -> None:
    assert GPSCoordinateType.format_dms(48, 51, 30, "N") == "48,51,30N"
    assert GPSCoordinateType.format_dm(48, 51.5, "N") == "48,51.5N"
    with pytest.raises(ValueError):
        GPSCoordinateType.format_dms(0, 0, 0, "X")


def test_gps_coordinate_parse_returns_none_for_garbage() -> None:
    metadata = _meta()
    coord = GPSCoordinateType(metadata, None, None, "tmp", "")
    assert coord.parse() is None
    coord = GPSCoordinateType(metadata, None, None, "tmp", "no-hemi")
    assert coord.parse() is None
    coord = GPSCoordinateType(metadata, None, None, "tmp", "48,51,xxN")
    assert coord.parse() is None


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_gps_latitude", "set_gps_latitude"),
        ("get_gps_longitude", "set_gps_longitude"),
        ("get_gps_dest_latitude", "set_gps_dest_latitude"),
        ("get_gps_dest_longitude", "set_gps_dest_longitude"),
    ],
)
def test_every_gps_coordinate_string_accessor_round_trips(
    getter: str, setter: str
) -> None:
    schema = _exif()
    assert getattr(schema, getter)() is None
    getattr(schema, setter)("0,0,0N")
    assert getattr(schema, getter)() == "0,0,0N"
    getattr(schema, setter)(None)
    assert getattr(schema, getter)() is None


@pytest.mark.parametrize(
    ("typed_getter", "typed_setter"),
    [
        ("get_gps_latitude_property", "set_gps_latitude_property"),
        ("get_gps_longitude_property", "set_gps_longitude_property"),
        ("get_gps_dest_latitude_property", "set_gps_dest_latitude_property"),
        ("get_gps_dest_longitude_property", "set_gps_dest_longitude_property"),
    ],
)
def test_every_gps_coordinate_typed_accessor_round_trips(
    typed_getter: str, typed_setter: str
) -> None:
    schema = _exif()
    metadata = schema.get_metadata()
    coord = GPSCoordinateType(
        metadata, schema.get_namespace(), schema.get_prefix(), "tmp", "1,2,3N"
    )
    getattr(schema, typed_setter)(coord)
    assert getattr(schema, typed_getter)() is coord
    getattr(schema, typed_setter)(None)
    assert getattr(schema, typed_getter)() is None


def test_dom_parser_dispatches_rational_attribute_form_onto_typed_schema() -> None:
    packet = (
        b"<?xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description rdf:about=''"
        b" xmlns:exif='http://ns.adobe.com/exif/1.0/'"
        b" exif:ExposureTime='1/250'"
        b" exif:FNumber='28/10'"
        b" exif:FocalLength='50/1'"
        b" exif:GPSAltitude='100/1'"
        b" exif:GPSLatitude='48,51,30N'"
        b" exif:GPSLongitude='2,17,40E'/>"
        b"</rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    metadata = DomXmpParser().parse(packet)
    schema = metadata.get_schema(ExifSchema)
    assert isinstance(schema, ExifSchema)
    assert schema.get_exposure_time() == "1/250"
    assert schema.get_f_number() == "28/10"
    assert schema.get_focal_length() == "50/1"
    assert schema.get_gps_altitude() == "100/1"
    assert schema.get_gps_latitude() == "48,51,30N"
    assert schema.get_gps_longitude() == "2,17,40E"
    # Typed accessors fabricate wrappers from the parser's raw strings.
    typed = schema.get_focal_length_property()
    assert isinstance(typed, RationalType)
    assert typed.as_fraction() == Fraction(50, 1)
    coord = schema.get_gps_latitude_property()
    assert isinstance(coord, GPSCoordinateType)
    assert coord.parse() == (48, 51.0, 30.0, "N")


def test_user_comment_property_returns_lang_alt() -> None:
    """Wave round-out: parity with upstream ``getUserCommentProperty``."""
    schema = _exif()
    assert schema.get_user_comment_property() is None
    schema.set_user_comment("hello")
    schema.add_user_comment("fr", "bonjour")
    la = schema.get_user_comment_property()
    assert isinstance(la, LangAlt)
    assert la.get_language_value("x-default") == "hello"
    assert la.get_language_value("fr") == "bonjour"
    children = la.get_all_properties()
    # x-default sorted first to match upstream reorganizeAltOrder.
    first_attr = children[0].get_attribute("xml:lang")
    assert first_attr is not None
    assert first_attr.get_value() == "x-default"


def test_user_comment_property_none_when_empty() -> None:
    schema = _exif()
    assert schema.get_user_comment_property() is None
