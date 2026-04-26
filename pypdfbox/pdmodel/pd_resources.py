from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSBase,
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
)


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

    Cluster #1 ships the *raw* surface only:

    - name-listing accessors (``get_xobject_names`` etc.) returning a list
      of ``COSName``;
    - raw value accessors (``get_xobject``, ``get_font``) returning the
      underlying ``COSStream`` / ``COSDictionary`` rather than the typed
      PD wrapper, since ``PDXObject`` lives in cluster #3 and ``PDFont``
      in cluster #4 (see ``CHANGES.md``);
    - ``add(category, value)`` for ``/XObject`` and ``/Font`` only — the
      writer needs this to register newly-minted resources.

    Methods that *must* return a typed PD object (``get_color_space``,
    ``get_pattern``, ``get_shading``, ``get_ext_gstate``) raise
    ``NotImplementedError`` with a cluster pointer.
    """

    def __init__(self, resources: COSDictionary | None = None) -> None:
        self._resources: COSDictionary = resources if resources is not None else COSDictionary()

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

    # ---------- raw category accessors ----------

    def get_xobject(self, name: COSName) -> COSBase | None:
        """Return the raw ``/XObject`` entry (typically a ``COSStream``)
        for ``name``, or ``None``. Cluster #1 returns the raw COS object;
        ``PDXObject`` wrapping lands in cluster #3."""
        sub = self._get_subdict(_X_OBJECT)
        if sub is None:
            return None
        entry = sub.get_item(name)
        if isinstance(entry, COSObject):
            return entry.get_object()
        return entry

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

    # ---------- typed-accessor stubs (later clusters) ----------

    def get_color_space(self, name: COSName) -> Any:
        raise NotImplementedError(
            "PDResources.get_color_space requires PDColorSpace family — pdmodel cluster #9"
        )

    def get_pattern(self, name: COSName) -> Any:
        raise NotImplementedError(
            "PDResources.get_pattern requires PDAbstractPattern — pdmodel cluster #9"
        )

    def get_shading(self, name: COSName) -> Any:
        raise NotImplementedError(
            "PDResources.get_shading requires PDShading — pdmodel cluster #9"
        )

    def get_ext_gstate(self, name: COSName) -> Any:
        raise NotImplementedError(
            "PDResources.get_ext_gstate requires PDExtendedGraphicsState — "
            "pdmodel cluster #9"
        )

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

        Cluster #1 supports ``/XObject`` and ``/Font`` (the categories the
        writer / parser currently exercise). Other categories raise
        ``NotImplementedError`` until their typed PD wrappers ship.

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
            raise NotImplementedError(
                f"PDResources.add: category {category!s} not supported in cluster #1"
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
