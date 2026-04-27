from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class TiffSchema(XMPSchema):
    """
    Representation of the Adobe TIFF XMP schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.TiffSchema`` (PDFBox 3.0). The schema captures
    EXIF/TIFF tag metadata (``tiff:Make``, ``tiff:Model``, image dimensions,
    resolution, etc.) Adobe applications embed alongside Dublin Core when
    archiving raw or developed photos. Per Adobe XMP Specification Part 2 the
    namespace is ``http://ns.adobe.com/tiff/1.0/`` with preferred prefix
    ``tiff``. Property local names match upstream constants verbatim.

    Substitute target — upstream PDFBox 3.0.x does **not** ship a
    ``CameraRawSchema`` (the public xmpbox skips Camera Raw), so this port
    fills the closest sibling: TIFF / camera-tag metadata. ``ExifSchema`` is
    a separate, larger sibling and is left for a follow-up cluster.

    Cluster ships text-typed accessors for the LangAlt-cardinality properties
    (``ImageDescription`` / ``Copyright``), simple-string accessors for the
    ProperName / AgentName / Date / Text properties, integer accessors for
    the simple Integer properties, and Seq-of-string accessors for the array
    properties:

      * ``ImageDescription`` (LangAlt) — caption / description.
      * ``Copyright`` (LangAlt) — copyright notice.
      * ``Artist`` (ProperName) — image creator.
      * ``Make`` (ProperName) — camera manufacturer.
      * ``Model`` (ProperName) — camera model.
      * ``Software`` (AgentName) — capture / processing software.
      * ``DateTime`` (Date) — file change date/time (XMP date string).
      * ``ImageWidth`` / ``ImageLength`` (Integer) — image pixel dimensions.
      * ``Compression`` (Integer) — TIFF compression scheme tag.
      * ``PhotometricInterpretation`` (Integer) — TIFF tag 262.
      * ``Orientation`` (Integer) — TIFF tag 274 (1..8).
      * ``SamplesPerPixel`` (Integer) — TIFF tag 277.
      * ``PlanarConfiguration`` (Integer) — TIFF tag 284 (1=Chunky, 2=Planar).
      * ``YCbCrPositioning`` (Integer) — TIFF tag 531.
      * ``ResolutionUnit`` (Integer) — TIFF tag 296.
      * ``BitsPerSample`` (Seq of Integer, stored as strings).
      * ``YCbCrSubSampling`` (Seq of Integer, stored as strings).
      * ``TransferFunction`` (Seq of Integer, stored as strings).
      * ``XResolution`` / ``YResolution`` (Rational, stored as the upstream
        ``"num/den"`` text form).
      * ``WhitePoint``, ``PrimaryChromaticities``, ``YCbCrCoefficients``,
        ``ReferenceBlackWhite`` (Seq of Rational, stored as ``"num/den"``).

    Deferred until the typed ``RationalType`` and ``OECFType`` structs land:
    typed Rational round-trip with numerator/denominator accessors. Callers
    that need raw access before those wrappers ship can use the generic
    :meth:`XMPSchema.get_property` accessor or the ``"num/den"`` string form.
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

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- internal: integer text round-trip ---------------------------

    def _get_integer(self, local_name: str) -> int | None:
        """Read an Integer-typed property, accepting both int and string forms."""
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, bool):
            # bool subclasses int; reject so True/False can't sneak in.
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

    # --- Artist (ProperName) ----------------------------------------

    def get_artist(self) -> str | None:
        return self.get_unqualified_text_property_value(self.ARTIST)

    def set_artist(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ARTIST)
            return
        self.set_text_property_value(self.ARTIST, value)

    # --- Make / Model / Software (ProperName / AgentName) -----------

    def get_make(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MAKE)

    def set_make(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MAKE)
            return
        self.set_text_property_value(self.MAKE, value)

    def get_model(self) -> str | None:
        return self.get_unqualified_text_property_value(self.MODEL)

    def set_model(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.MODEL)
            return
        self.set_text_property_value(self.MODEL, value)

    def get_software(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SOFTWARE)

    def set_software(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.SOFTWARE)
            return
        self.set_text_property_value(self.SOFTWARE, value)

    # --- DateTime (Date) --------------------------------------------

    def get_date_time(self) -> str | None:
        return self.get_unqualified_text_property_value(self.DATE_TIME)

    def set_date_time(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.DATE_TIME)
            return
        self.set_text_property_value(self.DATE_TIME, value)

    # --- ImageWidth / ImageLength (Integer) -------------------------

    def get_image_width(self) -> int | None:
        return self._get_integer(self.IMAGE_WIDTH)

    def set_image_width(self, value: int | str | None) -> None:
        self._set_integer(self.IMAGE_WIDTH, value)

    def get_image_length(self) -> int | None:
        return self._get_integer(self.IMAGE_LENGTH)

    def set_image_length(self, value: int | str | None) -> None:
        self._set_integer(self.IMAGE_LENGTH, value)

    # --- Compression / PhotometricInterpretation (Integer) ----------

    def get_compression(self) -> int | None:
        return self._get_integer(self.COMPRESSION)

    def set_compression(self, value: int | str | None) -> None:
        self._set_integer(self.COMPRESSION, value)

    def get_photometric_interpretation(self) -> int | None:
        return self._get_integer(self.PHOTOMETRIC_INTERPRETATION)

    def set_photometric_interpretation(self, value: int | str | None) -> None:
        self._set_integer(self.PHOTOMETRIC_INTERPRETATION, value)

    # --- Orientation / SamplesPerPixel / PlanarConfiguration --------

    def get_orientation(self) -> int | None:
        return self._get_integer(self.ORIENTATION)

    def set_orientation(self, value: int | str | None) -> None:
        self._set_integer(self.ORIENTATION, value)

    def get_samples_per_pixel(self) -> int | None:
        return self._get_integer(self.SAMPLES_PER_PIXEL)

    def set_samples_per_pixel(self, value: int | str | None) -> None:
        self._set_integer(self.SAMPLES_PER_PIXEL, value)

    def get_planar_configuration(self) -> int | None:
        return self._get_integer(self.PLANAR_CONFIGURATION)

    def set_planar_configuration(self, value: int | str | None) -> None:
        self._set_integer(self.PLANAR_CONFIGURATION, value)

    # --- YCbCrPositioning / ResolutionUnit (Integer) ----------------

    def get_y_cb_cr_positioning(self) -> int | None:
        return self._get_integer(self.YCB_CR_POSITIONING)

    def set_y_cb_cr_positioning(self, value: int | str | None) -> None:
        self._set_integer(self.YCB_CR_POSITIONING, value)

    def get_resolution_unit(self) -> int | None:
        return self._get_integer(self.RESOLUTION_UNIT)

    def set_resolution_unit(self, value: int | str | None) -> None:
        self._set_integer(self.RESOLUTION_UNIT, value)

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
        return self.get_unqualified_text_property_value(self.XRESOLUTION)

    def set_x_resolution(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.XRESOLUTION)
            return
        self.set_text_property_value(self.XRESOLUTION, value)

    def get_y_resolution(self) -> str | None:
        return self.get_unqualified_text_property_value(self.YRESOLUTION)

    def set_y_resolution(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.YRESOLUTION)
            return
        self.set_text_property_value(self.YRESOLUTION, value)

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
