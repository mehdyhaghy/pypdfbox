from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .glyph_data import GlyphData
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class GlyphTable(TTFTable):
    """``glyf`` — required TrueType table holding glyph outlines.

    Mirrors ``org.apache.fontbox.ttf.GlyphTable`` at the public-method
    level. Internally the per-glyph payload is parsed by ``fontTools``
    (``TTFont["glyf"]``) rather than by a hand-rolled
    ``GlyfSimpleDescript`` / ``GlyfCompositeDescript`` / ``GlyphRenderer``
    chain — we hand the parsing to the (MIT-licensed) library and only
    wrap the lookup surface.

    A :class:`GlyphTable` is constructed lazily on demand by
    :meth:`pypdfbox.fontbox.ttf.TrueTypeFont.get_glyph` — direct
    instantiation by callers is unusual.
    """

    TAG: str = "glyf"

    def __init__(self) -> None:
        super().__init__()
        self._glyf_table: Any | None = None  # fontTools ``_g_l_y_f`` instance
        self._glyph_order: list[str] = []
        self._num_glyphs: int = 0
        self._units_per_em: int = 1000
        # Cache of materialised :class:`GlyphData` views keyed by gid.
        # Mirrors upstream's ``glyphs[]`` array — populated lazily via
        # ``get_glyph``. Upstream caps the cache at 100 entries to keep
        # memory bounded for huge fonts; we do the same.
        self._glyphs: list[GlyphData | None] | None = None
        self._cached: int = 0

    # ---- upstream constants (public for callers that mirror Java) ----
    MAX_CACHE_SIZE: int = 5000
    MAX_CACHED_GLYPHS: int = 100

    # ---- bridge from fontTools-backed TrueTypeFont ----

    def _bind(self, ttf: TrueTypeFont) -> None:
        """Wire this table to a fontTools-parsed font.

        The pypdfbox :class:`TrueTypeFont` does not stream-read tables in
        the upstream sense — fontTools has already parsed the SFNT — so
        we expose a private ``_bind`` shortcut instead of overriding
        :meth:`TTFTable.read`. Called by ``TrueTypeFont.get_glyph``.
        """
        self._glyf_table = ttf._tt["glyf"]  # noqa: SLF001
        self._glyph_order = list(ttf._tt.getGlyphOrder())  # noqa: SLF001
        self._num_glyphs = ttf.get_number_of_glyphs()
        self._units_per_em = ttf.get_units_per_em()
        if self._num_glyphs < self.MAX_CACHE_SIZE:
            self._glyphs = [None] * self._num_glyphs
        else:
            self._glyphs = None
        self.initialized = True

    # ---- accessors mirroring upstream surface ----

    def get_glyph(self, gid: int) -> GlyphData | None:
        """Return the :class:`GlyphData` for ``gid``.

        Returns ``None`` for out-of-range gids. Glyphs with no outline
        (zero-length glyf entries — typical for ``.notdef`` aliases or
        whitespace) come back as a non-``None`` empty :class:`GlyphData`
        with a zero bounding box, matching upstream's PDFBOX-5135 fix
        where composite-glyph resolution can't tolerate ``None`` here.
        """
        if gid < 0 or gid >= self._num_glyphs:
            return None
        if self._glyphs is not None and self._glyphs[gid] is not None:
            return self._glyphs[gid]
        if self._glyf_table is None:
            return None
        glyph_name = self._glyph_order[gid]
        glyph = GlyphData(
            glyf_table=self._glyf_table,
            glyph_name=glyph_name,
            units_per_em=self._units_per_em,
        )
        if (
            self._glyphs is not None
            and self._glyphs[gid] is None
            and self._cached < self.MAX_CACHED_GLYPHS
        ):
            self._glyphs[gid] = glyph
            self._cached += 1
        return glyph

    def get_glyphs(self) -> list[GlyphData]:
        """Return all glyphs in glyph-ID order.

        Upstream exposes the underlying mutable ``GlyphData[]`` array;
        Python doesn't have a type-distinguishable array, so we
        materialise every glyph once and return the list. Use
        :meth:`get_glyph` for sparse access on large fonts.
        """
        result: list[GlyphData] = []
        for gid in range(self._num_glyphs):
            g = self.get_glyph(gid)
            if g is None:
                # Pad with an empty placeholder so list indices line up
                # with gids — should never happen for well-formed fonts.
                result.append(GlyphData())
            else:
                result.append(g)
        return result

    def set_glyphs(self, glyphs_value: list[GlyphData] | None) -> None:
        """Replace the cached glyph list.

        Mirrors upstream's ``setGlyphs(GlyphData[])``. Primarily used by
        subsetters that rebuild the glyph array externally.
        """
        if glyphs_value is None:
            self._glyphs = None
            self._cached = 0
            return
        self._glyphs = list(glyphs_value)
        self._cached = sum(1 for g in self._glyphs if g is not None)

    # ---- TTFTable override (delegates to ``_bind``) ----

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Populate this table from ``ttf``.

        The legacy ``data`` parameter is unused — the SFNT bytes have
        already been consumed by fontTools when ``ttf`` was constructed,
        so we just bind to the parsed ``glyf`` table.
        """
        self._bind(ttf)


__all__ = ["GlyphTable"]
