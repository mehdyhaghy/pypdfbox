from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class ExifSchema(XMPSchema):
    """
    Representation of the EXIF XMP schema.

    Ported (subset, simple-typed properties) from
    ``org.apache.xmpbox.schema.ExifSchema`` (PDFBox 3.0). The schema captures
    the EXIF camera/image metadata Adobe applications embed alongside Dublin
    Core. Per the EXIF/XMP specification the namespace is
    ``http://ns.adobe.com/exif/1.0/`` with preferred prefix ``exif``. Property
    local names match upstream constants verbatim.

    This cluster ships accessors for the simple-typed properties only:

      * ``UserComment`` (LangAlt) — user comment.
      * ``ExifVersion`` (Text) — EXIF spec version (e.g. "0220").
      * ``FlashpixVersion`` (Text) — Flashpix format version.
      * ``ColorSpace`` (Integer) — colour space (1=sRGB, 65535=uncalibrated).
      * ``ComponentsConfiguration`` (Seq of Integer) — channel mapping.
      * ``PixelXDimension`` / ``PixelYDimension`` (Integer) — pixel dimensions.
      * ``RelatedSoundFile`` (Text) — companion audio filename.
      * ``DateTimeOriginal`` / ``DateTimeDigitized`` (Date) — capture dates.
      * ``ExposureProgram`` (Integer) — exposure-program enum.
      * ``SpectralSensitivity`` (Text) — spectral sensitivity description.
      * ``ISOSpeedRatings`` (Seq of Integer) — ISO speed ratings.
      * ``MeteringMode`` / ``LightSource`` (Integer) — exposure-meter config.
      * ``SubjectArea`` (Seq of Integer) — subject area pixel coords.
      * ``FocalPlaneResolutionUnit`` (Integer) — resolution unit enum.
      * ``SubjectLocation`` (Seq of Integer) — subject focal-point coords.
      * ``SensingMethod`` (Integer) — sensor type.
      * ``FileSource`` / ``SceneType`` (Integer) — capture-source enums.
      * ``CustomRendered`` / ``WhiteBalance`` / ``ExposureMode`` (Integer).
      * ``FocalLengthIn35mmFilm`` (Integer) — 35-mm equivalent focal length.
      * ``SceneCaptureType`` / ``GainControl`` (Integer) — capture-mode enums.
      * ``Contrast`` / ``Saturation`` / ``Sharpness`` (Integer) — render hints.
      * ``SubjectDistanceRange`` (Integer) — subject-distance range enum.
      * ``ImageUniqueID`` (Text) — image unique identifier.
      * ``GPSVersionID`` (Text) — GPS tag version.
      * ``GPSSatellites`` (Text) — GPS satellites used for measurement.
      * ``GPSStatus`` / ``GPSMeasureMode`` (Text) — GPS receiver state.
      * ``GPSMapDatum`` (Text) — geodetic survey data used.
      * ``GPSSpeedRef`` / ``GPSTrackRef`` (Text) — GPS direction units.
      * ``GPSImgDirectionRef`` (Text) — image-direction reference.
      * ``GPSDestBearingRef`` / ``GPSDestDistanceRef`` (Text).
      * ``GPSProcessingMethod`` / ``GPSAreaInformation`` (Text).
      * ``GPSAltitudeRef`` / ``GPSDifferential`` (Integer) — GPS enums.
      * ``GPSTimeStamp`` (Date) — GPS UTC timestamp.

    Deferred until the typed-struct wrappers land (CFAPattern, OECF, Flash,
    GPSCoordinate, RationalType, DeviceSettings — see upstream
    ``org.apache.xmpbox.type``):

      * ``CompressedBitsPerPixel``, ``ExposureTime``, ``FNumber``,
        ``ShutterSpeedValue``, ``ApertureValue``, ``BrightnessValue``,
        ``ExposureBiasValue``, ``MaxApertureValue``, ``SubjectDistance``,
        ``FlashEnergy``, ``FocalLength``, ``FocalPlaneXResolution``,
        ``FocalPlaneYResolution``, ``ExposureIndex``, ``DigitalZoomRatio``,
        ``GPSAltitude``, ``GPSDOP``, ``GPSSpeed``, ``GPSTrack``,
        ``GPSImgDirection``, ``GPSDestBearing``, ``GPSDestDistance``
        (Rational typed struct).
      * ``GPSLatitude``, ``GPSLongitude``, ``GPSDestLatitude``,
        ``GPSDestLongitude`` (GPSCoordinate typed struct).
      * ``OECF``, ``SpatialFrequencyResponse`` (OECF typed struct).
      * ``CFAPattern``, ``CFAPatternType`` (CFAPattern typed struct).
      * ``Flash`` (Flash typed struct).
      * ``DeviceSettingDescription`` (DeviceSettings typed struct).

    Callers needing raw access before the wrappers ship can use the generic
    :meth:`XMPSchema.get_property` accessor.
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

    # Local-name constants — names match upstream ``public static final`` fields.
    USER_COMMENT = "UserComment"
    EXIF_VERSION = "ExifVersion"
    FLASH_PIX_VERSION = "FlashpixVersion"
    COLOR_SPACE = "ColorSpace"
    COMPONENTS_CONFIGURATION = "ComponentsConfiguration"
    COMPRESSED_BPP = "CompressedBitsPerPixel"
    PIXEL_X_DIMENSION = "PixelXDimension"
    PIXEL_Y_DIMENSION = "PixelYDimension"
    RELATED_SOUND_FILE = "RelatedSoundFile"
    DATE_TIME_ORIGINAL = "DateTimeOriginal"
    DATE_TIME_DIGITIZED = "DateTimeDigitized"
    EXPOSURE_TIME = "ExposureTime"
    F_NUMBER = "FNumber"
    EXPOSURE_PROGRAM = "ExposureProgram"
    SPECTRAL_SENSITIVITY = "SpectralSensitivity"
    ISO_SPEED_RATINGS = "ISOSpeedRatings"
    SHUTTER_SPEED_VALUE = "ShutterSpeedValue"
    APERTURE_VALUE = "ApertureValue"
    BRIGHTNESS_VALUE = "BrightnessValue"
    EXPOSURE_BIAS_VALUE = "ExposureBiasValue"
    MAX_APERTURE_VALUE = "MaxApertureValue"
    SUBJECT_DISTANCE = "SubjectDistance"
    METERING_MODE = "MeteringMode"
    LIGHT_SOURCE = "LightSource"
    FLASH_ENERGY = "FlashEnergy"
    FOCAL_LENGTH = "FocalLength"
    FOCAL_PLANE_XRESOLUTION = "FocalPlaneXResolution"
    FOCAL_PLANE_YRESOLUTION = "FocalPlaneYResolution"
    SUBJECT_AREA = "SubjectArea"
    FOCAL_PLANE_RESOLUTION_UNIT = "FocalPlaneResolutionUnit"
    SUBJECT_LOCATION = "SubjectLocation"
    EXPOSURE_INDEX = "ExposureIndex"
    SENSING_METHOD = "SensingMethod"
    FILE_SOURCE = "FileSource"
    SCENE_TYPE = "SceneType"
    CUSTOM_RENDERED = "CustomRendered"
    WHITE_BALANCE = "WhiteBalance"
    EXPOSURE_MODE = "ExposureMode"
    DIGITAL_ZOOM_RATIO = "DigitalZoomRatio"
    FOCAL_LENGTH_IN_3_5MM_FILM = "FocalLengthIn35mmFilm"
    SCENE_CAPTURE_TYPE = "SceneCaptureType"
    GAIN_CONTROL = "GainControl"
    CONTRAST = "Contrast"
    SATURATION = "Saturation"
    SHARPNESS = "Sharpness"
    SUBJECT_DISTANCE_RANGE = "SubjectDistanceRange"
    IMAGE_UNIQUE_ID = "ImageUniqueID"
    GPSVERSION_ID = "GPSVersionID"
    GPS_SATELLITES = "GPSSatellites"
    GPS_STATUS = "GPSStatus"
    GPS_MEASURE_MODE = "GPSMeasureMode"
    GPS_MAP_DATUM = "GPSMapDatum"
    GPS_SPEED_REF = "GPSSpeedRef"
    GPS_TRACK_REF = "GPSTrackRef"
    GPS_IMG_DIRECTION_REF = "GPSImgDirectionRef"
    GPS_DEST_BEARING_REF = "GPSDestBearingRef"
    GPS_DEST_DISTANCE_REF = "GPSDestDistanceRef"
    GPS_PROCESSING_METHOD = "GPSProcessingMethod"
    GPS_AREA_INFORMATION = "GPSAreaInformation"
    GPS_ALTITUDE = "GPSAltitude"
    GPS_DOP = "GPSDOP"
    GPS_SPEED = "GPSSpeed"
    GPS_TRACK = "GPSTrack"
    GPS_IMG_DIRECTION = "GPSImgDirection"
    GPS_DEST_BEARING = "GPSDestBearing"
    GPS_DEST_DISTANCE = "GPSDestDistance"
    GPS_ALTITUDE_REF = "GPSAltitudeRef"
    GPS_DIFFERENTIAL = "GPSDifferential"
    GPS_TIME_STAMP = "GPSTimeStamp"
    OECF = "OECF"
    SPATIAL_FREQUENCY_RESPONSE = "SpatialFrequencyResponse"
    GPS_LATITUDE = "GPSLatitude"
    GPS_LONGITUDE = "GPSLongitude"
    GPS_DEST_LATITUDE = "GPSDestLatitude"
    GPS_DEST_LONGITUDE = "GPSDestLongitude"
    CFA_PATTERN = "CFAPattern"
    FLASH = "Flash"
    CFA_PATTERN_TYPE = "CFAPatternType"
    DEVICE_SETTING_DESCRIPTION = "DeviceSettingDescription"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- internal: integer text round-trip ---------------------------

    def _get_integer(self, local_name: str) -> int | None:
        """Read an Integer-typed property, accepting both int and string forms."""
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, bool):
            # bool subclasses int; coerce so True/False round-trip cleanly.
            return int(raw)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str):
            try:
                return int(raw.strip())
            except ValueError:
                return None
        text = self.get_unqualified_text_property_value(local_name)
        if text is None:
            return None
        try:
            return int(text.strip())
        except ValueError:
            return None

    def _set_integer(self, local_name: str, value: int | str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        # Upstream serialises IntegerType as the decimal string form.
        if isinstance(value, str):
            self.set_text_property_value(local_name, value)
        else:
            self.set_text_property_value(local_name, str(int(value)))

    def _set_text(self, local_name: str, value: str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        self.set_text_property_value(local_name, value)

    # --- UserComment (LangAlt) --------------------------------------

    def set_user_comment(self, value: str) -> None:
        self.set_unqualified_language_property_value(self.USER_COMMENT, None, value)

    def add_user_comment(self, lang: str | None, value: str) -> None:
        # Mirror of upstream ``addUserComment(String lang, String value)`` patterns
        # used elsewhere in xmpbox; ExifSchema only exposes getters upstream but
        # we provide the same lang-aware setter shape for symmetry with TIFF.
        self.set_unqualified_language_property_value(self.USER_COMMENT, lang, value)

    def get_user_comment(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.USER_COMMENT, lang)

    def get_user_comment_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.USER_COMMENT)

    # --- ExifVersion (Text) -----------------------------------------

    def get_exif_version(self) -> str | None:
        return self.get_unqualified_text_property_value(self.EXIF_VERSION)

    def set_exif_version(self, value: str | None) -> None:
        self._set_text(self.EXIF_VERSION, value)

    # --- FlashpixVersion (Text) -------------------------------------

    def get_flashpix_version(self) -> str | None:
        return self.get_unqualified_text_property_value(self.FLASH_PIX_VERSION)

    def set_flashpix_version(self, value: str | None) -> None:
        self._set_text(self.FLASH_PIX_VERSION, value)

    # --- ColorSpace (Integer) ---------------------------------------

    def get_color_space(self) -> int | None:
        return self._get_integer(self.COLOR_SPACE)

    def set_color_space(self, value: int | str | None) -> None:
        self._set_integer(self.COLOR_SPACE, value)

    # --- ComponentsConfiguration (Seq of Integer, stored as strings) -

    def add_components_configuration(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.COMPONENTS_CONFIGURATION,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_components_configuration(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.COMPONENTS_CONFIGURATION)

    # --- PixelXDimension / PixelYDimension (Integer) ---------------

    def get_pixel_x_dimension(self) -> int | None:
        return self._get_integer(self.PIXEL_X_DIMENSION)

    def set_pixel_x_dimension(self, value: int | str | None) -> None:
        self._set_integer(self.PIXEL_X_DIMENSION, value)

    def get_pixel_y_dimension(self) -> int | None:
        return self._get_integer(self.PIXEL_Y_DIMENSION)

    def set_pixel_y_dimension(self, value: int | str | None) -> None:
        self._set_integer(self.PIXEL_Y_DIMENSION, value)

    # --- RelatedSoundFile (Text) ------------------------------------

    def get_related_sound_file(self) -> str | None:
        return self.get_unqualified_text_property_value(self.RELATED_SOUND_FILE)

    def set_related_sound_file(self, value: str | None) -> None:
        self._set_text(self.RELATED_SOUND_FILE, value)

    # --- DateTimeOriginal / DateTimeDigitized (Date) ----------------

    def get_date_time_original(self) -> str | None:
        return self.get_unqualified_text_property_value(self.DATE_TIME_ORIGINAL)

    def set_date_time_original(self, value: str | None) -> None:
        self._set_text(self.DATE_TIME_ORIGINAL, value)

    def get_date_time_digitized(self) -> str | None:
        return self.get_unqualified_text_property_value(self.DATE_TIME_DIGITIZED)

    def set_date_time_digitized(self, value: str | None) -> None:
        self._set_text(self.DATE_TIME_DIGITIZED, value)

    # --- ExposureProgram (Integer) ---------------------------------

    def get_exposure_program(self) -> int | None:
        return self._get_integer(self.EXPOSURE_PROGRAM)

    def set_exposure_program(self, value: int | str | None) -> None:
        self._set_integer(self.EXPOSURE_PROGRAM, value)

    # --- SpectralSensitivity (Text) --------------------------------

    def get_spectral_sensitivity(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SPECTRAL_SENSITIVITY)

    def set_spectral_sensitivity(self, value: str | None) -> None:
        self._set_text(self.SPECTRAL_SENSITIVITY, value)

    # --- ISOSpeedRatings (Seq of Integer) --------------------------

    def add_iso_speed_ratings(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.ISO_SPEED_RATINGS,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_iso_speed_ratings(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.ISO_SPEED_RATINGS)

    # --- MeteringMode / LightSource (Integer) ----------------------

    def get_metering_mode(self) -> int | None:
        return self._get_integer(self.METERING_MODE)

    def set_metering_mode(self, value: int | str | None) -> None:
        self._set_integer(self.METERING_MODE, value)

    def get_light_source(self) -> int | None:
        return self._get_integer(self.LIGHT_SOURCE)

    def set_light_source(self, value: int | str | None) -> None:
        self._set_integer(self.LIGHT_SOURCE, value)

    # --- SubjectArea (Seq of Integer) ------------------------------

    def add_subject_area(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.SUBJECT_AREA,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_subject_area(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.SUBJECT_AREA)

    # --- FocalPlaneResolutionUnit (Integer) ------------------------

    def get_focal_plane_resolution_unit(self) -> int | None:
        return self._get_integer(self.FOCAL_PLANE_RESOLUTION_UNIT)

    def set_focal_plane_resolution_unit(self, value: int | str | None) -> None:
        self._set_integer(self.FOCAL_PLANE_RESOLUTION_UNIT, value)

    # --- SubjectLocation (Seq of Integer) --------------------------

    def add_subject_location(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.SUBJECT_LOCATION,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_subject_location(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.SUBJECT_LOCATION)

    # --- SensingMethod / FileSource / SceneType (Integer) ----------

    def get_sensing_method(self) -> int | None:
        return self._get_integer(self.SENSING_METHOD)

    def set_sensing_method(self, value: int | str | None) -> None:
        self._set_integer(self.SENSING_METHOD, value)

    def get_file_source(self) -> int | None:
        return self._get_integer(self.FILE_SOURCE)

    def set_file_source(self, value: int | str | None) -> None:
        self._set_integer(self.FILE_SOURCE, value)

    def get_scene_type(self) -> int | None:
        return self._get_integer(self.SCENE_TYPE)

    def set_scene_type(self, value: int | str | None) -> None:
        self._set_integer(self.SCENE_TYPE, value)

    # --- CustomRendered / WhiteBalance / ExposureMode (Integer) ----

    def get_custom_rendered(self) -> int | None:
        return self._get_integer(self.CUSTOM_RENDERED)

    def set_custom_rendered(self, value: int | str | None) -> None:
        self._set_integer(self.CUSTOM_RENDERED, value)

    def get_white_balance(self) -> int | None:
        return self._get_integer(self.WHITE_BALANCE)

    def set_white_balance(self, value: int | str | None) -> None:
        self._set_integer(self.WHITE_BALANCE, value)

    def get_exposure_mode(self) -> int | None:
        return self._get_integer(self.EXPOSURE_MODE)

    def set_exposure_mode(self, value: int | str | None) -> None:
        self._set_integer(self.EXPOSURE_MODE, value)

    # --- FocalLengthIn35mmFilm (Integer) ---------------------------

    def get_focal_length_in_35mm_film(self) -> int | None:
        return self._get_integer(self.FOCAL_LENGTH_IN_3_5MM_FILM)

    def set_focal_length_in_35mm_film(self, value: int | str | None) -> None:
        self._set_integer(self.FOCAL_LENGTH_IN_3_5MM_FILM, value)

    # --- SceneCaptureType / GainControl (Integer) ------------------

    def get_scene_capture_type(self) -> int | None:
        return self._get_integer(self.SCENE_CAPTURE_TYPE)

    def set_scene_capture_type(self, value: int | str | None) -> None:
        self._set_integer(self.SCENE_CAPTURE_TYPE, value)

    def get_gain_control(self) -> int | None:
        return self._get_integer(self.GAIN_CONTROL)

    def set_gain_control(self, value: int | str | None) -> None:
        self._set_integer(self.GAIN_CONTROL, value)

    # --- Contrast / Saturation / Sharpness (Integer) ---------------

    def get_contrast(self) -> int | None:
        return self._get_integer(self.CONTRAST)

    def set_contrast(self, value: int | str | None) -> None:
        self._set_integer(self.CONTRAST, value)

    def get_saturation(self) -> int | None:
        return self._get_integer(self.SATURATION)

    def set_saturation(self, value: int | str | None) -> None:
        self._set_integer(self.SATURATION, value)

    def get_sharpness(self) -> int | None:
        return self._get_integer(self.SHARPNESS)

    def set_sharpness(self, value: int | str | None) -> None:
        self._set_integer(self.SHARPNESS, value)

    # --- SubjectDistanceRange (Integer) ----------------------------

    def get_subject_distance_range(self) -> int | None:
        return self._get_integer(self.SUBJECT_DISTANCE_RANGE)

    def set_subject_distance_range(self, value: int | str | None) -> None:
        self._set_integer(self.SUBJECT_DISTANCE_RANGE, value)

    # --- ImageUniqueID (Text) --------------------------------------

    def get_image_unique_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.IMAGE_UNIQUE_ID)

    def set_image_unique_id(self, value: str | None) -> None:
        self._set_text(self.IMAGE_UNIQUE_ID, value)

    # --- GPSVersionID (Text) ---------------------------------------

    def get_gps_version_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPSVERSION_ID)

    def set_gps_version_id(self, value: str | None) -> None:
        self._set_text(self.GPSVERSION_ID, value)

    # --- GPSSatellites (Text) --------------------------------------

    def get_gps_satellites(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_SATELLITES)

    def set_gps_satellites(self, value: str | None) -> None:
        self._set_text(self.GPS_SATELLITES, value)

    # --- GPSStatus / GPSMeasureMode (Text) -------------------------

    def get_gps_status(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_STATUS)

    def set_gps_status(self, value: str | None) -> None:
        self._set_text(self.GPS_STATUS, value)

    def get_gps_measure_mode(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_MEASURE_MODE)

    def set_gps_measure_mode(self, value: str | None) -> None:
        self._set_text(self.GPS_MEASURE_MODE, value)

    # --- GPSMapDatum (Text) ----------------------------------------

    def get_gps_map_datum(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_MAP_DATUM)

    def set_gps_map_datum(self, value: str | None) -> None:
        self._set_text(self.GPS_MAP_DATUM, value)

    # --- GPSSpeedRef / GPSTrackRef / GPSImgDirectionRef (Text) -----

    def get_gps_speed_ref(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_SPEED_REF)

    def set_gps_speed_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_SPEED_REF, value)

    def get_gps_track_ref(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_TRACK_REF)

    def set_gps_track_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_TRACK_REF, value)

    def get_gps_img_direction_ref(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_IMG_DIRECTION_REF)

    def set_gps_img_direction_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_IMG_DIRECTION_REF, value)

    # --- GPSDestBearingRef / GPSDestDistanceRef (Text) -------------

    def get_gps_dest_bearing_ref(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_DEST_BEARING_REF)

    def set_gps_dest_bearing_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_DEST_BEARING_REF, value)

    def get_gps_dest_distance_ref(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_DEST_DISTANCE_REF)

    def set_gps_dest_distance_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_DEST_DISTANCE_REF, value)

    # --- GPSProcessingMethod / GPSAreaInformation (Text) -----------

    def get_gps_processing_method(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_PROCESSING_METHOD)

    def set_gps_processing_method(self, value: str | None) -> None:
        self._set_text(self.GPS_PROCESSING_METHOD, value)

    def get_gps_area_information(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_AREA_INFORMATION)

    def set_gps_area_information(self, value: str | None) -> None:
        self._set_text(self.GPS_AREA_INFORMATION, value)

    # --- GPSAltitudeRef / GPSDifferential (Integer) ----------------

    def get_gps_altitude_ref(self) -> int | None:
        return self._get_integer(self.GPS_ALTITUDE_REF)

    def set_gps_altitude_ref(self, value: int | str | None) -> None:
        self._set_integer(self.GPS_ALTITUDE_REF, value)

    def get_gps_differential(self) -> int | None:
        return self._get_integer(self.GPS_DIFFERENTIAL)

    def set_gps_differential(self, value: int | str | None) -> None:
        self._set_integer(self.GPS_DIFFERENTIAL, value)

    # --- GPSTimeStamp (Date) ---------------------------------------

    def get_gps_time_stamp(self) -> str | None:
        return self.get_unqualified_text_property_value(self.GPS_TIME_STAMP)

    def set_gps_time_stamp(self, value: str | None) -> None:
        self._set_text(self.GPS_TIME_STAMP, value)
