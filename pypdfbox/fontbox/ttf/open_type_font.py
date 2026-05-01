from __future__ import annotations

from typing import TYPE_CHECKING, Union

from .true_type_font import TrueTypeFont

if TYPE_CHECKING:
    from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
    from pypdfbox.fontbox.cff.cff_font import CFFFont
    from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

    AnyCFF = Union[CFFFont, CFFCIDFont, CFFType1Font]


class OpenTypeFont(TrueTypeFont):
    """OpenType font with CFF outlines (``OTTO`` SFNT flavour).

    Mirrors ``org.apache.fontbox.ttf.OpenTypeFont`` (extends
    :class:`TrueTypeFont`). The only structural difference vs a
    TrueType-flavoured font is the ``CFF `` table (note trailing space),
    which carries Type 1C / CFF outlines instead of the ``glyf`` /
    ``loca`` pair.

    The CFF payload is exposed through :meth:`get_cff`, which projects
    the bytes onto the appropriate :class:`CFFFont` subclass (CID-keyed
    vs name-keyed) — this matches the upstream surface where callers
    routinely write ``otf.getCFF().getFont()`` to reach the CFF data.
    """

    def __init__(self, data) -> None:  # noqa: ANN001 — TTFDataStream, kept untyped for cycle-free import
        super().__init__(data)
        # Cache the CFF projection. ``_cff_resolved`` records the
        # negative case so a repeat call on a font without a CFF table
        # short-circuits.
        self._cff: AnyCFF | None = None
        self._cff_resolved: bool = False

    # ---------- predicates --------------------------------------------

    def is_post_script(self) -> bool:
        """Always ``True`` for an OpenType/CFF font.

        Mirrors ``OpenTypeFont.isPostScript()`` — the upstream
        :class:`TrueTypeFont` returns ``False``; this subclass overrides
        to ``True`` because CFF outlines are PostScript-flavoured.
        """
        return True

    def is_supported_otf(self) -> bool:
        """``True`` when the font carries a usable ``CFF `` table.

        Mirrors ``OpenTypeFont.isSupportedOTF()``: an OTF wrapper is
        only useful if its CFF payload is parseable. This delegates to
        :meth:`has_table` for cheap detection; full validation happens
        inside :meth:`get_cff`.
        """
        return self.has_table("CFF ")

    def has_layout_tables(self) -> bool:
        """``True`` if the font carries any OpenType Layout (Advanced
        Typographic) table.

        Mirrors ``OpenTypeFont.hasLayoutTables()`` — checks for ``BASE``,
        ``GDEF``, ``GPOS``, ``GSUB`` or ``OTL `` (the latter being the
        legacy Apple table name). Used by upstream callers that need to
        decide whether to route shaping through HarfBuzz vs the simpler
        cmap-only path.
        """
        return any(
            self.has_table(tag) for tag in ("BASE", "GDEF", "GPOS", "GSUB", "OTL ")
        )

    # ---------- CFF accessor ------------------------------------------

    def get_cff(self) -> AnyCFF | None:
        """Return the parsed CFF/Type 1C font, or ``None`` if absent.

        Picks the concrete subclass based on the CFF Top DICT:

        * presence of ROS (Registry/Ordering/Supplement) →
          :class:`CFFCIDFont` (CID-keyed CFF, used by Type 0 PDF fonts).
        * otherwise → :class:`CFFType1Font` (name-keyed CFF, used by
          Type 1C PDF fonts).

        Result is cached, including the negative case.
        """
        if self._cff_resolved:
            return self._cff
        self._cff_resolved = True
        # ``CFF `` (trailing space) is the SFNT tag for the CFF table.
        if "CFF " not in self._tt:
            self._cff = None
            return None
        # fontTools resolves the CFF table into a ``cff`` attribute that
        # holds a ``CFFFontSet``. Re-serialise the table bytes and hand
        # them to the cluster's pure-Python wrapper so the returned
        # object is the same shape callers see when they parse a
        # ``/FontFile3`` stream directly.
        cff_table = self._tt["CFF "]
        # ``compile`` accepts the parent TTFont and returns the on-wire
        # CFF byte payload. This avoids reaching into private fontTools
        # tree shapes — the bytes round-trip cleanly through CFFFont.
        try:
            cff_bytes = cff_table.compile(self._tt)
        except Exception:  # noqa: BLE001
            # Some malformed embedded subsets refuse to recompile; fall
            # back to the cached raw bytes that fontTools recorded
            # during decompile.
            cff_bytes = bytes(getattr(cff_table, "data", b""))
        if not cff_bytes:
            self._cff = None
            return None

        # Decide CID-keyed vs name-keyed from the parsed Top DICT
        # before constructing the wrapper, so we hand off to the right
        # subclass without a redundant decompile.
        font_set = getattr(cff_table, "cff", None)
        is_cid = False
        if font_set is not None and getattr(font_set, "fontNames", None):
            top = font_set[font_set.fontNames[0]]
            if hasattr(top, "ROS") or "ROS" in getattr(top, "rawDict", {}):
                is_cid = True

        if is_cid:
            from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont  # noqa: PLC0415

            self._cff = CFFCIDFont.from_bytes(cff_bytes)
        else:
            from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font  # noqa: PLC0415

            self._cff = CFFType1Font.from_bytes(cff_bytes)
        return self._cff


__all__ = ["OpenTypeFont"]
