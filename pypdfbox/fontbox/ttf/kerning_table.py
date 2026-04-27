from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .kerning_subtable import KerningSubtable
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont


class KerningTable(TTFTable):
    """``kern`` — the TrueType kerning table.

    Mirrors ``org.apache.fontbox.ttf.KerningTable``. The on-disk decoding
    is delegated to ``fontTools.ttLib`` — this class is only the API
    shim that preserves PDFBox's ``getSubtables`` /
    ``getHorizontalKerningSubtable`` surface and wraps each fontTools
    subtable inside a :class:`KerningSubtable` view.
    """

    TAG: str = "kern"

    def __init__(self) -> None:
        super().__init__()
        self._subtables: list[KerningSubtable] = []
        # Upstream stores the version too — fontTools exposes it on the
        # parent table as a float (0 for OpenType, 1.0 for Apple AAT).
        self._version: float | int = 0

    @classmethod
    def from_fonttools(
        cls,
        ft_kern: Any,
        ttf: TrueTypeFont,
    ) -> KerningTable:
        """Build a :class:`KerningTable` view backed by a fontTools
        ``table__k_e_r_n`` instance.

        Used by :meth:`TrueTypeFont.get_kerning_table`. Each fontTools
        subtable is wrapped in :class:`KerningSubtable` so callers see the
        upstream API surface.
        """
        view = cls()
        view._version = ft_kern.version  # noqa: SLF001
        view._subtables = [  # noqa: SLF001
            KerningSubtable(sub, ttf) for sub in (ft_kern.kernTables or [])
        ]
        view.initialized = True
        return view

    # ---------- accessors ----------

    def get_subtables(self) -> list[KerningSubtable]:
        """Return all kerning subtables in document order."""
        return list(self._subtables)

    def get_version(self) -> float | int:
        """``kern`` table version (0 for the OpenType layout PDFBox parses;
        1.0 for the Apple AAT extended layout)."""
        return self._version

    def get_horizontal_kerning_subtable(
        self, cross: bool = False
    ) -> KerningSubtable | None:
        """Return the first subtable that supports horizontal kerning.

        ``cross=False`` (default) finds an inline-progression horizontal
        subtable; ``cross=True`` finds a cross-stream horizontal subtable.
        Returns ``None`` if no matching subtable exists, matching upstream.
        """
        for s in self._subtables:
            if s.is_horizontal_kerning(cross):
                return s
        return None


__all__ = ["KerningTable"]
