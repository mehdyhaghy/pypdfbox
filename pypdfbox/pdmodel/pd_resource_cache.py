from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.cos import COSObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_font import PDFont
    from pypdfbox.pdmodel.graphics.color import PDColorSpace
    from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
    from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
    from pypdfbox.pdmodel.graphics.shading import PDShading
    from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState


class PDResourceCache(ABC):
    """
    Abstract resource cache. Mirrors ``org.apache.pdfbox.pdmodel.ResourceCache``.

    Caches typed PD wrappers keyed by the indirect ``COSObject`` reference of
    the underlying resource dictionary / array. Identity caching means that two
    ``get_*`` calls for the same indirect ref return the same wrapper instance,
    sparing callers from re-wrapping (and from re-parsing fonts in particular).

    Concrete implementation: :class:`DefaultResourceCache`.
    """

    @abstractmethod
    def get_font(self, indirect: COSObject) -> PDFont | None:
        """Return the cached :class:`PDFont` for ``indirect``, or ``None``."""

    @abstractmethod
    def put_font(self, indirect: COSObject, font: PDFont) -> None:
        """Cache ``font`` under the indirect ref ``indirect``."""

    @abstractmethod
    def get_x_object(self, indirect: COSObject) -> PDXObject | None:
        """Return the cached :class:`PDXObject` for ``indirect``, or ``None``."""

    @abstractmethod
    def put_x_object(self, indirect: COSObject, xobject: PDXObject) -> None:
        """Cache ``xobject`` under the indirect ref ``indirect``."""

    @abstractmethod
    def get_color_space(self, indirect: COSObject) -> PDColorSpace | None:
        """Return the cached :class:`PDColorSpace` for ``indirect``, or ``None``."""

    @abstractmethod
    def put_color_space(
        self, indirect: COSObject, color_space: PDColorSpace
    ) -> None:
        """Cache ``color_space`` under ``indirect``."""

    @abstractmethod
    def get_pattern(self, indirect: COSObject) -> PDAbstractPattern | None:
        """Return the cached :class:`PDAbstractPattern` for ``indirect``."""

    @abstractmethod
    def put_pattern(
        self, indirect: COSObject, pattern: PDAbstractPattern
    ) -> None:
        """Cache ``pattern`` under ``indirect``."""

    @abstractmethod
    def get_shading(self, indirect: COSObject) -> PDShading | None:
        """Return the cached :class:`PDShading` for ``indirect``."""

    @abstractmethod
    def put_shading(self, indirect: COSObject, shading: PDShading) -> None:
        """Cache ``shading`` under ``indirect``."""

    @abstractmethod
    def get_ext_g_state(
        self, indirect: COSObject
    ) -> PDExtendedGraphicsState | None:
        """Return the cached :class:`PDExtendedGraphicsState` for ``indirect``."""

    @abstractmethod
    def put_ext_g_state(
        self, indirect: COSObject, ext_g_state: PDExtendedGraphicsState
    ) -> None:
        """Cache ``ext_g_state`` under ``indirect``."""

    @abstractmethod
    def get_property_list(
        self, indirect: COSObject
    ) -> PDPropertyList | None:
        """Return the cached :class:`PDPropertyList` for ``indirect``."""

    @abstractmethod
    def put_property_list(
        self, indirect: COSObject, property_list: PDPropertyList
    ) -> None:
        """Cache ``property_list`` under ``indirect``."""


class DefaultResourceCache(PDResourceCache):
    """
    In-memory :class:`PDResourceCache`. Mirrors
    ``org.apache.pdfbox.pdmodel.DefaultResourceCache`` — one ``dict`` per
    resource category, keyed by the indirect ``COSObject`` and valued by the
    typed PD wrapper.

    Identity is provided by ``COSObject``'s ``__hash__`` / ``__eq__`` (the
    ``(object_number, generation_number)`` pair), so two distinct ``COSObject``
    instances pointing at the same indirect ref hit the same cache entry —
    matching upstream's :class:`SoftReference`-keyed map semantics minus the
    GC-driven eviction (Python deployments don't need it the same way; if a
    workload demands eviction, subclass and override).
    """

    def __init__(self) -> None:
        self._fonts: dict[COSObject, PDFont] = {}
        self._xobjects: dict[COSObject, PDXObject] = {}
        self._color_spaces: dict[COSObject, PDColorSpace] = {}
        self._patterns: dict[COSObject, PDAbstractPattern] = {}
        self._shadings: dict[COSObject, PDShading] = {}
        self._ext_g_states: dict[COSObject, PDExtendedGraphicsState] = {}
        self._property_lists: dict[COSObject, PDPropertyList] = {}

    # ---------- fonts ----------

    def get_font(self, indirect: COSObject) -> PDFont | None:
        return self._fonts.get(indirect)

    def put_font(self, indirect: COSObject, font: PDFont) -> None:
        self._fonts[indirect] = font

    # ---------- XObjects ----------

    def get_x_object(self, indirect: COSObject) -> PDXObject | None:
        return self._xobjects.get(indirect)

    def put_x_object(self, indirect: COSObject, xobject: PDXObject) -> None:
        self._xobjects[indirect] = xobject

    # ---------- color spaces ----------

    def get_color_space(self, indirect: COSObject) -> PDColorSpace | None:
        return self._color_spaces.get(indirect)

    def put_color_space(
        self, indirect: COSObject, color_space: PDColorSpace
    ) -> None:
        self._color_spaces[indirect] = color_space

    # ---------- patterns ----------

    def get_pattern(self, indirect: COSObject) -> PDAbstractPattern | None:
        return self._patterns.get(indirect)

    def put_pattern(
        self, indirect: COSObject, pattern: PDAbstractPattern
    ) -> None:
        self._patterns[indirect] = pattern

    # ---------- shadings ----------

    def get_shading(self, indirect: COSObject) -> PDShading | None:
        return self._shadings.get(indirect)

    def put_shading(self, indirect: COSObject, shading: PDShading) -> None:
        self._shadings[indirect] = shading

    # ---------- ext-g-states ----------

    def get_ext_g_state(
        self, indirect: COSObject
    ) -> PDExtendedGraphicsState | None:
        return self._ext_g_states.get(indirect)

    def put_ext_g_state(
        self, indirect: COSObject, ext_g_state: PDExtendedGraphicsState
    ) -> None:
        self._ext_g_states[indirect] = ext_g_state

    # ---------- property lists ----------

    def get_property_list(
        self, indirect: COSObject
    ) -> PDPropertyList | None:
        return self._property_lists.get(indirect)

    def put_property_list(
        self, indirect: COSObject, property_list: PDPropertyList
    ) -> None:
        self._property_lists[indirect] = property_list

    # ---------- maintenance ----------

    def clear(self) -> None:
        """Drop every cached entry across all categories. No upstream
        counterpart (PDFBox relies on JVM GC of soft references); pypdfbox
        exposes an explicit hook for tests and long-running services that
        rotate documents."""
        self._fonts.clear()
        self._xobjects.clear()
        self._color_spaces.clear()
        self._patterns.clear()
        self._shadings.clear()
        self._ext_g_states.clear()
        self._property_lists.clear()
