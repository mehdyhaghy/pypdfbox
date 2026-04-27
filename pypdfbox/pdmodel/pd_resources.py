from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.color import PDColorSpace
    from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.graphics.shading import PDShading
    from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache


# Category prefixes — match upstream ``PDResources.createKey()`` per kind.
_PREFIX_FONT: str = "F"
_PREFIX_FORM: str = "Form"
_PREFIX_IMAGE: str = "Im"
_PREFIX_COLOR_SPACE: str = "cs"
_PREFIX_EXT_GSTATE: str = "gs"
_PREFIX_SHADING: str = "sh"
_PREFIX_PATTERN: str = "p"
_PREFIX_PROPERTY_LIST: str = "Prop"


class PDResources:
    """
    PDF ``/Resources`` dictionary wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.PDResources``.

    Surface:

    - name-listing accessors (``get_xobject_names`` etc.) returning a list
      of ``COSName``;
    - raw value accessors (``get_xobject``, ``get_font``) returning the
      underlying ``COSStream`` / ``COSDictionary`` (``PDFont`` typed wrapper
      lands in cluster #4 — see ``CHANGES.md``);
    - typed accessors (``get_color_space``, ``get_pattern``, ``get_shading``,
      ``get_ext_gstate``, ``get_property_list``) returning the appropriate
      PD wrapper or ``None``;
    - ``add(category, value)`` and ``put(category, name, value)`` for
      registering newly-minted resources across all standard categories.
    """

    def __init__(
        self,
        resources: COSDictionary | None = None,
        *,
        document: PDDocument | None = None,
        resource_cache: PDResourceCache | None = None,
    ) -> None:
        self._resources: COSDictionary = resources if resources is not None else COSDictionary()
        self._document = document
        self._resource_cache = resource_cache

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._resources

    # ---------- helpers ----------

    def _get_subdict(self, category: COSName) -> COSDictionary | None:
        sub = self._resources.get_dictionary_object(category)
        if isinstance(sub, COSDictionary):
            return sub
        return None

    def _get_or_create_subdict(self, category: COSName) -> COSDictionary:
        sub = self._get_subdict(category)
        if sub is None:
            sub = COSDictionary()
            self._resources.set_item(category, sub)
        return sub

    @staticmethod
    def _names_in(sub: COSDictionary | None) -> list[COSName]:
        if sub is None:
            return []
        return list(sub.key_set())

    def _lookup(self, category: str, name: COSName) -> COSBase | None:
        """Resolve ``/Resources/<category>/<name>``. Returns the dereferenced
        COS value, or ``None`` when either the category sub-dictionary or the
        named entry is missing. Mirrors upstream ``getCOSObject().getDictionaryObject(...)``
        chained through the category dictionary."""
        sub = self._get_subdict(COSName.get_pdf_name(category))
        if sub is None:
            return None
        return sub.get_dictionary_object(name)

    def _lookup_raw_and_resolved(
        self, category: COSName, name: COSName
    ) -> tuple[COSBase | None, COSBase | None]:
        sub = self._get_subdict(category)
        if sub is None:
            return None, None
        raw = sub.get_item(name)
        if isinstance(raw, COSObject):
            return raw, raw.get_object()
        return raw, raw

    def _cache(self) -> PDResourceCache | None:
        if self._document is not None:
            return self._document.get_resource_cache()
        return self._resource_cache

    # ---------- raw category accessors ----------

    def get_xobject(self, name: COSName) -> COSBase | None:
        """Return the raw ``/XObject`` entry (typically a ``COSStream``)
        for ``name``, or ``None``. Kept from cluster #1 — returns the raw
        COS object. For the typed ``PDXObject`` wrapper, see
        ``get_x_object``."""
        sub = self._get_subdict(_X_OBJECT)
        if sub is None:
            return None
        entry = sub.get_item(name)
        if isinstance(entry, COSObject):
            return entry.get_object()
        return entry

    # ---------- typed XObject surface (cluster #3) ----------

    def get_x_object(self, name: COSName | str) -> PDXObject | None:
        """Return the typed ``PDXObject`` for ``name`` — either a
        ``PDFormXObject`` (/Subtype /Form) or a ``PDImageXObject``
        (/Subtype /Image). ``None`` when the entry is absent.

        Mirrors upstream ``PDResources.getXObject`` which delegates to
        ``PDXObject.createXObject`` for /Subtype dispatch."""
        # Local imports keep cluster boundaries explicit and avoid an
        # import cycle (graphics → common → pd_stream → cos).
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        key = name if isinstance(name, COSName) else COSName.get_pdf_name(name)
        _raw, entry = self._lookup_raw_and_resolved(_X_OBJECT, key)
        if entry is None:
            return None
        if not isinstance(entry, COSStream):
            raise TypeError(
                f"/XObject entry {key!s} is not a stream: {type(entry).__name__}"
            )
        subtype = entry.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        if subtype == "Form":
            return PDFormXObject(entry)
        if subtype == "Image":
            return PDImageXObject(entry)
        raise OSError(f"Invalid XObject Subtype: {subtype!r}")

    def get_x_object_names(self) -> list[str]:
        """``/XObject`` keys as plain strings. Mirrors upstream's
        ``getXObjectNames()`` which returns ``Set<COSName>`` — Python idiom
        is a list of strings here for pleasant iteration."""
        return [n.name for n in self.get_xobject_names()]

    def add_x_object(self, xobject: PDXObject) -> COSName:
        """Register ``xobject`` under a fresh key. Form XObjects are keyed
        ``Form0``/``Form1``/…, image XObjects ``Im0``/``Im1``/…, matching
        upstream ``createKey`` per kind."""
        # Local imports — cluster boundary, see ``get_x_object``.
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        if isinstance(xobject, PDFormXObject):
            prefix = _PREFIX_FORM
        elif isinstance(xobject, PDImageXObject):
            prefix = _PREFIX_IMAGE
        else:
            # Unknown subclass — fall back to subtype on the COS dict.
            subtype = xobject.get_cos_object().get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
            prefix = _PREFIX_FORM if subtype == "Form" else _PREFIX_IMAGE

        sub = self._get_or_create_subdict(_X_OBJECT)
        key = self._create_key(sub, prefix)
        sub.set_item(key, xobject.get_cos_object())
        return key

    def get_font(self, name: COSName) -> COSDictionary | None:
        """Raw font dictionary; ``PDFont`` wrapper lands in cluster #4."""
        sub = self._get_subdict(_FONT)
        if sub is None:
            return None
        entry = sub.get_dictionary_object(name)
        return entry if isinstance(entry, COSDictionary) else None

    # ---------- name-listing accessors ----------

    def get_xobject_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_X_OBJECT))

    def get_font_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_FONT))

    def get_color_space_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_COLOR_SPACE))

    def get_pattern_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_PATTERN))

    def get_shading_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_SHADING))

    def get_extgstate_names(self) -> list[COSName]:
        """``/ExtGState`` keys. Upstream method name is ``getExtGStateNames``."""
        return self._names_in(self._get_subdict(_EXT_GSTATE))

    def get_property_list_names(self) -> list[COSName]:
        """``/Properties`` keys. Upstream method name is ``getPropertiesNames``."""
        return self._names_in(self._get_subdict(_PROPERTIES))

    # ---------- typed-accessor surface ----------

    def get_color_space(self, name: COSName) -> PDColorSpace | None:
        """Return the typed ``PDColorSpace`` for ``name``, or ``None`` when
        the entry is absent. Mirrors upstream
        ``PDResources.getColorSpace(COSName)`` — dispatch lives in
        ``PDColorSpace.create``."""
        # Local import keeps cluster boundaries explicit.
        from pypdfbox.pdmodel.graphics.color import PDColorSpace  # noqa: PLC0415

        raw, base = self._lookup_raw_and_resolved(_COLOR_SPACE, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_color_space(raw)
            if cached is not None:
                return cached
        color_space = PDColorSpace.create(base)
        if cache is not None and isinstance(raw, COSObject) and color_space is not None:
            cache.put_color_space(raw, color_space)
        return color_space

    def get_pattern(self, name: COSName) -> PDAbstractPattern | None:
        """Return the typed ``PDAbstractPattern`` for ``name`` (a
        ``PDTilingPattern`` or ``PDShadingPattern``), or ``None`` when the
        entry is missing or not a dictionary."""
        from pypdfbox.pdmodel.graphics.pattern import (  # noqa: PLC0415
            PDAbstractPattern,
        )

        raw, base = self._lookup_raw_and_resolved(_PATTERN, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_pattern(raw)
            if cached is not None:
                return cached
        if isinstance(base, COSDictionary):
            pattern = PDAbstractPattern.create(base)
            if cache is not None and isinstance(raw, COSObject) and pattern is not None:
                cache.put_pattern(raw, pattern)
            return pattern
        return None

    def get_shading(self, name: COSName) -> PDShading | None:
        """Return the typed ``PDShading`` for ``name`` (one of
        ``PDShadingType1``..``PDShadingType7``), or ``None`` when the entry
        is absent."""
        from pypdfbox.pdmodel.graphics.shading import PDShading  # noqa: PLC0415

        raw, base = self._lookup_raw_and_resolved(_SHADING, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_shading(raw)
            if cached is not None:
                return cached
        if isinstance(base, COSDictionary):
            shading = PDShading.create(base)
            if cache is not None and isinstance(raw, COSObject) and shading is not None:
                cache.put_shading(raw, shading)
            return shading
        return None

    def get_ext_gstate(self, name: COSName) -> PDExtendedGraphicsState | None:
        """Return the typed ``PDExtendedGraphicsState`` for ``name``, or
        ``None`` when the entry is absent or not a dictionary."""
        from pypdfbox.pdmodel.graphics.state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        raw, base = self._lookup_raw_and_resolved(_EXT_GSTATE, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_ext_g_state(raw)
            if cached is not None:
                return cached
        if isinstance(base, COSDictionary):
            ext_g_state = PDExtendedGraphicsState(base)
            if cache is not None and isinstance(raw, COSObject):
                cache.put_ext_g_state(raw, ext_g_state)
            return ext_g_state
        return None

    def get_property_list(self, name: COSName) -> PDPropertyList | None:
        """Return the typed ``PDPropertyList`` (OCG / OCMD) for ``name``, or
        ``None`` when the entry is absent or not a dictionary."""
        from pypdfbox.pdmodel.graphics.pd_property_list import (  # noqa: PLC0415
            PDPropertyList,
        )

        raw, base = self._lookup_raw_and_resolved(_PROPERTIES, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_property_list(raw)
            if cached is not None:
                return cached
        if isinstance(base, COSDictionary):
            property_list = PDPropertyList.create(base)
            if (
                cache is not None
                and isinstance(raw, COSObject)
                and property_list is not None
            ):
                cache.put_property_list(raw, property_list)
            return property_list
        return None

    # ---------- put / add ----------

    def put(self, category: COSName, name: COSName, value: COSBase) -> None:
        """Place ``value`` at ``/Resources/<category>/<name>``. Mirrors the
        upstream ``put`` overloads (``putFont``, ``putXObject``, …) collapsed
        into one explicit-category form. Used by content-stream consumers
        and tests."""
        sub = self._get_or_create_subdict(category)
        sub.set_item(name, value)

    def add(self, category: COSName, value: COSBase) -> COSName:
        """Register ``value`` under a freshly-allocated key in ``category``.

        Supports the standard resource categories — ``/XObject``, ``/Font``,
        ``/ColorSpace``, ``/ExtGState``, ``/Shading``, ``/Pattern``,
        ``/Properties``. Unknown categories raise ``ValueError``.

        Returns the allocated ``COSName`` key.
        """
        if category is _X_OBJECT:
            prefix = _PREFIX_IMAGE if isinstance(value, COSStream) else _PREFIX_FORM
        elif category is _FONT:
            prefix = _PREFIX_FONT
        elif category is _COLOR_SPACE:
            prefix = _PREFIX_COLOR_SPACE
        elif category is _EXT_GSTATE:
            prefix = _PREFIX_EXT_GSTATE
        elif category is _SHADING:
            prefix = _PREFIX_SHADING
        elif category is _PATTERN:
            prefix = _PREFIX_PATTERN
        elif category is _PROPERTIES:
            prefix = _PREFIX_PROPERTY_LIST
        else:
            raise ValueError(
                f"PDResources.add: unknown resource category {category!s}"
            )

        sub = self._get_or_create_subdict(category)
        key = self._create_key(sub, prefix)
        sub.set_item(key, value)
        return key

    @staticmethod
    def _create_key(sub: COSDictionary, prefix: str) -> COSName:
        """Allocate ``<prefix><n>`` where ``n`` is the smallest non-negative
        integer not already used. Mirrors upstream ``createKey``."""
        n = 0
        while True:
            candidate = COSName.get_pdf_name(f"{prefix}{n}")
            if not sub.contains_key(candidate):
                return candidate
            n += 1


# ---- module-level COSName constants for category lookups -------------------

_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_FONT: COSName = COSName.get_pdf_name("Font")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_EXT_GSTATE: COSName = COSName.get_pdf_name("ExtGState")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PROPERTIES: COSName = COSName.get_pdf_name("Properties")
