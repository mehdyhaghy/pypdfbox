"""Cmap lookup with GSUB single-substitution applied.

Mirrors ``org.apache.fontbox.ttf.SubstitutingCmapLookup``
(upstream ``SubstitutingCmapLookup.java`` L26-53).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .cmap_lookup import CmapLookup
from .open_type_script import get_script_tags

if TYPE_CHECKING:
    from .cmap_subtable import CmapSubtable
    from .glyph_substitution_table import GlyphSubstitutionTable


class SubstitutingCmapLookup(CmapLookup):
    """Cmap lookup that pipes results through the font's GSUB table.

    Mirrors ``SubstitutingCmapLookup.java`` L26-53. Each
    :meth:`get_glyph_id` call:

    1. Resolves the base glyph id via the wrapped
       :class:`CmapSubtable`.
    2. Looks up the OpenType script tags for the codepoint via
       :func:`OpenTypeScript.get_script_tags`.
    3. Asks the font's :class:`GlyphSubstitutionTable` to apply any
       enabled features (single-substitution lookups, typically
       ``locl`` / ``ccmp`` / ``liga``) and returns the substituted gid.

    Reverse-direction :meth:`get_char_codes` walks through
    :meth:`GlyphSubstitutionTable.get_unsubstitution` first, then
    queries the cmap.
    """

    def __init__(
        self,
        cmap: CmapSubtable,
        gsub: GlyphSubstitutionTable,
        enabled_features: list[str] | tuple[str, ...] | None,
    ) -> None:
        self._cmap = cmap
        self._gsub = gsub
        # Store as a list to keep upstream's mutable ``List<String>``
        # semantics — :meth:`GlyphSubstitutionTable.get_substitution`
        # accepts either ``None`` (apply everything on the matched
        # script) or an explicit feature list.
        self._enabled_features: list[str] | None = (
            None if enabled_features is None else list(enabled_features)
        )

    def get_glyph_id(self, character_code: int) -> int:
        """Mirror ``getGlyphId(int)`` (SubstitutingCmapLookup.java L40-46).

        Empty / ``None`` script-tag list is forwarded as-is so the GSUB
        layer falls back to its first-script default.
        """
        gid = self._cmap.get_glyph_id(character_code)
        script_tags = get_script_tags(character_code)
        return self._gsub.get_substitution(
            gid,
            list(script_tags) if script_tags else None,
            self._enabled_features,
        )

    def get_char_codes(self, gid: int) -> list[int] | None:
        """Mirror ``getCharCodes(int)`` (SubstitutingCmapLookup.java L48-52)."""
        return self._cmap.get_char_codes(self._gsub.get_unsubstitution(gid))


__all__ = ["SubstitutingCmapLookup"]
