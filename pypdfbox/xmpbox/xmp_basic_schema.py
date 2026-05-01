from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from .type.array_property import ArrayProperty, Cardinality
from .type.date_type import DateType
from .type.integer_type import IntegerType
from .type.text_type import TextType
from .type.thumbnail_type import ThumbnailType
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPBasicSchema(XMPSchema):
    """
    Representation of the XMP Basic schema.

    Ported from ``org.apache.xmpbox.schema.XMPBasicSchema`` (PDFBox 3.0).
    Local-name constants and accessor names mirror upstream.

    Two parallel accessor surfaces are exposed for each property, matching
    the upstream ``setXxx(value)`` / ``setXxxProperty(field)`` /
    ``getXxx()`` / ``getXxxProperty()`` shape:

      * **String-form** (``set_creator_tool`` / ``get_creator_tool`` etc.):
        accepts and returns the raw Python primitive (``str``, ``int``,
        ``datetime``/ISO-8601 ``str``). Kept for back-compat with the
        cluster-#1 read path.
      * **Typed-form** (``set_creator_tool_property`` /
        ``get_creator_tool_property`` etc.): accepts and returns the
        upstream-equivalent typed wrapper (:class:`TextType`,
        :class:`DateType`, :class:`IntegerType`). The wrappers carry
        namespace/prefix/property-name and validate values per upstream.

    The two surfaces are interoperable: setting via the typed form is
    visible to the string getter, and vice-versa.

    ``Thumbnails`` is exposed as an ``Alt`` :class:`ArrayProperty` containing
    :class:`ThumbnailType` structs, mirroring upstream
    ``getThumbnailsProperty()`` / ``addThumbnails(...)``.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/"
    PREFERRED_PREFIX = "xmp"

    ADVISORY = "Advisory"
    BASEURL = "BaseURL"
    CREATEDATE = "CreateDate"
    CREATORTOOL = "CreatorTool"
    IDENTIFIER = "Identifier"
    LABEL = "Label"
    METADATADATE = "MetadataDate"
    MODIFYDATE = "ModifyDate"
    MODIFIER_DATE = "ModifierDate"
    NICKNAME = "Nickname"
    RATING = "Rating"
    THUMBNAILS = "Thumbnails"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- internal: typed/string interop helpers ----------------------

    def _read_text(self, local_name: str) -> str | None:
        """Return the string value, unwrapping a stored ``TextType`` if any."""
        v = self._properties.get(local_name)
        if isinstance(v, TextType):
            return v.get_string_value()
        return self.get_unqualified_text_property_value(local_name)

    def _read_date_string(self, local_name: str) -> str | None:
        """Return the ISO-8601 string for a Date property (typed or stringy)."""
        v = self._properties.get(local_name)
        if isinstance(v, DateType):
            return v.get_string_value()
        return self.get_unqualified_text_property_value(local_name)

    def _read_date_value(self, local_name: str) -> datetime | None:
        """
        Return the typed :class:`datetime` for a Date property.

        Mirrors upstream ``getXxxDate()`` returning ``Calendar``. If the
        property was set via the string-form setter, the ISO-8601 string is
        parsed lazily; an unparseable value yields ``None`` to match the
        upstream contract that absent/invalid dates surface as ``null``.
        """
        v = self._properties.get(local_name)
        if isinstance(v, DateType):
            return v.get_value()
        if isinstance(v, str):
            try:
                tmp = DateType(self._metadata, self._namespace, self._prefix, local_name, v)
            except ValueError:
                return None
            return tmp.get_value()
        return None

    def _read_integer(self, local_name: str) -> int | None:
        v = self._properties.get(local_name)
        if isinstance(v, IntegerType):
            return v.get_value()
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                return None
        return None

    def _array_property_for_bag(self, local_name: str) -> ArrayProperty | None:
        """
        Return an :class:`ArrayProperty` wrapper for a Bag property whose
        backing storage is either an existing wrapper or a plain ``list``
        of strings (cluster-#1 storage shape). Returns ``None`` when the
        property is absent.
        """
        existing = self._properties.get(local_name)
        if isinstance(existing, ArrayProperty):
            return existing
        if not isinstance(existing, list):
            return None
        wrapper = ArrayProperty(
            self._metadata,
            self._namespace,
            self._prefix,
            local_name,
            Cardinality.Bag,
        )
        for item in existing:
            wrapper.add_property(
                TextType(
                    self._metadata,
                    self._namespace,
                    self._prefix,
                    "li",
                    str(item),
                )
            )
        return wrapper

    # --- Advisory (Bag of XPath / Text) ------------------------------

    def add_advisory(self, xpath: str) -> None:
        """Mirror of upstream ``addAdvisory`` — append to the Advisory bag."""
        self.add_qualified_bag_value(self.ADVISORY, xpath)

    def remove_advisory(self, xpath: str) -> None:
        """Mirror of upstream ``removeAdvisory`` — remove a single entry."""
        self.remove_unqualified_bag_value(self.ADVISORY, xpath)

    def get_advisory(self) -> list[str] | None:
        """Mirror of upstream ``getAdvisory`` — return the Advisory bag."""
        return self.get_unqualified_bag_value_list(self.ADVISORY)

    def get_advisory_property(self) -> ArrayProperty | None:
        """
        Mirror of upstream ``getAdvisoryProperty()``. Cluster #1 stores Bag
        contents as a plain Python list; this materialises the entries into
        an :class:`ArrayProperty` wrapper on demand for callers that expect
        the typed return shape.
        """
        return self._array_property_for_bag(self.ADVISORY)

    # --- creator tool (AgentName / Text) -----------------------------

    def set_creator_tool(self, tool: str) -> None:
        self.set_text_property_value(self.CREATORTOOL, tool)

    def get_creator_tool(self) -> str | None:
        return self._read_text(self.CREATORTOOL)

    def set_creator_tool_property(self, prop: TextType) -> None:
        """Mirror of upstream ``setCreatorToolProperty(AgentNameType)``."""
        self._properties[self.CREATORTOOL] = prop

    def get_creator_tool_property(self) -> TextType | None:
        """Mirror of upstream ``getCreatorToolProperty`` — typed wrapper."""
        v = self._properties.get(self.CREATORTOOL)
        if isinstance(v, TextType):
            return v
        if isinstance(v, str):
            return TextType(
                self._metadata, self._namespace, self._prefix, self.CREATORTOOL, v
            )
        return None

    # --- create / modify / metadata / modifier dates -----------------

    def set_create_date(self, date_value: str | datetime | date) -> None:
        if isinstance(date_value, str):
            self.set_text_property_value(self.CREATEDATE, date_value)
            return
        prop = DateType(
            self._metadata, self._namespace, self._prefix, self.CREATEDATE, date_value
        )
        self._properties[self.CREATEDATE] = prop

    def get_create_date(self) -> str | None:
        return self._read_date_string(self.CREATEDATE)

    def set_create_date_property(self, prop: DateType) -> None:
        self._properties[self.CREATEDATE] = prop

    def get_create_date_property(self) -> DateType | None:
        v = self._properties.get(self.CREATEDATE)
        if isinstance(v, DateType):
            return v
        if isinstance(v, str):
            try:
                return DateType(
                    self._metadata, self._namespace, self._prefix, self.CREATEDATE, v
                )
            except ValueError:
                return None
        return None

    def get_create_date_value(self) -> datetime | None:
        """Typed mirror of upstream ``getCreateDate()`` returning ``Calendar``."""
        return self._read_date_value(self.CREATEDATE)

    def set_modify_date(self, date_value: str | datetime | date) -> None:
        if isinstance(date_value, str):
            self.set_text_property_value(self.MODIFYDATE, date_value)
            return
        prop = DateType(
            self._metadata, self._namespace, self._prefix, self.MODIFYDATE, date_value
        )
        self._properties[self.MODIFYDATE] = prop

    def get_modify_date(self) -> str | None:
        return self._read_date_string(self.MODIFYDATE)

    def set_modify_date_property(self, prop: DateType) -> None:
        self._properties[self.MODIFYDATE] = prop

    def get_modify_date_property(self) -> DateType | None:
        v = self._properties.get(self.MODIFYDATE)
        if isinstance(v, DateType):
            return v
        if isinstance(v, str):
            try:
                return DateType(
                    self._metadata, self._namespace, self._prefix, self.MODIFYDATE, v
                )
            except ValueError:
                return None
        return None

    def get_modify_date_value(self) -> datetime | None:
        return self._read_date_value(self.MODIFYDATE)

    def set_metadata_date(self, date_value: str | datetime | date) -> None:
        if isinstance(date_value, str):
            self.set_text_property_value(self.METADATADATE, date_value)
            return
        prop = DateType(
            self._metadata, self._namespace, self._prefix, self.METADATADATE, date_value
        )
        self._properties[self.METADATADATE] = prop

    def get_metadata_date(self) -> str | None:
        return self._read_date_string(self.METADATADATE)

    def set_metadata_date_property(self, prop: DateType) -> None:
        self._properties[self.METADATADATE] = prop

    def get_metadata_date_property(self) -> DateType | None:
        v = self._properties.get(self.METADATADATE)
        if isinstance(v, DateType):
            return v
        if isinstance(v, str):
            try:
                return DateType(
                    self._metadata, self._namespace, self._prefix, self.METADATADATE, v
                )
            except ValueError:
                return None
        return None

    def get_metadata_date_value(self) -> datetime | None:
        return self._read_date_value(self.METADATADATE)

    def set_modifier_date(self, date_value: str | datetime | date) -> None:
        """Mirror of upstream ``setModifierDate``."""
        if isinstance(date_value, str):
            self.set_text_property_value(self.MODIFIER_DATE, date_value)
            return
        prop = DateType(
            self._metadata,
            self._namespace,
            self._prefix,
            self.MODIFIER_DATE,
            date_value,
        )
        self._properties[self.MODIFIER_DATE] = prop

    def get_modifier_date(self) -> str | None:
        return self._read_date_string(self.MODIFIER_DATE)

    def set_modifier_date_property(self, prop: DateType) -> None:
        self._properties[self.MODIFIER_DATE] = prop

    def get_modifier_date_property(self) -> DateType | None:
        v = self._properties.get(self.MODIFIER_DATE)
        if isinstance(v, DateType):
            return v
        if isinstance(v, str):
            try:
                return DateType(
                    self._metadata,
                    self._namespace,
                    self._prefix,
                    self.MODIFIER_DATE,
                    v,
                )
            except ValueError:
                return None
        return None

    def get_modifier_date_value(self) -> datetime | None:
        return self._read_date_value(self.MODIFIER_DATE)

    # --- label / nickname / base url ---------------------------------

    def set_label(self, label: str) -> None:
        self.set_text_property_value(self.LABEL, label)

    def get_label(self) -> str | None:
        return self._read_text(self.LABEL)

    def set_label_property(self, prop: TextType) -> None:
        self._properties[self.LABEL] = prop

    def get_label_property(self) -> TextType | None:
        v = self._properties.get(self.LABEL)
        if isinstance(v, TextType):
            return v
        if isinstance(v, str):
            return TextType(
                self._metadata, self._namespace, self._prefix, self.LABEL, v
            )
        return None

    def set_nickname(self, nickname: str) -> None:
        self.set_text_property_value(self.NICKNAME, nickname)

    def get_nickname(self) -> str | None:
        return self._read_text(self.NICKNAME)

    def set_nickname_property(self, prop: TextType) -> None:
        self._properties[self.NICKNAME] = prop

    def get_nickname_property(self) -> TextType | None:
        v = self._properties.get(self.NICKNAME)
        if isinstance(v, TextType):
            return v
        if isinstance(v, str):
            return TextType(
                self._metadata, self._namespace, self._prefix, self.NICKNAME, v
            )
        return None

    def set_base_url(self, url: str) -> None:
        self.set_text_property_value(self.BASEURL, url)

    def get_base_url(self) -> str | None:
        return self._read_text(self.BASEURL)

    def set_base_url_property(self, prop: TextType) -> None:
        """Mirror of upstream ``setBaseURLProperty(URLType)`` — accepts TextType."""
        self._properties[self.BASEURL] = prop

    def get_base_url_property(self) -> TextType | None:
        """Mirror of upstream ``getBaseURLProperty``."""
        v = self._properties.get(self.BASEURL)
        if isinstance(v, TextType):
            return v
        if isinstance(v, str):
            return TextType(
                self._metadata, self._namespace, self._prefix, self.BASEURL, v
            )
        return None

    # --- identifier (Bag) --------------------------------------------

    def add_identifier(self, value: str) -> None:
        self.add_qualified_bag_value(self.IDENTIFIER, value)

    def remove_identifier(self, value: str) -> None:
        """Mirror of upstream ``removeIdentifier``."""
        self.remove_unqualified_bag_value(self.IDENTIFIER, value)

    def get_identifiers(self) -> list[str] | None:
        return self.get_unqualified_bag_value_list(self.IDENTIFIER)

    def get_identifiers_property(self) -> ArrayProperty | None:
        """
        Mirror of upstream ``getIdentifiersProperty()``. Materialises the
        plain-list cluster-#1 storage into an :class:`ArrayProperty` wrapper
        on demand.
        """
        return self._array_property_for_bag(self.IDENTIFIER)

    # --- rating (Integer) --------------------------------------------

    def set_rating(self, value: int | str) -> None:
        """Mirror of upstream ``setRating(Integer)``."""
        prop = IntegerType(
            self._metadata, self._namespace, self._prefix, self.RATING, value
        )
        self._properties[self.RATING] = prop

    def get_rating(self) -> int | None:
        """Mirror of upstream ``getRating()``."""
        return self._read_integer(self.RATING)

    def set_rating_property(self, prop: IntegerType) -> None:
        """Mirror of upstream ``setRatingProperty(IntegerType)``."""
        self._properties[self.RATING] = prop

    def get_rating_property(self) -> IntegerType | None:
        """Mirror of upstream ``getRatingProperty()`` — returns the typed wrapper."""
        v = self._properties.get(self.RATING)
        if isinstance(v, IntegerType):
            return v
        if isinstance(v, bool):
            # bool is a subclass of int; lift to a stable IntegerType.
            return IntegerType(
                self._metadata, self._namespace, self._prefix, self.RATING, int(v)
            )
        if isinstance(v, int):
            return IntegerType(
                self._metadata, self._namespace, self._prefix, self.RATING, v
            )
        if isinstance(v, str):
            try:
                return IntegerType(
                    self._metadata, self._namespace, self._prefix, self.RATING, v
                )
            except ValueError:
                return None
        return None

    # --- Thumbnails (Alt of ThumbnailType) ---------------------------

    def _ensure_thumbnails_alt(self) -> ArrayProperty:
        existing = self._properties.get(self.THUMBNAILS)
        if isinstance(existing, ArrayProperty):
            return existing
        alt = ArrayProperty(
            self._metadata,
            self._namespace,
            self._prefix,
            self.THUMBNAILS,
            Cardinality.Alt,
        )
        self._properties[self.THUMBNAILS] = alt
        return alt

    def get_thumbnails(self) -> list[ThumbnailType] | None:
        """
        Mirror of upstream ``getThumbnails()``. Return a fresh list of
        :class:`ThumbnailType` entries carried by the ``Thumbnails`` Alt, or
        ``None`` when the property is absent.
        """
        existing = self._properties.get(self.THUMBNAILS)
        if not isinstance(existing, ArrayProperty):
            return None
        return [
            child
            for child in existing.get_all_properties()
            if isinstance(child, ThumbnailType)
        ]

    def set_thumbnails(self, thumbnails: list[ThumbnailType] | None) -> None:
        """
        Replace the ``Thumbnails`` Alt with the supplied thumbnails. Passing
        ``None`` removes the property.
        """
        if thumbnails is None:
            self.remove_property(self.THUMBNAILS)
            return
        alt = ArrayProperty(
            self._metadata,
            self._namespace,
            self._prefix,
            self.THUMBNAILS,
            Cardinality.Alt,
        )
        for thumbnail in thumbnails:
            alt.add_property(thumbnail)
        self._properties[self.THUMBNAILS] = alt

    def add_thumbnails(self, thumbnail: ThumbnailType) -> None:
        """
        Mirror of upstream ``addThumbnails(ThumbnailType)``. Append a
        thumbnail to the ``Thumbnails`` Alt, allocating the container on first
        use.
        """
        self._ensure_thumbnails_alt().add_property(thumbnail)

    def add_thumbnail(self, thumbnail: ThumbnailType) -> None:
        """Singular convenience alias for :meth:`add_thumbnails`."""
        self.add_thumbnails(thumbnail)

    def get_thumbnails_property(self) -> ArrayProperty | None:
        """Mirror of upstream ``getThumbnailsProperty()``."""
        existing = self._properties.get(self.THUMBNAILS)
        return existing if isinstance(existing, ArrayProperty) else None

    def set_thumbnails_property(self, value: ArrayProperty | None) -> None:
        """Mirror of upstream ``setThumbnailsProperty(ArrayProperty)``."""
        if value is None:
            self.remove_property(self.THUMBNAILS)
            return
        value.set_property_name(self.THUMBNAILS)
        self._properties[self.THUMBNAILS] = value
