from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font import PDFont
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

_DEFAULT_COLOR_SPACE_BY_DEVICE: dict[str, COSName] = {
    "DeviceGray": COSName.get_pdf_name("DefaultGray"),
    "G": COSName.get_pdf_name("DefaultGray"),
    "DeviceRGB": COSName.get_pdf_name("DefaultRGB"),
    "RGB": COSName.get_pdf_name("DefaultRGB"),
    "DeviceCMYK": COSName.get_pdf_name("DefaultCMYK"),
    "CMYK": COSName.get_pdf_name("DefaultCMYK"),
}


class PDResources:
    """
    PDF ``/Resources`` dictionary wrapper. Mirrors
    ``org.apache.pdfbox.pdmodel.PDResources``.

    Surface:

    - name-listing accessors (``get_xobject_names`` etc.) returning a list
      of ``COSName``;
    - raw accessors for direct font dictionaries and XObjects
      (``get_font``, ``get_xobject``);
    - typed accessors (``get_x_object``, ``get_color_space``,
      ``get_pattern``, ``get_shading``, ``get_ext_gstate``,
      ``get_property_list``) returning the appropriate PD wrapper or ``None``;
    - ``get_proc_set`` / ``set_proc_set`` for the legacy ``/ProcSet`` array;
    - ``add(category, value)`` and ``put(category, name, value)`` for
      registering newly-minted resources across all standard categories.
    """

    def __init__(
        self,
        resources: COSDictionary | None = None,
        resource_cache: PDResourceCache | None = None,
        *,
        document: PDDocument | None = None,
        direct_font_cache: dict[COSName, Any] | None = None,
    ) -> None:
        self._resources: COSDictionary = resources if resources is not None else COSDictionary()
        self._document = document
        self._resource_cache = resource_cache
        # Accepted for constructor parity with PDFBox 3.x. pypdfbox preserves
        # the historical direct-font raw dictionary surface, so this cache is
        # intentionally not consulted by get_font().
        self._direct_font_cache = direct_font_cache

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

    def get_resource_cache(self) -> PDResourceCache | None:
        """Return the resource cache associated with these resources, or
        ``None``. Mirrors upstream ``getResourceCache()``."""
        return self._cache()

    # ---------- /ProcSet ----------

    def get_proc_set(self) -> list[COSName]:
        """Return the names in the legacy ``/ProcSet`` array.

        Mirrors upstream ``PDResources.getProcSet``. Non-name entries are
        ignored so malformed resource dictionaries remain readable.
        """
        value = self._resources.get_dictionary_object(_PROC_SET)
        if not isinstance(value, COSArray):
            return []
        names: list[COSName] = []
        for index in range(value.size()):
            item = value.get_object(index)
            if isinstance(item, COSName):
                names.append(item)
        return names

    def set_proc_set(self, proc_set: Iterable[COSName | str] | None) -> None:
        """Set the legacy ``/ProcSet`` array, or remove it when ``None``.

        String entries are accepted as a Python convenience and converted to
        ``COSName`` values before storage.
        """
        if proc_set is None:
            self._resources.remove_item(_PROC_SET)
            return
        array = COSArray()
        for entry in proc_set:
            if isinstance(entry, COSName):
                array.add(entry)
            elif isinstance(entry, str):
                array.add(COSName.get_pdf_name(entry))
            else:
                raise TypeError(
                    "proc_set entries must be COSName or str, "
                    f"got {type(entry).__name__}"
                )
        self._resources.set_item(_PROC_SET, array)

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
        raw, entry = self._lookup_raw_and_resolved(_X_OBJECT, key)
        if entry is None:
            return None
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_x_object(raw)
            if cached is not None:
                return cached
        if not isinstance(entry, COSStream):
            raise TypeError(
                f"/XObject entry {key!s} is not a stream: {type(entry).__name__}"
            )
        subtype = entry.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        if subtype == "Form":
            xobject = PDFormXObject(entry)
            if cache is not None and isinstance(raw, COSObject):
                cache.put_x_object(raw, xobject)
            return xobject
        if subtype == "Image":
            xobject = PDImageXObject(entry)
            if cache is not None and isinstance(raw, COSObject):
                cache.put_x_object(raw, xobject)
            return xobject
        raise OSError(f"Invalid XObject Subtype: {subtype!r}")

    def get_x_object_names(self) -> list[COSName]:
        """``/XObject`` keys. Upstream method name is ``getXObjectNames``."""
        return self.get_xobject_names()

    def add_x_object(
        self, xobject: PDXObject, prefix: str | None = None
    ) -> COSName:
        """Register ``xobject`` under a fresh key. Form XObjects are keyed
        ``Form0``/``Form1``/…, image XObjects ``Im0``/``Im1``/…, unless a
        custom ``prefix`` is supplied. Matching upstream ``createKey`` per
        kind, returns an existing key when the same COS object is already
        present."""
        # Local imports — cluster boundary, see ``get_x_object``.
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        cos_object = xobject.get_cos_object()
        sub = self._get_or_create_subdict(_X_OBJECT)
        existing = self._find_existing_key(sub, cos_object)
        if existing is not None:
            return existing

        if prefix is not None:
            key_prefix = prefix
        elif isinstance(xobject, PDFormXObject):
            key_prefix = _PREFIX_FORM
        elif isinstance(xobject, PDImageXObject):
            key_prefix = _PREFIX_IMAGE
        else:
            # Unknown subclass — fall back to subtype on the COS dict.
            subtype = cos_object.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
            key_prefix = _PREFIX_FORM if subtype == "Form" else _PREFIX_IMAGE

        key = self._create_key(sub, key_prefix)
        sub.set_item(key, cos_object)
        return key

    def get_font(self, name: COSName) -> COSDictionary | PDFont | None:
        """Return the font resource for ``name``.

        Direct entries preserve the cluster #1 raw ``COSDictionary`` surface.
        Indirect entries use ``PDFontFactory`` and the document resource cache,
        matching upstream's cache hookup for typed font resources.
        """
        from pypdfbox.pdmodel.font import PDFontFactory  # noqa: PLC0415

        raw, base = self._lookup_raw_and_resolved(_FONT, name)
        if base is None:
            return None
        if not isinstance(raw, COSObject):
            return base if isinstance(base, COSDictionary) else None
        cache = self._cache()
        if cache is not None:
            cached = cache.get_font(raw)
            if cached is not None:
                return cached
        if isinstance(base, COSDictionary):
            font = PDFontFactory.create_font(base)
            if cache is not None and font is not None:
                cache.put_font(raw, font)
            return font
        return None

    # ---------- name-listing accessors ----------

    def get_xobject_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_X_OBJECT))

    def getXObjectNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_xobject_names()

    def get_font_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_FONT))

    def getFontNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_font_names()

    def get_color_space_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_COLOR_SPACE))

    def getColorSpaceNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_color_space_names()

    def get_pattern_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_PATTERN))

    def getPatternNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_pattern_names()

    def get_shading_names(self) -> list[COSName]:
        return self._names_in(self._get_subdict(_SHADING))

    def getShadingNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_shading_names()

    def get_extgstate_names(self) -> list[COSName]:
        """``/ExtGState`` keys. Upstream method name is ``getExtGStateNames``."""
        return self._names_in(self._get_subdict(_EXT_GSTATE))

    def getExtGStateNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_extgstate_names()

    def get_ext_g_state_names(self) -> list[COSName]:
        """Upstream-spelled alias for ``get_extgstate_names``."""
        return self.get_extgstate_names()

    def get_property_list_names(self) -> list[COSName]:
        """``/Properties`` keys. Upstream method name is ``getPropertiesNames``."""
        return self._names_in(self._get_subdict(_PROPERTIES))

    def getPropertiesNames(self) -> list[COSName]:  # noqa: N802 - upstream Java name
        return self.get_property_list_names()

    def get_properties_names(self) -> list[COSName]:
        """Upstream-spelled alias for ``get_property_list_names``."""
        return self.get_property_list_names()

    # ---------- typed-accessor surface ----------

    def get_color_space(
        self, name: COSName, was_default: bool = False
    ) -> PDColorSpace | None:
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

        if base is None:
            default_color_space = self._get_default_color_space(name, was_default)
            if default_color_space is not None:
                return default_color_space
            return PDColorSpace.create(name)

        color_space = PDColorSpace.create(base)
        if cache is not None and isinstance(raw, COSObject) and color_space is not None:
            cache.put_color_space(raw, color_space)
        return color_space

    def _get_default_color_space(
        self, name: COSName, was_default: bool
    ) -> PDColorSpace | None:
        if was_default:
            return None
        default_name = _DEFAULT_COLOR_SPACE_BY_DEVICE.get(name.get_name())
        if default_name is None or not self.has_color_space(default_name):
            return None
        return self.get_color_space(default_name, was_default=True)

    def has_color_space(self, name: COSName) -> bool:
        """Return ``True`` if a ``/ColorSpace`` entry exists for ``name``."""
        sub = self._get_subdict(_COLOR_SPACE)
        return sub is not None and sub.contains_key(name)

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
            # Forward our resource cache to PDTilingPattern (upstream
            # ``PDAbstractPattern.create(COSDictionary, ResourceCache)``).
            pattern = PDAbstractPattern.create(base, resource_cache=cache)
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

    def get_ext_g_state(self, name: COSName) -> PDExtendedGraphicsState | None:
        """Upstream-spelled alias for ``get_ext_gstate``."""
        return self.get_ext_gstate(name)

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

    def get_properties(self, name: COSName) -> PDPropertyList | None:
        """Upstream-spelled alias for ``get_property_list``."""
        return self.get_property_list(name)

    def is_image_x_object(self, name: COSName) -> bool:
        """Return whether the named ``/XObject`` is an image XObject."""
        _raw, entry = self._lookup_raw_and_resolved(_X_OBJECT, name)
        return (
            isinstance(entry, COSStream)
            and entry.get_name(COSName.SUBTYPE) == "Image"  # type: ignore[attr-defined]
        )

    # ---------- put / add ----------

    def put(
        self,
        category_or_name: COSName,
        name_or_value: COSName | COSBase | Any,
        value: COSBase | Any | None = None,
    ) -> None:
        """Place a value in the resource dictionary.

        Supported call forms:

        - ``put(category, name, value)``: pypdfbox explicit-category form.
        - ``put(name, typed_resource)``: upstream-style typed overload.
        """
        if value is None:
            category = self._category_for_resource(name_or_value)
            name = category_or_name
            cos_value = self._cos_value(name_or_value)
        else:
            category = category_or_name
            name = name_or_value
            cos_value = self._cos_value(value)
        if not isinstance(name, COSName):
            raise TypeError(f"resource name must be COSName, got {type(name).__name__}")
        sub = self._get_or_create_subdict(category)
        sub.set_item(name, cos_value)

    def add(
        self,
        category_or_value: COSName | COSBase | Any,
        value: COSBase | Any | None = None,
        *,
        prefix: str | None = None,
    ) -> COSName:
        """Register a value and return its resource key.

        Supports both ``add(category, value)`` (the existing pypdfbox form)
        and ``add(typed_resource, prefix=...)`` (upstream-style typed
        overloads). If the same COS object is already present in the target
        subdictionary, its existing key is returned.

        Returns the allocated ``COSName`` key.
        """
        if value is None:
            original_value = category_or_value
            category = self._category_for_resource(category_or_value)
            cos_value = self._cos_value(category_or_value)
        else:
            original_value = value
            category = category_or_value
            cos_value = self._cos_value(value)
            if not isinstance(category, COSName):
                raise TypeError(
                    "explicit add category must be COSName, "
                    f"got {type(category).__name__}"
                )

        sub = self._get_or_create_subdict(category)
        existing = self._find_existing_key(sub, cos_value)
        if existing is not None:
            return existing

        if prefix is not None:
            key_prefix = prefix
        else:
            key_prefix = self._prefix_for_category_value(
                category, cos_value, original_value
            )

        key = self._create_key(sub, key_prefix)
        sub.set_item(key, cos_value)
        return key

    @staticmethod
    def _cos_value(value: COSBase | Any) -> COSBase:
        if isinstance(value, COSBase):
            return value
        get_cos_object = getattr(value, "get_cos_object", None)
        if callable(get_cos_object):
            cos_value = get_cos_object()
            if isinstance(cos_value, COSBase):
                return cos_value
        raise TypeError(f"resource value is not COS-backed: {type(value).__name__}")

    @staticmethod
    def _find_existing_key(sub: COSDictionary, value: COSBase) -> COSName | None:
        for key, existing in sub.entry_set():
            if existing is value:
                return key
            if isinstance(existing, COSObject) and existing.get_object() is value:
                return key
        return None

    @staticmethod
    def _category_for_resource(value: Any) -> COSName:
        from pypdfbox.pdmodel.font import PDFont  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.color import PDColorSpace  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.pd_property_list import (  # noqa: PLC0415
            PDPropertyList,
        )
        from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.shading import PDShading  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.state import (  # noqa: PLC0415
            PDExtendedGraphicsState,
        )

        if isinstance(value, PDFont):
            return _FONT
        if isinstance(value, PDColorSpace):
            return _COLOR_SPACE
        if isinstance(value, PDExtendedGraphicsState):
            return _EXT_GSTATE
        if isinstance(value, PDShading):
            return _SHADING
        if isinstance(value, PDAbstractPattern):
            return _PATTERN
        if isinstance(value, PDPropertyList):
            return _PROPERTIES
        if isinstance(value, PDXObject):
            return _X_OBJECT
        raise TypeError(f"cannot infer PDResources category for {type(value).__name__}")

    @staticmethod
    def _prefix_for_category_value(
        category: COSName, value: COSBase, original_value: Any = None
    ) -> str:
        if category is _X_OBJECT:
            from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
                PDFormXObject,
            )
            from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
                PDImageXObject,
            )

            if isinstance(original_value, PDFormXObject):
                prefix = _PREFIX_FORM
            elif isinstance(original_value, PDImageXObject):
                prefix = _PREFIX_IMAGE
            elif (
                isinstance(value, (COSStream, COSDictionary))
                and value.get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]
            ):
                prefix = _PREFIX_FORM
            else:
                prefix = _PREFIX_IMAGE
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
        return prefix

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
_PROC_SET: COSName = COSName.get_pdf_name("ProcSet")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_EXT_GSTATE: COSName = COSName.get_pdf_name("ExtGState")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PROPERTIES: COSName = COSName.get_pdf_name("Properties")
