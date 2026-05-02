from __future__ import annotations

from typing import TYPE_CHECKING

from .type import (
    AbstractSimpleProperty,
    Attribute,
    DateType,
    GPSCoordinateType,
    IntegerType,
    LangAlt,
    RationalType,
    TextType,
)
from .type.lang_alt import LANG_ATTR_NAME, X_DEFAULT, XML_NS_URI
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class ExifSchema(XMPSchema):
    """
    Representation of the EXIF XMP schema.

    Ported (subset) from ``org.apache.xmpbox.schema.ExifSchema`` (PDFBox 3.0).
    The schema captures the EXIF camera/image metadata Adobe applications embed
    alongside Dublin Core. Per the EXIF/XMP specification the namespace is
    ``http://ns.adobe.com/exif/1.0/`` with preferred prefix ``exif``. Property
    local names match upstream constants verbatim.

    Wave 33 layers typed (``TextType`` / ``IntegerType`` / ``DateType`` /
    ``RationalType`` / ``GPSCoordinateType``) ``*_property`` getter/setter pairs
    on top of the existing simple string-form accessors. Both forms share the
    same underlying property store: typed setters install an
    :class:`AbstractSimpleProperty` instance under the upstream local-name,
    string-form getters transparently read either form, and string-form setters
    continue to write plain string/int values for back-compat.

    Simple-typed accessors (string / int / Date forms):

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

    Rational-typed accessors (``RationalType``, "<num>/<den>" wire form):

      * ``CompressedBitsPerPixel``, ``ExposureTime``, ``FNumber``,
        ``ShutterSpeedValue``, ``ApertureValue``, ``BrightnessValue``,
        ``ExposureBiasValue``, ``MaxApertureValue``, ``SubjectDistance``,
        ``FlashEnergy``, ``FocalLength``, ``FocalPlaneXResolution``,
        ``FocalPlaneYResolution``, ``ExposureIndex``, ``DigitalZoomRatio``,
        ``GPSAltitude``, ``GPSDOP``, ``GPSSpeed``, ``GPSTrack``,
        ``GPSImgDirection``, ``GPSDestBearing``, ``GPSDestDistance``.

    GPSCoordinate-typed accessors (``GPSCoordinateType``,
    ``"D,M,S<hemisphere>"`` wire form — pypdfbox addition; no upstream class):

      * ``GPSLatitude``, ``GPSLongitude``, ``GPSDestLatitude``,
        ``GPSDestLongitude``.

    Deferred until the typed-struct wrappers land for the EXIF-specific
    structures (Wave 33 ships only the foundation structured types):

      * ``OECF`` / ``SpatialFrequencyResponse`` (OECFType — not yet ported).
      * ``CFAPattern`` / ``CFAPatternType`` (CFAPattern struct — not yet ported).
      * ``Flash`` (Flash struct — not yet ported).
      * ``DeviceSettingDescription`` (DeviceSettings struct — not yet ported).

    Constants for the deferred fields are exposed so the parser can still round-
    trip the raw values via the generic :meth:`XMPSchema.get_property` accessor.
    """

    NAMESPACE = "http://ns.adobe.com/exif/1.0/"
    PREFERRED_PREFIX = "exif"

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
        if isinstance(raw, IntegerType):
            return raw.get_value()
        if isinstance(raw, AbstractSimpleProperty):
            text = raw.get_string_value()
            try:
                return int(text.strip())
            except (AttributeError, ValueError):
                return None
        if isinstance(raw, bool):
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
        if isinstance(value, str):
            self.set_text_property_value(local_name, value)
        else:
            self.set_text_property_value(local_name, str(int(value)))

    def _set_text(self, local_name: str, value: str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        self.set_text_property_value(local_name, value)

    # --- internal: typed-instance helpers ----------------------------

    def _read_text_string(self, local_name: str) -> str | None:
        raw = self._properties.get(local_name)
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        return self.get_unqualified_text_property_value(local_name)

    def _typed_get(
        self, local_name: str, expected: type[AbstractSimpleProperty]
    ) -> AbstractSimpleProperty | None:
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, expected):
            return raw
        if isinstance(raw, AbstractSimpleProperty):
            return expected(
                self._metadata,
                self._namespace,
                self._prefix,
                local_name,
                raw.get_string_value(),
            )
        return expected(
            self._metadata, self._namespace, self._prefix, local_name, raw
        )

    def _typed_set(
        self, local_name: str, prop: AbstractSimpleProperty | None
    ) -> None:
        if prop is None:
            self.remove_property(local_name)
            return
        prop.set_property_name(local_name)
        self._properties[local_name] = prop

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

    def remove_user_comment(self, lang: str | None = None) -> None:
        """
        Drop the per-language ``UserComment`` value identified by ``lang``
        (defaulting to the ``x-default`` slot). No-op when the property or
        the requested language slot is absent. Convenience wrapper over
        :meth:`remove_unqualified_language_property_value` -- upstream
        ExifSchema only exposes getters, but the underlying
        ``XMPSchema.removeUnqualifiedLanguagePropertyValue`` is public so
        callers reach the same effect through it.
        """
        self.remove_unqualified_language_property_value(self.USER_COMMENT, lang)

    def get_user_comment_property(self) -> LangAlt | None:
        """
        Mirror of upstream ``getUserCommentProperty()`` — returns the typed
        :class:`LangAlt` view of the ``UserComment`` slot, or ``None`` when no
        value has been set. Upstream returns the raw ``ArrayProperty``;
        :class:`LangAlt` is our typed subclass carrying language-tagged
        :class:`TextType` children.
        """
        raw = self._properties.get(self.USER_COMMENT)
        if not isinstance(raw, dict) or not raw:
            return None
        la = LangAlt(
            self._metadata, self._namespace, self._prefix, self.USER_COMMENT
        )
        keys = list(raw.keys())
        if X_DEFAULT in keys:
            keys.remove(X_DEFAULT)
            keys.insert(0, X_DEFAULT)
        for lang in keys:
            value = raw[lang]
            if not isinstance(value, str):
                continue
            text = TextType(
                self._metadata,
                self._namespace,
                self._prefix,
                self.USER_COMMENT,
                value,
            )
            text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, lang))
            la.add_property(text)
        return la

    # --- ExifVersion (Text) -----------------------------------------

    def get_exif_version(self) -> str | None:
        return self._read_text_string(self.EXIF_VERSION)

    def set_exif_version(self, value: str | None) -> None:
        self._set_text(self.EXIF_VERSION, value)

    def get_exif_version_property(self) -> TextType | None:
        result = self._typed_get(self.EXIF_VERSION, TextType)
        return result if isinstance(result, TextType) else None

    def set_exif_version_property(self, value: TextType | None) -> None:
        self._typed_set(self.EXIF_VERSION, value)

    # --- FlashpixVersion (Text) -------------------------------------

    def get_flashpix_version(self) -> str | None:
        return self._read_text_string(self.FLASH_PIX_VERSION)

    def set_flashpix_version(self, value: str | None) -> None:
        self._set_text(self.FLASH_PIX_VERSION, value)

    def get_flashpix_version_property(self) -> TextType | None:
        result = self._typed_get(self.FLASH_PIX_VERSION, TextType)
        return result if isinstance(result, TextType) else None

    def set_flashpix_version_property(self, value: TextType | None) -> None:
        self._typed_set(self.FLASH_PIX_VERSION, value)

    # --- ColorSpace (Integer) ---------------------------------------

    def get_color_space(self) -> int | None:
        return self._get_integer(self.COLOR_SPACE)

    def set_color_space(self, value: int | str | None) -> None:
        self._set_integer(self.COLOR_SPACE, value)

    def get_color_space_property(self) -> IntegerType | None:
        result = self._typed_get(self.COLOR_SPACE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_color_space_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.COLOR_SPACE, value)

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

    def get_pixel_x_dimension_property(self) -> IntegerType | None:
        result = self._typed_get(self.PIXEL_X_DIMENSION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_pixel_x_dimension_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.PIXEL_X_DIMENSION, value)

    def get_pixel_y_dimension(self) -> int | None:
        return self._get_integer(self.PIXEL_Y_DIMENSION)

    def set_pixel_y_dimension(self, value: int | str | None) -> None:
        self._set_integer(self.PIXEL_Y_DIMENSION, value)

    def get_pixel_y_dimension_property(self) -> IntegerType | None:
        result = self._typed_get(self.PIXEL_Y_DIMENSION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_pixel_y_dimension_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.PIXEL_Y_DIMENSION, value)

    # --- RelatedSoundFile (Text) ------------------------------------

    def get_related_sound_file(self) -> str | None:
        return self._read_text_string(self.RELATED_SOUND_FILE)

    def set_related_sound_file(self, value: str | None) -> None:
        self._set_text(self.RELATED_SOUND_FILE, value)

    def get_related_sound_file_property(self) -> TextType | None:
        result = self._typed_get(self.RELATED_SOUND_FILE, TextType)
        return result if isinstance(result, TextType) else None

    def set_related_sound_file_property(self, value: TextType | None) -> None:
        self._typed_set(self.RELATED_SOUND_FILE, value)

    # --- DateTimeOriginal / DateTimeDigitized (Date) ----------------

    def get_date_time_original(self) -> str | None:
        return self._read_text_string(self.DATE_TIME_ORIGINAL)

    def set_date_time_original(self, value: str | None) -> None:
        self._set_text(self.DATE_TIME_ORIGINAL, value)

    def get_date_time_original_property(self) -> DateType | None:
        result = self._typed_get(self.DATE_TIME_ORIGINAL, DateType)
        return result if isinstance(result, DateType) else None

    def set_date_time_original_property(self, value: DateType | None) -> None:
        self._typed_set(self.DATE_TIME_ORIGINAL, value)

    def get_date_time_digitized(self) -> str | None:
        return self._read_text_string(self.DATE_TIME_DIGITIZED)

    def set_date_time_digitized(self, value: str | None) -> None:
        self._set_text(self.DATE_TIME_DIGITIZED, value)

    def get_date_time_digitized_property(self) -> DateType | None:
        result = self._typed_get(self.DATE_TIME_DIGITIZED, DateType)
        return result if isinstance(result, DateType) else None

    def set_date_time_digitized_property(self, value: DateType | None) -> None:
        self._typed_set(self.DATE_TIME_DIGITIZED, value)

    # --- ExposureProgram (Integer) ---------------------------------

    def get_exposure_program(self) -> int | None:
        return self._get_integer(self.EXPOSURE_PROGRAM)

    def set_exposure_program(self, value: int | str | None) -> None:
        self._set_integer(self.EXPOSURE_PROGRAM, value)

    def get_exposure_program_property(self) -> IntegerType | None:
        result = self._typed_get(self.EXPOSURE_PROGRAM, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_exposure_program_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.EXPOSURE_PROGRAM, value)

    # --- SpectralSensitivity (Text) --------------------------------

    def get_spectral_sensitivity(self) -> str | None:
        return self._read_text_string(self.SPECTRAL_SENSITIVITY)

    def set_spectral_sensitivity(self, value: str | None) -> None:
        self._set_text(self.SPECTRAL_SENSITIVITY, value)

    def get_spectral_sensitivity_property(self) -> TextType | None:
        result = self._typed_get(self.SPECTRAL_SENSITIVITY, TextType)
        return result if isinstance(result, TextType) else None

    def set_spectral_sensitivity_property(self, value: TextType | None) -> None:
        self._typed_set(self.SPECTRAL_SENSITIVITY, value)

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

    def get_metering_mode_property(self) -> IntegerType | None:
        result = self._typed_get(self.METERING_MODE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_metering_mode_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.METERING_MODE, value)

    def get_light_source(self) -> int | None:
        return self._get_integer(self.LIGHT_SOURCE)

    def set_light_source(self, value: int | str | None) -> None:
        self._set_integer(self.LIGHT_SOURCE, value)

    def get_light_source_property(self) -> IntegerType | None:
        result = self._typed_get(self.LIGHT_SOURCE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_light_source_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.LIGHT_SOURCE, value)

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

    def get_focal_plane_resolution_unit_property(self) -> IntegerType | None:
        result = self._typed_get(self.FOCAL_PLANE_RESOLUTION_UNIT, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_focal_plane_resolution_unit_property(
        self, value: IntegerType | None
    ) -> None:
        self._typed_set(self.FOCAL_PLANE_RESOLUTION_UNIT, value)

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

    def get_sensing_method_property(self) -> IntegerType | None:
        result = self._typed_get(self.SENSING_METHOD, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_sensing_method_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SENSING_METHOD, value)

    def get_file_source(self) -> int | None:
        return self._get_integer(self.FILE_SOURCE)

    def set_file_source(self, value: int | str | None) -> None:
        self._set_integer(self.FILE_SOURCE, value)

    def get_file_source_property(self) -> IntegerType | None:
        result = self._typed_get(self.FILE_SOURCE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_file_source_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.FILE_SOURCE, value)

    def get_scene_type(self) -> int | None:
        return self._get_integer(self.SCENE_TYPE)

    def set_scene_type(self, value: int | str | None) -> None:
        self._set_integer(self.SCENE_TYPE, value)

    def get_scene_type_property(self) -> IntegerType | None:
        result = self._typed_get(self.SCENE_TYPE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_scene_type_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SCENE_TYPE, value)

    # --- CustomRendered / WhiteBalance / ExposureMode (Integer) ----

    def get_custom_rendered(self) -> int | None:
        return self._get_integer(self.CUSTOM_RENDERED)

    def set_custom_rendered(self, value: int | str | None) -> None:
        self._set_integer(self.CUSTOM_RENDERED, value)

    def get_custom_rendered_property(self) -> IntegerType | None:
        result = self._typed_get(self.CUSTOM_RENDERED, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_custom_rendered_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.CUSTOM_RENDERED, value)

    def get_white_balance(self) -> int | None:
        return self._get_integer(self.WHITE_BALANCE)

    def set_white_balance(self, value: int | str | None) -> None:
        self._set_integer(self.WHITE_BALANCE, value)

    def get_white_balance_property(self) -> IntegerType | None:
        result = self._typed_get(self.WHITE_BALANCE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_white_balance_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.WHITE_BALANCE, value)

    def get_exposure_mode(self) -> int | None:
        return self._get_integer(self.EXPOSURE_MODE)

    def set_exposure_mode(self, value: int | str | None) -> None:
        self._set_integer(self.EXPOSURE_MODE, value)

    def get_exposure_mode_property(self) -> IntegerType | None:
        result = self._typed_get(self.EXPOSURE_MODE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_exposure_mode_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.EXPOSURE_MODE, value)

    # --- FocalLengthIn35mmFilm (Integer) ---------------------------

    def get_focal_length_in_35mm_film(self) -> int | None:
        return self._get_integer(self.FOCAL_LENGTH_IN_3_5MM_FILM)

    def set_focal_length_in_35mm_film(self, value: int | str | None) -> None:
        self._set_integer(self.FOCAL_LENGTH_IN_3_5MM_FILM, value)

    def get_focal_length_in_35mm_film_property(self) -> IntegerType | None:
        result = self._typed_get(self.FOCAL_LENGTH_IN_3_5MM_FILM, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_focal_length_in_35mm_film_property(
        self, value: IntegerType | None
    ) -> None:
        self._typed_set(self.FOCAL_LENGTH_IN_3_5MM_FILM, value)

    # --- SceneCaptureType / GainControl (Integer) ------------------

    def get_scene_capture_type(self) -> int | None:
        return self._get_integer(self.SCENE_CAPTURE_TYPE)

    def set_scene_capture_type(self, value: int | str | None) -> None:
        self._set_integer(self.SCENE_CAPTURE_TYPE, value)

    def get_scene_capture_type_property(self) -> IntegerType | None:
        result = self._typed_get(self.SCENE_CAPTURE_TYPE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_scene_capture_type_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SCENE_CAPTURE_TYPE, value)

    def get_gain_control(self) -> int | None:
        return self._get_integer(self.GAIN_CONTROL)

    def set_gain_control(self, value: int | str | None) -> None:
        self._set_integer(self.GAIN_CONTROL, value)

    def get_gain_control_property(self) -> IntegerType | None:
        result = self._typed_get(self.GAIN_CONTROL, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_gain_control_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.GAIN_CONTROL, value)

    # --- Contrast / Saturation / Sharpness (Integer) ---------------

    def get_contrast(self) -> int | None:
        return self._get_integer(self.CONTRAST)

    def set_contrast(self, value: int | str | None) -> None:
        self._set_integer(self.CONTRAST, value)

    def get_contrast_property(self) -> IntegerType | None:
        result = self._typed_get(self.CONTRAST, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_contrast_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.CONTRAST, value)

    def get_saturation(self) -> int | None:
        return self._get_integer(self.SATURATION)

    def set_saturation(self, value: int | str | None) -> None:
        self._set_integer(self.SATURATION, value)

    def get_saturation_property(self) -> IntegerType | None:
        result = self._typed_get(self.SATURATION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_saturation_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SATURATION, value)

    def get_sharpness(self) -> int | None:
        return self._get_integer(self.SHARPNESS)

    def set_sharpness(self, value: int | str | None) -> None:
        self._set_integer(self.SHARPNESS, value)

    def get_sharpness_property(self) -> IntegerType | None:
        result = self._typed_get(self.SHARPNESS, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_sharpness_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SHARPNESS, value)

    # --- SubjectDistanceRange (Integer) ----------------------------

    def get_subject_distance_range(self) -> int | None:
        return self._get_integer(self.SUBJECT_DISTANCE_RANGE)

    def set_subject_distance_range(self, value: int | str | None) -> None:
        self._set_integer(self.SUBJECT_DISTANCE_RANGE, value)

    def get_subject_distance_range_property(self) -> IntegerType | None:
        result = self._typed_get(self.SUBJECT_DISTANCE_RANGE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_subject_distance_range_property(
        self, value: IntegerType | None
    ) -> None:
        self._typed_set(self.SUBJECT_DISTANCE_RANGE, value)

    # --- ImageUniqueID (Text) --------------------------------------

    def get_image_unique_id(self) -> str | None:
        return self._read_text_string(self.IMAGE_UNIQUE_ID)

    def set_image_unique_id(self, value: str | None) -> None:
        self._set_text(self.IMAGE_UNIQUE_ID, value)

    def get_image_unique_id_property(self) -> TextType | None:
        result = self._typed_get(self.IMAGE_UNIQUE_ID, TextType)
        return result if isinstance(result, TextType) else None

    def set_image_unique_id_property(self, value: TextType | None) -> None:
        self._typed_set(self.IMAGE_UNIQUE_ID, value)

    # --- GPSVersionID (Text) ---------------------------------------

    def get_gps_version_id(self) -> str | None:
        return self._read_text_string(self.GPSVERSION_ID)

    def set_gps_version_id(self, value: str | None) -> None:
        self._set_text(self.GPSVERSION_ID, value)

    def get_gps_version_id_property(self) -> TextType | None:
        result = self._typed_get(self.GPSVERSION_ID, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_version_id_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPSVERSION_ID, value)

    # --- GPSSatellites (Text) --------------------------------------

    def get_gps_satellites(self) -> str | None:
        return self._read_text_string(self.GPS_SATELLITES)

    def set_gps_satellites(self, value: str | None) -> None:
        self._set_text(self.GPS_SATELLITES, value)

    def get_gps_satellites_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_SATELLITES, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_satellites_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_SATELLITES, value)

    # --- GPSStatus / GPSMeasureMode (Text) -------------------------

    def get_gps_status(self) -> str | None:
        return self._read_text_string(self.GPS_STATUS)

    def set_gps_status(self, value: str | None) -> None:
        self._set_text(self.GPS_STATUS, value)

    def get_gps_status_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_STATUS, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_status_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_STATUS, value)

    def get_gps_measure_mode(self) -> str | None:
        return self._read_text_string(self.GPS_MEASURE_MODE)

    def set_gps_measure_mode(self, value: str | None) -> None:
        self._set_text(self.GPS_MEASURE_MODE, value)

    def get_gps_measure_mode_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_MEASURE_MODE, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_measure_mode_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_MEASURE_MODE, value)

    # --- GPSMapDatum (Text) ----------------------------------------

    def get_gps_map_datum(self) -> str | None:
        return self._read_text_string(self.GPS_MAP_DATUM)

    def set_gps_map_datum(self, value: str | None) -> None:
        self._set_text(self.GPS_MAP_DATUM, value)

    def get_gps_map_datum_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_MAP_DATUM, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_map_datum_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_MAP_DATUM, value)

    # --- GPSSpeedRef / GPSTrackRef / GPSImgDirectionRef (Text) -----

    def get_gps_speed_ref(self) -> str | None:
        return self._read_text_string(self.GPS_SPEED_REF)

    def set_gps_speed_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_SPEED_REF, value)

    def get_gps_speed_ref_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_SPEED_REF, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_speed_ref_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_SPEED_REF, value)

    def get_gps_track_ref(self) -> str | None:
        return self._read_text_string(self.GPS_TRACK_REF)

    def set_gps_track_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_TRACK_REF, value)

    def get_gps_track_ref_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_TRACK_REF, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_track_ref_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_TRACK_REF, value)

    def get_gps_img_direction_ref(self) -> str | None:
        return self._read_text_string(self.GPS_IMG_DIRECTION_REF)

    def set_gps_img_direction_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_IMG_DIRECTION_REF, value)

    def get_gps_img_direction_ref_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_IMG_DIRECTION_REF, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_img_direction_ref_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_IMG_DIRECTION_REF, value)

    # --- GPSDestBearingRef / GPSDestDistanceRef (Text) -------------

    def get_gps_dest_bearing_ref(self) -> str | None:
        return self._read_text_string(self.GPS_DEST_BEARING_REF)

    def set_gps_dest_bearing_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_DEST_BEARING_REF, value)

    def get_gps_dest_bearing_ref_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_DEST_BEARING_REF, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_dest_bearing_ref_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_DEST_BEARING_REF, value)

    def get_gps_dest_distance_ref(self) -> str | None:
        return self._read_text_string(self.GPS_DEST_DISTANCE_REF)

    def set_gps_dest_distance_ref(self, value: str | None) -> None:
        self._set_text(self.GPS_DEST_DISTANCE_REF, value)

    def get_gps_dest_distance_ref_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_DEST_DISTANCE_REF, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_dest_distance_ref_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_DEST_DISTANCE_REF, value)

    # --- GPSProcessingMethod / GPSAreaInformation (Text) -----------

    def get_gps_processing_method(self) -> str | None:
        return self._read_text_string(self.GPS_PROCESSING_METHOD)

    def set_gps_processing_method(self, value: str | None) -> None:
        self._set_text(self.GPS_PROCESSING_METHOD, value)

    def get_gps_processing_method_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_PROCESSING_METHOD, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_processing_method_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_PROCESSING_METHOD, value)

    def get_gps_area_information(self) -> str | None:
        return self._read_text_string(self.GPS_AREA_INFORMATION)

    def set_gps_area_information(self, value: str | None) -> None:
        self._set_text(self.GPS_AREA_INFORMATION, value)

    def get_gps_area_information_property(self) -> TextType | None:
        result = self._typed_get(self.GPS_AREA_INFORMATION, TextType)
        return result if isinstance(result, TextType) else None

    def set_gps_area_information_property(self, value: TextType | None) -> None:
        self._typed_set(self.GPS_AREA_INFORMATION, value)

    # --- GPSAltitudeRef / GPSDifferential (Integer) ----------------

    def get_gps_altitude_ref(self) -> int | None:
        return self._get_integer(self.GPS_ALTITUDE_REF)

    def set_gps_altitude_ref(self, value: int | str | None) -> None:
        self._set_integer(self.GPS_ALTITUDE_REF, value)

    def get_gps_altitude_ref_property(self) -> IntegerType | None:
        result = self._typed_get(self.GPS_ALTITUDE_REF, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_gps_altitude_ref_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.GPS_ALTITUDE_REF, value)

    def get_gps_differential(self) -> int | None:
        return self._get_integer(self.GPS_DIFFERENTIAL)

    def set_gps_differential(self, value: int | str | None) -> None:
        self._set_integer(self.GPS_DIFFERENTIAL, value)

    def get_gps_differential_property(self) -> IntegerType | None:
        result = self._typed_get(self.GPS_DIFFERENTIAL, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_gps_differential_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.GPS_DIFFERENTIAL, value)

    # --- GPSTimeStamp (Date) ---------------------------------------

    def get_gps_time_stamp(self) -> str | None:
        return self._read_text_string(self.GPS_TIME_STAMP)

    def set_gps_time_stamp(self, value: str | None) -> None:
        self._set_text(self.GPS_TIME_STAMP, value)

    def get_gps_time_stamp_property(self) -> DateType | None:
        result = self._typed_get(self.GPS_TIME_STAMP, DateType)
        return result if isinstance(result, DateType) else None

    def set_gps_time_stamp_property(self, value: DateType | None) -> None:
        self._typed_set(self.GPS_TIME_STAMP, value)

    # --- Rational accessors (RationalType, "<num>/<den>" wire form)

    def _get_rational_string(self, local_name: str) -> str | None:
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        if isinstance(raw, str):
            return raw
        return self.get_unqualified_text_property_value(local_name)

    def _set_rational_string(self, local_name: str, value: str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        self.set_text_property_value(local_name, value)

    def _get_rational_property(self, local_name: str) -> RationalType | None:
        result = self._typed_get(local_name, RationalType)
        return result if isinstance(result, RationalType) else None

    def _set_rational_property(
        self, local_name: str, value: RationalType | None
    ) -> None:
        self._typed_set(local_name, value)

    def get_compressed_bits_per_pixel(self) -> str | None:
        return self._get_rational_string(self.COMPRESSED_BPP)

    def set_compressed_bits_per_pixel(self, value: str | None) -> None:
        self._set_rational_string(self.COMPRESSED_BPP, value)

    def get_compressed_bits_per_pixel_property(self) -> RationalType | None:
        return self._get_rational_property(self.COMPRESSED_BPP)

    def set_compressed_bits_per_pixel_property(
        self, value: RationalType | None
    ) -> None:
        self._set_rational_property(self.COMPRESSED_BPP, value)

    def get_exposure_time(self) -> str | None:
        return self._get_rational_string(self.EXPOSURE_TIME)

    def set_exposure_time(self, value: str | None) -> None:
        self._set_rational_string(self.EXPOSURE_TIME, value)

    def get_exposure_time_property(self) -> RationalType | None:
        return self._get_rational_property(self.EXPOSURE_TIME)

    def set_exposure_time_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.EXPOSURE_TIME, value)

    def get_f_number(self) -> str | None:
        return self._get_rational_string(self.F_NUMBER)

    def set_f_number(self, value: str | None) -> None:
        self._set_rational_string(self.F_NUMBER, value)

    def get_f_number_property(self) -> RationalType | None:
        return self._get_rational_property(self.F_NUMBER)

    def set_f_number_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.F_NUMBER, value)

    def get_shutter_speed_value(self) -> str | None:
        return self._get_rational_string(self.SHUTTER_SPEED_VALUE)

    def set_shutter_speed_value(self, value: str | None) -> None:
        self._set_rational_string(self.SHUTTER_SPEED_VALUE, value)

    def get_shutter_speed_value_property(self) -> RationalType | None:
        return self._get_rational_property(self.SHUTTER_SPEED_VALUE)

    def set_shutter_speed_value_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.SHUTTER_SPEED_VALUE, value)

    def get_aperture_value(self) -> str | None:
        return self._get_rational_string(self.APERTURE_VALUE)

    def set_aperture_value(self, value: str | None) -> None:
        self._set_rational_string(self.APERTURE_VALUE, value)

    def get_aperture_value_property(self) -> RationalType | None:
        return self._get_rational_property(self.APERTURE_VALUE)

    def set_aperture_value_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.APERTURE_VALUE, value)

    def get_brightness_value(self) -> str | None:
        return self._get_rational_string(self.BRIGHTNESS_VALUE)

    def set_brightness_value(self, value: str | None) -> None:
        self._set_rational_string(self.BRIGHTNESS_VALUE, value)

    def get_brightness_value_property(self) -> RationalType | None:
        return self._get_rational_property(self.BRIGHTNESS_VALUE)

    def set_brightness_value_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.BRIGHTNESS_VALUE, value)

    def get_exposure_bias_value(self) -> str | None:
        return self._get_rational_string(self.EXPOSURE_BIAS_VALUE)

    def set_exposure_bias_value(self, value: str | None) -> None:
        self._set_rational_string(self.EXPOSURE_BIAS_VALUE, value)

    def get_exposure_bias_value_property(self) -> RationalType | None:
        return self._get_rational_property(self.EXPOSURE_BIAS_VALUE)

    def set_exposure_bias_value_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.EXPOSURE_BIAS_VALUE, value)

    def get_max_aperture_value(self) -> str | None:
        return self._get_rational_string(self.MAX_APERTURE_VALUE)

    def set_max_aperture_value(self, value: str | None) -> None:
        self._set_rational_string(self.MAX_APERTURE_VALUE, value)

    def get_max_aperture_value_property(self) -> RationalType | None:
        return self._get_rational_property(self.MAX_APERTURE_VALUE)

    def set_max_aperture_value_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.MAX_APERTURE_VALUE, value)

    def get_subject_distance(self) -> str | None:
        return self._get_rational_string(self.SUBJECT_DISTANCE)

    def set_subject_distance(self, value: str | None) -> None:
        self._set_rational_string(self.SUBJECT_DISTANCE, value)

    def get_subject_distance_property(self) -> RationalType | None:
        return self._get_rational_property(self.SUBJECT_DISTANCE)

    def set_subject_distance_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.SUBJECT_DISTANCE, value)

    def get_flash_energy(self) -> str | None:
        return self._get_rational_string(self.FLASH_ENERGY)

    def set_flash_energy(self, value: str | None) -> None:
        self._set_rational_string(self.FLASH_ENERGY, value)

    def get_flash_energy_property(self) -> RationalType | None:
        return self._get_rational_property(self.FLASH_ENERGY)

    def set_flash_energy_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.FLASH_ENERGY, value)

    def get_focal_length(self) -> str | None:
        return self._get_rational_string(self.FOCAL_LENGTH)

    def set_focal_length(self, value: str | None) -> None:
        self._set_rational_string(self.FOCAL_LENGTH, value)

    def get_focal_length_property(self) -> RationalType | None:
        return self._get_rational_property(self.FOCAL_LENGTH)

    def set_focal_length_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.FOCAL_LENGTH, value)

    def get_focal_plane_x_resolution(self) -> str | None:
        return self._get_rational_string(self.FOCAL_PLANE_XRESOLUTION)

    def set_focal_plane_x_resolution(self, value: str | None) -> None:
        self._set_rational_string(self.FOCAL_PLANE_XRESOLUTION, value)

    def get_focal_plane_x_resolution_property(self) -> RationalType | None:
        return self._get_rational_property(self.FOCAL_PLANE_XRESOLUTION)

    def set_focal_plane_x_resolution_property(
        self, value: RationalType | None
    ) -> None:
        self._set_rational_property(self.FOCAL_PLANE_XRESOLUTION, value)

    def get_focal_plane_y_resolution(self) -> str | None:
        return self._get_rational_string(self.FOCAL_PLANE_YRESOLUTION)

    def set_focal_plane_y_resolution(self, value: str | None) -> None:
        self._set_rational_string(self.FOCAL_PLANE_YRESOLUTION, value)

    def get_focal_plane_y_resolution_property(self) -> RationalType | None:
        return self._get_rational_property(self.FOCAL_PLANE_YRESOLUTION)

    def set_focal_plane_y_resolution_property(
        self, value: RationalType | None
    ) -> None:
        self._set_rational_property(self.FOCAL_PLANE_YRESOLUTION, value)

    def get_exposure_index(self) -> str | None:
        return self._get_rational_string(self.EXPOSURE_INDEX)

    def set_exposure_index(self, value: str | None) -> None:
        self._set_rational_string(self.EXPOSURE_INDEX, value)

    def get_exposure_index_property(self) -> RationalType | None:
        return self._get_rational_property(self.EXPOSURE_INDEX)

    def set_exposure_index_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.EXPOSURE_INDEX, value)

    def get_digital_zoom_ratio(self) -> str | None:
        return self._get_rational_string(self.DIGITAL_ZOOM_RATIO)

    def set_digital_zoom_ratio(self, value: str | None) -> None:
        self._set_rational_string(self.DIGITAL_ZOOM_RATIO, value)

    def get_digital_zoom_ratio_property(self) -> RationalType | None:
        return self._get_rational_property(self.DIGITAL_ZOOM_RATIO)

    def set_digital_zoom_ratio_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.DIGITAL_ZOOM_RATIO, value)

    def get_gps_altitude(self) -> str | None:
        return self._get_rational_string(self.GPS_ALTITUDE)

    def set_gps_altitude(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_ALTITUDE, value)

    def get_gps_altitude_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_ALTITUDE)

    def set_gps_altitude_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_ALTITUDE, value)

    def get_gps_dop(self) -> str | None:
        return self._get_rational_string(self.GPS_DOP)

    def set_gps_dop(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_DOP, value)

    def get_gps_dop_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_DOP)

    def set_gps_dop_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_DOP, value)

    def get_gps_speed(self) -> str | None:
        return self._get_rational_string(self.GPS_SPEED)

    def set_gps_speed(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_SPEED, value)

    def get_gps_speed_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_SPEED)

    def set_gps_speed_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_SPEED, value)

    def get_gps_track(self) -> str | None:
        return self._get_rational_string(self.GPS_TRACK)

    def set_gps_track(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_TRACK, value)

    def get_gps_track_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_TRACK)

    def set_gps_track_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_TRACK, value)

    def get_gps_img_direction(self) -> str | None:
        return self._get_rational_string(self.GPS_IMG_DIRECTION)

    def set_gps_img_direction(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_IMG_DIRECTION, value)

    def get_gps_img_direction_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_IMG_DIRECTION)

    def set_gps_img_direction_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_IMG_DIRECTION, value)

    def get_gps_dest_bearing(self) -> str | None:
        return self._get_rational_string(self.GPS_DEST_BEARING)

    def set_gps_dest_bearing(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_DEST_BEARING, value)

    def get_gps_dest_bearing_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_DEST_BEARING)

    def set_gps_dest_bearing_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_DEST_BEARING, value)

    def get_gps_dest_distance(self) -> str | None:
        return self._get_rational_string(self.GPS_DEST_DISTANCE)

    def set_gps_dest_distance(self, value: str | None) -> None:
        self._set_rational_string(self.GPS_DEST_DISTANCE, value)

    def get_gps_dest_distance_property(self) -> RationalType | None:
        return self._get_rational_property(self.GPS_DEST_DISTANCE)

    def set_gps_dest_distance_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.GPS_DEST_DISTANCE, value)

    # --- GPSCoordinate accessors (D,M,S<hemi> wire form) -----------

    def _get_gps_coord_string(self, local_name: str) -> str | None:
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        if isinstance(raw, str):
            return raw
        return self.get_unqualified_text_property_value(local_name)

    def _set_gps_coord_string(self, local_name: str, value: str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        self.set_text_property_value(local_name, value)

    def _get_gps_coord_property(self, local_name: str) -> GPSCoordinateType | None:
        result = self._typed_get(local_name, GPSCoordinateType)
        return result if isinstance(result, GPSCoordinateType) else None

    def _set_gps_coord_property(
        self, local_name: str, value: GPSCoordinateType | None
    ) -> None:
        self._typed_set(local_name, value)

    def get_gps_latitude(self) -> str | None:
        return self._get_gps_coord_string(self.GPS_LATITUDE)

    def set_gps_latitude(self, value: str | None) -> None:
        self._set_gps_coord_string(self.GPS_LATITUDE, value)

    def get_gps_latitude_property(self) -> GPSCoordinateType | None:
        return self._get_gps_coord_property(self.GPS_LATITUDE)

    def set_gps_latitude_property(self, value: GPSCoordinateType | None) -> None:
        self._set_gps_coord_property(self.GPS_LATITUDE, value)

    def get_gps_longitude(self) -> str | None:
        return self._get_gps_coord_string(self.GPS_LONGITUDE)

    def set_gps_longitude(self, value: str | None) -> None:
        self._set_gps_coord_string(self.GPS_LONGITUDE, value)

    def get_gps_longitude_property(self) -> GPSCoordinateType | None:
        return self._get_gps_coord_property(self.GPS_LONGITUDE)

    def set_gps_longitude_property(self, value: GPSCoordinateType | None) -> None:
        self._set_gps_coord_property(self.GPS_LONGITUDE, value)

    def get_gps_dest_latitude(self) -> str | None:
        return self._get_gps_coord_string(self.GPS_DEST_LATITUDE)

    def set_gps_dest_latitude(self, value: str | None) -> None:
        self._set_gps_coord_string(self.GPS_DEST_LATITUDE, value)

    def get_gps_dest_latitude_property(self) -> GPSCoordinateType | None:
        return self._get_gps_coord_property(self.GPS_DEST_LATITUDE)

    def set_gps_dest_latitude_property(
        self, value: GPSCoordinateType | None
    ) -> None:
        self._set_gps_coord_property(self.GPS_DEST_LATITUDE, value)

    def get_gps_dest_longitude(self) -> str | None:
        return self._get_gps_coord_string(self.GPS_DEST_LONGITUDE)

    def set_gps_dest_longitude(self, value: str | None) -> None:
        self._set_gps_coord_string(self.GPS_DEST_LONGITUDE, value)

    def get_gps_dest_longitude_property(self) -> GPSCoordinateType | None:
        return self._get_gps_coord_property(self.GPS_DEST_LONGITUDE)

    def set_gps_dest_longitude_property(
        self, value: GPSCoordinateType | None
    ) -> None:
        self._set_gps_coord_property(self.GPS_DEST_LONGITUDE, value)
