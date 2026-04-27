from __future__ import annotations

from typing import TYPE_CHECKING

from .type import (
    AbstractSimpleProperty,
    DateType,
    IntegerType,
    ProperNameType,
    TextType,
    URIType,
)
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class PhotoshopSchema(XMPSchema):
    """
    Representation of the Adobe Photoshop XMP schema.

    Ported (read+write path) from
    ``org.apache.xmpbox.schema.PhotoshopSchema`` (PDFBox 3.0). The schema
    captures the Photoshop-specific IPTC-style metadata Adobe applications
    embed alongside Dublin Core. Per Adobe XMP Specification Part 2 the
    namespace is ``http://ns.adobe.com/photoshop/1.0/`` with preferred prefix
    ``photoshop``. Property local names match upstream constants verbatim.

    This schema layers typed (``TextType`` / ``IntegerType`` / ``URIType`` /
    ``ProperNameType`` / ``DateType``) ``*_property`` getter/setter pairs on
    top of the existing simple string-form accessors. Both forms share the
    same underlying property store: typed setters install an
    :class:`AbstractSimpleProperty` instance under the upstream local-name,
    string-form getters transparently read either form, and string-form
    setters continue to write plain string/int values for back-compat.

      * ``AncestorID`` (URI) — reference to a parent document.
      * ``AuthorsPosition`` (Text) — author's job title.
      * ``CaptionWriter`` (ProperName) — writer / editor of the caption.
      * ``Category`` (Text) — IPTC short-form category code.
      * ``City`` (Text) — city the image was created in.
      * ``ColorMode`` (Integer) — Photoshop colour-mode enum
        (0=Bitmap, 1=Grayscale, 2=Indexed, 3=RGB, 4=CMYK, 7=Multichannel,
        8=Duotone, 9=Lab).
      * ``Country`` (Text) — country the image was created in.
      * ``Credit`` (Text) — IPTC credit line.
      * ``DateCreated`` (Date) — creation date (XMP date string).
      * ``DocumentAncestors`` (Bag of Text) — list of ancestor document IDs.
      * ``Headline`` (Text) — IPTC headline.
      * ``History`` (Text) — Photoshop edit history string.
      * ``ICCProfile`` (Text) — name of the embedded ICC profile.
      * ``Instructions`` (Text) — IPTC special instructions.
      * ``Source`` (Text) — IPTC source.
      * ``State`` (Text) — state/province the image was created in.
      * ``SupplementalCategories`` (Text) — IPTC supplemental category.
      * ``TextLayers`` (Seq of LayerType) — Photoshop text-layer descriptors.
      * ``TransmissionReference`` (Text) — IPTC original transmission reference.
      * ``Urgency`` (Integer) — IPTC urgency, 1..8.

    Deferred until the typed ``LayerType`` struct lands (see CHANGES note for
    Wave 32): full ``TextLayers`` round-trip. Callers needing raw access
    before the wrapper ships can use the generic
    :meth:`XMPSchema.get_property` accessor.
    """

    NAMESPACE = "http://ns.adobe.com/photoshop/1.0/"
    PREFERRED_PREFIX = "photoshop"

    # Local-name constants — names match upstream ``public static final`` fields.
    ANCESTORID = "AncestorID"
    AUTHORS_POSITION = "AuthorsPosition"
    CAPTION_WRITER = "CaptionWriter"
    CATEGORY = "Category"
    CITY = "City"
    COLOR_MODE = "ColorMode"
    COUNTRY = "Country"
    CREDIT = "Credit"
    DATE_CREATED = "DateCreated"
    DOCUMENT_ANCESTORS = "DocumentAncestors"
    HEADLINE = "Headline"
    HISTORY = "History"
    ICC_PROFILE = "ICCProfile"
    INSTRUCTIONS = "Instructions"
    SOURCE = "Source"
    STATE = "State"
    SUPPLEMENTAL_CATEGORIES = "SupplementalCategories"
    TEXT_LAYERS = "TextLayers"
    TRANSMISSION_REFERENCE = "TransmissionReference"
    URGENCY = "Urgency"

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
            # bool is a subclass of int in Python; reject it explicitly so a
            # caller can't accidentally store True/False under an integer slot.
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

    # --- internal: typed-instance read helpers -----------------------

    def _read_text_string(self, local_name: str) -> str | None:
        """
        Reach through either a typed :class:`AbstractSimpleProperty` instance
        installed via a ``set_xxx_property`` call or a plain string written by
        the simple ``set_xxx`` form. Used by every string-form Text getter so
        the two storage forms stay interchangeable.
        """
        raw = self._properties.get(local_name)
        if isinstance(raw, AbstractSimpleProperty):
            value = raw.get_string_value()
            return value if isinstance(value, str) else None
        return self.get_unqualified_text_property_value(local_name)

    def _typed_get(
        self, local_name: str, expected: type[AbstractSimpleProperty]
    ) -> AbstractSimpleProperty | None:
        """
        Return the typed wrapper for ``local_name``: if the slot already holds
        an instance of ``expected`` (or any :class:`AbstractSimpleProperty`),
        return it as-is; if it holds a plain string/int written by the
        simple-form setter, wrap it on the fly so callers always get a typed
        view. Returns ``None`` when the property is absent.
        """
        raw = self._properties.get(local_name)
        if raw is None:
            return None
        if isinstance(raw, expected):
            return raw
        if isinstance(raw, AbstractSimpleProperty):
            # Cross-type request (e.g. asked for URIType, slot holds TextType
            # because the parser was generic). Re-wrap from the string form.
            return expected(
                self._metadata,
                self._namespace,
                self._prefix,
                local_name,
                raw.get_string_value(),
            )
        # Plain string / int from the simple-form setter or parser.
        return expected(
            self._metadata, self._namespace, self._prefix, local_name, raw
        )

    def _typed_set(
        self, local_name: str, prop: AbstractSimpleProperty | None
    ) -> None:
        if prop is None:
            self.remove_property(local_name)
            return
        # Mirror upstream addProperty(AbstractField): keep the upstream local
        # name on the field and store the typed instance in the slot.
        prop.set_property_name(local_name)
        self._properties[local_name] = prop

    # --- AncestorID (URI) --------------------------------------------

    def get_ancestor_id(self) -> str | None:
        return self._read_text_string(self.ANCESTORID)

    def set_ancestor_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ANCESTORID)
            return
        self.set_text_property_value(self.ANCESTORID, value)

    def get_ancestor_id_property(self) -> URIType | None:
        result = self._typed_get(self.ANCESTORID, URIType)
        return result if isinstance(result, URIType) else None

    def set_ancestor_id_property(self, value: URIType | None) -> None:
        self._typed_set(self.ANCESTORID, value)

    # --- AuthorsPosition (Text) --------------------------------------

    def get_authors_position(self) -> str | None:
        return self._read_text_string(self.AUTHORS_POSITION)

    def set_authors_position(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.AUTHORS_POSITION)
            return
        self.set_text_property_value(self.AUTHORS_POSITION, value)

    def get_authors_position_property(self) -> TextType | None:
        result = self._typed_get(self.AUTHORS_POSITION, TextType)
        return result if isinstance(result, TextType) else None

    def set_authors_position_property(self, value: TextType | None) -> None:
        self._typed_set(self.AUTHORS_POSITION, value)

    # --- CaptionWriter (ProperName) ----------------------------------

    def get_caption_writer(self) -> str | None:
        return self._read_text_string(self.CAPTION_WRITER)

    def set_caption_writer(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CAPTION_WRITER)
            return
        self.set_text_property_value(self.CAPTION_WRITER, value)

    def get_caption_writer_property(self) -> ProperNameType | None:
        result = self._typed_get(self.CAPTION_WRITER, ProperNameType)
        return result if isinstance(result, ProperNameType) else None

    def set_caption_writer_property(self, value: ProperNameType | None) -> None:
        self._typed_set(self.CAPTION_WRITER, value)

    # --- Category (Text) ---------------------------------------------

    def get_category(self) -> str | None:
        return self._read_text_string(self.CATEGORY)

    def set_category(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CATEGORY)
            return
        self.set_text_property_value(self.CATEGORY, value)

    def get_category_property(self) -> TextType | None:
        result = self._typed_get(self.CATEGORY, TextType)
        return result if isinstance(result, TextType) else None

    def set_category_property(self, value: TextType | None) -> None:
        self._typed_set(self.CATEGORY, value)

    # --- City (Text) -------------------------------------------------

    def get_city(self) -> str | None:
        return self._read_text_string(self.CITY)

    def set_city(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CITY)
            return
        self.set_text_property_value(self.CITY, value)

    def get_city_property(self) -> TextType | None:
        result = self._typed_get(self.CITY, TextType)
        return result if isinstance(result, TextType) else None

    def set_city_property(self, value: TextType | None) -> None:
        self._typed_set(self.CITY, value)

    # --- ColorMode (Integer) -----------------------------------------

    def get_color_mode(self) -> int | None:
        return self._get_integer(self.COLOR_MODE)

    def set_color_mode(self, value: int | str | None) -> None:
        self._set_integer(self.COLOR_MODE, value)

    def get_color_mode_property(self) -> IntegerType | None:
        result = self._typed_get(self.COLOR_MODE, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_color_mode_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.COLOR_MODE, value)

    # --- Country (Text) ----------------------------------------------

    def get_country(self) -> str | None:
        return self._read_text_string(self.COUNTRY)

    def set_country(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.COUNTRY)
            return
        self.set_text_property_value(self.COUNTRY, value)

    def get_country_property(self) -> TextType | None:
        result = self._typed_get(self.COUNTRY, TextType)
        return result if isinstance(result, TextType) else None

    def set_country_property(self, value: TextType | None) -> None:
        self._typed_set(self.COUNTRY, value)

    # --- Credit (Text) -----------------------------------------------

    def get_credit(self) -> str | None:
        return self._read_text_string(self.CREDIT)

    def set_credit(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CREDIT)
            return
        self.set_text_property_value(self.CREDIT, value)

    def get_credit_property(self) -> TextType | None:
        result = self._typed_get(self.CREDIT, TextType)
        return result if isinstance(result, TextType) else None

    def set_credit_property(self, value: TextType | None) -> None:
        self._typed_set(self.CREDIT, value)

    # --- DateCreated (Date) ------------------------------------------

    def get_date_created(self) -> str | None:
        return self._read_text_string(self.DATE_CREATED)

    def set_date_created(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.DATE_CREATED)
            return
        self.set_text_property_value(self.DATE_CREATED, value)

    def get_date_created_property(self) -> DateType | None:
        result = self._typed_get(self.DATE_CREATED, DateType)
        return result if isinstance(result, DateType) else None

    def set_date_created_property(self, value: DateType | None) -> None:
        self._typed_set(self.DATE_CREATED, value)

    # --- DocumentAncestors (Bag of Text) ------------------------------

    def add_document_ancestors(self, value: str) -> None:
        self.add_qualified_bag_value(self.DOCUMENT_ANCESTORS, value)

    def get_document_ancestors(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.DOCUMENT_ANCESTORS)

    def set_document_ancestors(self, values: list[str] | None) -> None:
        if values is None:
            self.remove_property(self.DOCUMENT_ANCESTORS)
            return
        self._properties[self.DOCUMENT_ANCESTORS] = list(values)

    # --- Headline (Text) ---------------------------------------------

    def get_headline(self) -> str | None:
        return self._read_text_string(self.HEADLINE)

    def set_headline(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.HEADLINE)
            return
        self.set_text_property_value(self.HEADLINE, value)

    def get_headline_property(self) -> TextType | None:
        result = self._typed_get(self.HEADLINE, TextType)
        return result if isinstance(result, TextType) else None

    def set_headline_property(self, value: TextType | None) -> None:
        self._typed_set(self.HEADLINE, value)

    # --- History (Text) ----------------------------------------------

    def get_history(self) -> str | None:
        return self._read_text_string(self.HISTORY)

    def set_history(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.HISTORY)
            return
        self.set_text_property_value(self.HISTORY, value)

    def get_history_property(self) -> TextType | None:
        result = self._typed_get(self.HISTORY, TextType)
        return result if isinstance(result, TextType) else None

    def set_history_property(self, value: TextType | None) -> None:
        self._typed_set(self.HISTORY, value)

    # --- ICCProfile (Text) -------------------------------------------

    def get_icc_profile(self) -> str | None:
        return self._read_text_string(self.ICC_PROFILE)

    def set_icc_profile(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ICC_PROFILE)
            return
        self.set_text_property_value(self.ICC_PROFILE, value)

    def get_icc_profile_property(self) -> TextType | None:
        result = self._typed_get(self.ICC_PROFILE, TextType)
        return result if isinstance(result, TextType) else None

    def set_icc_profile_property(self, value: TextType | None) -> None:
        self._typed_set(self.ICC_PROFILE, value)

    # --- Instructions (Text) -----------------------------------------

    def get_instructions(self) -> str | None:
        return self._read_text_string(self.INSTRUCTIONS)

    def set_instructions(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.INSTRUCTIONS)
            return
        self.set_text_property_value(self.INSTRUCTIONS, value)

    def get_instructions_property(self) -> TextType | None:
        result = self._typed_get(self.INSTRUCTIONS, TextType)
        return result if isinstance(result, TextType) else None

    def set_instructions_property(self, value: TextType | None) -> None:
        self._typed_set(self.INSTRUCTIONS, value)

    # --- Source (Text) -----------------------------------------------

    def get_source(self) -> str | None:
        return self._read_text_string(self.SOURCE)

    def set_source(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.SOURCE)
            return
        self.set_text_property_value(self.SOURCE, value)

    def get_source_property(self) -> TextType | None:
        result = self._typed_get(self.SOURCE, TextType)
        return result if isinstance(result, TextType) else None

    def set_source_property(self, value: TextType | None) -> None:
        self._typed_set(self.SOURCE, value)

    # --- State (Text) ------------------------------------------------

    def get_state(self) -> str | None:
        return self._read_text_string(self.STATE)

    def set_state(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.STATE)
            return
        self.set_text_property_value(self.STATE, value)

    def get_state_property(self) -> TextType | None:
        result = self._typed_get(self.STATE, TextType)
        return result if isinstance(result, TextType) else None

    def set_state_property(self, value: TextType | None) -> None:
        self._typed_set(self.STATE, value)

    # --- SupplementalCategories (Text) -------------------------------

    def get_supplemental_categories(self) -> str | None:
        return self._read_text_string(self.SUPPLEMENTAL_CATEGORIES)

    def set_supplemental_categories(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.SUPPLEMENTAL_CATEGORIES)
            return
        self.set_text_property_value(self.SUPPLEMENTAL_CATEGORIES, value)

    def get_supplemental_categories_property(self) -> TextType | None:
        result = self._typed_get(self.SUPPLEMENTAL_CATEGORIES, TextType)
        return result if isinstance(result, TextType) else None

    def set_supplemental_categories_property(self, value: TextType | None) -> None:
        self._typed_set(self.SUPPLEMENTAL_CATEGORIES, value)

    # --- TransmissionReference (Text) --------------------------------

    def get_transmission_reference(self) -> str | None:
        return self._read_text_string(self.TRANSMISSION_REFERENCE)

    def set_transmission_reference(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.TRANSMISSION_REFERENCE)
            return
        self.set_text_property_value(self.TRANSMISSION_REFERENCE, value)

    def get_transmission_reference_property(self) -> TextType | None:
        result = self._typed_get(self.TRANSMISSION_REFERENCE, TextType)
        return result if isinstance(result, TextType) else None

    def set_transmission_reference_property(self, value: TextType | None) -> None:
        self._typed_set(self.TRANSMISSION_REFERENCE, value)

    # --- Urgency (Integer) -------------------------------------------

    def get_urgency(self) -> int | None:
        return self._get_integer(self.URGENCY)

    def set_urgency(self, value: int | str | None) -> None:
        self._set_integer(self.URGENCY, value)

    def get_urgency_property(self) -> IntegerType | None:
        result = self._typed_get(self.URGENCY, IntegerType)
        return result if isinstance(result, IntegerType) else None

    def set_urgency_property(self, value: IntegerType | None) -> None:
        self._typed_set(self.URGENCY, value)
