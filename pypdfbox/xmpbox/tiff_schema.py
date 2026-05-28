from __future__ import annotations

from typing import TYPE_CHECKING

from .type import (
    AbstractSimpleProperty,
    AgentNameType,
    Attribute,
    DateType,
    IntegerType,
    LangAlt,
    ProperNameType,
    RationalType,
    TextType,
)
from .type.lang_alt import LANG_ATTR_NAME, XML_NS_URI
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class TiffSchema(XMPSchema):
    """
    Representation of the Adobe TIFF XMP schema.

    Ported from ``org.apache.xmpbox.schema.TIFFSchema`` (PDFBox 3.0). The
    schema captures EXIF/TIFF tag metadata Adobe applications embed alongside
    Dublin Core when archiving raw or developed photos. Per Adobe XMP
    Specification Part 2 the namespace is ``http://ns.adobe.com/tiff/1.0/``
    with preferred prefix ``tiff``. Property local names match upstream
    constants verbatim.

    Wave 39 round-out: layered typed (``TextType`` / ``IntegerType`` /
    ``RationalType`` / ``DateType`` / ``ProperNameType`` / ``AgentNameType``)
    ``*_property`` getter/setter pairs on top of the existing simple
    string/int form accessors. Both forms share the same underlying property
    store: typed setters install an :class:`AbstractSimpleProperty` instance
    under the upstream local name, string-form getters transparently read
    either form, and string-form setters continue to write plain string/int
    values for back-compat.

    Adobe TIFF tags covered (all 30+ per Adobe XMP spec Part 2):

      Image-data structure (Integer):

        * ``ImageWidth`` (tag 256), ``ImageLength`` (tag 257),
          ``Compression`` (tag 259), ``PhotometricInterpretation`` (tag 262),
          ``Orientation`` (tag 274 — 1..8), ``SamplesPerPixel`` (tag 277),
          ``PlanarConfiguration`` (tag 284 — 1=Chunky, 2=Planar),
          ``YCbCrPositioning`` (tag 531), ``ResolutionUnit`` (tag 296).

      Image-data structure (Seq of Integer):

        * ``BitsPerSample`` (tag 258), ``YCbCrSubSampling`` (tag 530),
          ``TransferFunction`` (tag 301).

      Image-data structure (Rational):

        * ``XResolution`` (tag 282), ``YResolution`` (tag 283).

      Image-data structure (Seq of Rational):

        * ``WhitePoint`` (tag 318), ``PrimaryChromaticities`` (tag 319),
          ``YCbCrCoefficients`` (tag 529), ``ReferenceBlackWhite`` (tag 532).

      Recording offsets / data location: not part of XMP — only on disk.

      Date / description (Date / LangAlt / ProperName / AgentName):

        * ``DateTime`` (tag 306, Date), ``ImageDescription`` (tag 270,
          LangAlt), ``Copyright`` (tag 33432, LangAlt), ``Make`` (tag 271,
          ProperName), ``Model`` (tag 272, ProperName), ``Software``
          (tag 305, AgentName), ``Artist`` (tag 315, ProperName).

      Internal:

        * ``NativeDigest`` (Text) — internal property used by Adobe
          applications to detect XMP/legacy-EXIF round-trip mismatches.

    Structured-type wiring: TIFF schema does not declare ``OECFType`` /
    ``CFAPatternType`` properties — those structures live on
    :class:`ExifSchema` (``exif:OECF``, ``exif:SpatialFrequencyResponse``,
    ``exif:CFAPattern``). Wave 1371 added the typed struct wrappers, so any
    EXIF metadata embedded alongside TIFF tags now round-trips through the
    typed-struct API. The Rational accessors provided here keep both a
    string "<num>/<den>" form (round-trip parity with upstream wire format)
    and a typed :class:`RationalType` form (callers can use
    :meth:`RationalType.as_fraction`).
    """

    NAMESPACE = "http://ns.adobe.com/tiff/1.0/"
    PREFERRED_PREFIX = "tiff"

    # Local-name constants — names match upstream ``public static final`` fields.
    IMAGE_DESCRIPTION = "ImageDescription"
    COPYRIGHT = "Copyright"
    ARTIST = "Artist"
    IMAGE_WIDTH = "ImageWidth"
    IMAGE_LENGTH = "ImageLength"
    BITS_PER_SAMPLE = "BitsPerSample"
    COMPRESSION = "Compression"
    PHOTOMETRIC_INTERPRETATION = "PhotometricInterpretation"
    ORIENTATION = "Orientation"
    SAMPLES_PER_PIXEL = "SamplesPerPixel"
    PLANAR_CONFIGURATION = "PlanarConfiguration"
    YCB_CR_SUB_SAMPLING = "YCbCrSubSampling"
    YCB_CR_POSITIONING = "YCbCrPositioning"
    XRESOLUTION = "XResolution"
    YRESOLUTION = "YResolution"
    RESOLUTION_UNIT = "ResolutionUnit"
    TRANSFER_FUNCTION = "TransferFunction"
    WHITE_POINT = "WhitePoint"
    PRIMARY_CHROMATICITIES = "PrimaryChromaticities"
    YCB_CR_COEFFICIENTS = "YCbCrCoefficients"
    REFERENCE_BLACK_WHITE = "ReferenceBlackWhite"
    DATE_TIME = "DateTime"
    SOFTWARE = "Software"
    MAKE = "Make"
    MODEL = "Model"
    NATIVE_DIGEST = "NativeDigest"

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
        text: str | None
        if isinstance(raw, AbstractSimpleProperty):
            text = raw.get_string_value()
            try:
                return int(text.strip())
            except (AttributeError, ValueError):
                return None
        if isinstance(raw, bool):
            # bool subclasses int; reject so True/False can't sneak in.
            return None
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
            if isinstance(value, bool):
                raise TypeError("_set_integer expects int or str, got bool")
            self.set_text_property_value(local_name, str(int(value)))

    def _set_text(self, local_name: str, value: str | None) -> None:
        if value is None:
            self.remove_property(local_name)
            return
        self.set_text_property_value(local_name, value)

    def _read_text_string(self, local_name: str) -> str | None:
        raw = self._properties.get(local_name)
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        return self.get_unqualified_text_property_value(local_name)

    # --- internal: typed-instance helpers ----------------------------

    def _typed_get(
        self, local_name: str, expected: type[AbstractSimpleProperty]
    ) -> AbstractSimpleProperty | None:
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, expected):
            return raw
        try:
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
        except (TypeError, ValueError):
            return None

    def _typed_set(
        self, local_name: str, prop: AbstractSimpleProperty | None
    ) -> None:
        if prop is None:
            self.remove_property(local_name)
            return
        prop.set_property_name(local_name)
        self._properties[local_name] = prop

    # --- internal: rational text/typed helpers -----------------------

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

    # --- internal: LangAlt typed-view fabricator ---------------------

    def _build_lang_alt(self, local_name: str) -> LangAlt | None:
        """
        Synthesize a typed :class:`LangAlt` view from the dict-form storage
        used for LangAlt slots. Mirrors upstream's ``getXxxProperty()``
        accessors which return the underlying ``ArrayProperty`` carrying the
        per-language children. Returns ``None`` when the slot is empty.
        """
        raw = self._properties.get(local_name)
        if not isinstance(raw, dict) or not raw:
            return None
        la = LangAlt(self._metadata, self._namespace, self._prefix, local_name)
        # Emit children in stored dict order — the setters reorganize x-default
        # to the front, while the parser deposits source document order
        # (upstream DomXmpParser does not reorganize on parse). Re-sorting here
        # would override the parser's faithful order and diverge from xmpbox.
        for lang in list(raw.keys()):
            value = raw[lang]
            if not isinstance(value, str):
                continue
            text = TextType(
                self._metadata, self._namespace, self._prefix, local_name, value
            )
            text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, lang))
            la.add_property(text)
        return la

    # --- ImageDescription (LangAlt) ---------------------------------

    def set_image_description(self, value: str) -> None:
        self.set_unqualified_language_property_value(self.IMAGE_DESCRIPTION, None, value)

    def add_image_description(self, lang: str | None, value: str) -> None:
        # Mirror of upstream ``addImageDescription(String lang, String value)``.
        self.set_unqualified_language_property_value(self.IMAGE_DESCRIPTION, lang, value)

    def get_image_description(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.IMAGE_DESCRIPTION, lang)

    def get_image_description_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.IMAGE_DESCRIPTION)

    def remove_image_description(self, lang: str | None = None) -> None:
        """
        Drop the per-language ``ImageDescription`` value identified by
        ``lang`` (defaulting to the ``x-default`` slot). No-op when the
        property or the requested language slot is absent. Convenience
        wrapper over :meth:`remove_unqualified_language_property_value` --
        upstream has no direct equivalent, but the underlying
        ``XMPSchema.removeUnqualifiedLanguagePropertyValue`` is public so
        callers reach the same effect through it.
        """
        self.remove_unqualified_language_property_value(self.IMAGE_DESCRIPTION, lang)

    def get_image_description_property(self) -> LangAlt | None:
        """
        Mirror of upstream ``getImageDescriptionProperty()`` — returns the
        typed :class:`LangAlt` view of the ``ImageDescription`` slot, or
        ``None`` when no value has been set. Upstream returns the raw
        ``ArrayProperty``; :class:`LangAlt` is our typed subclass.
        """
        return self._build_lang_alt(self.IMAGE_DESCRIPTION)

    # --- Copyright (LangAlt) ----------------------------------------

    def set_copyright(self, value: str) -> None:
        self.set_unqualified_language_property_value(self.COPYRIGHT, None, value)

    def add_copyright(self, lang: str | None, value: str) -> None:
        # Mirror of upstream ``addCopyright(String lang, String value)``.
        self.set_unqualified_language_property_value(self.COPYRIGHT, lang, value)

    def get_copyright(self, lang: str | None = None) -> str | None:
        return self.get_unqualified_language_property_value(self.COPYRIGHT, lang)

    def get_copyright_languages(self) -> list[str] | None:
        return self.get_unqualified_language_property_languages_value(self.COPYRIGHT)

    def remove_copyright(self, lang: str | None = None) -> None:
        """
        Drop the per-language ``Copyright`` value identified by ``lang``
        (defaulting to the ``x-default`` slot). No-op when the property or
        the requested language slot is absent. Convenience wrapper over
        :meth:`remove_unqualified_language_property_value`.
        """
        self.remove_unqualified_language_property_value(self.COPYRIGHT, lang)

    def get_copyright_property(self) -> LangAlt | None:
        """
        Mirror of upstream ``getCopyrightProperty()`` — returns the typed
        :class:`LangAlt` view of the ``Copyright`` slot, or ``None`` when no
        value has been set.
        """
        return self._build_lang_alt(self.COPYRIGHT)

    # --- Artist (ProperName) ----------------------------------------

    def get_artist(self) -> str | None:
        return self._read_text_string(self.ARTIST)

    def set_artist(self, value: str | None) -> None:
        self._set_text(self.ARTIST, value)

    def get_artist_property(self) -> ProperNameType | None:
        result = self._typed_get(self.ARTIST, ProperNameType)
        return result if isinstance(result, ProperNameType) else None

    def set_artist_property(self, value: ProperNameType | None) -> None:
        self._typed_set(self.ARTIST, value)

    # --- Make (ProperName) ------------------------------------------

    def get_make(self) -> str | None:
        return self._read_text_string(self.MAKE)

    def set_make(self, value: str | None) -> None:
        self._set_text(self.MAKE, value)

    def get_make_property(self) -> ProperNameType | None:
        result = self._typed_get(self.MAKE, ProperNameType)
        return result if isinstance(result, ProperNameType) else None

    def set_make_property(self, value: ProperNameType | None) -> None:
        self._typed_set(self.MAKE, value)

    # --- Model (ProperName) -----------------------------------------

    def get_model(self) -> str | None:
        return self._read_text_string(self.MODEL)

    def set_model(self, value: str | None) -> None:
        self._set_text(self.MODEL, value)

    def get_model_property(self) -> ProperNameType | None:
        result = self._typed_get(self.MODEL, ProperNameType)
        return result if isinstance(result, ProperNameType) else None

    def set_model_property(self, value: ProperNameType | None) -> None:
        self._typed_set(self.MODEL, value)

    # --- Software (AgentName) ---------------------------------------

    def get_software(self) -> str | None:
        return self._read_text_string(self.SOFTWARE)

    def set_software(self, value: str | None) -> None:
        self._set_text(self.SOFTWARE, value)

    def get_software_property(self) -> AgentNameType | None:
        result = self._typed_get(self.SOFTWARE, AgentNameType)
        return result if isinstance(result, AgentNameType) else None

    def set_software_property(self, value: AgentNameType | None) -> None:
        self._typed_set(self.SOFTWARE, value)

    # --- DateTime (Date) --------------------------------------------

    def get_date_time(self) -> str | None:
        return self._read_text_string(self.DATE_TIME)

    def set_date_time(self, value: str | None) -> None:
        self._set_text(self.DATE_TIME, value)

    def get_date_time_property(self) -> DateType | None:
        result = self._typed_get(self.DATE_TIME, DateType)
        return result if isinstance(result, DateType) else None

    def set_date_time_property(self, value: DateType | None) -> None:
        self._typed_set(self.DATE_TIME, value)

    # --- NativeDigest (Text) ----------------------------------------

    def get_native_digest(self) -> str | None:
        return self._read_text_string(self.NATIVE_DIGEST)

    def set_native_digest(self, value: str | None) -> None:
        self._set_text(self.NATIVE_DIGEST, value)

    def get_native_digest_property(self) -> TextType | None:
        result = self._typed_get(self.NATIVE_DIGEST, TextType)
        return result if isinstance(result, TextType) else None

    def set_native_digest_property(self, value: TextType | None) -> None:
        self._typed_set(self.NATIVE_DIGEST, value)

    # --- ImageWidth / ImageLength (Integer) -------------------------

    def get_image_width(self) -> int | None:
        return self._get_integer(self.IMAGE_WIDTH)

    def set_image_width(self, value: int | str | None) -> None:
        self._set_integer(self.IMAGE_WIDTH, value)

    def get_image_width_property(self) -> IntegerType | None:
        result = self._typed_get(self.IMAGE_WIDTH, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_image_width_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.IMAGE_WIDTH, value)

    def get_image_length(self) -> int | None:
        return self._get_integer(self.IMAGE_LENGTH)

    def set_image_length(self, value: int | str | None) -> None:
        self._set_integer(self.IMAGE_LENGTH, value)

    def get_image_length_property(self) -> IntegerType | None:
        result = self._typed_get(self.IMAGE_LENGTH, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_image_length_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.IMAGE_LENGTH, value)

    # --- Compression / PhotometricInterpretation (Integer) ----------

    def get_compression(self) -> int | None:
        return self._get_integer(self.COMPRESSION)

    def set_compression(self, value: int | str | None) -> None:
        self._set_integer(self.COMPRESSION, value)

    def get_compression_property(self) -> IntegerType | None:
        result = self._typed_get(self.COMPRESSION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_compression_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.COMPRESSION, value)

    def get_photometric_interpretation(self) -> int | None:
        return self._get_integer(self.PHOTOMETRIC_INTERPRETATION)

    def set_photometric_interpretation(self, value: int | str | None) -> None:
        self._set_integer(self.PHOTOMETRIC_INTERPRETATION, value)

    def get_photometric_interpretation_property(self) -> IntegerType | None:
        result = self._typed_get(self.PHOTOMETRIC_INTERPRETATION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_photometric_interpretation_property(
        self, value: IntegerType | None
    ) -> None:
        self._typed_set(self.PHOTOMETRIC_INTERPRETATION, value)

    # --- Orientation / SamplesPerPixel / PlanarConfiguration --------

    def get_orientation(self) -> int | None:
        return self._get_integer(self.ORIENTATION)

    def set_orientation(self, value: int | str | None) -> None:
        self._set_integer(self.ORIENTATION, value)

    def get_orientation_property(self) -> IntegerType | None:
        result = self._typed_get(self.ORIENTATION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_orientation_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.ORIENTATION, value)

    def get_samples_per_pixel(self) -> int | None:
        return self._get_integer(self.SAMPLES_PER_PIXEL)

    def set_samples_per_pixel(self, value: int | str | None) -> None:
        self._set_integer(self.SAMPLES_PER_PIXEL, value)

    def get_samples_per_pixel_property(self) -> IntegerType | None:
        result = self._typed_get(self.SAMPLES_PER_PIXEL, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_samples_per_pixel_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.SAMPLES_PER_PIXEL, value)

    def get_planar_configuration(self) -> int | None:
        return self._get_integer(self.PLANAR_CONFIGURATION)

    def set_planar_configuration(self, value: int | str | None) -> None:
        self._set_integer(self.PLANAR_CONFIGURATION, value)

    def get_planar_configuration_property(self) -> IntegerType | None:
        result = self._typed_get(self.PLANAR_CONFIGURATION, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_planar_configuration_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.PLANAR_CONFIGURATION, value)

    # --- YCbCrPositioning / ResolutionUnit (Integer) ----------------

    def get_y_cb_cr_positioning(self) -> int | None:
        return self._get_integer(self.YCB_CR_POSITIONING)

    def set_y_cb_cr_positioning(self, value: int | str | None) -> None:
        self._set_integer(self.YCB_CR_POSITIONING, value)

    def get_y_cb_cr_positioning_property(self) -> IntegerType | None:
        result = self._typed_get(self.YCB_CR_POSITIONING, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_y_cb_cr_positioning_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.YCB_CR_POSITIONING, value)

    def get_resolution_unit(self) -> int | None:
        return self._get_integer(self.RESOLUTION_UNIT)

    def set_resolution_unit(self, value: int | str | None) -> None:
        self._set_integer(self.RESOLUTION_UNIT, value)

    def get_resolution_unit_property(self) -> IntegerType | None:
        result = self._typed_get(self.RESOLUTION_UNIT, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_resolution_unit_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.RESOLUTION_UNIT, value)

    # --- BitsPerSample / YCbCrSubSampling / TransferFunction (Seq) --

    def add_bits_per_sample(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.BITS_PER_SAMPLE,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_bits_per_sample(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.BITS_PER_SAMPLE)

    def add_y_cb_cr_sub_sampling(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.YCB_CR_SUB_SAMPLING,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_y_cb_cr_sub_sampling(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.YCB_CR_SUB_SAMPLING)

    def add_transfer_function(self, value: int | str) -> None:
        self.add_unqualified_sequence_value(
            self.TRANSFER_FUNCTION,
            value if isinstance(value, str) else str(int(value)),
        )

    def get_transfer_function(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.TRANSFER_FUNCTION)

    # --- XResolution / YResolution (Rational, "num/den") ------------

    def get_x_resolution(self) -> str | None:
        return self._get_rational_string(self.XRESOLUTION)

    def set_x_resolution(self, value: str | None) -> None:
        self._set_rational_string(self.XRESOLUTION, value)

    def get_x_resolution_property(self) -> RationalType | None:
        return self._get_rational_property(self.XRESOLUTION)

    def set_x_resolution_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.XRESOLUTION, value)

    def get_y_resolution(self) -> str | None:
        return self._get_rational_string(self.YRESOLUTION)

    def set_y_resolution(self, value: str | None) -> None:
        self._set_rational_string(self.YRESOLUTION, value)

    def get_y_resolution_property(self) -> RationalType | None:
        return self._get_rational_property(self.YRESOLUTION)

    def set_y_resolution_property(self, value: RationalType | None) -> None:
        self._set_rational_property(self.YRESOLUTION, value)

    # --- WhitePoint / PrimaryChromaticities / YCbCrCoefficients /
    # ReferenceBlackWhite (Seq of Rational, stored as "num/den") -----

    def add_white_point(self, value: str) -> None:
        self.add_unqualified_sequence_value(self.WHITE_POINT, value)

    def get_white_point(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.WHITE_POINT)

    def add_primary_chromaticities(self, value: str) -> None:
        self.add_unqualified_sequence_value(self.PRIMARY_CHROMATICITIES, value)

    def get_primary_chromaticities(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.PRIMARY_CHROMATICITIES)

    def add_y_cb_cr_coefficients(self, value: str) -> None:
        self.add_unqualified_sequence_value(self.YCB_CR_COEFFICIENTS, value)

    def get_y_cb_cr_coefficients(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.YCB_CR_COEFFICIENTS)

    def add_reference_black_white(self, value: str) -> None:
        self.add_unqualified_sequence_value(self.REFERENCE_BLACK_WHITE, value)

    def get_reference_black_white(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.REFERENCE_BLACK_WHITE)
