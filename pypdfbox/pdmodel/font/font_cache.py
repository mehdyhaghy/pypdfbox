"""In-memory soft-reference cache for system fonts.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontCache`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontCache.java``
lines 31-58).

Upstream stores ``Map<FontInfo, SoftReference<FontBoxFont>>``. Python's
:mod:`weakref` provides ``ref()`` (no soft semantics — GC reclaims
weakly-referenced objects immediately when no strong reference exists),
which is closer to a *weak* reference than a *soft* one. The closest
practical equivalent on CPython is a plain dict that callers can purge
manually (matches upstream's ``"PDFBox is free to purge this cache at
will"`` docstring).

Implementation choice: hold strong references but expose
:meth:`clear` so callers can drop the cache. This is consistent with
upstream's contract — the cache is advisory, not authoritative.
"""

from __future__ import annotations

import threading
import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.fontbox.font_box_font import FontBoxFont
    from pypdfbox.fontbox.font_info import FontInfo


class FontCache:
    """Soft-reference cache for :class:`FontBoxFont` keyed by :class:`FontInfo`.

    Mirrors upstream Java (line 31-58). Thread-safe via a
    :class:`threading.Lock` (upstream uses ``ConcurrentHashMap``).
    """

    def __init__(self) -> None:
        # weakref.WeakValueDictionary is the closest Python analogue to
        # ``Map<K, SoftReference<V>>`` — entries vanish when no other
        # strong reference exists. Fall back to a regular dict for
        # FontInfo / FontBoxFont implementations that don't support
        # weak references (e.g. when callers register dataclasses).
        self._cache: weakref.WeakValueDictionary[FontInfo, FontBoxFont] = (
            weakref.WeakValueDictionary()
        )
        # Strong fallback for types that don't allow weak refs.
        self._strong: dict[FontInfo, FontBoxFont] = {}
        self._lock = threading.Lock()

    def add_font(self, info: FontInfo, font: FontBoxFont) -> None:
        """Insert *font* into the cache under key *info*.

        Mirrors upstream ``addFont(FontInfo, FontBoxFont)`` (Java line
        41-44).
        """
        with self._lock:
            try:
                self._cache[info] = font
            except TypeError:
                # Object doesn't support weak refs (e.g. some
                # ``__slots__`` classes without ``__weakref__``).
                # Fall back to a strong-reference dict.
                self._strong[info] = font

    def get_font(self, info: FontInfo) -> FontBoxFont | None:
        """Return the cached :class:`FontBoxFont` for *info*, or ``None``.

        Mirrors upstream ``getFont(FontInfo)`` (Java line 53-57). Returns
        ``None`` when the cache has no entry or the soft reference has
        been cleared.
        """
        with self._lock:
            font = self._cache.get(info)
            if font is not None:
                return font
            return self._strong.get(info)

    def clear(self) -> None:
        """Discard all cached entries.

        No upstream equivalent — provided so callers can implement the
        "PDFBox is free to purge this cache at will" contract.
        """
        with self._lock:
            self._cache.clear()
            self._strong.clear()


__all__ = ["FontCache"]
