from __future__ import annotations

import io
from typing import Any


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used by ``PD…Font.get_glyph_path``.
    """
    from fontTools.pens.basePen import BasePen  # noqa: PLC0415

    class _PathPen(BasePen):
        def __init__(self) -> None:
            super().__init__(glyphSet=None)
            self.commands: list[tuple] = []

        def _moveTo(self, pt: tuple[float, float]) -> None:
            self.commands.append(("moveto", float(pt[0]), float(pt[1])))

        def _lineTo(self, pt: tuple[float, float]) -> None:
            self.commands.append(("lineto", float(pt[0]), float(pt[1])))

        def _curveToOne(
            self,
            pt1: tuple[float, float],
            pt2: tuple[float, float],
            pt3: tuple[float, float],
        ) -> None:
            self.commands.append(
                (
                    "curveto",
                    float(pt1[0]),
                    float(pt1[1]),
                    float(pt2[0]),
                    float(pt2[1]),
                    float(pt3[0]),
                    float(pt3[1]),
                )
            )

        def _closePath(self) -> None:
            self.commands.append(("closepath",))

    return _PathPen()


class CFFFont:
    """Compact Font Format (CFF / Type 1C) font wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.cff.CFFFont`` (subset). Internally, parsing is
    delegated to ``fontTools.cffLib.CFFFontSet`` (MIT) — we do not
    reimplement CFF DICT / INDEX / charstring parsing in pure Python.

    A CFF *font set* may contain multiple top-level fonts; for the
    PDF /FontFile3 use-case there is always exactly one and we expose
    it as the ``primary`` font transparently.
    """

    def __init__(self) -> None:
        self._fontset: Any | None = None  # fontTools CFFFontSet
        self._top: Any | None = None  # primary top-level font dict
        self._charstrings: Any | None = None
        self._private: Any | None = None
        self._font_matrix: list[float] | None = None
        self._units_per_em: int | None = None
        # Per-glyph width cache. CFF charstring widths are computed by
        # the T2WidthExtractor below and memoised here.
        self._widths: dict[str, float] = {}
        # Raw CFF byte payload (set by ``from_bytes``); upstream
        # ``CFFFont.getData()`` returns the original /FontFile3 stream.
        self._data: bytes | None = None
        # Top DICT mutation overlay for ``add_value_to_top_dict`` (upstream
        # ``CFFFont.addValueToTopDict``). fontTools' parsed Top DICT is
        # immutable for our purposes, so we keep a separate dict that
        # ``get_property`` / ``get_top_dict`` consult before falling
        # through to fontTools.
        self._top_overlay: dict[str, Any] = {}

    # ---------- factory ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "CFFFont":
        """Parse a CFF font from raw ``/FontFile3`` bytes (``/Subtype /Type1C``)."""
        from fontTools.cffLib import CFFFontSet  # noqa: PLC0415

        fontset = CFFFontSet()
        fontset.decompile(io.BytesIO(bytes(data)), otFont=None)
        if not fontset.fontNames:
            msg = "CFF font set is empty"
            raise OSError(msg)

        instance = cls()
        instance._fontset = fontset
        instance._top = fontset[fontset.fontNames[0]]
        instance._data = bytes(data)
        return instance

    # ---------- font-level metrics ----------

    @property
    def font_names(self) -> list[str]:
        if self._fontset is None:
            return []
        return list(self._fontset.fontNames)

    @property
    def name(self) -> str | None:
        names = self.font_names
        return names[0] if names else None

    # ---------- PDFBox-style accessors ------------------------------------
    # Mirror the public surface of upstream
    # ``org.apache.fontbox.cff.CFFFont``: small "get" wrappers around
    # the underlying fontTools TopDict / PrivateDict so callers can use
    # the familiar PDFBox API instead of poking at the fontTools tree.

    def get_name(self) -> str:
        """PDFBox: ``CFFFont.getName()`` — primary font name (PostScript name).

        Empty string when the font set has no entries (matches the
        upstream contract where the field is non-null but may be blank).
        """
        return self.name or ""

    def get_top_dict(self) -> dict[str, Any]:
        """PDFBox: ``CFFFont.getTopDict()`` — Top DICT entries as a plain
        ``dict`` snapshot. Backed by fontTools' ``TopDict.rawDict``,
        with any entries added via :meth:`add_value_to_top_dict`
        layered on top."""
        merged: dict[str, Any] = {}
        if self._top is not None:
            merged.update(self._top.rawDict)
        merged.update(self._top_overlay)
        return merged

    def add_value_to_top_dict(self, name: str, value: Any) -> None:
        """PDFBox: ``CFFFont.addValueToTopDict(String, Object)`` — store
        a custom value in the Top DICT overlay. Subsequent
        :meth:`get_top_dict` and :meth:`get_property` lookups see the
        new value. Setting ``None`` is a no-op (matches upstream's
        null-guard)."""
        if value is None:
            return
        self._top_overlay[name] = value

    def get_private_dict(self) -> dict[str, Any]:
        """PDFBox: ``CFFFont.getPrivateDict()`` — Private DICT entries.
        Empty dict when no Private DICT is present (e.g. CIDKeyed CFF
        whose Private DICTs live in /FDArray)."""
        if self._top is None:
            return {}
        try:
            priv = self._top.Private
        except AttributeError:
            return {}
        if priv is None:
            return {}
        return dict(getattr(priv, "rawDict", {}))

    def get_charset(self) -> list[str]:
        """PDFBox: ``CFFFont.getCharset()`` — ordered glyph names in
        CharStrings order (index = GID). For CID fonts the entries are
        ``cid<NNNNN>`` strings as fontTools synthesises them."""
        if self._top is None:
            return []
        charset = getattr(self._top, "charset", None)
        if charset is None:
            return []
        return [str(name) for name in charset]

    def get_num_char_strings(self) -> int:
        """PDFBox: ``CFFFont.getNumCharStrings()`` — total glyph count."""
        if self._top is None:
            return 0
        try:
            return len(self._charstrings_dict())
        except Exception:  # noqa: BLE001
            return 0

    def get_global_subrs(self) -> int:
        """Count of global subroutines in the parent CFF font set."""
        if self._top is None:
            return 0
        gsubrs = getattr(self._top, "GlobalSubrs", None)
        return len(gsubrs) if gsubrs is not None else 0

    def get_local_subrs(self) -> int:
        """Count of local subroutines in this font's Private DICT.

        Returns 0 when the font has no Private DICT or no /Subrs index
        (e.g. CIDKeyed CFF — local subrs live per-FD in /FDArray)."""
        if self._top is None:
            return 0
        try:
            priv = self._top.Private
        except AttributeError:
            return 0
        if priv is None:
            return 0
        subrs = getattr(priv, "Subrs", None)
        return len(subrs) if subrs is not None else 0

    def get_subrs(self) -> int:
        """Alias for :py:meth:`get_global_subrs` — kept for parity with
        upstream callers that use the shorter name."""
        return self.get_global_subrs()

    def is_cid_font(self) -> bool:
        """PDFBox: ``CFFFont.isCIDFont()`` — true when the Top DICT has
        ROS (Registry/Ordering/Supplement) set, marking the font as a
        CIDFont (CFF Type 0)."""
        if self._top is None:
            return False
        # fontTools surfaces ROS both as an attribute and a raw DICT key.
        if hasattr(self._top, "ROS"):
            return True
        return "ROS" in getattr(self._top, "rawDict", {})

    def get_property(self, name: str) -> Any | None:
        """PDFBox: ``CFFFont.getProperty(name)`` — generic Top DICT
        accessor by raw key name (e.g. ``"FullName"``, ``"FamilyName"``,
        ``"Weight"``, ``"FontBBox"``). Returns ``None`` for absent keys.

        The overlay populated by :meth:`add_value_to_top_dict` takes
        precedence over fontTools' parsed Top DICT.
        """
        if name in self._top_overlay:
            return self._top_overlay[name]
        if self._top is None:
            return None
        raw = getattr(self._top, "rawDict", {})
        if name in raw:
            return raw[name]
        # Some entries are exposed only as attributes after parsing.
        return getattr(self._top, name, None)

    # ---------- additional upstream accessors ----------

    def get_font_matrix(self) -> list[float]:
        """PDFBox: ``CFFFont.getFontMatrix()`` — six-element font matrix
        as a ``List<Number>``. Mirrors the :py:attr:`font_matrix`
        property; provided as a method for parity with upstream
        callers."""
        if self._top is None:
            return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
        return list(self.font_matrix)

    def get_font_b_box(self) -> list[float]:
        """PDFBox: ``CFFFont.getFontBBox()`` — Top DICT /FontBBox as a
        4-element ``[xMin, yMin, xMax, yMax]`` list. Defaults to
        ``[0,0,0,0]`` when missing (upstream throws ``IOException``;
        we diverge for ergonomics — callers can detect via
        ``bbox == [0,0,0,0]``).
        """
        bbox = self.get_property("FontBBox")
        if bbox is None:
            return [0.0, 0.0, 0.0, 0.0]
        try:
            return [float(v) for v in bbox]
        except (TypeError, ValueError):
            return [0.0, 0.0, 0.0, 0.0]

    # PDFBox naming convention: ``getFontBBox`` → ``get_font_b_box`` per
    # our snake_case rule. Provide the human-readable alias too.
    get_font_bbox = get_font_b_box

    def get_data(self) -> bytes:
        """PDFBox: ``CFFFont.getData()`` — return the raw CFF byte
        stream this font was decoded from. Empty bytes when the font
        was constructed without a backing payload (e.g. via
        :meth:`from_cff_font` re-wrapping)."""
        return self._data or b""

    def get_global_subr_index(self) -> list[bytes]:
        """PDFBox: ``CFFFont.getGlobalSubrIndex()`` — global subroutine
        bytecodes as a list of ``bytes``. Empty list when the font has
        no /GSubrs."""
        if self._top is None:
            return []
        gsubrs = getattr(self._top, "GlobalSubrs", None)
        if gsubrs is None:
            return []
        out: list[bytes] = []
        for entry in gsubrs:
            # fontTools T2CharString instances expose ``.bytecode`` post-decompile.
            bc = getattr(entry, "bytecode", None)
            if bc is not None:
                out.append(bytes(bc))
            elif isinstance(entry, (bytes, bytearray)):
                out.append(bytes(entry))
            else:
                out.append(b"")
        return out

    def get_char_string_bytes(self) -> list[bytes]:
        """PDFBox: ``CFFFont.getCharStringBytes()`` — per-glyph charstring
        bytecode in GID order. Empty list when the font is unparsed."""
        if self._top is None:
            return []
        try:
            cs_map = self._charstrings_dict()
        except Exception:  # noqa: BLE001
            return []
        out: list[bytes] = []
        for name in self.get_charset():
            try:
                cs = cs_map[name]
            except KeyError:
                out.append(b"")
                continue
            bc = getattr(cs, "bytecode", None)
            if bc is None:
                # fontTools may lazily compile on demand; trigger it.
                try:
                    cs.compile()
                except Exception:  # noqa: BLE001
                    out.append(b"")
                    continue
                bc = getattr(cs, "bytecode", None)
            out.append(bytes(bc) if bc is not None else b"")
        return out

    # ---------- charset name/SID/CID/GID lookups ----------
    # PDFBox surfaces these on ``CFFCharset``; we attach them directly to
    # ``CFFFont`` (one less wrapper layer) since fontTools doesn't model
    # the charset as a separate object the way upstream does.

    def get_name_for_gid(self, gid: int) -> str:
        """Glyph name for ``gid``, or ``".notdef"`` for out-of-range."""
        charset = self.get_charset()
        if 0 <= gid < len(charset):
            return charset[gid]
        return ".notdef"

    def get_gid_for_sid(self, sid: int) -> int:
        """Resolve a CFF SID (string id) to the GID whose glyph name
        matches the SID's string. Returns 0 (.notdef) for an unknown SID.

        This is the inverse of ``get_sid_for_gid``: charset is
        GID-ordered and each entry is a string identifier into the
        combined Standard Strings + STRING INDEX table.
        """
        name = self.get_string(sid)
        if not name:
            return 0
        for gid, candidate in enumerate(self.get_charset()):
            if candidate == name:
                return gid
        return 0

    def get_sid_for_gid(self, gid: int) -> int:
        """Resolve a GID to its CFF SID. Returns 0 (.notdef) for
        out-of-range GIDs or when the SID cannot be looked up."""
        name = self.get_name_for_gid(gid)
        return self.get_sid(name)

    def get_sid(self, name: str) -> int:
        """Resolve a glyph name to its CFF SID — first via the Standard
        Strings table (SIDs 0..390), then via the font's private STRING
        INDEX. Returns 0 (.notdef) for unknown names."""
        if not name:
            return 0
        # Standard SIDs first (immutable, font-independent).
        from fontTools.cffLib import cffStandardStrings  # noqa: PLC0415

        try:
            return cffStandardStrings.index(name)
        except ValueError:
            pass
        # Then this font's private STRING INDEX (SIDs ≥ 391).
        if self._fontset is not None:
            strings = getattr(self._fontset, "strings", None)
            if strings is not None:
                try:
                    table = list(strings.strings)
                except AttributeError:
                    table = []
                for i, candidate in enumerate(table):
                    if candidate == name:
                        return len(cffStandardStrings) + i
        return 0

    def get_string(self, sid: int) -> str:
        """Resolve a CFF SID to a glyph name string. SIDs 0..390 are
        the Standard Strings; higher SIDs index into the font's STRING
        INDEX. Returns an empty string for an unknown SID.
        """
        from fontTools.cffLib import cffStandardStrings  # noqa: PLC0415

        if sid < 0:
            return ""
        if sid < len(cffStandardStrings):
            return cffStandardStrings[sid]
        idx = sid - len(cffStandardStrings)
        if self._fontset is None:
            return ""
        strings = getattr(self._fontset, "strings", None)
        if strings is None:
            return ""
        try:
            table = list(strings.strings)
        except AttributeError:
            return ""
        if 0 <= idx < len(table):
            return str(table[idx])
        return ""

    def get_cid_for_gid(self, gid: int) -> int:
        """Resolve a GID to its CID for CIDKeyed fonts. For name-keyed
        fonts the CID space is undefined — we return ``gid`` unchanged
        as a sane fallback (matches the behaviour where charset entries
        are PostScript names, not CIDs).

        For CIDKeyed fonts fontTools synthesises ``cid<NNNNN>`` glyph
        names; we parse the suffix back out to recover the CID.
        """
        name = self.get_name_for_gid(gid)
        if name.startswith("cid") and name[3:].isdigit():
            return int(name[3:])
        return gid

    def get_gid_for_cid(self, cid: int) -> int:
        """Resolve a CID to a GID. Inverse of :meth:`get_cid_for_gid`.
        Returns 0 (.notdef) for an unmapped CID.
        """
        if cid < 0:
            return 0
        target = f"cid{cid:05d}"
        for gid, name in enumerate(self.get_charset()):
            if name == target:
                return gid
        return 0

    def get_default_width_x(self) -> float:
        """Private DICT ``defaultWidthX``. CFF spec §10: width assigned
        to glyphs whose charstring omits the leading width operand.

        For CIDKeyed CFF the Top DICT carries no Private DICT — the
        real values live in /FDArray and are FD-specific. Returns
        ``0.0`` here; CID-aware callers should use
        :meth:`CFFCIDFont.get_default_width_x_for_gid` instead.
        """
        if self._top is None:
            return 0.0
        try:
            priv = self._top.Private
        except AttributeError:
            return 0.0
        if priv is None:
            return 0.0
        return float(getattr(priv, "defaultWidthX", 0))

    def get_nominal_width_x(self) -> float:
        """Private DICT ``nominalWidthX``. CFF spec §10: when a charstring
        carries an explicit width operand, the actual advance is
        ``operand + nominalWidthX``.

        Returns ``0.0`` for CIDKeyed fonts (see
        :meth:`get_default_width_x` for the rationale).
        """
        if self._top is None:
            return 0.0
        try:
            priv = self._top.Private
        except AttributeError:
            return 0.0
        if priv is None:
            return 0.0
        return float(getattr(priv, "nominalWidthX", 0))

    def get_glyph_widths(self) -> dict[str, float]:
        """Batch view of advance widths keyed by glyph name. Computes
        widths lazily for any glyph not yet cached, then returns a copy
        of the cache so callers can mutate freely."""
        if self._top is None:
            return {}
        try:
            cs_map = self._charstrings_dict()
        except Exception:  # noqa: BLE001
            return {}
        for name in cs_map.keys():  # noqa: SIM118 — fontTools mapping isn't a real dict
            if name not in self._widths:
                self.get_width(name)
        return dict(self._widths)

    @property
    def font_matrix(self) -> list[float]:
        """Six-element font matrix. Default for CFF is ``[0.001 0 0 0.001 0 0]``."""
        if self._font_matrix is None:
            assert self._top is not None  # noqa: S101
            matrix = self._top.FontMatrix
            self._font_matrix = [float(v) for v in matrix]
        return self._font_matrix

    @property
    def units_per_em(self) -> int:
        """Derived from the font matrix's x-scale (matrix[0]).

        CFF defaults to ``[0.001 0 0 0.001 0 0]`` → 1000-unit em.
        """
        if self._units_per_em is None:
            scale = self.font_matrix[0]
            self._units_per_em = int(round(1.0 / scale)) if scale else 1000
        return self._units_per_em

    # ---------- glyph access ----------

    def _charstrings_dict(self) -> Any:
        if self._charstrings is None:
            assert self._top is not None  # noqa: S101
            self._charstrings = self._top.CharStrings
        return self._charstrings

    def has_glyph(self, name: str) -> bool:
        if self._top is None:
            return False
        try:
            return name in self._charstrings_dict()
        except Exception:  # noqa: BLE001
            return False

    def get_width(self, name: str) -> float:
        """Advance width of glyph ``name`` in *font units* (typically 1000-unit em).

        Uses fontTools' ``T2WidthExtractor`` to interpret the charstring
        prologue per CFF spec §3.1: a leading operand on the stack
        before the first moveto is interpreted as ``width - nominalWidthX``.
        Glyphs without a leading width operand default to ``defaultWidthX``.
        """
        cached = self._widths.get(name)
        if cached is not None:
            return cached
        cs_map = self._charstrings_dict()
        try:
            cs = cs_map[name]
        except KeyError:
            return 0.0

        from fontTools.misc.psCharStrings import T2WidthExtractor  # noqa: PLC0415

        assert self._top is not None  # noqa: S101
        # For name-keyed CFF the Private DICT lives on the Top DICT;
        # for CIDKeyed CFF the Top DICT has no Private DICT — instead
        # fontTools attaches the per-FD Private to each CharString via
        # ``cs.private``. Prefer that, then fall back to Top.Private,
        # then to a defaults-only stub.
        priv = getattr(cs, "private", None)
        if priv is None:
            try:
                priv = self._top.Private
            except AttributeError:
                priv = None
        # T2WidthExtractor needs the *actual* local Subrs index when the
        # charstring uses callsubr / callgsubr in its prologue. Passing
        # an empty list here used to yield 0 for many real-world fonts.
        local_subrs = getattr(priv, "Subrs", []) or [] if priv is not None else []
        extractor = T2WidthExtractor(
            local_subrs,
            self._top.GlobalSubrs,
            getattr(priv, "nominalWidthX", 0) if priv is not None else 0,
            getattr(priv, "defaultWidthX", 0) if priv is not None else 0,
        )
        try:
            extractor.execute(cs)
        except Exception:  # noqa: BLE001
            return 0.0
        width = float(extractor.width)
        self._widths[name] = width
        return width

    def get_path(self, name: str) -> list[tuple]:
        """Glyph outline for ``name`` as a list of draw commands in
        font units. Returns ``[]`` when the glyph is missing."""
        cs_map = self._charstrings_dict()
        try:
            cs = cs_map[name]
        except KeyError:
            return []
        pen = _make_path_pen()
        try:
            cs.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        return list(pen.commands)  # type: ignore[attr-defined]

    # ---------- Type 2 charstring accessor ---------------------------------

    def get_type2_char_string(self, cid_or_gid: int) -> Any:
        """PDFBox: ``CFFFont.getType2CharString(int cidOrGid)`` —
        return a :class:`Type2CharString` wrapper for the glyph at
        index ``cid_or_gid``.

        For name-keyed CFF fonts this is the GID; for CID-keyed fonts
        the upstream contract is that the caller passes a CID and the
        font does the CID→GID resolution. fontTools surfaces both
        flavours through the same ``CharStrings`` mapping (CID fonts
        use synthetic ``cid<NNNNN>`` names), so we just look up by
        ordinal in the GID-ordered charset.

        Returns a :class:`Type2CharString` whose ``get_path`` /
        ``get_width`` methods delegate to fontTools, never an exception
        for an out-of-range GID — instead an empty-program wrapper is
        returned so callers can probe ``get_path() == []``.
        """
        # Defer the import: type2_char_string.py imports from this
        # module's package, but the class itself doesn't depend on
        # CFFFont, so circular import is not a concern in practice.
        from .type2_char_string import Type2CharString  # noqa: PLC0415

        charset = self.get_charset()
        if not charset or cid_or_gid < 0 or cid_or_gid >= len(charset):
            # Out-of-range: return an empty wrapper. Upstream throws
            # IOException; we deliberately diverge for ergonomics —
            # callers can detect via ``get_path() == []``.
            return Type2CharString(
                font=self,
                font_name=self.get_name(),
                glyph_name="",
                gid=cid_or_gid,
                sequence=None,
                default_width_x=int(self.get_default_width_x()),
                nominal_width_x=int(self.get_nominal_width_x()),
            )

        glyph_name = charset[cid_or_gid]
        cs_map = self._charstrings_dict()
        try:
            cs = cs_map[glyph_name]
        except KeyError:
            cs = None
        return Type2CharString(
            font=self,
            font_name=self.get_name(),
            glyph_name=glyph_name,
            gid=cid_or_gid,
            sequence=cs,  # fontTools T2CharString from the parsed font
            default_width_x=int(self.get_default_width_x()),
            nominal_width_x=int(self.get_nominal_width_x()),
        )


__all__ = ["CFFFont"]
