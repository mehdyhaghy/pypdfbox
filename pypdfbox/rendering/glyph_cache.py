"""Simple glyph-outline cache keyed by character code.

Mirrors ``org.apache.pdfbox.rendering.GlyphCache``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_vector_font import PDVectorFont

_LOG = logging.getLogger(__name__)


class GlyphCache:
    """Cache glyph outlines keyed by character code."""

    def __init__(self, font: PDVectorFont) -> None:
        self.font = font
        self._cache: dict[int, Any] = {}

    def get_path_for_character_code(self, code: int) -> Any:
        """Return the cached :class:`GeneralPath`-like outline for ``code``.

        Returns an empty path on missing-glyph errors, matching upstream
        warning behaviour.
        """
        cached = self._cache.get(code)
        if cached is not None:
            return cached
        font = self.font
        try:
            has_glyph = font.has_glyph(code) if hasattr(font, "has_glyph") else True
            if not has_glyph:
                font_name = getattr(font, "get_name", lambda: "?")()
                # Mirror upstream's special-casing of LF (PDFBOX-4001).
                if hasattr(font, "code_to_cid"):
                    cid = font.code_to_cid(code)
                    _LOG.warning("No glyph for code %s (CID %04x) in font %s", code, cid, font_name)
                else:
                    _LOG.warning("No glyph for code %s in font %s", code, font_name)
                    is_std14 = getattr(font, "is_standard14", lambda: False)()
                    if code == 10 and is_std14:
                        path: Any = _empty_path()
                        self._cache[code] = path
                        return path
            if hasattr(font, "get_normalized_path"):
                path = font.get_normalized_path(code)
            else:
                path = _empty_path()
            self._cache[code] = path
            return path
        except OSError as exc:
            _LOG.error("Glyph rendering failed for code %s: %s", code, exc)
            return _empty_path()


def _empty_path() -> Any:
    """Return a placeholder for ``java.awt.geom.GeneralPath``.

    pypdfbox doesn't ship a path type yet; callers in the renderer treat
    a ``list`` of path operations as the path equivalent.
    """
    return []


__all__ = ["GlyphCache"]
