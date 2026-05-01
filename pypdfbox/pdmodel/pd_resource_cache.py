from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.cos import COSObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
    from pypdfbox.pdmodel.font.pd_font import PDFont
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
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

    # ---------- CID fonts (default no-op for binary compatibility) ----------

    def get_cid_font(self, indirect: COSObject) -> PDCIDFont | None:
        """Return the cached :class:`PDCIDFont` for ``indirect``, or ``None``.
        Mirrors upstream ``ResourceCache.getCIDFont`` (default ``null``)."""
        return None

    def put_cid_font(self, indirect: COSObject, cid_font: PDCIDFont) -> None:
        """Cache ``cid_font`` under ``indirect``. Mirrors upstream
        ``ResourceCache.put(COSObject, PDCIDFont)`` default (no-op)."""

    # ---------- font descriptors ----------

    def get_font_descriptor(
        self, indirect: COSObject
    ) -> PDFontDescriptor | None:
        """Return the cached :class:`PDFontDescriptor` for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.getFontDescriptor``."""
        return None

    def put_font_descriptor(
        self, indirect: COSObject, font_descriptor: PDFontDescriptor
    ) -> None:
        """Cache ``font_descriptor`` under ``indirect``. Mirrors upstream
        default ``put(COSObject, PDFontDescriptor)`` (no-op)."""

    # ---------- removal hooks (default ``None``, matching upstream) ----------

    def remove_color_space(self, indirect: COSObject) -> PDColorSpace | None:
        """Remove and return the cached color space for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeColorSpace``."""
        return None

    def remove_ext_g_state(
        self, indirect: COSObject
    ) -> PDExtendedGraphicsState | None:
        """Remove and return the cached extended graphics state for
        ``indirect``, or ``None``. Mirrors upstream
        ``ResourceCache.removeExtState``."""
        return None

    def remove_font(self, indirect: COSObject) -> PDFont | None:
        """Remove and return the cached font for ``indirect``, or ``None``.
        Mirrors upstream ``ResourceCache.removeFont``."""
        return None

    def remove_cid_font(self, indirect: COSObject) -> PDCIDFont | None:
        """Remove and return the cached CID font for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeCIDFont``."""
        return None

    def remove_font_descriptor(
        self, indirect: COSObject
    ) -> PDFontDescriptor | None:
        """Remove and return the cached font descriptor for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeFontDescriptor``."""
        return None

    def remove_shading(self, indirect: COSObject) -> PDShading | None:
        """Remove and return the cached shading for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeShading``."""
        return None

    def remove_pattern(self, indirect: COSObject) -> PDAbstractPattern | None:
        """Remove and return the cached pattern for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removePattern``."""
        return None

    def remove_property_list(
        self, indirect: COSObject
    ) -> PDPropertyList | None:
        """Remove and return the cached property list for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeProperties``."""
        return None

    def remove_x_object(self, indirect: COSObject) -> PDXObject | None:
        """Remove and return the cached XObject for ``indirect``, or
        ``None``. Mirrors upstream ``ResourceCache.removeXObject``."""
        return None


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
        self._cid_fonts: dict[COSObject, PDCIDFont] = {}
        self._font_descriptors: dict[COSObject, PDFontDescriptor] = {}
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

    # ---------- CID fonts ----------

    def get_cid_font(self, indirect: COSObject) -> PDCIDFont | None:
        return self._cid_fonts.get(indirect)

    def put_cid_font(self, indirect: COSObject, cid_font: PDCIDFont) -> None:
        self._cid_fonts[indirect] = cid_font

    # ---------- font descriptors ----------

    def get_font_descriptor(
        self, indirect: COSObject
    ) -> PDFontDescriptor | None:
        return self._font_descriptors.get(indirect)

    def put_font_descriptor(
        self, indirect: COSObject, font_descriptor: PDFontDescriptor
    ) -> None:
        self._font_descriptors[indirect] = font_descriptor

    # ---------- removal hooks ----------

    def remove_color_space(self, indirect: COSObject) -> PDColorSpace | None:
        return self._color_spaces.pop(indirect, None)

    def remove_ext_g_state(
        self, indirect: COSObject
    ) -> PDExtendedGraphicsState | None:
        return self._ext_g_states.pop(indirect, None)

    def remove_font(self, indirect: COSObject) -> PDFont | None:
        return self._fonts.pop(indirect, None)

    def remove_cid_font(self, indirect: COSObject) -> PDCIDFont | None:
        return self._cid_fonts.pop(indirect, None)

    def remove_font_descriptor(
        self, indirect: COSObject
    ) -> PDFontDescriptor | None:
        return self._font_descriptors.pop(indirect, None)

    def remove_shading(self, indirect: COSObject) -> PDShading | None:
        return self._shadings.pop(indirect, None)

    def remove_pattern(self, indirect: COSObject) -> PDAbstractPattern | None:
        return self._patterns.pop(indirect, None)

    def remove_property_list(
        self, indirect: COSObject
    ) -> PDPropertyList | None:
        return self._property_lists.pop(indirect, None)

    def remove_x_object(self, indirect: COSObject) -> PDXObject | None:
        return self._xobjects.pop(indirect, None)

    # ---------- maintenance ----------

    def clear(self) -> None:
        """Drop every cached entry across all categories. No upstream
        counterpart (PDFBox relies on JVM GC of soft references); pypdfbox
        exposes an explicit hook for tests and long-running services that
        rotate documents."""
        self._fonts.clear()
        self._cid_fonts.clear()
        self._font_descriptors.clear()
        self._xobjects.clear()
        self._color_spaces.clear()
        self._patterns.clear()
        self._shadings.clear()
        self._ext_g_states.clear()
        self._property_lists.clear()
