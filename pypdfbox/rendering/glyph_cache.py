"""Simple glyph-outline cache keyed by character code.

Mirrors ``org.apache.pdfbox.rendering.GlyphCache``.
"""

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
        # (code, ppem) -> hinted path, or None when the font does not hint
        # that glyph / ppem. Mirrors upstream's ``hintedCache`` map, but
        # keeps the raw "no hinting" decision so the renderer can fall
        # back to its own unhinted outline source.
        self._hinted_cache: dict[tuple[int, int], Any] = {}

    def get_path_for_character_code(self, code: int, ppem: int | None = None) -> Any:
        """Return the cached :class:`GeneralPath`-like outline for ``code``.

        Mirrors upstream's two overloads: ``getPathForCharacterCode(int)``
        and ``getPathForCharacterCode(int, int)``. With ``ppem`` given,
        the grid-fitted (hinted) path at that ppem is returned, falling
        back to the unhinted path when the font does not hint that
        glyph / ppem; results are cached per ``(code, ppem)``.

        Returns an empty path on missing-glyph errors, matching upstream
        warning behaviour.
        """
        if ppem is not None:
            hinted = self._get_hinted_path(code, ppem)
            return hinted if hinted is not None else self.get_path_for_character_code(code)
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


    def _get_hinted_path(self, code: int, ppem: int) -> Any:
        """Return the cached hinted path for ``(code, ppem)`` or ``None``."""
        key = (code, ppem)
        if key in self._hinted_cache:
            return self._hinted_cache[key]
        path: Any = None
        getter = getattr(self.font, "get_hinted_normalized_path", None)
        if callable(getter):
            try:
                path = getter(code, ppem)
            except OSError as exc:
                font_name = getattr(self.font, "get_name", lambda: "?")()
                _LOG.warning("Hinting failed for code %s in font %s: %s", code, font_name, exc)
                path = None
        self._hinted_cache[key] = path
        return path


def _empty_path() -> Any:
    """Return a placeholder for ``java.awt.geom.GeneralPath``.

    pypdfbox doesn't ship a path type yet; callers in the renderer treat
    a ``list`` of path operations as the path equivalent.
    """
    return []


__all__ = ["GlyphCache"]
