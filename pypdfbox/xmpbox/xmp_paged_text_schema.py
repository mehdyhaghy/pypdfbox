from __future__ import annotations

from typing import TYPE_CHECKING

from .type.colorant_type import ColorantType
from .type.dimensions_type import DimensionsType
from .type.font_type import FontType
from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class XMPageTextSchema(XMPSchema):
    """
    Representation of the Adobe XMP "Paged-Text" schema.

    Ported from ``org.apache.xmpbox.schema.XMPageTextSchema`` (PDFBox 3.0).
    The schema captures paged-text-format metadata: page count, page geometry,
    plate names, colorants, embedded fonts, and visible-overprint /
    transparency flags. Property local names match upstream
    ``public static final`` constants verbatim. The upstream class name
    (``XMPageTextSchema`` — note the missing "d" between "XMP" and
    "ageText") is preserved as-is for source-level compatibility.

    Wave 39 round-out properties:

      * ``MaxPageSize`` — :class:`DimensionsType` struct (``stDim:w`` /
        ``stDim:h`` / ``stDim:unit``); typed accessors landed alongside the
        legacy dict accessor that callers may continue to use.
      * ``NPages`` — Integer scalar property; exposed as a Python ``int``.
      * ``HasVisibleTransparency`` — Boolean scalar.
      * ``HasVisibleOverprint`` — Boolean scalar.
      * ``Fonts`` — unordered (``Bag``) array of :class:`FontType` structs.
      * ``Colorants`` — ordered (``Seq``) array of :class:`ColorantType`
        structs. (Upstream models this as ``Seq``, not ``Bag``.)
      * ``PlateNames`` — ordered (``Seq``) array of plate names (strings).
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/t/pg/"
    PREFERRED_PREFIX = "xmpTPg"

    # Local-name constants — names match upstream ``public static final`` fields.
    MAX_PAGE_SIZE = "MaxPageSize"
    N_PAGES = "NPages"
    HAS_VISIBLE_TRANSPARENCY = "HasVisibleTransparency"
    HAS_VISIBLE_OVERPRINT = "HasVisibleOverprint"
    PLATENAMES = "PlateNames"
    COLORANTS = "Colorants"
    FONTS = "Fonts"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)
        # Pre-register the structured-type sub-namespaces so callers serialising
        # MaxPageSize / Fonts / Colorants get the right xmlns declarations on
        # the surrounding rdf:Description element.
        self.add_namespace(DimensionsType.PREFERRED_PREFIX, DimensionsType.NAMESPACE)
        self.add_namespace(FontType.PREFERRED_PREFIX, FontType.NAMESPACE)
        self.add_namespace(ColorantType.PREFERRED_PREFIX, ColorantType.NAMESPACE)

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

    # --- HasVisibleTransparency / HasVisibleOverprint -------------------

    @staticmethod
    def _coerce_boolean(raw: object | None) -> bool | None:
        """
        Normalise a stored Boolean property to a Python ``bool``. Upstream
        ``BooleanType`` accepts ``"True"``/``"False"`` (capitalised, per the
        XMP spec) on the wire; cluster #1 stores the raw string, so we coerce
        on read to keep callers Python-native. Lower-case ``true`` / ``false``
        are accepted defensively. Returns ``None`` when the value is absent or
        cannot be interpreted as a boolean.
        """
        if raw is None:
            return None
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        return None

    def get_has_visible_transparency(self) -> bool | None:
        """Return the ``HasVisibleTransparency`` boolean, or ``None`` if absent."""
        return self._coerce_boolean(
            self.get_unqualified_text_property_value(self.HAS_VISIBLE_TRANSPARENCY)
        )

    def set_has_visible_transparency(self, value: bool | None) -> None:
        if value is None:
            self.remove_property(self.HAS_VISIBLE_TRANSPARENCY)
            return
        # XMP Boolean serialisation uses capitalised ``True`` / ``False``.
        self.set_text_property_value(
            self.HAS_VISIBLE_TRANSPARENCY, "True" if value else "False"
        )

    def get_has_visible_overprint(self) -> bool | None:
        """Return the ``HasVisibleOverprint`` boolean, or ``None`` if absent."""
        return self._coerce_boolean(
            self.get_unqualified_text_property_value(self.HAS_VISIBLE_OVERPRINT)
        )

    def set_has_visible_overprint(self, value: bool | None) -> None:
        if value is None:
            self.remove_property(self.HAS_VISIBLE_OVERPRINT)
            return
        self.set_text_property_value(
            self.HAS_VISIBLE_OVERPRINT, "True" if value else "False"
        )

    # --- MaxPageSize -------------------------------------------------
    #
    # Upstream models ``MaxPageSize`` as a ``Dimensions`` struct (``stDim:w`` /
    # ``stDim:h`` / ``stDim:unit``). Cluster #1 stored it as an opaque object;
    # Wave 39 lifts that to typed :class:`DimensionsType` accessors while
    # keeping the dict / opaque pass-through for parser-produced payloads.

    def get_max_page_size(self) -> object | None:
        """
        Return the ``MaxPageSize`` property as stored. Returns either a
        :class:`DimensionsType` (when populated via :meth:`set_max_page_size`
        with a typed instance), a ``dict[str, str]`` (parser-produced shape),
        or ``None`` when absent.
        """
        return self.get_property(self.MAX_PAGE_SIZE)

    def set_max_page_size(self, value: object | None) -> None:
        """
        Install ``MaxPageSize``. ``value`` may be a :class:`DimensionsType`
        instance, a ``dict`` mapping struct field names to strings (the parser-
        produced shape), or any other payload the caller wishes to round-trip.
        Passing ``None`` clears.
        """
        if value is None:
            self.remove_property(self.MAX_PAGE_SIZE)
            return
        self.set_property(self.MAX_PAGE_SIZE, value)

    def get_max_page_size_property(self) -> DimensionsType | None:
        """
        Typed accessor: return the ``MaxPageSize`` value as a
        :class:`DimensionsType`. Materialises a fresh struct from the stored
        ``dict``-form payload (the parser shape) when needed, so existing
        cluster-#1 callers that wrote a dict still see a typed view here.
        Returns ``None`` when the property is absent or cannot be interpreted
        as a Dimensions struct.
        """
        raw = self._properties.get(self.MAX_PAGE_SIZE)
        if raw is None:
            return None
        if isinstance(raw, DimensionsType):
            return raw
        if isinstance(raw, dict):
            dim = DimensionsType(self._metadata)
            w = raw.get(DimensionsType.W)
            h = raw.get(DimensionsType.H)
            unit = raw.get(DimensionsType.UNIT)
            if w is not None:
                try:
                    dim.set_w(float(w))
                except (TypeError, ValueError):
                    pass
            if h is not None:
                try:
                    dim.set_h(float(h))
                except (TypeError, ValueError):
                    pass
            if unit is not None:
                dim.set_unit(str(unit))
            return dim
        return None

    def set_max_page_size_property(self, dimensions: DimensionsType) -> None:
        """
        Typed setter: install ``MaxPageSize`` as a :class:`DimensionsType`.
        Stored verbatim so :meth:`get_max_page_size_property` returns the same
        instance and :meth:`get_max_page_size` returns the typed object too.
        """
        self.set_property(self.MAX_PAGE_SIZE, dimensions)

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
    # Upstream typing: ``Seq`` of ``Colorant`` structs. Cluster #1 stored the
    # array as ``list[str | dict]``; Wave 39 adds typed accessors that
    # round-trip :class:`ColorantType` instances. The legacy
    # :meth:`add_colorant` / :meth:`get_colorants` accessors continue to
    # accept and return the existing string/dict shape so callers that
    # haven't migrated keep working.

    def add_colorant(self, value: object) -> None:
        """
        Append ``value`` to the ``Colorants`` ordered array. Accepts strings,
        dicts (struct-shaped), or :class:`ColorantType` instances.
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

    def add_colorant_property(self, colorant: ColorantType) -> None:
        """
        Typed variant: append a :class:`ColorantType` struct to the
        ``Colorants`` Seq. Stored verbatim so :meth:`get_colorant_properties`
        returns the same instance.
        """
        self.add_colorant(colorant)

    def get_colorant_properties(self) -> list[ColorantType] | None:
        """
        Return only the typed :class:`ColorantType` entries from the
        ``Colorants`` Seq, or ``None`` when the property is absent. Untyped
        (string / dict) entries are skipped — callers wanting the raw mixed
        list should use :meth:`get_colorants`.
        """
        v = self._properties.get(self.COLORANTS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, ColorantType)]

    # --- Fonts (Bag) ------------------------------------------------
    #
    # Upstream typing: ``Bag`` of ``Font`` structs. Wave 39 mirrors the
    # Colorants pattern: legacy string/dict storage is preserved, typed
    # :class:`FontType` accessors land alongside.

    def add_font(self, value: object) -> None:
        """
        Append ``value`` to the ``Fonts`` unordered array. Accepts strings,
        dicts (struct-shaped), or :class:`FontType` instances.
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

    def add_font_property(self, font: FontType) -> None:
        """
        Typed variant: append a :class:`FontType` struct to the ``Fonts`` Bag.
        Stored verbatim so :meth:`get_font_properties` returns the same
        instance.
        """
        self.add_font(font)

    def get_font_properties(self) -> list[FontType] | None:
        """
        Return only the typed :class:`FontType` entries from the ``Fonts``
        Bag, or ``None`` when the property is absent. Untyped (string / dict)
        entries are skipped — callers wanting the raw mixed list should use
        :meth:`get_fonts`.
        """
        v = self._properties.get(self.FONTS)
        if v is None:
            return None
        if not isinstance(v, list):
            v = [v]
        return [item for item in v if isinstance(item, FontType)]
