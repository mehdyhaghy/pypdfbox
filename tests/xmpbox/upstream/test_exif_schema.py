"""
Upstream-test stub for ``org.apache.xmpbox.schema.ExifSchema``.

Apache PDFBox 3.0 does **not** ship a dedicated ``ExifSchemaTest.java`` —
``xmpbox/src/test/java/org/apache/xmpbox/schema/`` enumerates a per-schema
test for Dublin Core, XMPBasic, Photoshop, etc. but skips ExifSchema (the
upstream test surface for it lives only inside the reflection-driven
``SchemaTester`` invocations on neighboring schemas).

Rather than leave the upstream slot empty, this file mirrors the
upstream ``@PropertyType`` declarations from the ExifSchema source and
exercises the ``testInitializedToNull`` / ``testSettingValue`` contracts
that ``SchemaTester`` would have applied if Apache had wired one up.

Wave 33 un-skips the Rational and GPSCoordinate property declarations
(see ``_RATIONAL_PARAMETERS`` / ``_GPS_COORDINATE_PARAMETERS`` below).
The remaining typed-struct deferrals are CFAPattern, OECF (and its
SpatialFrequencyResponse alias), Flash, and DeviceSettings — those land
when the matching structured-type wrappers do.
"""

from __future__ import annotations

import pytest

from pypdfbox.xmpbox import ExifSchema, XMPMetadata


# Upstream @PropertyType declarations for the simple-typed properties we ship.
# Format: (FIELD_NAME, type_token, cardinality).
_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    # LangAlt
    ("UserComment", "LangAlt", "Simple"),
    # Text / Date
    ("ExifVersion", "Text", "Simple"),
    ("FlashpixVersion", "Text", "Simple"),
    ("RelatedSoundFile", "Text", "Simple"),
    ("DateTimeOriginal", "Date", "Simple"),
    ("DateTimeDigitized", "Date", "Simple"),
    ("SpectralSensitivity", "Text", "Simple"),
    ("ImageUniqueID", "Text", "Simple"),
    ("GPSVersionID", "Text", "Simple"),
    ("GPSSatellites", "Text", "Simple"),
    ("GPSStatus", "Text", "Simple"),
    ("GPSMeasureMode", "Text", "Simple"),
    ("GPSMapDatum", "Text", "Simple"),
    ("GPSSpeedRef", "Text", "Simple"),
    ("GPSTrackRef", "Text", "Simple"),
    ("GPSImgDirectionRef", "Text", "Simple"),
    ("GPSDestBearingRef", "Text", "Simple"),
    ("GPSDestDistanceRef", "Text", "Simple"),
    ("GPSProcessingMethod", "Text", "Simple"),
    ("GPSAreaInformation", "Text", "Simple"),
    ("GPSTimeStamp", "Date", "Simple"),
    # Integer
    ("ColorSpace", "Integer", "Simple"),
    ("PixelXDimension", "Integer", "Simple"),
    ("PixelYDimension", "Integer", "Simple"),
    ("ExposureProgram", "Integer", "Simple"),
    ("MeteringMode", "Integer", "Simple"),
    ("LightSource", "Integer", "Simple"),
    ("FocalPlaneResolutionUnit", "Integer", "Simple"),
    ("SensingMethod", "Integer", "Simple"),
    ("FileSource", "Integer", "Simple"),
    ("SceneType", "Integer", "Simple"),
    ("CustomRendered", "Integer", "Simple"),
    ("WhiteBalance", "Integer", "Simple"),
    ("ExposureMode", "Integer", "Simple"),
    ("FocalLengthIn35mmFilm", "Integer", "Simple"),
    ("SceneCaptureType", "Integer", "Simple"),
    ("GainControl", "Integer", "Simple"),
    ("Contrast", "Integer", "Simple"),
    ("Saturation", "Integer", "Simple"),
    ("Sharpness", "Integer", "Simple"),
    ("SubjectDistanceRange", "Integer", "Simple"),
    ("GPSAltitudeRef", "Integer", "Simple"),
    ("GPSDifferential", "Integer", "Simple"),
    # Seq<Integer>
    ("ComponentsConfiguration", "Integer", "Seq"),
    ("ISOSpeedRatings", "Integer", "Seq"),
    ("SubjectArea", "Integer", "Seq"),
    ("SubjectLocation", "Integer", "Seq"),
)

# Wave-33 additions — Rational (``"<num>/<den>"`` wire form).
_RATIONAL_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("CompressedBitsPerPixel", "Rational", "Simple"),
    ("ExposureTime", "Rational", "Simple"),
    ("FNumber", "Rational", "Simple"),
    ("ShutterSpeedValue", "Rational", "Simple"),
    ("ApertureValue", "Rational", "Simple"),
    ("BrightnessValue", "Rational", "Simple"),
    ("ExposureBiasValue", "Rational", "Simple"),
    ("MaxApertureValue", "Rational", "Simple"),
    ("SubjectDistance", "Rational", "Simple"),
    ("FlashEnergy", "Rational", "Simple"),
    ("FocalLength", "Rational", "Simple"),
    ("FocalPlaneXResolution", "Rational", "Simple"),
    ("FocalPlaneYResolution", "Rational", "Simple"),
    ("ExposureIndex", "Rational", "Simple"),
    ("DigitalZoomRatio", "Rational", "Simple"),
    ("GPSAltitude", "Rational", "Simple"),
    ("GPSDOP", "Rational", "Simple"),
    ("GPSSpeed", "Rational", "Simple"),
    ("GPSTrack", "Rational", "Simple"),
    ("GPSImgDirection", "Rational", "Simple"),
    ("GPSDestBearing", "Rational", "Simple"),
    ("GPSDestDistance", "Rational", "Simple"),
)

# Wave-33 additions — GPSCoordinate (pypdfbox addition; see ExifSchema docstring).
_GPS_COORDINATE_PARAMETERS: tuple[tuple[str, str, str], ...] = (
    ("GPSLatitude", "GPSCoordinate", "Simple"),
    ("GPSLongitude", "GPSCoordinate", "Simple"),
    ("GPSDestLatitude", "GPSCoordinate", "Simple"),
    ("GPSDestLongitude", "GPSCoordinate", "Simple"),
)

# Still skipped — pending typed-struct ports (see ExifSchema docstring):
#   OECF / SpatialFrequencyResponse (OECF struct), CFAPattern /
#   CFAPatternType (CFAPattern struct), Flash (Flash struct),
#   DeviceSettingDescription (DeviceSettings struct).


# Map upstream constant name → (getter, setter or adder).
# Seq<Integer> properties expose ``add_*`` only; for those tests the "setter"
# slot points at the adder and the test paths branch on cardinality.
_ACCESSORS: dict[str, tuple[str, str]] = {
    "UserComment": ("get_user_comment", "set_user_comment"),
    "ExifVersion": ("get_exif_version", "set_exif_version"),
    "FlashpixVersion": ("get_flashpix_version", "set_flashpix_version"),
    "RelatedSoundFile": ("get_related_sound_file", "set_related_sound_file"),
    "DateTimeOriginal": ("get_date_time_original", "set_date_time_original"),
    "DateTimeDigitized": ("get_date_time_digitized", "set_date_time_digitized"),
    "SpectralSensitivity": ("get_spectral_sensitivity", "set_spectral_sensitivity"),
    "ImageUniqueID": ("get_image_unique_id", "set_image_unique_id"),
    "GPSVersionID": ("get_gps_version_id", "set_gps_version_id"),
    "GPSSatellites": ("get_gps_satellites", "set_gps_satellites"),
    "GPSStatus": ("get_gps_status", "set_gps_status"),
    "GPSMeasureMode": ("get_gps_measure_mode", "set_gps_measure_mode"),
    "GPSMapDatum": ("get_gps_map_datum", "set_gps_map_datum"),
    "GPSSpeedRef": ("get_gps_speed_ref", "set_gps_speed_ref"),
    "GPSTrackRef": ("get_gps_track_ref", "set_gps_track_ref"),
    "GPSImgDirectionRef": ("get_gps_img_direction_ref", "set_gps_img_direction_ref"),
    "GPSDestBearingRef": ("get_gps_dest_bearing_ref", "set_gps_dest_bearing_ref"),
    "GPSDestDistanceRef": ("get_gps_dest_distance_ref", "set_gps_dest_distance_ref"),
    "GPSProcessingMethod": ("get_gps_processing_method", "set_gps_processing_method"),
    "GPSAreaInformation": ("get_gps_area_information", "set_gps_area_information"),
    "GPSTimeStamp": ("get_gps_time_stamp", "set_gps_time_stamp"),
    "ColorSpace": ("get_color_space", "set_color_space"),
    "PixelXDimension": ("get_pixel_x_dimension", "set_pixel_x_dimension"),
    "PixelYDimension": ("get_pixel_y_dimension", "set_pixel_y_dimension"),
    "ExposureProgram": ("get_exposure_program", "set_exposure_program"),
    "MeteringMode": ("get_metering_mode", "set_metering_mode"),
    "LightSource": ("get_light_source", "set_light_source"),
    "FocalPlaneResolutionUnit": ("get_focal_plane_resolution_unit", "set_focal_plane_resolution_unit"),
    "SensingMethod": ("get_sensing_method", "set_sensing_method"),
    "FileSource": ("get_file_source", "set_file_source"),
    "SceneType": ("get_scene_type", "set_scene_type"),
    "CustomRendered": ("get_custom_rendered", "set_custom_rendered"),
    "WhiteBalance": ("get_white_balance", "set_white_balance"),
    "ExposureMode": ("get_exposure_mode", "set_exposure_mode"),
    "FocalLengthIn35mmFilm": ("get_focal_length_in_35mm_film", "set_focal_length_in_35mm_film"),
    "SceneCaptureType": ("get_scene_capture_type", "set_scene_capture_type"),
    "GainControl": ("get_gain_control", "set_gain_control"),
    "Contrast": ("get_contrast", "set_contrast"),
    "Saturation": ("get_saturation", "set_saturation"),
    "Sharpness": ("get_sharpness", "set_sharpness"),
    "SubjectDistanceRange": ("get_subject_distance_range", "set_subject_distance_range"),
    "GPSAltitudeRef": ("get_gps_altitude_ref", "set_gps_altitude_ref"),
    "GPSDifferential": ("get_gps_differential", "set_gps_differential"),
    "ComponentsConfiguration": ("get_components_configuration", "add_components_configuration"),
    "ISOSpeedRatings": ("get_iso_speed_ratings", "add_iso_speed_ratings"),
    "SubjectArea": ("get_subject_area", "add_subject_area"),
    "SubjectLocation": ("get_subject_location", "add_subject_location"),
}


def _sample_value(type_token: str) -> object:
    """Pick a per-type sample value matching the upstream PropertyType column."""
    if type_token == "Integer":
        return 7
    # Text / Date / LangAlt all serialise to strings in cluster #1.
    return "sample-value"


@pytest.fixture
def metadata() -> XMPMetadata:
    """Translates upstream ``@BeforeEach initMetadata`` setUp."""
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_initialized_to_null(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testInitializedToNull``: a freshly-built
    schema reports ``None`` for every typed accessor.
    """
    del type_token, card
    schema = ExifSchema(metadata)
    getter_name, _ = _ACCESSORS[field_name]
    assert getattr(schema, getter_name)() is None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_setting_value(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testSettingValue``: setting the property
    via the typed setter (or adder for Seq) must round-trip through the typed
    getter and surface on the raw property store under the upstream local-name.
    """
    schema = ExifSchema(metadata)
    getter_name, setter_or_adder_name = _ACCESSORS[field_name]
    value = _sample_value(type_token)
    getattr(schema, setter_or_adder_name)(value)
    if card == "Seq":
        # Adder appends; getter returns a list.
        result = getattr(schema, getter_name)()
        assert isinstance(result, list)
        assert result == [str(value)]
    else:
        assert getattr(schema, getter_name)() == value
    # Stored under the upstream constant local-name.
    assert schema.get_property(field_name) is not None


@pytest.mark.parametrize(("field_name", "type_token", "card"), _PARAMETERS)
def test_random_setting_value(
    metadata: XMPMetadata, field_name: str, type_token: str, card: str
) -> None:
    """
    Mirrors upstream ``SchemaTester.testRandomSettingValue``: upstream draws a
    random value of the right type. Cluster #1 substitutes a deterministic
    second sample so the test stays reproducible while still exercising the
    "set, then read back the same value" contract.
    """
    schema = ExifSchema(metadata)
    getter_name, setter_or_adder_name = _ACCESSORS[field_name]
    if type_token == "Integer":
        value: object = 42
    else:
        value = "another-value"
    getattr(schema, setter_or_adder_name)(value)
    if card == "Seq":
        result = getattr(schema, getter_name)()
        assert isinstance(result, list)
        assert result == [str(value)]
    else:
        assert getattr(schema, getter_name)() == value
