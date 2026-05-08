from __future__ import annotations

import io
import struct
from typing import Any, BinaryIO


def _cff_string_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("latin-1")
    return str(value)


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used by ``PD…Font.get_glyph_path``.
    """
    from fontTools.pens.basePen import BasePen  # type: ignore[import-untyped]  # noqa: PLC0415

    class _PathPen(BasePen):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(glyphSet=None)
            self.commands: list[tuple[Any, ...]] = []

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

    # ---------- spec constants ----------
    # Adobe Technote #5176 §10: SIDs 0..390 index into the Standard
    # Strings table (immutable, font-independent); SIDs >= 391 index
    # into the per-font STRING INDEX.
    NUM_STANDARD_STRINGS: int = 391
    # CFF Top DICT default /CIDCount per Adobe Technote #5176 §9, Table 9.
    DEFAULT_CID_COUNT: int = 8720

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
        # Font name override populated by :meth:`set_name` (mirrors
        # upstream package-private ``CFFFont.setName``). When ``None`` the
        # primary fontset name is used.
        self._name_override: str | None = None

    # ---------- factory ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> CFFFont:
        """Parse a CFF font from raw ``/FontFile3`` bytes (``/Subtype /Type1C``)."""
        from fontTools.cffLib import CFFFontSet  # type: ignore[import-untyped]  # noqa: PLC0415

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
        if self._name_override is not None:
            return self._name_override
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

    def _copy_base_state_from(self, base: CFFFont) -> None:
        """Copy parsed base-font state when re-wrapping as a CFF subclass."""
        self._fontset = base._fontset
        self._top = base._top
        self._charstrings = base._charstrings
        self._private = base._private
        self._font_matrix = (
            list(base._font_matrix) if base._font_matrix is not None else None
        )
        self._units_per_em = base._units_per_em
        self._widths = dict(base._widths)
        self._data = base._data
        self._top_overlay = dict(base._top_overlay)
        self._name_override = base._name_override

    def set_name(self, name: str | None) -> None:
        """PDFBox: ``CFFFont.setName(String)`` — override the PostScript
        font name returned by :meth:`get_name`. Pass ``None`` to clear
        the override and fall back to the parsed fontset name.

        Upstream this is package-private; we expose it for parity with
        callers (and tests) that synthesise a :class:`CFFFont` outside
        the parser path."""
        self._name_override = name

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
            return int(cffStandardStrings.index(name))
        except ValueError:
            pass
        # Then this font's private STRING INDEX (SIDs ≥ NUM_STANDARD_STRINGS).
        if self._fontset is not None:
            strings = getattr(self._fontset, "strings", None)
            if strings is not None:
                try:
                    table = list(strings.strings)
                except AttributeError:
                    table = []
                for i, candidate in enumerate(table):
                    if _cff_string_to_str(candidate) == name:
                        return self.NUM_STANDARD_STRINGS + i
        return 0

    @classmethod
    def is_standard_sid(cls, sid: int) -> bool:
        """Predicate: whether ``sid`` is a Standard Strings SID
        (CFF spec §10: SIDs 0..390 are font-independent; higher SIDs
        index into the per-font STRING INDEX). Useful for callers
        deciding whether a SID needs the font set to resolve."""
        return 0 <= sid < cls.NUM_STANDARD_STRINGS

    def get_string(self, sid: int) -> str:
        """Resolve a CFF SID to a glyph name string. SIDs 0..390 are
        the Standard Strings; higher SIDs index into the font's STRING
        INDEX. Returns an empty string for an unknown SID.
        """
        from fontTools.cffLib import cffStandardStrings  # noqa: PLC0415

        if sid < 0:
            return ""
        if self.is_standard_sid(sid):
            return str(cffStandardStrings[sid])
        idx = sid - self.NUM_STANDARD_STRINGS
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
            return _cff_string_to_str(table[idx])
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

        from fontTools.misc import psCharStrings  # type: ignore[import-untyped]  # noqa: PLC0415

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
        extractor = psCharStrings.T2WidthExtractor(
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

    def get_path(self, name: str) -> list[tuple[Any, ...]]:
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
        return list(pen.commands)

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

    def __repr__(self) -> str:
        """Mirror upstream ``CFFFont.toString()``:
        ``ClassName[name=..., topDict=..., charset=..., charStrings=...]``.

        We diverge slightly: ``charStrings`` is summarised as the count
        rather than the full byte dump (upstream's
        ``Arrays.deepToString`` produces megabytes of output for real
        fonts; counts are more useful for debugging in Python)."""
        return (
            f"{type(self).__name__}[name={self.get_name()},"
            f" topDict={self.get_top_dict()},"
            f" charset={self.get_charset()},"
            f" charStrings={self.get_num_char_strings()}]"
        )


# --------------------------------------------------------------------------
# Explicit charset / encoding parsing — Adobe Technote #5176 §13 / §12.
# --------------------------------------------------------------------------
#
# These helpers mirror the byte-level parsing in upstream
# ``org.apache.fontbox.cff.CFFParser`` (methods ``readCharset`` and
# ``readEncoding``). The actual font-set decompile we use at runtime is
# delegated to ``fontTools.cffLib.CFFFontSet`` (MIT) — fontTools handles
# all three charset formats and both encoding formats with supplement
# correctly. The helpers below are exposed for parity with upstream's
# public API, for synthetic-stream testing, and so callers that already
# hold a raw byte slice (e.g. an embedded /CharStrings index in a private
# parser) can invoke them directly without round-tripping through
# fontTools.
#
# Format reference (Adobe Technote #5176, "The Compact Font Format
# Specification", v1.0, December 2003):
#   §13 Charsets:
#     - Format 0: array of (nGlyphs - 1) Card16 SIDs after the implicit
#       .notdef at GID 0.
#     - Format 1: ranges of (Card16 first, Card8 nLeft); each range covers
#       nLeft + 1 glyphs starting at SID `first`.
#     - Format 2: ranges of (Card16 first, Card16 nLeft); used by CID
#       fonts when nLeft can exceed 255.
#   §12 Encodings:
#     - Format 0: Card8 nCodes followed by nCodes Card8 codes.
#     - Format 1: Card8 nRanges followed by ranges of (Card8 first, Card8
#       nLeft); covers nLeft + 1 codes per range.
#     - Supplement: when the high bit (0x80) of the format byte is set,
#       follow the base table with Card8 nSups + nSups (Card8 code,
#       Card16 SID) pairs.
#
# Values returned mirror upstream's ``CFFCharset`` / ``CFFEncoding``
# semantics: charsets are GID-ordered SID lists (with SID 0 == .notdef
# at GID 0); encodings are 256-entry SID lists, default 0 (.notdef).
# Supplement entries return as a list of (code, SID) pairs and are
# *also* applied to the base encoding list so callers that don't care
# about the distinction can ignore the second tuple element.


def _read_card8(stream: BinaryIO) -> int:
    """Read a Card8 (1-byte unsigned int). Raises ``EOFError`` if the
    stream is exhausted (mirrors upstream's IOException on short read)."""
    b = stream.read(1)
    if len(b) != 1:
        msg = "Unexpected end of stream while reading Card8"
        raise EOFError(msg)
    return b[0]


def _read_card16(stream: BinaryIO) -> int:
    """Read a Card16 (2-byte big-endian unsigned int)."""
    b = stream.read(2)
    if len(b) != 2:
        msg = "Unexpected end of stream while reading Card16"
        raise EOFError(msg)
    return int(struct.unpack(">H", b)[0])


def read_charset(
    stream: BinaryIO, n_glyphs: int, fmt: int | None = None
) -> list[int]:
    """Parse a CFF charset table from ``stream`` and return the resulting
    GID-ordered list of SIDs (or CIDs for CID fonts — the format byte
    treatment is identical; the caller decides how to interpret the
    integer values).

    The returned list always has length ``n_glyphs`` and starts with
    SID 0 at index 0 (.notdef), matching CFF spec §13.

    When ``fmt`` is ``None`` (default), the format byte is read from
    ``stream``; when supplied, the caller is asserting the format byte
    was already consumed (matches upstream's overload pattern).

    Mirrors ``CFFParser.readCharset`` (handles formats 0, 1, 2).
    """
    if n_glyphs <= 0:
        return []
    if fmt is None:
        fmt = _read_card8(stream)
    charset: list[int] = [0]  # .notdef
    if fmt == 0:
        for _ in range(n_glyphs - 1):
            charset.append(_read_card16(stream))
        return charset
    if fmt in (1, 2):
        n_left_reader = _read_card8 if fmt == 1 else _read_card16
        count = 1
        while count < n_glyphs:
            first = _read_card16(stream)
            n_left = n_left_reader(stream)
            for sid in range(first, first + n_left + 1):
                charset.append(sid)
                count += 1
                if count >= n_glyphs:
                    break
        return charset
    msg = f"Unknown CFF charset format: {fmt}"
    raise ValueError(msg)


def read_encoding(
    stream: BinaryIO, charset: list[int], fmt_byte: int | None = None
) -> tuple[list[int], list[tuple[int, int]]]:
    """Parse a CFF encoding table from ``stream``.

    Returns a 2-tuple ``(encoding, supplement)`` where:
      * ``encoding`` is a 256-entry list of SIDs indexed by character
        code (entries default to 0 / .notdef).
      * ``supplement`` is a list of ``(code, sid)`` pairs for any
        supplemental mappings; supplement entries are *also* applied to
        ``encoding`` in place (last write wins, matching upstream).

    ``charset`` is the parsed charset (GID → SID list) — encoding format
    0/1 entries are GID-relative pointers into this list. When
    ``fmt_byte`` is supplied the caller asserts it was already read;
    otherwise it is read from ``stream``.

    The high bit (0x80) of the format byte signals a supplement; the
    low 7 bits give the format (0 or 1).

    Mirrors ``CFFParser.readEncoding`` (handles formats 0/1 + supplement).
    """
    if fmt_byte is None:
        fmt_byte = _read_card8(stream)
    have_supplement = bool(fmt_byte & 0x80)
    fmt = fmt_byte & 0x7F

    encoding: list[int] = [0] * 256
    if fmt == 0:
        n_codes = _read_card8(stream)
        for gid in range(1, n_codes + 1):
            code = _read_card8(stream)
            if 0 <= gid < len(charset):
                encoding[code] = charset[gid]
    elif fmt == 1:
        n_ranges = _read_card8(stream)
        gid = 1
        for _ in range(n_ranges):
            code = _read_card8(stream)
            n_left = _read_card8(stream)
            for _ in range(n_left + 1):
                if 0 <= gid < len(charset):
                    encoding[code] = charset[gid]
                code = (code + 1) & 0xFF
                gid += 1
    else:
        msg = f"Unknown CFF encoding format: {fmt}"
        raise ValueError(msg)

    supplement: list[tuple[int, int]] = []
    if have_supplement:
        n_sups = _read_card8(stream)
        for _ in range(n_sups):
            code = _read_card8(stream)
            sid = _read_card16(stream)
            encoding[code] = sid
            supplement.append((code, sid))

    return encoding, supplement


__all__ = [
    "CFFFont",
    "read_charset",
    "read_encoding",
]
