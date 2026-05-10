from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .true_type_font import TrueTypeFont

if TYPE_CHECKING:
    from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
    from pypdfbox.fontbox.cff.cff_font import CFFFont
    from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
    from pypdfbox.fontbox.ttf.glyph_table import GlyphTable
    from pypdfbox.fontbox.ttf.ttf_data_stream import TTFDataStream

    AnyCFF = CFFFont | CFFCIDFont | CFFType1Font


# 0x469EA8A9 is the IEEE-754 single-precision encoding of the float
# whose 4-byte big-endian SFNT-version field is the ASCII tag ``OTTO``
# (0x4F, 0x54, 0x54, 0x4F). Upstream stores the version as a Java
# ``float`` and fingerprints it via ``Float.floatToIntBits`` to avoid a
# table lookup; we replicate the same fingerprint so a TTFParser that
# pushes a synthetic version through :meth:`set_version` agrees with
# upstream byte-for-byte. See OpenTypeFont.java line 44.
_OTTO_FLOAT_BITS: int = 0x469EA8A9


class OpenTypeFont(TrueTypeFont):
    """OpenType (OTF/TTF) font.

    Mirrors ``org.apache.fontbox.ttf.OpenTypeFont`` (extends
    :class:`TrueTypeFont`). An OpenType wrapper can carry either
    TrueType-flavoured outlines (``glyf`` / ``loca``) or CFF outlines
    (``CFF `` / ``CFF2``); the SFNT version tag (``OTTO`` for CFF) is the
    discriminator captured by :meth:`set_version`.

    The CFF payload is exposed through :meth:`get_cff`, which projects
    the bytes onto the appropriate :class:`CFFFont` subclass (CID-keyed
    vs name-keyed) — this matches the upstream surface where callers
    routinely write ``otf.getCFF().getFont()`` to reach the CFF data.
    """

    def __init__(self, data: TTFDataStream) -> None:
        super().__init__(data)
        # Mirrors the package-private ``hasPostScriptTag`` field set by
        # :meth:`set_version` (OpenTypeFont.java line 29). Upstream
        # tracks the SFNT-version fingerprint independently of the
        # ``CFF ``/``CFF2`` table presence so a malformed font with the
        # wrong magic still reports its declared flavour.
        self._has_post_script_tag: bool = False
        # Cache the CFF projection. ``_cff_resolved`` records the
        # negative case so a repeat call on a font without a CFF table
        # short-circuits.
        self._cff: AnyCFF | None = None
        self._cff_resolved: bool = False

    # ---------- version / flavour discriminator -----------------------

    def set_version(self, version_value: float) -> None:
        """Record the SFNT version and remember whether it spelt ``OTTO``.

        Mirrors ``OpenTypeFont.setVersion(float)`` (OpenTypeFont.java
        line 42). The upstream method is package-private and called by
        :class:`TTFParser` while seeding the font; the override over the
        :class:`TrueTypeFont` base just adds the OTTO fingerprint check
        before delegating. We leave it public for parity with other
        ported parser hooks — Python has no package visibility — but
        callers outside parsing should not invoke it directly.
        """
        # ``Float.floatToIntBits`` round-trips an ``OTTO``-flavoured
        # SFNT version through IEEE-754 single precision; we encode the
        # incoming float the same way so synthetic test vectors match
        # upstream bit-for-bit.
        try:
            import struct  # noqa: PLC0415

            bits = struct.unpack(">I", struct.pack(">f", float(version_value)))[0]
        except (struct.error, OverflowError, ValueError):
            bits = 0
        self._has_post_script_tag = bits == _OTTO_FLOAT_BITS
        # The base ``TrueTypeFont`` exposes a ``get_version()`` reading
        # the ``name`` table; the SFNT-header version is parser-only
        # state. We keep it as a private attribute to avoid clashing
        # with the name-table accessor.
        self._sfnt_version: float = float(version_value)

    # ---------- predicates --------------------------------------------

    def is_post_script(self) -> bool:
        """``True`` when this font carries PostScript (CFF) outlines.

        Mirrors ``OpenTypeFont.isPostScript()`` (OpenTypeFont.java line
        94): true when the SFNT magic spelt ``OTTO`` *or* the directory
        contains a ``CFF ``/``CFF2`` table. The first check matters when
        the parser sees the magic but the table directory is malformed;
        the second matters when an OTF wrapper is built directly from
        bytes (no parser dispatch).
        """
        return (
            self._has_post_script_tag
            or self.has_table("CFF ")
            or self.has_table("CFF2")
        )

    def is_supported_otf(self) -> bool:
        """``True`` when the font carries supported OpenType outlines.

        Mirrors ``OpenTypeFont.isSupportedOTF()`` (OpenTypeFont.java
        line 108). Three flavours exist in the wild:

        * TrueType outlines (``glyf``) — supported.
        * CFF outlines version 1 (``CFF ``) — supported.
        * CFF outlines version 2 (``CFF2``) — *not* yet supported.

        The upstream rule: reject only the case where the SFNT version
        was ``OTTO`` *and* the directory ships ``CFF2`` without a
        ``CFF `` fallback.
        """
        return not (
            self._has_post_script_tag
            and not self.has_table("CFF ")
            and self.has_table("CFF2")
        )

    def has_layout_tables(self) -> bool:
        """``True`` if the font carries any OpenType Layout (Advanced
        Typographic) table.

        Mirrors ``OpenTypeFont.hasLayoutTables()`` (OpenTypeFont.java
        line 122) — checks for ``BASE``, ``GDEF``, ``GPOS``, ``GSUB`` or
        ``OTL `` (the latter being the legacy Apple table name). Used by
        upstream callers that need to decide whether to route shaping
        through HarfBuzz vs the simpler cmap-only path.
        """
        return any(
            self.has_table(tag) for tag in ("BASE", "GDEF", "GPOS", "GSUB", "OTL ")
        )

    # ---------- glyf accessor (override) -------------------------------

    def get_glyph_table(self) -> GlyphTable | None:
        """Return the ``glyf`` table view, refusing CFF-flavoured fonts.

        Mirrors ``OpenTypeFont.getGlyph()`` (OpenTypeFont.java line 66)
        which raises ``UnsupportedOperationException`` when the font is
        PostScript-flavoured. CFF fonts have no ``glyf`` table, so the
        accessor would otherwise return ``None`` and silently mask a
        caller bug; upstream prefers a hard failure.
        """
        if self._has_post_script_tag:
            msg = "OTF fonts do not have a glyf table"
            raise NotImplementedError(msg)
        return super().get_glyph_table()

    # ---------- glyph path (override) ----------------------------------

    def get_path(self, gid: int | str) -> Any | None:
        """Return the outline of a glyph, routing through CFF when present.

        Mirrors ``OpenTypeFont.getPath(String)`` (OpenTypeFont.java line
        76). Upstream only overrides the name-keyed signature; integer
        ``gid`` keeps the parent's ``glyf``-based behaviour. When the
        font is CFF-flavoured *and* supported, we resolve the name to a
        GID, fetch the Type 2 charstring, and ask it for its path —
        matching ``getCFF().getFont().getType2CharString(gid).getPath()``.
        """
        if isinstance(gid, str) and self._has_post_script_tag and self.is_supported_otf():
            cff = self.get_cff()
            if cff is None:
                return None
            resolved_gid = self.name_to_gid(gid)
            cs = cff.get_type2_char_string(resolved_gid)
            if cs is None:
                return None
            return cs.get_path()
        return super().get_path(gid)

    # ---------- CFF accessor ------------------------------------------

    def get_cff(self) -> AnyCFF | None:
        """Return the parsed CFF/Type 1C font, or ``None`` if absent.

        Mirrors ``OpenTypeFont.getCFF()`` (OpenTypeFont.java line 56)
        which throws ``UnsupportedOperationException`` for non-CFF
        fonts. Upstream's contract is "callers should have probed
        :meth:`is_post_script` first" — but the only consequence of a
        bad call is a missing-table exception. We return ``None`` (the
        Pythonic sibling of "no such accessor") for the common
        TTF-flavoured-OpenTypeFont case, since multiple upstream
        callers (e.g. ``OTFParser._check_tables``) already gate on the
        flavour before invoking us.

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
