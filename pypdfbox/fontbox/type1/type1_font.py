from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _make_path_pen() -> Any:
    """Build a fontTools BasePen subclass that records draw commands as
    the simple list-of-tuples format used by ``PD…Font.get_glyph_path``.

    Lazily imports fontTools so this module is cheap to import when no
    glyph paths are ever requested.
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


class _ParsedT1:
    """Stand-in for fontTools' ``T1Font`` populated by our own
    :class:`Type1Parser`. Only the two access patterns our accessors
    exercise are implemented: attribute ``.font`` and item lookup."""

    def __init__(self, font_dict: dict[str, Any]) -> None:
        self.font = font_dict
        self.data: bytes = b""
        self.encoding: str = "ascii"

    def __getitem__(self, key: str) -> Any:
        return self.font[key]

    def __contains__(self, key: str) -> bool:
        return key in self.font


class Type1Font:
    """Type 1 (PostScript) font wrapper.

    Mirrors the public surface of upstream
    ``org.apache.fontbox.type1.Type1Font`` (a subset — full PostScript
    introspection is not exposed). Internally, parsing is delegated to
    the (MIT-licensed) ``fontTools.t1Lib.T1Font`` which already provides
    a battle-tested PostScript-subset interpreter and eexec / charstring
    decoder. We do not reimplement Type 1 parsing in pure Python.

    The fontTools-side ``T1Font`` requires a file path, but PDF
    ``/FontFile`` streams arrive as in-memory bytes — so this class
    bypasses the file path and feeds the raw bytes through the same
    chunk-discovery + hex-eexec normalisation that ``readOther`` runs.

    fontTools is imported lazily inside :meth:`from_bytes` so callers
    that never touch a Type 1 stream do not pay its import cost.
    """

    def __init__(self) -> None:
        self._t1: Any | None = None  # fontTools T1Font instance
        self._charstrings: dict[str, Any] | None = None
        self._font_matrix: list[float] | None = None
        self._units_per_em: int | None = None
        # Per-glyph advance cache. The fontTools T1CharString sets the
        # advance on the charstring object only after .draw() runs, so we
        # memoise once we've forced a draw.
        self._widths: dict[str, float] = {}
        # Lazy caches for the FontInfo / top-level metadata accessors.
        # None means "not yet looked up"; once populated we store the
        # resolved value (or its safe default).
        self._meta_cache: dict[str, Any] = {}
        self._encoding_map: dict[int, str] | None = None
        # Eexec-decrypted private-dict bytes (set by create_with_segments).
        self.decrypted_binary: bytes = b""
        # Raw segment 1 / segment 2 bytes for round-trip use. Upstream
        # exposes these as ``getASCIISegment()`` / ``getBinarySegment()``;
        # populated by :meth:`create_with_segments` (and best-effort
        # populated by :meth:`from_bytes` from the chunk-discovered
        # cleartext / eexec halves).
        self._segment1: bytes = b""
        self._segment2: bytes = b""

    # ---------- factory ----------

    @classmethod
    def from_bytes(cls, data: bytes | bytearray | memoryview) -> "Type1Font":
        """Parse a Type 1 PostScript font from raw ``/FontFile`` bytes.

        Bytes must follow the PDF 32000-1 §9.9 layout — cleartext header
        followed by binary eexec section followed by trailing zeros — or
        the equivalent hex-encoded form. PFB-wrapped (0x80-prefixed)
        bytes are NOT supported here; call :meth:`from_pfb_bytes` for
        those (PDF /FontFile streams are never PFB-wrapped).
        """
        from fontTools.t1Lib import (  # noqa: PLC0415
            T1Font,
            assertType1,
            deHexString,
            findEncryptedChunks,
            isHex,
        )
        from fontTools.misc.py23 import bytesjoin  # noqa: PLC0415

        raw = bytes(data)
        assertType1(raw)
        chunks = findEncryptedChunks(raw)
        normalised: list[bytes] = []
        seg1_parts: list[bytes] = []
        seg2_parts: list[bytes] = []
        for is_encrypted, chunk in chunks:
            if is_encrypted and isHex(chunk[:4]):
                decoded = deHexString(chunk)
                normalised.append(decoded)
                seg2_parts.append(decoded)
            elif is_encrypted:
                normalised.append(chunk)
                seg2_parts.append(chunk)
            else:
                normalised.append(chunk)
                seg1_parts.append(chunk)
        merged = bytesjoin(normalised)

        # Subclass T1Font in-place to skip its file-path read; everything
        # downstream (parse + draw) keys off self.data + self.encoding.
        t1 = T1Font.__new__(T1Font)
        t1.data = merged
        t1.encoding = "ascii"
        # Touching the font dict triggers parse() which lazily decrypts
        # eexec and converts each charstring to a fontTools T1CharString.
        _ = t1["CharStrings"]

        instance = cls()
        instance._t1 = t1
        instance._segment1 = bytesjoin(seg1_parts)
        instance._segment2 = bytesjoin(seg2_parts)
        return instance

    @classmethod
    def create_with_segments(
        cls,
        segment1: bytes | bytearray,
        segment2: bytes | bytearray,
    ) -> "Type1Font":
        """Build a ``Type1Font`` from a (cleartext, eexec-binary) pair.

        Mirrors upstream ``Type1Font.createWithSegments(byte[], byte[])``.
        Uses the in-house :class:`Type1Parser` for the cleartext header
        and exposes the eexec-decrypted bytes via
        :attr:`decrypted_binary` — note that we do NOT run a private-dict
        interpreter on those bytes (upstream does); callers that need
        glyph outlines should still use :meth:`from_bytes` which routes
        through fontTools' full PostScript-subset interpreter.
        """
        from .type1_parser import Type1Parser  # noqa: PLC0415

        parser = Type1Parser()
        font_dict = parser.parse(segment1, segment2)

        instance = cls()
        instance._t1 = _ParsedT1(font_dict)
        instance.decrypted_binary = parser.decrypted_binary
        instance._segment1 = bytes(segment1)
        instance._segment2 = bytes(segment2)
        return instance

    # ---------- internal lookup helpers ----------

    def _font_dict(self) -> dict[str, Any]:
        """Return the underlying fontTools-parsed top-level font dict.

        Returns an empty dict when no T1 program has been attached yet
        (so accessor methods return safe defaults instead of crashing
        when callers inject only ``_charstrings`` for testing).
        """
        if self._t1 is None:
            return {}
        font = getattr(self._t1, "font", None)
        return font if isinstance(font, dict) else {}

    def _font_info(self) -> dict[str, Any]:
        fi = self._font_dict().get("FontInfo")
        return fi if isinstance(fi, dict) else {}

    def _private_dict(self) -> dict[str, Any]:
        priv = self._font_dict().get("Private")
        return priv if isinstance(priv, dict) else {}

    # ---------- font-level metrics ----------

    @property
    def font_matrix(self) -> list[float]:
        """Six-element font matrix (Type 1 default ``[0.001 0 0 0.001 0 0]``)."""
        if self._font_matrix is None:
            assert self._t1 is not None  # noqa: S101 — guarded by from_bytes
            matrix = self._t1["FontMatrix"]
            self._font_matrix = [float(v) for v in matrix]
        return self._font_matrix

    @property
    def units_per_em(self) -> int:
        """Derived from the font matrix's x-scale (matrix[0]).

        Type 1 fonts do not store ``unitsPerEm`` directly — they encode
        it as ``1 / matrix[0]`` (matrix is em -> user-space). For the
        Adobe-default matrix ``[0.001 ...]`` this yields ``1000``.
        """
        if self._units_per_em is None:
            scale = self.font_matrix[0]
            self._units_per_em = int(round(1.0 / scale)) if scale else 1000
        return self._units_per_em

    # ---------- FontInfo / top-level metadata accessors ----------
    #
    # These mirror the upstream ``org.apache.fontbox.type1.Type1Font``
    # FontInfo getters. Each one is a thin lookup over the parsed
    # PostScript font dict (FontInfo sub-dict for textual fields,
    # top-level for FontBBox / Encoding / Subrs). Missing fields fall
    # back to a sensible default with a debug log so callers always get
    # a typed value back — matching the Java behaviour of returning
    # "" / 0 / false / null instead of throwing.

    def get_name(self) -> str:
        """PostScript font name (top-level ``/FontName``).

        Falls back to ``FontInfo /FontName`` then empty string.
        """
        if "name" not in self._meta_cache:
            value = self._font_dict().get("FontName")
            if value is None:
                value = self._font_info().get("FontName")
            if value is None:
                logger.debug("Type1Font: /FontName missing, returning ''")
                value = ""
            self._meta_cache["name"] = str(value)
        return self._meta_cache["name"]  # type: ignore[no-any-return]

    def get_family_name(self) -> str:
        """``FontInfo /FamilyName``. Empty string when absent."""
        if "family" not in self._meta_cache:
            value = self._font_info().get("FamilyName")
            if value is None:
                logger.debug("Type1Font: /FamilyName missing, returning ''")
                value = ""
            self._meta_cache["family"] = str(value)
        return self._meta_cache["family"]  # type: ignore[no-any-return]

    def get_full_name(self) -> str:
        """``FontInfo /FullName``. Empty string when absent."""
        if "full" not in self._meta_cache:
            value = self._font_info().get("FullName")
            if value is None:
                logger.debug("Type1Font: /FullName missing, returning ''")
                value = ""
            self._meta_cache["full"] = str(value)
        return self._meta_cache["full"]  # type: ignore[no-any-return]

    def get_weight(self) -> str:
        """``FontInfo /Weight`` (e.g. ``Bold``, ``Roman``, ``Light``).

        Empty string when absent.
        """
        if "weight" not in self._meta_cache:
            value = self._font_info().get("Weight")
            if value is None:
                logger.debug("Type1Font: /Weight missing, returning ''")
                value = ""
            self._meta_cache["weight"] = str(value)
        return self._meta_cache["weight"]  # type: ignore[no-any-return]

    def get_notice(self) -> str:
        """``FontInfo /Notice`` (copyright / legal notice). Empty when absent."""
        if "notice" not in self._meta_cache:
            value = self._font_info().get("Notice")
            if value is None:
                logger.debug("Type1Font: /Notice missing, returning ''")
                value = ""
            self._meta_cache["notice"] = str(value)
        return self._meta_cache["notice"]  # type: ignore[no-any-return]

    def is_italic(self) -> bool:
        """Convenience: ``True`` when the italic angle is non-zero.

        Mirrors upstream ``Type1Font.isItalic()`` which is implemented as
        ``getItalicAngle() != 0`` against the parsed FontInfo dict.
        """
        return self.get_italic_angle() != 0.0

    def is_fixed_pitch(self) -> bool:
        """Alias for :meth:`get_is_fixed_pitch` matching upstream's
        ``isFixedPitch()`` accessor name."""
        return self.get_is_fixed_pitch()

    def get_italic_angle(self) -> float:
        """``FontInfo /ItalicAngle`` in degrees. ``0.0`` when absent."""
        if "italic" not in self._meta_cache:
            value = self._font_info().get("ItalicAngle")
            if value is None:
                logger.debug("Type1Font: /ItalicAngle missing, returning 0.0")
                value = 0.0
            try:
                self._meta_cache["italic"] = float(value)
            except (TypeError, ValueError):
                logger.debug("Type1Font: /ItalicAngle %r not numeric, returning 0.0", value)
                self._meta_cache["italic"] = 0.0
        return self._meta_cache["italic"]  # type: ignore[no-any-return]

    def get_is_fixed_pitch(self) -> bool:
        """``FontInfo /isFixedPitch``. ``False`` when absent."""
        if "fixed" not in self._meta_cache:
            value = self._font_info().get("isFixedPitch")
            if value is None:
                logger.debug("Type1Font: /isFixedPitch missing, returning False")
                self._meta_cache["fixed"] = False
            else:
                # PostScript booleans round-trip as Python bool through
                # fontTools; accept the string forms ``true`` / ``false``
                # too in case a custom dict put them there.
                if isinstance(value, bool):
                    self._meta_cache["fixed"] = value
                elif isinstance(value, str):
                    self._meta_cache["fixed"] = value.strip().lower() == "true"
                else:
                    self._meta_cache["fixed"] = bool(value)
        return self._meta_cache["fixed"]  # type: ignore[no-any-return]

    def get_underline_position(self) -> float:
        """``FontInfo /UnderlinePosition`` in font units. ``0.0`` when absent."""
        if "ulpos" not in self._meta_cache:
            value = self._font_info().get("UnderlinePosition")
            if value is None:
                logger.debug("Type1Font: /UnderlinePosition missing, returning 0.0")
                value = 0.0
            try:
                self._meta_cache["ulpos"] = float(value)
            except (TypeError, ValueError):
                logger.debug(
                    "Type1Font: /UnderlinePosition %r not numeric, returning 0.0", value
                )
                self._meta_cache["ulpos"] = 0.0
        return self._meta_cache["ulpos"]  # type: ignore[no-any-return]

    def get_underline_thickness(self) -> float:
        """``FontInfo /UnderlineThickness`` in font units. ``0.0`` when absent."""
        if "ulthick" not in self._meta_cache:
            value = self._font_info().get("UnderlineThickness")
            if value is None:
                logger.debug("Type1Font: /UnderlineThickness missing, returning 0.0")
                value = 0.0
            try:
                self._meta_cache["ulthick"] = float(value)
            except (TypeError, ValueError):
                logger.debug(
                    "Type1Font: /UnderlineThickness %r not numeric, returning 0.0",
                    value,
                )
                self._meta_cache["ulthick"] = 0.0
        return self._meta_cache["ulthick"]  # type: ignore[no-any-return]

    def get_font_bbox(self) -> tuple[float, float, float, float] | None:
        """Top-level ``/FontBBox`` as ``(llx, lly, urx, ury)`` in font units.

        Returns ``None`` when the key is missing entirely, matching the
        Java upstream behaviour of returning ``null`` for an unknown box.
        """
        if "bbox" not in self._meta_cache:
            value = self._font_dict().get("FontBBox")
            if value is None:
                logger.debug("Type1Font: /FontBBox missing, returning None")
                self._meta_cache["bbox"] = None
            else:
                try:
                    floats = [float(v) for v in value]
                except (TypeError, ValueError):
                    logger.debug("Type1Font: /FontBBox %r not coercible, returning None", value)
                    self._meta_cache["bbox"] = None
                else:
                    if len(floats) != 4:
                        logger.debug(
                            "Type1Font: /FontBBox length %d != 4, returning None",
                            len(floats),
                        )
                        self._meta_cache["bbox"] = None
                    else:
                        self._meta_cache["bbox"] = (
                            floats[0],
                            floats[1],
                            floats[2],
                            floats[3],
                        )
        return self._meta_cache["bbox"]  # type: ignore[no-any-return]

    def get_encoding(self) -> dict[int, str]:
        """Code → glyph name mapping for the font's ``/Encoding`` vector.

        Returns the parsed Encoding when present (each non-``.notdef``
        entry produces one ``code -> name`` row). When the font names a
        predefined encoding the upstream fontTools interpreter resolves
        it to ``StandardEncoding``; we surface that as the standard
        Adobe table. Returns ``{}`` when no encoding is recoverable.
        """
        if self._encoding_map is not None:
            return dict(self._encoding_map)

        raw = self._font_dict().get("Encoding")
        result: dict[int, str] = {}
        if raw is None:
            logger.debug("Type1Font: /Encoding missing, returning empty map")
        elif isinstance(raw, str):
            # Predefined named encoding (e.g. "StandardEncoding"). Fold
            # to the equivalent Adobe table so callers don't have to
            # special-case the string form.
            if raw == "StandardEncoding":
                from ..encoding.standard_encoding import StandardEncoding  # noqa: PLC0415

                result = StandardEncoding.INSTANCE.get_codes()
            else:
                logger.debug("Type1Font: unknown named /Encoding %r", raw)
        else:
            try:
                for code, name in enumerate(raw):
                    if name is None:
                        continue
                    if name == ".notdef":
                        continue
                    result[code] = str(name)
            except TypeError:
                logger.debug("Type1Font: /Encoding %r not iterable", raw)

        # If the font carried an /Encoding key but every slot was
        # .notdef the upstream behaviour is to fall back to the
        # StandardEncoding — Adobe Type 1 spec 5.6 §2.3.
        if not result and raw is not None and not isinstance(raw, str):
            from ..encoding.standard_encoding import StandardEncoding  # noqa: PLC0415

            result = StandardEncoding.INSTANCE.get_codes()

        self._encoding_map = result
        return dict(self._encoding_map)

    def get_char_strings_dict(self) -> dict[str, Any]:
        """Upstream ``Type1Font.getCharStringsDict()`` — the same
        glyph-name → charstring map ``get_char_strings_subroutines_charset``
        returns, exposed under its more familiar name. Returned dict is
        a copy so callers may mutate freely."""
        return self.get_char_strings_subroutines_charset()

    def get_char_string(self, name: str) -> Any:
        """Upstream ``Type1Font.getCharString(String name)`` — return the
        :class:`Type1CharString` wrapper for glyph ``name``.

        Thin alias of :meth:`get_type1_char_string` to match upstream's
        getter name (the older method stays for back-compat)."""
        return self.get_type1_char_string(name)

    def get_type1_mappings(self) -> list[Any]:
        """Upstream ``Type1Font.getType1Mappings()`` — one
        :class:`~pypdfbox.fontbox.type1.type1_mapping.Type1Mapping` row
        per non-``.notdef`` slot in the font's encoding vector.

        The list is sorted by code so callers can iterate in encoding
        order (matching upstream which builds the list inside a loop
        from 0 to 255)."""
        from .type1_mapping import Type1Mapping  # noqa: PLC0415

        encoding = self.get_encoding()
        rows: list[Type1Mapping] = []
        for code in sorted(encoding):
            name = encoding[code]
            cs = self.get_type1_char_string(name)
            rows.append(Type1Mapping(code=code, name=name, char_string=cs))
        return rows

    def get_metrics(self) -> dict[str, Any]:
        """Upstream ``Type1Font.getMetrics()`` — bundle the font-level
        metrics into a single dict for callers that want everything at
        once. Includes the bbox, font matrix, italic angle, underline
        position / thickness, and units-per-em."""
        return {
            "FontBBox": self.get_font_bbox(),
            "FontMatrix": list(self.font_matrix),
            "ItalicAngle": self.get_italic_angle(),
            "UnderlinePosition": self.get_underline_position(),
            "UnderlineThickness": self.get_underline_thickness(),
            "UnitsPerEm": self.units_per_em,
            "isFixedPitch": self.get_is_fixed_pitch(),
        }

    def get_char_strings_subroutines_charset(self) -> dict[str, Any]:
        """Best-effort dict view of the ``/CharStrings`` table.

        Mirrors the upstream accessor that hands back the parsed
        glyph-name → charstring map. The returned dict is a *copy* so
        callers can mutate it without disturbing the cached parse —
        each value is the underlying fontTools T1CharString instance
        (callers that just need glyph-name presence can iterate the
        keys; glyph outlines should go through :meth:`get_path`).
        """
        try:
            cs = self._charstrings_dict()
        except AssertionError:
            logger.debug("Type1Font: no charstrings parsed yet, returning {}")
            return {}
        return dict(cs)

    def get_subrs(self) -> int:
        """Number of subroutines in the ``Private /Subrs`` array.

        Returns ``0`` when the font has no subroutines (or when the
        program has not been attached via :meth:`from_bytes`).
        """
        subrs = self._private_dict().get("Subrs")
        if subrs is None:
            logger.debug("Type1Font: /Private/Subrs missing, returning 0")
            return 0
        try:
            return len(subrs)
        except TypeError:
            logger.debug("Type1Font: /Private/Subrs %r has no length, returning 0", subrs)
            return 0

    # ---------- glyph access ----------

    def has_glyph(self, name: str) -> bool:
        try:
            return name in self._charstrings_dict()
        except AssertionError:
            return False

    def _charstrings_dict(self) -> dict[str, Any]:
        if self._charstrings is None:
            assert self._t1 is not None  # noqa: S101
            self._charstrings = self._t1["CharStrings"]
        return self._charstrings

    def get_width(self, name: str) -> float:
        """Advance width of glyph ``name`` in *font units* (typically 1000-unit em).

        Returns ``0.0`` when the glyph is missing from the charstrings
        table. The fontTools T1CharString stores the advance on the
        instance only after ``.draw()`` has run, so we trigger a one-off
        draw against a no-op pen the first time we ask for a width.
        """
        cached = self._widths.get(name)
        if cached is not None:
            return cached
        cs_map = self._charstrings_dict()
        cs = cs_map.get(name)
        if cs is None:
            return 0.0
        # Force draw to populate .width. We use a no-op pen so we don't
        # build the path twice.
        from fontTools.pens.basePen import NullPen  # noqa: PLC0415

        try:
            cs.draw(NullPen())
        except Exception:  # noqa: BLE001
            return 0.0
        width = float(getattr(cs, "width", 0.0) or 0.0)
        self._widths[name] = width
        return width

    def get_path(self, name: str) -> list[tuple]:
        """Glyph outline for ``name`` as a list of draw commands in
        font units. Returns ``[]`` when the glyph is missing.

        Format: ``("moveto", x, y)``, ``("lineto", x, y)``,
        ``("curveto", x1, y1, x2, y2, x, y)``, ``("closepath",)``.
        """
        cs_map = self._charstrings_dict()
        cs = cs_map.get(name)
        if cs is None:
            return []
        pen = _make_path_pen()
        try:
            cs.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        # Side-effect: the draw populates cs.width — cache it while we're here.
        self._widths.setdefault(name, float(getattr(cs, "width", 0.0) or 0.0))
        return list(pen.commands)  # type: ignore[attr-defined]

    def get_type1_char_string(self, name: str) -> Any:
        """PDFBox: ``Type1Font.getType1CharString(String name)`` —
        return a :class:`~pypdfbox.fontbox.cff.type1_char_string.Type1CharString`
        wrapper for glyph ``name``.

        Falls back to ``.notdef`` when ``name`` is missing — matching
        the upstream behaviour. Upstream raises ``IOException`` when
        ``.notdef`` itself is undefined; we deliberately diverge for
        ergonomics and instead return an empty wrapper whose
        ``get_path() == []``.
        """
        from ..cff.type1_char_string import Type1CharString  # noqa: PLC0415

        cs_map: dict[str, Any]
        try:
            cs_map = self._charstrings_dict()
        except AssertionError:
            cs_map = {}
        cs = cs_map.get(name)
        glyph_name = name
        if cs is None:
            cs = cs_map.get(".notdef")
            glyph_name = ".notdef" if cs is not None else name
        return Type1CharString(
            font=self,
            font_name=self.get_name(),
            glyph_name=glyph_name,
            sequence=cs,
        )


__all__ = ["Type1Font"]
