from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

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
_PREFIX_OPTIONAL_CONTENT_GROUP: str = "oc"

# Device color-space name -> its Default* override key (PDF 32000-1 §8.6.5.6).
# Only the long Device* forms reach ``getColorSpace`` — inline-image short
# forms (G / RGB / CMYK) are expanded by ``PDInlineImage#toLongName`` before
# any resource-dictionary lookup, so they never participate in this override.
_DEFAULT_COLOR_SPACE_BY_DEVICE: dict[str, COSName] = {
    "DeviceGray": COSName.get_pdf_name("DefaultGray"),
    "DeviceRGB": COSName.get_pdf_name("DefaultRGB"),
    "DeviceCMYK": COSName.get_pdf_name("DefaultCMYK"),
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
      ``get_property_list``) returning the appropriate PD wrapper or ``None``
      for missing/malformed non-XObject entries;
    - ``get_proc_set`` / ``set_proc_set`` for the legacy ``/ProcSet`` array;
    - ``add(category, value)`` and ``put(category, name, value)`` for
      registering newly-minted resources across all standard categories.
    - ``has_*`` / ``clear_*`` helpers for resource-entry presence checks and
      removals.

    Class attributes ``XOBJECT``, ``FONT``, ``COLOR_SPACE``, ``EXT_G_STATE``,
    ``SHADING``, ``PATTERN``, ``PROPERTIES``, and ``PROC_SET`` expose the
    standard ``/Resources`` sub-dictionary keys as ``COSName`` constants so
    callers can pass them straight to ``put`` / ``add`` without re-interning
    the string each time.
    """

    # Class-level COSName constants for the standard /Resources sub-dictionary
    # keys. Forward references to the module-level constants defined at the
    # bottom of this module — see ``_X_OBJECT`` etc.
    XOBJECT: COSName
    FONT: COSName
    COLOR_SPACE: COSName
    EXT_G_STATE: COSName
    SHADING: COSName
    PATTERN: COSName
    PROPERTIES: COSName
    PROC_SET: COSName

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
        self._resolving_color_spaces: set[COSName] = set()

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

    def get_indirect(self, kind: COSName, name: COSName) -> COSObject | None:
        """Return the resource entry as an indirect ``COSObject`` reference,
        or ``None`` when the category sub-dictionary is missing or the entry
        is a direct (inline) value. Mirrors upstream private
        ``getIndirect(COSName, COSName)`` (line 485) — used by typed
        accessors to drive the resource cache."""
        sub = self._get_subdict(kind)
        if sub is None:
            return None
        raw = sub.get_item(name)
        if isinstance(raw, COSObject):
            return raw
        return None

    def get(self, kind: COSName, name: COSName) -> COSBase | None:
        """Return the dereferenced resource entry under ``kind``/``name``, or
        ``None``. Mirrors upstream private ``get(COSName, COSName)``
        (line 504) — the inner accessor that resolves indirect references
        through the category sub-dictionary."""
        sub = self._get_subdict(kind)
        if sub is None:
            return None
        return sub.get_dictionary_object(name)

    def _cache(self) -> PDResourceCache | None:
        if self._document is not None:
            return cast("PDResourceCache", self._document.get_resource_cache())
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

    def has_proc_set(self) -> bool:
        """Return ``True`` when ``/ProcSet`` is present as a ``COSArray``."""
        return isinstance(self._resources.get_dictionary_object(_PROC_SET), COSArray)

    def clear_proc_set(self) -> None:
        """Remove ``/ProcSet``. No-op if absent."""
        self.set_proc_set(None)

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
            xobject: PDXObject = PDFormXObject(entry)
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

    def get_ext_g_state_names(self) -> list[COSName]:
        """Upstream-spelled mirror of ``get_extgstate_names``."""
        return self.get_extgstate_names()

    def get_property_list_names(self) -> list[COSName]:
        """``/Properties`` keys. Upstream method name is ``getPropertiesNames``."""
        return self._names_in(self._get_subdict(_PROPERTIES))

    def get_properties_names(self) -> list[COSName]:
        """Upstream-spelled mirror of ``get_property_list_names``."""
        return self.get_property_list_names()

    def get_names(self, kind: COSName) -> list[COSName]:
        """Return the resource names of the given category, or ``[]`` when
        the category sub-dictionary is absent. Mirrors upstream private
        ``getNames(COSName)`` (line 583)."""
        return self._names_in(self._get_subdict(kind))

    # ---------- typed-accessor surface ----------

    def get_color_space(
        self, name: COSName, was_default: bool = False
    ) -> PDColorSpace | None:
        """Return the typed ``PDColorSpace`` for ``name``, or ``None`` when
        the entry is absent. Mirrors upstream
        ``PDResources.getColorSpace(COSName)`` — dispatch lives in
        ``PDColorSpace.create``."""
        if name in self._resolving_color_spaces:
            return None

        self._resolving_color_spaces.add(name)
        try:
            return self._get_color_space(name, was_default)
        finally:
            self._resolving_color_spaces.remove(name)

    def _get_color_space(
        self, name: COSName, was_default: bool = False
    ) -> PDColorSpace | None:
        from pypdfbox.pdmodel.graphics.color import PDColorSpace  # noqa: PLC0415

        raw, base = self._lookup_raw_and_resolved(_COLOR_SPACE, name)
        cache = self._cache()
        if cache is not None and isinstance(raw, COSObject):
            cached = cache.get_color_space(raw)
            if cached is not None:
                return cached

        if base is None:
            return self._color_space_for_bare_name(name, was_default)

        color_space = PDColorSpace.create(base, self, was_default)
        if cache is not None and isinstance(raw, COSObject) and color_space is not None:
            cache.put_color_space(raw, color_space)
        return color_space

    def _color_space_for_bare_name(
        self, name: COSName, was_default: bool
    ) -> PDColorSpace | None:
        """Resolve a ``/ColorSpace`` name with no resource-dictionary entry.

        Mirrors the ``COSName`` branch of upstream
        ``PDColorSpace.create(COSBase, PDResources, boolean)`` (which is the
        path PDFBox's ``getColorSpace`` takes when ``get(COLORSPACE, name)``
        is null): apply the ``Default*`` override for ``Device*`` references,
        return the device singleton for ``Device*`` / ``Pattern`` names, and
        raise :class:`MissingResourceException` for any other unresolved name.
        pypdfbox keeps this branch here (rather than in ``PDColorSpace.create``)
        so the bare ``PDColorSpace.create(name)`` factory stays permissive for
        callers outside the resource-dictionary lookup."""
        from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import (  # noqa: PLC0415
            PDDeviceCMYK,
        )
        from pypdfbox.pdmodel.graphics.color.pd_device_gray import (  # noqa: PLC0415
            PDDeviceGray,
        )
        from pypdfbox.pdmodel.graphics.color.pd_device_rgb import (  # noqa: PLC0415
            PDDeviceRGB,
        )
        from pypdfbox.pdmodel.graphics.color.pd_pattern import (  # noqa: PLC0415
            PDPattern,
        )
        from pypdfbox.pdmodel.missing_resource_exception import (  # noqa: PLC0415
            MissingResourceException,
        )

        cs_name = name.get_name()
        # Default* override (PDF 32000-1 §8.6.5.6): a Device* reference picks
        # up the page's DefaultGray/DefaultRGB/DefaultCMYK when present, unless
        # we are already resolving a default (``was_default``), which loops.
        default_name = _DEFAULT_COLOR_SPACE_BY_DEVICE.get(cs_name)
        if (
            not was_default
            and default_name is not None
            and self.has_color_space(default_name)
        ):
            return self.get_color_space(default_name, was_default=True)

        if cs_name == "DeviceCMYK":
            return PDDeviceCMYK.INSTANCE
        if cs_name == "DeviceRGB":
            return PDDeviceRGB.INSTANCE
        if cs_name == "DeviceGray":
            return PDDeviceGray.INSTANCE
        if cs_name == "Pattern":
            return PDPattern(resources=self)
        raise MissingResourceException(f"Missing color space: {cs_name}")

    def has_color_space(self, name: COSName) -> bool:
        """Return ``True`` if a ``/ColorSpace`` entry exists for ``name``."""
        return self._has(_COLOR_SPACE, name)

    def has_font(self, name: COSName) -> bool:
        """Return ``True`` if a ``/Font`` entry exists for ``name``."""
        return self._has(_FONT, name)

    def has_x_object(self, name: COSName) -> bool:
        """Return ``True`` if an ``/XObject`` entry exists for ``name``."""
        return self._has(_X_OBJECT, name)

    def has_pattern(self, name: COSName | str) -> bool:
        """Return ``True`` if a ``/Pattern`` entry exists for ``name``."""
        return self._has(_PATTERN, _to_cos_name(name))

    def has_shading(self, name: COSName | str) -> bool:
        """Return ``True`` if a ``/Shading`` entry exists for ``name``."""
        return self._has(_SHADING, _to_cos_name(name))

    def has_ext_g_state(self, name: COSName) -> bool:
        """Return ``True`` if an ``/ExtGState`` entry exists for ``name``."""
        return self._has(_EXT_GSTATE, name)

    def has_ext_gstate(self, name: COSName) -> bool:
        """Compact-spelled alias for ``has_ext_g_state``."""
        return self.has_ext_g_state(name)

    def has_property_list(self, name: COSName) -> bool:
        """Return ``True`` if a ``/Properties`` entry exists for ``name``."""
        return self._has(_PROPERTIES, name)

    def has_properties(self, name: COSName) -> bool:
        """Upstream-spelled alias for ``has_property_list``."""
        return self.has_property_list(name)

    def _has(self, category: COSName, name: COSName) -> bool:
        sub = self._get_subdict(category)
        return sub is not None and sub.contains_key(name)

    def clear_color_space(self, name: COSName) -> None:
        """Remove a ``/ColorSpace`` entry. No-op if absent."""
        self._clear(_COLOR_SPACE, name)

    def clear_font(self, name: COSName) -> None:
        """Remove a ``/Font`` entry. No-op if absent."""
        self._clear(_FONT, name)

    def clear_x_object(self, name: COSName) -> None:
        """Remove an ``/XObject`` entry. No-op if absent."""
        self._clear(_X_OBJECT, name)

    def clear_xobject(self, name: COSName) -> None:
        """Compact-spelled alias for ``clear_x_object``."""
        self.clear_x_object(name)

    def clear_pattern(self, name: COSName | str) -> None:
        """Remove a ``/Pattern`` entry. No-op if absent."""
        self._clear(_PATTERN, _to_cos_name(name))

    def clear_shading(self, name: COSName | str) -> None:
        """Remove a ``/Shading`` entry. No-op if absent."""
        self._clear(_SHADING, _to_cos_name(name))

    def clear_ext_g_state(self, name: COSName) -> None:
        """Remove an ``/ExtGState`` entry. No-op if absent."""
        self._clear(_EXT_GSTATE, name)

    def clear_ext_gstate(self, name: COSName) -> None:
        """Compact-spelled alias for ``clear_ext_g_state``."""
        self.clear_ext_g_state(name)

    def clear_property_list(self, name: COSName) -> None:
        """Remove a ``/Properties`` entry. No-op if absent."""
        self._clear(_PROPERTIES, name)

    def clear_properties(self, name: COSName) -> None:
        """Upstream-spelled alias for ``clear_property_list``."""
        self.clear_property_list(name)

    def _clear(self, category: COSName, name: COSName) -> None:
        sub = self._get_subdict(category)
        if sub is not None:
            sub.remove_item(name)

    def get_pattern(self, name: COSName | str) -> PDAbstractPattern | None:
        """Return the typed ``PDAbstractPattern`` for ``name`` (a
        ``PDTilingPattern`` or ``PDShadingPattern``), or ``None`` when the
        entry is missing or not a dictionary."""
        from pypdfbox.pdmodel.graphics.pattern import (  # noqa: PLC0415
            PDAbstractPattern,
        )

        key = _to_cos_name(name)
        raw, base = self._lookup_raw_and_resolved(_PATTERN, key)
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

    def get_shading(self, name: COSName | str) -> PDShading | None:
        """Return the typed ``PDShading`` for ``name`` (one of
        ``PDShadingType1``..``PDShadingType7``), or ``None`` when the entry
        is absent."""
        from pypdfbox.pdmodel.graphics.shading import PDShading  # noqa: PLC0415

        key = _to_cos_name(name)
        raw, base = self._lookup_raw_and_resolved(_SHADING, key)
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

    def is_form_x_object(self, name: COSName) -> bool:
        """Return whether the named ``/XObject`` is a form XObject. Mirrors
        ``is_image_x_object`` for the ``/Subtype /Form`` case — useful when
        callers need to dispatch without instantiating the wrapper."""
        _raw, entry = self._lookup_raw_and_resolved(_X_OBJECT, name)
        return (
            isinstance(entry, COSStream)
            and entry.get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]
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
        name: object
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
            cos_value = self._cos_value(value)
            if not isinstance(category_or_value, COSName):
                raise TypeError(
                    "explicit add category must be COSName, "
                    f"got {type(category_or_value).__name__}"
                )
            category = category_or_value

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
            # Upstream PDResources.add(PDPropertyList) routes
            # PDOptionalContentGroup to prefix "oc" and falls back to "Prop"
            # for other property-list flavours.
            from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (  # noqa: PLC0415
                PDOptionalContentGroup,
            )

            if isinstance(original_value, PDOptionalContentGroup):
                prefix = _PREFIX_OPTIONAL_CONTENT_GROUP
            else:
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

    def create_key(self, kind: COSName, prefix: str) -> COSName:
        """Allocate a fresh resource key for ``kind``/``prefix``. Mirrors
        upstream private ``createKey(COSName, String)`` (line 740) — the
        kind-aware wrapper that picks the next free ``<prefix><n>`` slot in
        the category sub-dictionary, creating the sub-dictionary lazily if
        absent."""
        sub = self._get_or_create_subdict(kind)
        return self._create_key(sub, prefix)

    def is_allowed_cache(self, xobject: Any) -> bool:
        """Return ``True`` if ``xobject`` may be stored in the resource
        cache. Mirrors upstream private ``isAllowedCache(PDXObject)``
        (line 453) — image XObjects whose colour space could be overridden
        by a ``Default*`` entry on the page must not be cached, because the
        cache is shared across pages with potentially different defaults
        (PDFBOX-2370 / PDFBOX-3484)."""
        # Local import — keeps the cluster boundary explicit.
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        if not isinstance(xobject, PDImageXObject):
            return True
        cos = xobject.get_cos_object()
        get_name = getattr(cos, "get_name", None)
        if not callable(get_name):
            return True
        cs_name_str = get_name(_COLOR_SPACE)  # type: ignore[attr-defined]
        if cs_name_str is None:
            return True
        cs_name = COSName.get_pdf_name(cs_name_str)
        if cs_name is COSName.get_pdf_name("DeviceCMYK") and self.has_color_space(
            COSName.get_pdf_name("DefaultCMYK")
        ):
            return False
        if cs_name is COSName.get_pdf_name("DeviceRGB") and self.has_color_space(
            COSName.get_pdf_name("DefaultRGB")
        ):
            return False
        if cs_name is COSName.get_pdf_name("DeviceGray") and self.has_color_space(
            COSName.get_pdf_name("DefaultGray")
        ):
            return False
        return not self.has_color_space(cs_name)


def _to_cos_name(name: COSName | str) -> COSName:
    return name if isinstance(name, COSName) else COSName.get_pdf_name(name)


# ---- module-level COSName constants for category lookups -------------------

_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_FONT: COSName = COSName.get_pdf_name("Font")
_PROC_SET: COSName = COSName.get_pdf_name("ProcSet")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_EXT_GSTATE: COSName = COSName.get_pdf_name("ExtGState")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_PROPERTIES: COSName = COSName.get_pdf_name("Properties")

# Bind the class-level aliases — these live on PDResources so callers can write
# ``res.put(PDResources.FONT, name, value)`` instead of carrying around an
# extra ``COSName.get_pdf_name("Font")`` import. Mirrors how upstream surfaces
# the same concept via ``COSName.FONT``, ``COSName.XOBJECT``, etc.
PDResources.XOBJECT = _X_OBJECT
PDResources.FONT = _FONT
PDResources.COLOR_SPACE = _COLOR_SPACE
PDResources.EXT_G_STATE = _EXT_GSTATE
PDResources.SHADING = _SHADING
PDResources.PATTERN = _PATTERN
PDResources.PROPERTIES = _PROPERTIES
PDResources.PROC_SET = _PROC_SET
