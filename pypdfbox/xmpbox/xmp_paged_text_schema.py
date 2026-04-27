from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPageTextSchema(XMPSchema):
    """
    Representation of the Adobe XMP "Paged-Text" schema.

    Ported from ``org.apache.xmpbox.schema.XMPageTextSchema`` (PDFBox 3.0).
    The schema captures paged-text-format metadata: page count, page geometry,
    plate names, colorants, and embedded fonts. Property local names match
    upstream ``public static final`` constants verbatim. The upstream class
    name (``XMPageTextSchema`` — note the missing "d" between "XMP" and
    "ageText") is preserved as-is for source-level compatibility.

    Cluster #1 ships:

      * ``NPages`` — Integer scalar property; exposed as a Python ``int``.
      * ``MaxPageSize`` — placeholder accessors for the ``Dimensions`` struct.
        The typed struct wrapper is deferred until the field hierarchy lands;
        callers may pass a plain ``str``/``dict`` payload via the generic
        :meth:`XMPSchema.set_property` accessor.
      * ``Colorants`` — ordered (``Seq``) array of colorant entries.
      * ``PlateNames`` — ordered (``Seq``) array of plate names (strings).
      * ``Fonts`` — unordered (``Bag``) array of font entries.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/t/pg/"
    PREFERRED_PREFIX = "xmpTPg"

    # Local-name constants — names match upstream ``public static final`` fields.
    MAX_PAGE_SIZE = "MaxPageSize"
    N_PAGES = "NPages"
    PLATENAMES = "PlateNames"
    COLORANTS = "Colorants"
    FONTS = "Fonts"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- NPages ------------------------------------------------------

    def get_n_pages(self) -> int | None:
        """
        Return the ``NPages`` integer property. The cluster #1 storage is the
        raw text value written by :meth:`set_n_pages`; we coerce to ``int`` on
        read so callers see Python-native semantics. Returns ``None`` when the
        property is absent or cannot be parsed as an integer.
        """
        raw = self.get_unqualified_text_property_value(self.N_PAGES)
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def set_n_pages(self, value: int | None) -> None:
        if value is None:
            self.remove_property(self.N_PAGES)
            return
        self.set_text_property_value(self.N_PAGES, str(int(value)))

    # --- MaxPageSize -------------------------------------------------
    #
    # Upstream models ``MaxPageSize`` as a ``Dimensions`` struct (``stDim:w`` /
    # ``stDim:h`` / ``stDim:unit``). Cluster #1 has not ported the structured-
    # type hierarchy yet, so we expose a generic accessor that returns
    # whatever the parser stored (a ``dict[str, str]`` of struct fields when
    # parsed in, or whatever a caller supplies via :meth:`set_max_page_size`).

    def get_max_page_size(self) -> object | None:
        """
        Return the ``MaxPageSize`` property as stored. Until the
        ``Dimensions`` struct wrapper lands the value is returned untyped —
        callers should treat the return as ``object`` and inspect at the call
        site. Returns ``None`` when the property is absent.
        """
        return self.get_property(self.MAX_PAGE_SIZE)

    def set_max_page_size(self, value: object | None) -> None:
        """
        Install ``MaxPageSize``. ``value`` may be a ``dict`` mapping struct
        field names to strings (the parser-produced shape) or any other
        payload the caller wishes to round-trip. Passing ``None`` clears.
        """
        if value is None:
            self.remove_property(self.MAX_PAGE_SIZE)
            return
        self.set_property(self.MAX_PAGE_SIZE, value)

    # --- PlateNames (Seq) -------------------------------------------

    def add_plate_name(self, value: str) -> None:
        """Append ``value`` to the ``PlateNames`` ordered array."""
        self.add_unqualified_sequence_value(self.PLATENAMES, value)

    def remove_plate_name(self, value: str) -> None:
        self.remove_unqualified_sequence_value(self.PLATENAMES, value)

    def get_plate_names(self) -> list[str] | None:
        return self.get_unqualified_sequence_value_list(self.PLATENAMES)

    # --- Colorants (Seq) --------------------------------------------
    #
    # Upstream typing: ``Seq`` of ``Colorant`` structs. Cluster #1 stores the
    # array as ``list`` and accepts whatever the caller supplies (string or
    # dict). When the structured-type wrapper lands the typed accessors will
    # replace these.

    def add_colorant(self, value: object) -> None:
        """
        Append ``value`` to the ``Colorants`` ordered array. Accepts strings or
        dicts (struct-shaped) until the typed wrapper lands.
        """
        existing = self._properties.get(self.COLORANTS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.COLORANTS] = existing
        existing.append(value)

    def get_colorants(self) -> list[object] | None:
        v = self._properties.get(self.COLORANTS)
        if v is None:
            return None
        if isinstance(v, list):
            return list(v)
        return [v]

    # --- Fonts (Bag) ------------------------------------------------
    #
    # Upstream typing: ``Bag`` of ``Font`` structs. Same deferred-struct
    # caveat as ``Colorants``.

    def add_font(self, value: object) -> None:
        """
        Append ``value`` to the ``Fonts`` unordered array. Accepts strings or
        dicts (struct-shaped) until the typed wrapper lands.
        """
        existing = self._properties.get(self.FONTS)
        if not isinstance(existing, list):
            existing = []
            self._properties[self.FONTS] = existing
        existing.append(value)

    def get_fonts(self) -> list[object] | None:
        v = self._properties.get(self.FONTS)
        if v is None:
            return None
        if isinstance(v, list):
            return list(v)
        return [v]
