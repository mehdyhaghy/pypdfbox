from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class PhotoshopSchema(XMPSchema):
    """
    Representation of the Adobe Photoshop XMP schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.PhotoshopSchema`` (PDFBox 3.0). The schema
    captures the Photoshop-specific IPTC-style metadata Adobe applications
    embed alongside Dublin Core. Per Adobe XMP Specification Part 2 the
    namespace is ``http://ns.adobe.com/photoshop/1.0/`` with preferred prefix
    ``photoshop``. Property local names match upstream constants verbatim.

    Cluster #1 ships text-typed accessors for the simple (string) properties
    and an integer-typed pair for ``ColorMode`` / ``Urgency``:

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

    Deferred until the typed ``LayerType`` struct lands (see cluster #1 plan):
    full ``TextLayers`` round-trip. Callers needing raw access before the
    wrapper ships can use the generic :meth:`XMPSchema.get_property` accessor.
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

    # --- AncestorID (URI) --------------------------------------------

    def get_ancestor_id(self) -> str | None:
        return self.get_unqualified_text_property_value(self.ANCESTORID)

    def set_ancestor_id(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ANCESTORID)
            return
        self.set_text_property_value(self.ANCESTORID, value)

    # --- AuthorsPosition (Text) --------------------------------------

    def get_authors_position(self) -> str | None:
        return self.get_unqualified_text_property_value(self.AUTHORS_POSITION)

    def set_authors_position(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.AUTHORS_POSITION)
            return
        self.set_text_property_value(self.AUTHORS_POSITION, value)

    # --- CaptionWriter (ProperName) ----------------------------------

    def get_caption_writer(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CAPTION_WRITER)

    def set_caption_writer(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CAPTION_WRITER)
            return
        self.set_text_property_value(self.CAPTION_WRITER, value)

    # --- Category (Text) ---------------------------------------------

    def get_category(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CATEGORY)

    def set_category(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CATEGORY)
            return
        self.set_text_property_value(self.CATEGORY, value)

    # --- City (Text) -------------------------------------------------

    def get_city(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CITY)

    def set_city(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CITY)
            return
        self.set_text_property_value(self.CITY, value)

    # --- ColorMode (Integer) -----------------------------------------

    def get_color_mode(self) -> int | None:
        return self._get_integer(self.COLOR_MODE)

    def set_color_mode(self, value: int | str | None) -> None:
        self._set_integer(self.COLOR_MODE, value)

    # --- Country (Text) ----------------------------------------------

    def get_country(self) -> str | None:
        return self.get_unqualified_text_property_value(self.COUNTRY)

    def set_country(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.COUNTRY)
            return
        self.set_text_property_value(self.COUNTRY, value)

    # --- Credit (Text) -----------------------------------------------

    def get_credit(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CREDIT)

    def set_credit(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CREDIT)
            return
        self.set_text_property_value(self.CREDIT, value)

    # --- DateCreated (Date) ------------------------------------------

    def get_date_created(self) -> str | None:
        return self.get_unqualified_text_property_value(self.DATE_CREATED)

    def set_date_created(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.DATE_CREATED)
            return
        self.set_text_property_value(self.DATE_CREATED, value)

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
        return self.get_unqualified_text_property_value(self.HEADLINE)

    def set_headline(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.HEADLINE)
            return
        self.set_text_property_value(self.HEADLINE, value)

    # --- History (Text) ----------------------------------------------

    def get_history(self) -> str | None:
        return self.get_unqualified_text_property_value(self.HISTORY)

    def set_history(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.HISTORY)
            return
        self.set_text_property_value(self.HISTORY, value)

    # --- ICCProfile (Text) -------------------------------------------

    def get_icc_profile(self) -> str | None:
        return self.get_unqualified_text_property_value(self.ICC_PROFILE)

    def set_icc_profile(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.ICC_PROFILE)
            return
        self.set_text_property_value(self.ICC_PROFILE, value)

    # --- Instructions (Text) -----------------------------------------

    def get_instructions(self) -> str | None:
        return self.get_unqualified_text_property_value(self.INSTRUCTIONS)

    def set_instructions(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.INSTRUCTIONS)
            return
        self.set_text_property_value(self.INSTRUCTIONS, value)

    # --- Source (Text) -----------------------------------------------

    def get_source(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SOURCE)

    def set_source(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.SOURCE)
            return
        self.set_text_property_value(self.SOURCE, value)

    # --- State (Text) ------------------------------------------------

    def get_state(self) -> str | None:
        return self.get_unqualified_text_property_value(self.STATE)

    def set_state(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.STATE)
            return
        self.set_text_property_value(self.STATE, value)

    # --- SupplementalCategories (Text) -------------------------------

    def get_supplemental_categories(self) -> str | None:
        return self.get_unqualified_text_property_value(self.SUPPLEMENTAL_CATEGORIES)

    def set_supplemental_categories(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.SUPPLEMENTAL_CATEGORIES)
            return
        self.set_text_property_value(self.SUPPLEMENTAL_CATEGORIES, value)

    # --- TransmissionReference (Text) --------------------------------

    def get_transmission_reference(self) -> str | None:
        return self.get_unqualified_text_property_value(self.TRANSMISSION_REFERENCE)

    def set_transmission_reference(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.TRANSMISSION_REFERENCE)
            return
        self.set_text_property_value(self.TRANSMISSION_REFERENCE, value)

    # --- Urgency (Integer) -------------------------------------------

    def get_urgency(self) -> int | None:
        return self._get_integer(self.URGENCY)

    def set_urgency(self, value: int | str | None) -> None:
        self._set_integer(self.URGENCY, value)
