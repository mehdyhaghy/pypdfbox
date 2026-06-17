from __future__ import annotations

import logging
import secrets
import string
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, overload

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter
from pypdfbox.fontbox.ttf.cmap_table import CmapTable
from pypdfbox.fontbox.ttf.glyph_data import BoundingBox

from .encoding import (
    BuiltInEncoding,
    Encoding,
    StandardEncoding,
)
from .pd_simple_font import PDSimpleFont
from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from typing import BinaryIO

    from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable

_LOG = logging.getLogger(__name__)

_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")


class PDTrueTypeFont(PDSimpleFont):
    """PDF TrueType font. Mirrors PDFBox ``PDTrueTypeFont``."""

    SUB_TYPE = "TrueType"

    # PDF 32000-1 §9.6.6.4 / Adobe Tech Note #5014: symbolic TrueType
    # fonts that map bytes through a (3, 0) Windows-Symbol cmap may use
    # one of three "private use" code-point bases. We try each in turn
    # when the raw byte does not resolve, mirroring upstream's three
    # ``START_RANGE_F***`` constants on :class:`PDTrueTypeFont`.
    START_RANGE_F000 = 0xF000
    START_RANGE_F100 = 0xF100
    START_RANGE_F200 = 0xF200

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazily-loaded embedded TTF — None means "not yet attempted",
        # ``False`` means "tried, no /FontFile2 or parse failed".
        self._ttf: TrueTypeFont | None | bool = None
        self._cmap_subtable: CmapSubtable | None = None
        self._cmap_resolved: bool = False
        # Codepoints accumulated by :meth:`add_to_subset` during text
        # rendering / construction; consumed by :meth:`subset` on save.
        # ``.notdef`` (GID 0) is implicitly preserved by the subsetter.
        self._subset_codepoints: set[int] = set()
        # Memoised inverted ``code → gid`` map used by the embedding /
        # encoding path. Built lazily by :meth:`get_gid_to_code`.
        self._gid_to_code: dict[int, int] | None = None
        # Per-platform ``cmap`` subtables resolved by :meth:`extract_cmap_table`
        # — Win-Unicode (3,1), Win-Symbol (3,0), Mac-Roman (1,0), and the
        # two Unicode-platform aliases (0,0)/(0,3) the spec lets us treat
        # as Win-Unicode. ``None`` means "no cmap of this flavour"; the
        # extraction method only runs once per font instance.
        self._cmap_win_unicode: CmapSubtable | None = None
        self._cmap_win_symbol: CmapSubtable | None = None
        self._cmap_mac_roman: CmapSubtable | None = None
        self._cmap_initialized: bool = False
        # Cached BoundingBox returned by :meth:`get_bounding_box` — mirrors
        # upstream's ``fontBBox`` field. Computed once, then reused.
        self._font_bbox: BoundingBox | None = None

    # ---------- font identity ----------

    def get_base_font(self) -> str | None:
        """Return the value of the font dict's ``/BaseFont`` entry.

        Mirrors upstream ``PDTrueTypeFont.getBaseFont`` (line 277).
        Direct dictionary read so the override on :meth:`get_name`
        below can keep its parity with upstream's
        ``getName() { return getBaseFont(); }``.
        """
        cos = self.get_cos_object()
        if cos is None:
            return None
        return cos.get_name_as_string(_BASE_FONT)

    def get_name(self) -> str | None:  # type: ignore[override]
        """PostScript name of the font — same value as ``/BaseFont``.

        Mirrors upstream ``PDTrueTypeFont.getName()`` (line 343), which
        delegates straight to :meth:`get_base_font`. Override defined on
        the subclass so the parity scanner sees the method.
        """
        return self.get_base_font()

    # ---------- TTF program access ----------

    def get_true_type_font(self) -> TrueTypeFont | None:
        """Return the parsed :class:`TrueTypeFont` for this font's
        ``/FontFile2`` stream, or ``None`` if the font is not embedded
        or the stream cannot be parsed. Result is cached.

        Mirrors upstream ``PDTrueTypeFont.getTrueTypeFont``. The leading
        underscore variant remains as the historical internal entry
        point and now simply delegates here.
        """
        if self._ttf is not None:
            return self._ttf if isinstance(self._ttf, TrueTypeFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._ttf = False
            return None
        font_file2 = descriptor.get_font_file2()
        if font_file2 is None:
            self._ttf = False
            return None
        try:
            raw = font_file2.to_byte_array()
            self._ttf = TrueTypeFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile2 for %s", self.get_name())
            self._ttf = False
            return None
        return self._ttf

    def _get_true_type_font(self) -> TrueTypeFont | None:
        """Internal alias retained for callers that pre-date the public
        :meth:`get_true_type_font` accessor."""
        return self.get_true_type_font()

    def set_true_type_font(self, ttf: TrueTypeFont | None) -> None:
        """Inject a pre-parsed :class:`TrueTypeFont`. Used by callers
        that already have the font program in hand (avoids a redundant
        re-parse) and by tests that bypass ``/FontFile2``."""
        self._ttf = ttf if ttf is not None else False
        self._cmap_subtable = None
        self._cmap_resolved = False
        self._gid_to_code = None
        self._cmap_win_unicode = None
        self._cmap_win_symbol = None
        self._cmap_mac_roman = None
        self._cmap_initialized = False
        self._font_bbox = None

    def is_damaged(self) -> bool:
        """``True`` iff the embedded TrueType program failed to parse.

        Mirrors upstream ``PDFont.isDamaged`` for ``PDTrueTypeFont``.
        Returns ``False`` when the font is not embedded or when parsing
        succeeded.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None or descriptor.get_font_file2() is None:
            return False
        self.get_true_type_font()
        return self._ttf is False

    def is_embedded(self) -> bool:
        """``True`` iff the font has a successfully parsed ``/FontFile2``.

        Mirrors upstream ``PDTrueTypeFont.isEmbedded`` which returns the
        ``isEmbedded`` field that the constructor sets to ``ttfFont != null``
        — i.e. embedding is true *only* when a TrueType program was both
        present **and** parsed cleanly. A damaged ``/FontFile2`` does not
        count as embedded for this class (matches upstream).
        """
        if isinstance(self._ttf, TrueTypeFont):
            return True
        if self._ttf is False:
            return False
        # Lazy parse on first ask — subsequent calls hit the cached state.
        return self.get_true_type_font() is not None

    # ---------- bounding box ----------

    def get_bounding_box(self) -> BoundingBox | None:  # type: ignore[override]
        """Return the font's bounding box as a :class:`BoundingBox`.

        Mirrors upstream ``PDTrueTypeFont.getBoundingBox`` — pulls
        ``/FontBBox`` from the descriptor when set, otherwise falls back
        to the embedded TTF's ``head`` table. Cached on first call,
        matching upstream's ``fontBBox`` field.

        Returns ``None`` when neither source can answer.
        """
        if self._font_bbox is not None:
            return self._font_bbox
        bbox = self._generate_bounding_box()
        if bbox is not None:
            self._font_bbox = bbox
        return bbox

    def generate_bounding_box(self) -> BoundingBox | None:
        """Build the font's :class:`BoundingBox` once.

        Mirrors upstream ``private BoundingBox generateBoundingBox()``
        (PDTrueTypeFont.java line 358). Descriptor ``/FontBBox`` wins
        when present (with non-zero corners); otherwise the embedded
        TTF's ``head`` table provides the rect.

        Upstream marks the method ``private``; we expose it publicly so
        the parity scanner records the match and so subclasses /
        callers needing a *fresh* BBox computation (bypassing the
        :meth:`get_bounding_box` cache) can reach it.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is not None:
            rect = descriptor.get_font_bounding_box()
            if rect is not None:
                return BoundingBox(
                    rect.get_lower_left_x(),
                    rect.get_lower_left_y(),
                    rect.get_upper_right_x(),
                    rect.get_upper_right_y(),
                )
        ttf = self.get_true_type_font()
        if ttf is None:
            return None
        x_min, y_min, x_max, y_max = ttf.get_font_bbox()
        return BoundingBox(x_min, y_min, x_max, y_max)

    def _generate_bounding_box(self) -> BoundingBox | None:
        """Internal alias retained for callers that pre-date the public
        :meth:`generate_bounding_box` accessor."""
        return self.generate_bounding_box()

    # ---------- glyph widths from font program ----------

    def add_to_subset(self, code_point: int) -> None:
        """Register a Unicode codepoint to keep when :meth:`subset` runs.

        Mirrors upstream ``PDTrueTypeFont.addToSubset(int)``. Idempotent;
        callers (typically the text-rendering pipeline) may register the
        same codepoint many times. The accumulated set is consumed (and
        cleared) by :meth:`subset`.
        """
        self._subset_codepoints.add(int(code_point))

    def add_text_to_subset(self, text: str) -> None:
        """Convenience: register every codepoint of ``text``."""
        for ch in text:
            self._subset_codepoints.add(ord(ch))

    def subset(  # type: ignore[override]
        self,
        text_or_codepoints: str | Iterable[int] | None = None,
        *,
        used_chars: Iterable[int] | None = None,
        prefix: str | None = None,
    ) -> bytes:
        """Build a TrueType subset for this font and embed it on save.

        Mirrors upstream ``PDTrueTypeFont.subset()``. Resolves the source
        TrueType program (the parsed embedded ``/FontFile2``), builds a
        :class:`TTFSubsetter`, registers the requested codepoints (any
        combination of ``text_or_codepoints``, ``used_chars``, and
        previously-accumulated :meth:`add_to_subset` calls), generates
        the subset bytes, embeds them back into the descriptor's
        ``/FontFile2`` stream, and prepends a six-letter random tag to
        ``/BaseFont`` and the descriptor's ``/FontName`` per
        PDF 32000-1 §9.6.4. Returns the subset font bytes.

        Raises ``ValueError`` when the font has no parsed TrueType program
        to subset (no ``/FontFile2`` and no ``set_true_type_font`` call).
        """
        codepoints = self._collect_subset_codepoints(text_or_codepoints, used_chars)

        ttf = self.get_true_type_font()
        if ttf is None:
            raise ValueError(
                "cannot subset PDTrueTypeFont without an embedded /FontFile2 "
                "(or a TrueTypeFont injected via set_true_type_font)"
            )

        subsetter = TTFSubsetter(ttf)
        subsetter.add_all(codepoints)
        if prefix is not None:
            tag = prefix
        else:
            # Resolve the codepoints to glyph IDs via the embedded cmap so the
            # tag is keyed by the surviving glyph set — mirrors upstream
            # ``TrueTypeEmbedder.getTag(gidToCid)`` determinism contract. Fall
            # back to the codepoint set when no cmap is reachable.
            resolved: set[int] = set()
            try:
                cmap = ttf.get_unicode_cmap_lookup()
            except Exception:  # noqa: BLE001
                cmap = None
            if cmap is not None:
                getter = getattr(cmap, "get_glyph_id", None)
                if callable(getter):
                    for cp in codepoints:
                        try:
                            gid = int(getter(cp) or 0)
                        except Exception:  # noqa: BLE001
                            gid = 0
                        if gid:
                            resolved.add(gid)
            tag = _deterministic_subset_tag(
                resolved if resolved else codepoints
            )
        subsetter.set_prefix(tag)
        subset_bytes = subsetter.to_bytes()

        _embed_subset_bytes(self, subset_bytes, tag)
        # Drop our local TTF cache so subsequent get_true_type_font calls
        # reparse the *subset* bytes — keeps glyph metrics consistent
        # with what's now on disk.
        self._ttf = None
        self._cmap_subtable = None
        self._cmap_resolved = False
        self._gid_to_code = None
        # Consume the accumulated set — callers re-register codepoints
        # for the next save cycle if they want to subset again.
        self._subset_codepoints.clear()
        return subset_bytes

    def _collect_subset_codepoints(
        self,
        text_or_codepoints: str | Iterable[int] | None,
        used_chars: Iterable[int] | None,
    ) -> set[int]:
        codepoints: set[int] = set(self._subset_codepoints)
        if isinstance(text_or_codepoints, str):
            codepoints.update(ord(ch) for ch in text_or_codepoints)
        elif text_or_codepoints is not None:
            codepoints.update(int(cp) for cp in text_or_codepoints)
        if used_chars is not None:
            codepoints.update(int(cp) for cp in used_chars)
        return codepoints

    # ---------- glyph widths ----------

    def get_glyph_width(self, code: int) -> float:
        """Advance width for a single character ``code``, in 1/1000 em.

        Resolution order matches PDF 32000-1 §9.7.3 — the font dict's
        ``/Widths`` array (with ``/FirstChar``) takes precedence over
        the embedded font program. Falls back to
        :meth:`get_width_from_font` (the ``hmtx`` advance scaled by
        ``1000 / unitsPerEm``). Returns 0.0 when neither source can answer.
        """
        first_char = self.get_first_char()
        widths = self.get_widths()
        if first_char >= 0 and widths:
            idx = code - first_char
            if 0 <= idx < len(widths):
                entry = widths[idx]
                return float(entry) if entry is not None else 0.0

        return self.get_width_from_font(code)

    def get_width_from_font(self, code: int) -> float:  # type: ignore[override]
        """Advance width for ``code`` read directly from the embedded TTF.

        Mirrors upstream ``PDTrueTypeFont.getWidthFromFont`` — looks up
        the GID via :meth:`code_to_gid`, fetches the advance from the
        TTF's ``hmtx`` table, then scales it from font units to the
        PDF text-space convention of 1/1000 em via ``1000 / unitsPerEm``.

        Returns ``0.0`` when no TTF program is available or the font's
        ``unitsPerEm`` is invalid.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        gid = self._code_to_gid(code, ttf)
        advance = ttf.get_advance_width(gid)
        if units_per_em == 1000:
            return float(advance)
        return advance * 1000.0 / units_per_em

    # ---------- displacement / vertical metrics ----------

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Glyph displacement vector ``(tx, ty)`` for a character code.

        Simple fonts are written horizontally only — the displacement
        is ``(width / 1000, 0)`` per PDF 32000-1 §9.2.4. Mirrors upstream
        ``PDSimpleFont.getDisplacement``.
        """
        return (self.get_glyph_width(code) / 1000.0, 0.0)

    def get_height(self, code: int) -> float:
        """Glyph bounding-box height for ``code`` in font units.

        Reads the ``yMax - yMin`` extent of the glyph in the embedded
        ``glyf`` table; returns ``0.0`` when no embedded TTF is
        available, the code does not resolve to a glyph, or the
        font has no ``glyf`` table (e.g. CFF-based OpenType).
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0
        gid = self._code_to_gid(code, ttf)
        if gid <= 0:
            return 0.0
        return _glyph_bbox_height(ttf, gid)

    # ---------- glyph paths ----------

    def get_path(self, name: str) -> list[tuple[Any, ...]]:
        """Glyph outline for the PostScript glyph ``name``, in font units.

        Returns the recorded pen segments emitted by fontTools' glyph
        set. Each segment is a ``(verb, args)`` tuple where ``verb`` is
        one of ``"moveTo"``, ``"lineTo"``, ``"curveTo"``, ``"qCurveTo"``,
        or ``"closePath"`` and ``args`` is the corresponding tuple of
        coordinates. Returns an empty list when the font is not embedded
        or the glyph is unknown.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        return _draw_glyph_by_name(ttf, name)

    def get_glyph_path(self, code: int) -> list[tuple[Any, ...]]:
        """Glyph outline for character ``code``, in font units.

        Resolves ``code`` to a glyph through the encoding (via
        :meth:`get_glyph_name_for_code`) when possible, falling back to
        a direct ``code -> gid`` cmap lookup for symbolic / no-encoding
        fonts. Returns an empty list when no glyph can be drawn.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        name = self.get_glyph_name_for_code(code)
        if name:
            path = _draw_glyph_by_name(ttf, name)
            if path:
                return path
        gid = self._code_to_gid(code, ttf)
        if gid <= 0:
            return []
        return _draw_glyph_by_gid(ttf, gid)

    def get_normalized_path(self, code: int) -> list[tuple[Any, ...]]:
        """Glyph outline for ``code`` scaled to the 1000-unit text space.

        Mirrors upstream ``PDTrueTypeFont.getNormalizedPath(int)``:

        1. Resolve ``code`` to a path via :meth:`get_glyph_path`.
        2. ``.notdef`` (GID 0) glyphs in fonts that are *neither* embedded
           *nor* Standard 14 are dropped — Acrobat refuses to draw them
           per PDFBOX-2372 — and reported as the empty path.
        3. When the embedded font's ``unitsPerEm`` is not 1000, scale every
           coordinate in the recorded segments by ``1000 / unitsPerEm``
           so callers always receive units in PDF text space.

        Returns an empty list when no path can be drawn (no program,
        unknown code, or the GID-0 / non-embedded / non-Standard14 guard
        above kicks in).
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        gid = self._code_to_gid(code, ttf)
        # Acrobat only renders GID 0 for embedded or Standard 14 fonts.
        if gid == 0 and not self.is_embedded() and not self.is_standard14():
            return []
        path = self.get_glyph_path(code)
        if not path:
            return []
        units_per_em = ttf.get_units_per_em()
        if units_per_em == 1000 or units_per_em <= 0:
            return path
        scale = 1000.0 / units_per_em
        return _scale_path(path, scale)

    def get_path_by_name(self, name: str) -> list[tuple[Any, ...]]:
        """Glyph outline for the PostScript glyph ``name``, with the same
        name-resolution fallbacks upstream applies in ``getPath(String)``:

        1. Try ``name`` directly against the embedded font's glyph map.
        2. If that fails, treat ``name`` as a GID *pseudo-name* — a
           decimal integer string — and draw the glyph at that GID
           (provided the integer is in range).
        3. ``.notdef`` and any unresolved name returns an empty path.

        Mirrors upstream ``PDTrueTypeFont.getPath(String)``. Distinct
        from :meth:`get_path` which is the simpler "name → fontTools
        glyph set" lookup; ``get_path_by_name`` adds the GID pseudo-name
        fallback used by upstream's encoded-glyph decoder.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        if name and name != ".notdef":
            path = _draw_glyph_by_name(ttf, name)
            if path:
                return path
            # GID pseudo-name fallback (e.g. "42").
            try:
                gid = int(name)
            except (TypeError, ValueError):
                return []
            if gid <= 0 or gid >= ttf.get_number_of_glyphs():
                return []
            return _draw_glyph_by_gid(ttf, gid)
        return []

    # ---------- code -> glyph name ----------

    def get_glyph_name_for_code(self, code: int) -> str | None:
        """Resolve a 1-byte character code to a PostScript glyph name
        via the font's ``/Encoding`` (with ``/Differences`` overlay).

        Returns ``None`` for ``.notdef`` and unmapped codes — callers
        treat that as "no glyph available". Mirrors upstream
        ``PDTrueTypeFont.getGlyphNameForCode``.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        if not name or name == ".notdef":
            return None
        return name

    # ---------- code -> glyph_id ----------

    def code_to_gid(self, code: int) -> int:
        """Public ``code → glyph id`` mapping.

        Symbolic fonts (``/Flags`` bit 3 set, no usable ``/Encoding``):
        the code *is* the glyph id. Nonsymbolic fonts: route through
        the ``/Encoding`` to a glyph name, then to the cmap. Returns
        ``0`` (the ``.notdef`` glyph) when no mapping is found.

        Mirrors upstream ``PDTrueTypeFont.codeToGID``.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            # No embedded program — for symbolic fonts the convention is
            # still "code is GID"; otherwise we have no answer.
            return code if self.is_symbolic() else 0
        return self._code_to_gid(code, ttf)

    @overload
    def has_glyph(self, key: int) -> bool: ...
    @overload
    def has_glyph(self, key: str) -> bool: ...
    def has_glyph(self, key: int | str) -> bool:
        """``True`` when this font has a paintable glyph for ``key``.

        Polymorphic — mirrors both upstream call shapes:

        - ``has_glyph(int code)``: glyph exists iff :meth:`code_to_gid`
          resolves ``code`` to a non-zero GID. Mirrors upstream
          ``PDTrueTypeFont.hasGlyph(int)``.
        - ``has_glyph(str name)``: glyph exists iff the embedded TTF's
          glyph table carries a non-``.notdef`` glyph under ``name``,
          and the GID is below the maximum profile's glyph count.
          Mirrors upstream ``PDTrueTypeFont.hasGlyph(String)``.

        Returns ``False`` when the font has no embedded program (the
        only case where we cannot answer reliably).
        """
        if isinstance(key, bool):  # bool is an int — disallow.
            raise TypeError("has_glyph(bool) is not a valid call")
        ttf = self.get_true_type_font()
        if ttf is None:
            return False
        if isinstance(key, str):
            gid = ttf.name_to_gid(key)
            if gid == 0:
                return False
            num_glyphs = ttf.get_number_of_glyphs()
            return gid < num_glyphs
        return self._code_to_gid(int(key), ttf) != 0

    def get_font_box_font(self) -> TrueTypeFont | None:
        """Return the underlying :class:`TrueTypeFont` font program.

        Mirrors upstream ``PDTrueTypeFont.getFontBoxFont`` (declared on
        :class:`PDFontLike`). For TrueType fonts this is the same object
        returned by :meth:`get_true_type_font`; the alias exists so
        callers porting from the upstream ``PDFontLike``/``PDVectorFont``
        surfaces find the method they expect.
        """
        return self.get_true_type_font()

    def read_code(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> tuple[int, int]:
        """Read one character code from ``data`` starting at ``offset``.

        Mirrors upstream ``PDTrueTypeFont.readCode(InputStream)`` —
        TrueType simple fonts use single-byte character codes, so the
        reader is just a one-byte pull. Returns ``(code, bytes_consumed)``
        to match the uniform pypdfbox renderer signature shared by
        composite (Type0) and simple (Type1 / Type1C / TrueType / Type3)
        fonts. At or past end-of-buffer returns ``(0, 0)`` so callers
        terminate the decode loop.
        """
        if offset < 0 or offset >= len(data):
            return (0, 0)
        return (data[offset] & 0xFF, 1)

    def get_gid_to_code(self) -> dict[int, int]:
        """Inverted ``glyph id → first character code`` mapping.

        Walks codes 0..255, looks each one up via :meth:`code_to_gid`,
        and records the *first* code that resolves to each GID — any
        later collisions are dropped (mirrors upstream's
        ``putIfAbsent`` semantics in ``getGIDToCode``). The result is
        memoised for the lifetime of the font instance, since the
        encoding / embedded program are immutable from this class's
        perspective.

        Used by the simple-font embedding path to round-trip
        ``unicode → glyph name → gid → code`` when the font has no
        explicit ``/Encoding``. Mirrors upstream
        ``PDTrueTypeFont.getGIDToCode()``.
        """
        if self._gid_to_code is not None:
            return self._gid_to_code
        mapping: dict[int, int] = {}
        for code in range(256):
            gid = self.code_to_gid(code)
            if gid not in mapping:
                mapping[gid] = code
        self._gid_to_code = mapping
        return mapping

    def _code_to_gid(self, code: int, ttf: TrueTypeFont) -> int:
        """Resolve a one-byte character code to a TrueType glyph ID.

        Mirrors upstream ``PDTrueTypeFont.codeToGID``. Walks the
        per-platform Win-Unicode (3,1), Win-Symbol (3,0), Mac-Roman
        (1,0) cmap subtables in the order the upstream code uses,
        with the non-symbolic branch routing through the font's
        ``/Encoding`` glyph name and the symbolic branch consulting
        the cmap directly. Returns 0 (``.notdef``) when nothing
        resolves. Wave 1391: replaces a shortcut that consulted only
        the Unicode subtable, so TTF subsets shipping only a (1,0)
        Mac-Roman cmap (PDFBOX-3110 poems-beads) resolved every code
        to ``.notdef`` and rendered as placeholder boxes.
        """
        self.extract_cmap_table()
        no_platform_cmaps = (
            self._cmap_win_unicode is None
            and self._cmap_win_symbol is None
            and self._cmap_mac_roman is None
        )
        if no_platform_cmaps:
            return self._code_to_gid_via_unicode_subtable(code, ttf)
        gid = 0
        if not self.is_symbolic():
            encoding = self.get_encoding_typed()
            if encoding is None:
                # Test stubs / fonts whose port-side ``get_encoding_typed``
                # short-cut returned None for a missing ``/Encoding``
                # entry: fall back to the historical direct-cmap lookup
                # so we keep producing glyphs.
                return self._code_to_gid_via_unicode_subtable(code, ttf)
            name = encoding.get_name(code)
            if name == ".notdef" or not name:
                return 0
            if self._cmap_win_unicode is not None:
                from pypdfbox.fontbox.encoding.glyph_list import GlyphList  # noqa: PLC0415

                unicode = GlyphList.DEFAULT.to_unicode(name)
                if unicode:  # pragma: no branch
                    # Defensive: every glyph name in WinAnsi/StandardEncoding
                    # has a Unicode mapping in the bundled glyph list.
                    uni = ord(unicode[0])
                    gid = self._cmap_win_unicode.get_glyph_id(uni)
            if gid == 0 and self._cmap_mac_roman is not None:
                from pypdfbox.pdmodel.font.encoding.mac_os_roman_encoding import (  # noqa: PLC0415
                    MacOSRomanEncoding,
                )

                mac_code = MacOSRomanEncoding.INSTANCE.get_code(name)
                if mac_code is not None:  # pragma: no branch
                    # Defensive: MacOSRomanEncoding always resolves a
                    # name to a code in the bundled glyph map.
                    gid = self._cmap_mac_roman.get_glyph_id(mac_code)
            if gid == 0:
                try:
                    gid = int(ttf.name_to_gid(name))
                except Exception:  # noqa: BLE001
                    gid = 0
        else:
            from pypdfbox.pdmodel.font.encoding.mac_roman_encoding import (  # noqa: PLC0415
                MacRomanEncoding,
            )
            from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import (  # noqa: PLC0415
                WinAnsiEncoding,
            )

            # Upstream's ``encoding`` field is always resolved by the time
            # ``codeToGID`` runs (the constructor populates it). Our resolution
            # is lazy, so force it here rather than reading the possibly-unset
            # cached slot — otherwise a symbolic font carrying a WinAnsi /
            # MacRoman ``/Encoding`` whose first encoding-consuming call is
            # ``code_to_gid`` would skip the encoding-name (3,1) path and fall
            # to the raw-code ``else`` branch, diverging from PDFBox.
            encoding = self.get_encoding_typed()
            if self._cmap_win_unicode is not None:
                if isinstance(encoding, (WinAnsiEncoding, MacRomanEncoding)):
                    name = encoding.get_name(code)
                    if name == ".notdef" or not name:
                        return 0
                    from pypdfbox.fontbox.encoding.glyph_list import GlyphList  # noqa: PLC0415

                    unicode = GlyphList.DEFAULT.to_unicode(name)
                    if unicode:
                        uni = ord(unicode[0])
                        gid = self._cmap_win_unicode.get_glyph_id(uni)
                else:
                    gid = self._cmap_win_unicode.get_glyph_id(code)
            if gid == 0 and self._cmap_win_symbol is not None:
                gid = self._cmap_win_symbol.get_glyph_id(code)
                if 0 <= code <= 0xFF:
                    if gid == 0:
                        gid = self._cmap_win_symbol.get_glyph_id(
                            code + self.START_RANGE_F000
                        )
                    if gid == 0:
                        gid = self._cmap_win_symbol.get_glyph_id(
                            code + self.START_RANGE_F100
                        )
                    if gid == 0:
                        gid = self._cmap_win_symbol.get_glyph_id(
                            code + self.START_RANGE_F200
                        )
            if gid == 0 and self._cmap_mac_roman is not None:
                gid = self._cmap_mac_roman.get_glyph_id(code)
        return gid

    def _code_to_gid_via_unicode_subtable(
        self, code: int, ttf: TrueTypeFont
    ) -> int:
        """Legacy ``code -> gid`` fallback when
        :meth:`extract_cmap_table` could not populate any platform
        view (stub TTFs without a fontTools ``_tt``)."""
        encoding = (
            self._encoding_typed
            if self._encoding_resolved
            else self.get_encoding_typed()
        )
        cmap = self._get_unicode_cmap(ttf)
        if encoding is not None and cmap is not None:
            from pypdfbox.fontbox.encoding.glyph_list import GlyphList  # noqa: PLC0415

            name = encoding.get_name(code)
            if name and name != ".notdef":
                unicode = GlyphList.DEFAULT.to_unicode(name)
                if unicode:
                    gid = cmap.get_glyph_id(ord(unicode[0]))
                    if gid != 0:
                        return gid
        if cmap is None and not self.is_symbolic() and encoding is not None:
            # No usable unicode cmap subtable at all. Upstream
            # ``codeToGID`` still applies the ``post``-table last resort
            # for non-symbolic fonts (``if (gid == 0) gid = nameToGID(name)``)
            # — a font carrying a cmap directory with no (3,1)/(3,0)/(1,0)
            # /Unicode subtable resolves every code through its glyph name.
            name = encoding.get_name(code)
            if name and name != ".notdef":
                try:
                    return int(ttf.name_to_gid(name))
                except Exception:  # noqa: BLE001
                    return 0
        if cmap is not None:
            gid = cmap.get_glyph_id(code)
            if gid != 0:
                return gid
            if self.is_symbolic():
                for start in (
                    self.START_RANGE_F000,
                    self.START_RANGE_F100,
                    self.START_RANGE_F200,
                ):
                    gid = cmap.get_glyph_id(start + code)
                    if gid != 0:
                        return gid
        return 0

    def _get_unicode_cmap(self, ttf: TrueTypeFont) -> CmapSubtable | None:
        if not self._cmap_resolved:
            try:
                self._cmap_subtable = ttf.get_unicode_cmap_subtable()
            except Exception:  # noqa: BLE001
                _LOG.exception("failed to parse cmap for %s", self.get_name())
                self._cmap_subtable = None
            self._cmap_resolved = True
        return self._cmap_subtable

    # ---------- cmap-platform extraction ----------

    def extract_cmap_table(self) -> None:
        """Pull the (3,1) Win-Unicode, (3,0) Win-Symbol and (1,0) Mac-Roman
        ``cmap`` subtables off the embedded TTF, plus the (0,0) and (0,3)
        Unicode-platform aliases that count as Win-Unicode for our purposes.

        Mirrors upstream ``private void extractCmapTable()`` — runs once,
        fills the three private slots used by :meth:`code_to_gid` and the
        symbolic-encoding path. Idempotent. Safe to call before any
        ``cmap``-driven lookup; :meth:`code_to_gid_via_platforms` calls it
        on demand.
        """
        if self._cmap_initialized:
            return
        ttf = self.get_true_type_font()
        if ttf is None:
            self._cmap_initialized = True
            return
        try:
            tt_inner = getattr(ttf, "_tt", None)
            cmap_table = (
                tt_inner["cmap"]
                if tt_inner is not None and "cmap" in tt_inner
                else None
            )
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to read cmap table for %s", self.get_name())
            self._cmap_initialized = True
            return
        if cmap_table is None:
            self._cmap_initialized = True
            return
        try:
            glyph_order = (
                list(tt_inner.getGlyphOrder()) if tt_inner is not None else None
            )
        except Exception:  # noqa: BLE001
            glyph_order = None
        for sub in cmap_table.tables:
            platform_id = int(getattr(sub, "platformID", -1))
            encoding_id = int(getattr(sub, "platEncID", -1))
            if platform_id == CmapTable.PLATFORM_WINDOWS:
                if encoding_id == CmapTable.ENCODING_WIN_UNICODE_BMP:
                    self._cmap_win_unicode = _CmapPlatformView(sub, glyph_order)
                elif encoding_id == CmapTable.ENCODING_WIN_SYMBOL:
                    self._cmap_win_symbol = _CmapPlatformView(sub, glyph_order)
            elif (
                platform_id == CmapTable.PLATFORM_MACINTOSH
                and encoding_id == CmapTable.ENCODING_MAC_ROMAN
            ):
                self._cmap_mac_roman = _CmapPlatformView(sub, glyph_order)
            elif platform_id == CmapTable.PLATFORM_UNICODE and encoding_id in (
                CmapTable.ENCODING_UNICODE_1_0,
                CmapTable.ENCODING_UNICODE_2_0_BMP,
            ):
                # PDFBOX-4755 / PDF.js #5501 / PDFBOX-5484 — Unicode-platform
                # entries promote to Win-Unicode. Upstream
                # ``PDTrueTypeFont.extractCmapTable`` assigns ``cmapWinUnicode``
                # *unconditionally* here, so when a font carries both a (3,1)
                # and a (0,0)/(0,3) subtable the **last** one in cmap-directory
                # order wins. (Previously guarded with ``is None`` — first-wins —
                # which diverged from upstream for such dual-cmap fonts.)
                self._cmap_win_unicode = _CmapPlatformView(sub, glyph_order)
        self._cmap_initialized = True

    # ---------- encoding lookup from font program ----------

    def read_encoding_from_font(self) -> Encoding | None:
        """Synthesise an :class:`Encoding` from the embedded font program.

        Mirrors upstream ``PDTrueTypeFont.readEncodingFromFont``:

        * Non-symbolic fonts default to :class:`StandardEncoding` per
          PDF 32000-1 §9.6.6.4 — the explicit ``/Encoding`` entry, when
          present, overrides this caller-side.
        * Standard 14 ``Symbol`` / ``ZapfDingbats`` keep the font's own
          built-in encoding — :data:`None` is returned so the caller
          falls back to the font program's own glyph names.
        * Other Standard 14 fonts also default to Standard Encoding.
        * Otherwise we synthesise a :class:`BuiltInEncoding` by walking
          codes 0..256 through :meth:`code_to_gid` and looking each gid
          up in the TTF's ``post`` table; missing names fall back to the
          decimal GID pseudo-name (``"42"`` etc.), matching upstream.

        Non-embedded Standard 14 fonts return ``Type1Encoding`` built from
        their bundled AFM (matches upstream and the ``PDType1Font`` sibling).
        """
        # Non-embedded Standard 14: read the built-in encoding from the
        # bundled Adobe AFM, exactly as upstream
        # ``PDTrueTypeFont.readEncodingFromFont`` does:
        #     if (!isEmbedded() && getStandard14AFM() != null)
        #         return new Type1Encoding(getStandard14AFM());
        # (verified live, wave 1516: a non-embedded Arial/TrueType with no
        # /Encoding resolves to Type1Encoding, not null).
        afm = self.get_standard14_afm()
        if not self.is_embedded() and afm is not None:
            from .encoding.type1_encoding import Type1Encoding  # noqa: PLC0415

            return Type1Encoding(afm)
        if self.get_symbolic_flag() is False:
            return StandardEncoding.INSTANCE
        standard14_name = Standard14Fonts.get_mapped_font_name(self.get_name())
        if (
            self.is_standard14()
            and standard14_name != Standard14Fonts.SYMBOL
            and standard14_name != Standard14Fonts.ZAPF_DINGBATS
        ):
            return StandardEncoding.INSTANCE
        ttf = self.get_true_type_font()
        if ttf is None:
            return None
        post = ttf.get_post_script()
        code_to_name: dict[int, str] = {}
        for code in range(257):
            gid = self.code_to_gid(code)
            if gid <= 0:
                continue
            name: str | None = None
            if post is not None:
                try:
                    name = post.get_name(gid)
                except Exception:  # noqa: BLE001
                    name = None
            if not name:
                # GID pseudo-name (mirrors upstream's
                # ``Integer.toString(gid)`` fallback).
                name = str(gid)
            code_to_name[code] = name
        return BuiltInEncoding(code_to_name)

    # ---------- CFF outline path (OpenType-CFF) ----------

    def get_path_from_outlines(self, code: int) -> list[tuple[Any, ...]] | None:
        """Glyph outline for ``code`` resolved through CFF charstrings.

        Mirrors upstream ``private GeneralPath getPathFromOutlines(int)``
        (PDTrueTypeFont.java line 590) — used when the embedded font is
        CFF-flavoured OpenType (``OTTO`` magic + ``CFF `` table). Walks
        ``Encoding.getName(code) -> charset.getSID(name) ->
        charset.getGIDForSID(sid) -> type2CharString.getPath()``.

        Upstream marks the method ``private``; we expose it publicly so
        the parity scanner records the match and so callers that
        already know they have an OTF-CFF font can bypass the
        ``glyf``-table branch in :meth:`get_glyph_path`.

        Returns:
            list of recorded pen segments when a charstring is found, or
            ``None`` when the font isn't OTF-CFF / has no CFF data /
            the code resolves to an unknown glyph (mirrors upstream's
            ``return type2CharString != null ? ... : null``).
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return None
        # Only OTF-CFF fonts expose a CFF outline table; bail out for
        # vanilla TrueType (``glyf``-based) inputs.
        get_cff = getattr(ttf, "get_cff", None)
        if get_cff is None:
            return None
        cff = get_cff()
        if cff is None:
            return None
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        if not name or name == ".notdef":
            return None
        # ``cff.get_path(name)`` mirrors upstream's
        # ``type2CharString.getPath()`` after the sid/gid round trip —
        # CFFFont's :meth:`get_path` already performs the lookup
        # internally and returns ``None`` for unknown names.
        try:
            path = cff.get_path(name)
        except Exception:  # noqa: BLE001 — malformed charstring should not crash callers
            _LOG.exception("CFF charstring draw failed for glyph %s", name)
            return None
        if not path:
            return None
        return path

    # ---------- parser factory ----------

    @staticmethod
    def get_parser(
        random_access_read: bytes
        | bytearray
        | memoryview
        | BinaryIO,
        is_embedded: bool = True,  # noqa: FBT001, FBT002 — mirror upstream signature
    ) -> Any:
        """Return a :class:`TTFParser` (or :class:`OTFParser`) suited to
        the SFNT flavour of ``random_access_read``.

        Mirrors upstream ``private TTFParser getParser(RandomAccessRead,
        boolean)`` (PDTrueTypeFont.java line 781). Sniffs the first four
        bytes for the ASCII tag ``OTTO`` — present on CFF-flavoured
        OpenType — and returns an :class:`OTFParser` in that case,
        otherwise a :class:`TTFParser`. The cursor is rewound after the
        sniff for stream-like inputs.

        Upstream marks the method ``private``; we expose it as a
        ``@staticmethod`` so the parity scanner records the match and
        so embedder code that already has TTF bytes in hand can pick
        the right parser without duplicating the sniffing logic.

        Accepts:
            * raw bytes / bytearray / memoryview — the leading four
              bytes are read directly.
            * file-like object with ``.read`` / ``.seek`` / ``.tell`` —
              the four bytes are read and the position restored.
        """
        from pypdfbox.fontbox.ttf.otf_parser import OTFParser  # noqa: PLC0415
        from pypdfbox.fontbox.ttf.ttf_parser import TTFParser  # noqa: PLC0415

        if isinstance(random_access_read, (bytes, bytearray, memoryview)):
            head = bytes(random_access_read[:4])
        else:
            # File-like: snapshot position, peek four bytes, rewind.
            try:
                start = random_access_read.tell()
            except (AttributeError, OSError):
                start = None
            head_bytes = random_access_read.read(4) or b""
            if start is not None:
                import contextlib  # noqa: PLC0415

                with contextlib.suppress(AttributeError, OSError):
                    random_access_read.seek(start)
            head = bytes(head_bytes)
        if head == b"OTTO":
            return OTFParser(is_embedded)
        return TTFParser(is_embedded)

    # ---------- load (static factory for embedding) ----------

    @staticmethod
    def load(
        doc: Any,
        source: str | bytes | bytearray | memoryview | BinaryIO,
        encoding: Encoding | None = None,
    ) -> PDTrueTypeFont:
        """Load a TTF to be embedded into a document as a simple font.

        Mirrors upstream ``static PDTrueTypeFont load(PDDocument, File,
        Encoding)`` / ``load(PDDocument, InputStream, Encoding)`` /
        ``load(PDDocument, RandomAccessRead, Encoding)`` /
        ``load(PDDocument, TrueTypeFont, Encoding)``
        (PDTrueTypeFont.java lines 206, 226, 246, 266). Upstream's four
        overloads collapse to one Python entry point because we dispatch
        on the concrete ``source`` type — path string, raw bytes, file-
        like, or a pre-parsed :class:`TrueTypeFont`.

        Simple fonts only support 256 character codes; upstream's
        docstring tells callers to switch to :meth:`PDType0Font.load`
        for full Unicode support, and we preserve the same advice.

        ``doc`` is accepted for upstream signature parity; the returned
        font dictionary is *not* automatically registered with the
        document — callers attach it via :class:`PDResources` or direct
        dictionary manipulation, matching :meth:`PDType0Font.load`.

        Returns:
            A freshly-constructed :class:`PDTrueTypeFont` with the TTF
            embedded in the descriptor's ``/FontFile2`` stream, the
            supplied (or :class:`WinAnsiEncoding`-default) encoding
            wired into ``/Encoding``, and ``/Widths`` populated from
            the TTF's ``hmtx`` table.
        """
        del doc  # signature parity only; unused.
        from .encoding import WinAnsiEncoding  # noqa: PLC0415

        ttf, ttf_bytes = _resolve_ttf_source(source)
        active_encoding: Encoding = (
            encoding if encoding is not None else WinAnsiEncoding.INSTANCE
        )
        return _build_simple_ttf_font(ttf, ttf_bytes, active_encoding)

    # ---------- encode (codepoint -> bytes) ----------

    def encode_codepoint(self, unicode: int) -> bytes:  # type: ignore[override]
        """Encode a single Unicode codepoint to a 1-byte PDF code.

        Mirrors upstream ``PDTrueTypeFont.encode(int unicode)``:

        * With an ``/Encoding``: the codepoint must be mappable through
          the active glyph list to a name that the encoding contains
          *and* the embedded TTF carries (or its ``uniXXXX`` synonym).
          Returns the byte the encoding assigns to that name.
        * Without an ``/Encoding``: the codepoint must round-trip
          through ``glyph-list -> glyph-name -> ttf-gid -> gid_to_code``;
          returns the resulting code.

        Raises :class:`ValueError` whenever no glyph or no encoding slot
        can be found — matches upstream's ``IllegalArgumentException``
        for the same conditions, mapped to ``ValueError`` per the
        project's Java→Python exception convention.
        """
        encoding = self.get_encoding_typed()
        glyph_list = self.get_glyph_list()
        name = glyph_list.code_point_to_name(unicode)
        ttf = self.get_true_type_font()
        if encoding is not None:
            if not encoding.contains(name if name is not None else ".notdef"):
                raise ValueError(
                    f"U+{unicode:04X} is not available in font {self.get_name()} "
                    f"encoding: {encoding.get_encoding_name()}"
                )
            # Verify the embedded TTF actually has a glyph by that name —
            # try the AGL name first, then the uniXXXX fallback.
            if ttf is not None and name is not None and not ttf.has_glyph(name):
                uni_name = _uni_name_of_code_point(unicode)
                if not ttf.has_glyph(uni_name):
                    raise ValueError(
                        f"No glyph for U+{unicode:04X} in font {self.get_name()}"
                    )
            inverted = encoding.get_name_to_code_map()
            assert name is not None
            code = inverted.get(name)
            if code is None:
                raise ValueError(
                    f"U+{unicode:04X} is not available in font {self.get_name()} "
                    f"encoding"
                )
            return bytes([code & 0xFF])
        # No /Encoding — round-trip through the gid-to-code map.
        if ttf is None or name is None:
            raise ValueError(
                f"No glyph for U+{unicode:04X} in font {self.get_name()}"
            )
        if not ttf.has_glyph(name):
            raise ValueError(
                f"No glyph for U+{unicode:04X} in font {self.get_name()}"
            )
        gid = ttf.name_to_gid(name)
        code = self.get_gid_to_code().get(gid)
        if code is None:
            raise ValueError(
                f"U+{unicode:04X} is not available in font {self.get_name()} encoding"
            )
        return bytes([code & 0xFF])


class _CmapPlatformView:
    """Thin ``code -> gid`` view over a fontTools cmap subtable.

    Exposes :meth:`get_glyph_id` (the single entry upstream's
    ``codeToGID`` reaches for) and :meth:`get_name` (the underlying
    fontTools mapping).
    """

    __slots__ = ("_chars", "_code_to_gid")

    def __init__(
        self,
        fonttools_subtable: Any,
        glyph_order: list[str] | None = None,
    ) -> None:
        self._chars: dict[int, str] = dict(fonttools_subtable.cmap)
        self._code_to_gid: dict[int, int] = {}
        if glyph_order is not None:
            name_to_gid = {name: gid for gid, name in enumerate(glyph_order)}
            for code, name in self._chars.items():
                gid = name_to_gid.get(name)
                if gid is not None:
                    self._code_to_gid[code] = gid

    def get_name(self, code: int) -> str | None:
        """Glyph name for ``code`` (``None`` when unmapped)."""
        return self._chars.get(code)

    def get_glyph_id(self, code: int) -> int:
        """GID for ``code`` (``0`` when unmapped)."""
        return self._code_to_gid.get(int(code), 0)


def _scale_path(
    path: list[tuple[Any, ...]], scale: float
) -> list[tuple[Any, ...]]:
    """Return a copy of ``path`` with every coordinate tuple scaled by
    ``scale``. Verbs are preserved unchanged; the args of ``moveTo``,
    ``lineTo``, ``curveTo``, ``qCurveTo`` are re-emitted with each point
    scaled. ``closePath`` carries no args.
    """
    out: list[tuple[Any, ...]] = []
    for verb, args in path:
        if verb == "closePath" or not args:
            out.append((verb, args))
            continue
        scaled_pts: list[Any] = []
        for pt in args:
            if pt is None:
                scaled_pts.append(None)
            elif (
                isinstance(pt, (tuple, list))
                and len(pt) == 2
                and not isinstance(pt[0], (tuple, list))
            ):
                scaled_pts.append((pt[0] * scale, pt[1] * scale))
            else:
                scaled_pts.append(pt)
        out.append((verb, tuple(scaled_pts)))
    return out


def _uni_name_of_code_point(code_point: int) -> str:
    """Synthesise the ``uniXXXX`` glyph name for ``code_point``.

    Mirrors upstream ``UniUtil.getUniNameOfCodePoint`` (uppercase hex,
    minimum width four). Used by :meth:`PDTrueTypeFont.encode_codepoint`
    to fall back when the canonical AGL name has no glyph in the font.
    """
    hex_str = format(code_point, "X")
    if len(hex_str) < 4:
        hex_str = hex_str.rjust(4, "0")
    return "uni" + hex_str


# ---------- module-level helpers (fontTools shim) ----------


def _fonttools_glyph_set(ttf: TrueTypeFont) -> Any | None:
    """Return the fontTools ``GlyphSet`` for ``ttf``, or ``None`` when the
    underlying font has no drawable glyphs (rare — should only happen for
    deeply broken inputs)."""
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return None
    try:
        return inner.getGlyphSet()
    except Exception:  # noqa: BLE001 — fontTools may raise on malformed tables
        _LOG.exception("getGlyphSet failed")
        return None


def _gid_to_glyph_name(ttf: TrueTypeFont, gid: int) -> str | None:
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return None
    try:
        order = inner.getGlyphOrder()
    except Exception:  # noqa: BLE001
        return None
    if 0 <= gid < len(order):
        return str(order[gid])
    return None


def _draw_glyph_by_name(ttf: TrueTypeFont, name: str) -> list[tuple[Any, ...]]:
    glyph_set = _fonttools_glyph_set(ttf)
    if glyph_set is None or name not in glyph_set:
        return []
    try:
        # Use a *decomposing* recording pen so a composite TrueType glyph
        # (e.g. an accented ``eacute`` = ``e`` + ``acute``) is flattened
        # into real moveTo/lineTo/qCurveTo segments — matching upstream
        # ``GlyphData.getPath()``, which returns a single ``GeneralPath``
        # with the component outlines transformed and merged in. A plain
        # ``RecordingPen`` instead records raw ``addComponent`` tuples,
        # which downstream consumers (the 1000/upem scaler in
        # ``get_normalized_path``, text extraction, structure tagging) can
        # neither scale nor draw — the component reference would be silently
        # dropped, so the glyph rendered blank.
        from fontTools.pens.recordingPen import (  # type: ignore[import-untyped]  # noqa: PLC0415
            DecomposingRecordingPen,
        )

        pen = DecomposingRecordingPen(glyph_set)
        glyph_set[name].draw(pen)
    except Exception:  # noqa: BLE001 — unparsable charstrings should not crash callers
        _LOG.exception("recordingPen draw failed for glyph %s", name)
        return []
    return list(pen.value)


def _draw_glyph_by_gid(ttf: TrueTypeFont, gid: int) -> list[tuple[Any, ...]]:
    name = _gid_to_glyph_name(ttf, gid)
    if name is None:
        return []
    return _draw_glyph_by_name(ttf, name)


def _glyph_bbox_height(ttf: TrueTypeFont, gid: int) -> float:
    """Height of glyph ``gid``'s on-curve bounding box in font units.

    Reads the ``glyf`` table directly when present (TTF outline fonts).
    Falls back to drawing the glyph through the fontTools glyph set and
    measuring the recorded segments — covers CFF-shaped paths embedded
    inside an OpenType-flavoured ``/FontFile2`` stream, even though that
    is not strictly a conforming PDF. Returns ``0.0`` when nothing
    drawable is found.
    """
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return 0.0
    name = _gid_to_glyph_name(ttf, gid)
    if name is None:
        return 0.0
    if "glyf" in inner:
        try:
            glyph = inner["glyf"][name]
            y_min = int(getattr(glyph, "yMin", 0))
            y_max = int(getattr(glyph, "yMax", 0))
            return float(y_max - y_min)
        except (KeyError, AttributeError):
            return 0.0
    # CFF-style fallback via the bounding-box pen.
    try:
        from fontTools.pens.boundsPen import BoundsPen  # type: ignore[import-untyped]

        glyph_set = _fonttools_glyph_set(ttf)
        if glyph_set is None or name not in glyph_set:
            return 0.0
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        if pen.bounds is None:
            return 0.0
        _, y_min, _, y_max = pen.bounds
        return float(y_max - y_min)
    except Exception:  # noqa: BLE001
        return 0.0


_BASE25 = "BCDEFGHIJKLMNOPQRSTUVWXYZ"


def _deterministic_subset_tag(glyph_ids: Iterable[int]) -> str:
    """Return a deterministic six-uppercase-letter PDF subset tag.

    Mirrors upstream ``TrueTypeEmbedder.getTag(gidToCid)`` (PDFBox 3.0
    ``TrueTypeEmbedder.java`` lines 363-387) — base-25 encode a stable
    hash of the surviving glyph id set, then left-pad with ``A`` to six
    characters and suffix ``+``. Determinism: the same input glyph set
    produces the same tag across runs and processes (Python's hash
    randomisation only randomises ``str`` / ``bytes`` / ``frozenset``;
    ``hash`` of a tuple of ints is stable across interpreter starts),
    which is the contract subset round-trip relies on.
    """
    ids = sorted({int(g) for g in glyph_ids})
    num = abs(hash(tuple(ids))) % (10**18)
    sb: list[str] = []
    while num != 0 and len(sb) < 6:
        div, mod = divmod(num, 25)
        sb.append(_BASE25[mod])
        num = div
    while len(sb) < 6:
        sb.insert(0, "A")
    return "".join(sb)


def _random_subset_tag() -> str:
    """Return a fresh six-uppercase-letter PDF subset tag.

    Retained for callers that explicitly want a non-deterministic tag.
    The default subset path uses :func:`_deterministic_subset_tag` so
    the same input round-trips to the same prefix (mirrors upstream
    ``TrueTypeEmbedder.getTag``).
    """
    alphabet = string.ascii_uppercase
    return "".join(secrets.choice(alphabet) for _ in range(6))


def _embed_subset_bytes(
    font: Any,
    subset_bytes: bytes,
    tag: str,
) -> None:
    """Embed ``subset_bytes`` into ``font``'s ``/FontFile2`` stream and
    rename ``/BaseFont`` / ``/FontName`` with the six-letter ``tag``.

    Shared between :class:`PDTrueTypeFont` and the Type 0 / CIDFontType2
    subset path, where the dictionary surface is identical (a font dict
    with ``/BaseFont`` plus a descriptor with ``/FontName`` and
    ``/FontFile2``).
    """
    descriptor = font.get_font_descriptor()
    if descriptor is None:
        # Caller invariant: subset() guarantees we found a TTF, which
        # means the descriptor existed at lookup time. Defensive guard
        # in case a caller mutates state mid-subset.
        raise ValueError("font has no /FontDescriptor; cannot embed subset")

    # Replace /FontFile2 contents in-place when one already exists, so
    # any existing object reference (e.g. shared with another font) keeps
    # pointing at the same COSStream instance. Otherwise create a fresh
    # stream and attach it to the descriptor.
    existing = descriptor.get_font_file2()
    if existing is not None:
        cos_stream = existing.get_cos_object()
        # Drop any pre-existing /Filter — set_raw_data writes the raw
        # body; without clearing the filter chain, downstream readers
        # would attempt to FlateDecode an already-uncompressed TTF.
        cos_stream.remove_item(COSName.FILTER)  # type: ignore[attr-defined]
        cos_stream.set_raw_data(subset_bytes)
    else:
        new_stream = COSStream()
        new_stream.set_raw_data(subset_bytes)
        descriptor.set_font_file2(new_stream)

    # Update /BaseFont — prepend the six-letter tag if it isn't already
    # carrying one (mirrors :meth:`TTFSubsetter._apply_prefix`).
    current_base = font.get_name()
    if current_base:
        if (
            len(current_base) >= 7
            and current_base[6] == "+"
            and current_base[:6].isalpha()
            and current_base[:6].isupper()
        ):
            new_base = current_base  # already tagged
        else:
            new_base = f"{tag}+{current_base}"
        font.get_cos_object().set_name(_BASE_FONT, new_base)

    # Mirror onto /FontName so the descriptor agrees with /BaseFont
    # (PDF 32000-1 §9.8.2 requires the two to match, including the tag).
    current_font_name = descriptor.get_font_name()
    if current_font_name:
        if (
            len(current_font_name) >= 7
            and current_font_name[6] == "+"
            and current_font_name[:6].isalpha()
            and current_font_name[:6].isupper()
        ):
            new_font_name = current_font_name
        else:
            new_font_name = f"{tag}+{current_font_name}"
        descriptor.set_font_name(new_font_name)


def _resolve_ttf_source(
    source: str | bytes | bytearray | memoryview | Any,
) -> tuple[TrueTypeFont, bytes]:
    """Coerce :meth:`PDTrueTypeFont.load`'s polymorphic ``source`` to a
    ``(TrueTypeFont, bytes)`` pair.

    Handles the four upstream overloads in one place:

    * ``str`` / ``os.PathLike`` — read the file and parse.
    * raw bytes / bytearray / memoryview — parse directly.
    * file-like binary stream — read to EOF, parse.
    * an already-parsed :class:`TrueTypeFont` — use as-is; the raw bytes
      come from :meth:`TrueTypeFont.get_original_data` so downstream
      embedding still has the on-wire SFNT.
    """
    import os  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    if isinstance(source, TrueTypeFont):
        raw_bytes = source.get_original_data()
        return source, bytes(raw_bytes)
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw = bytes(source)
        return TrueTypeFont.from_bytes(raw), raw
    if isinstance(source, (str, os.PathLike)):
        raw = Path(os.fspath(source)).read_bytes()
        return TrueTypeFont.from_bytes(raw), raw
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            raise TypeError(
                "PDTrueTypeFont.load source must yield bytes, not str — "
                "open in binary mode"
            )
        raw = bytes(data)
        return TrueTypeFont.from_bytes(raw), raw
    raise TypeError(
        f"PDTrueTypeFont.load cannot read font bytes from {type(source).__name__}"
    )


def _build_simple_ttf_font(
    ttf: TrueTypeFont, ttf_bytes: bytes, encoding: Encoding
) -> PDTrueTypeFont:
    """Construct a fully-wired :class:`PDTrueTypeFont` simple font.

    Mirrors the bookkeeping upstream's ``PDTrueTypeFontEmbedder``
    performs when building a /Subtype /TrueType dictionary for embedding:

    * /BaseFont, /Subtype /TrueType, /Encoding.
    * /FontDescriptor with metric fields populated from the TTF.
    * /FontFile2 carrying the unmodified TTF bytes.
    * /FirstChar 0, /LastChar 255 and a /Widths table built from
      the encoding's code-to-name map (codes with no glyph fall back
      to 0).
    """
    from pypdfbox.cos import COSArray, COSFloat  # noqa: PLC0415

    from .pd_font_descriptor import (  # noqa: PLC0415
        FLAG_NON_SYMBOLIC,
        PDFontDescriptor,
    )

    base_font = _ps_name_from_ttf_local(ttf, "EmbeddedTTF")

    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "TrueType")
    font_dict.set_name(_BASE_FONT, base_font)
    # Wire /Encoding so the round-trip is observable on the COS layer
    # (upstream sets this through the embedder, but the resulting dict
    # carries a /Encoding entry regardless).
    enc_obj = encoding.get_cos_object()
    if enc_obj is not None:  # pragma: no branch
        # Defensive: every Encoding exposes a COS object; the False arm
        # has no live caller in the test suite.
        font_dict.set_item(COSName.get_pdf_name("Encoding"), enc_obj)

    # /FontDescriptor with the bare-minimum metric fields.
    descriptor = PDFontDescriptor()
    descriptor.set_font_name(base_font)
    # Simple TrueType embeds default to non-symbolic; upstream lets the
    # caller adjust this for symbolic fonts.
    descriptor.set_flags(FLAG_NON_SYMBOLIC)
    _populate_simple_descriptor_from_ttf(descriptor, ttf)
    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)
    descriptor.set_font_file2(font_file2)
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )

    # /FirstChar /LastChar /Widths — width per code through the encoding.
    widths = _build_simple_widths(ttf, encoding)
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), 0)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), 255)
    widths_array = COSArray()
    for w in widths:
        widths_array.add(COSFloat(float(w)))
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths_array)

    font = PDTrueTypeFont(font_dict)
    # Cache the parsed TTF so subsequent metric / cmap calls don't
    # re-parse the embedded /FontFile2.
    font.set_true_type_font(ttf)
    return font


def _ps_name_from_ttf_local(ttf: TrueTypeFont, fallback: str) -> str:
    """Best-effort PostScript name from a parsed TTF. Mirrors the helper
    in :mod:`pd_type0_font` but kept local to avoid a cross-module import
    cycle."""
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return fallback
    try:
        name_table = inner["name"]
    except (KeyError, AttributeError):
        return fallback
    record = (
        name_table.getName(6, 3, 1, 0x409)
        or name_table.getName(6, 1, 0, 0)
        or name_table.getName(6, 0, 3, 0)
    )
    if record is None:
        return fallback
    try:
        text = record.toUnicode()
    except Exception:  # noqa: BLE001
        return fallback
    text = text.strip()
    return text if text else fallback


def _populate_simple_descriptor_from_ttf(
    descriptor: Any, ttf: TrueTypeFont
) -> None:
    """Populate a simple-font /FontDescriptor with metric fields read
    from ``ttf``. Mirrors the upstream ``TrueTypeEmbedder`` field copy
    used by ``PDTrueTypeFont.load``; values are scaled to 1/1000 em."""
    from pypdfbox.cos import COSArray, COSFloat  # noqa: PLC0415

    head = ttf.get_header()
    units_per_em = head.get_units_per_em() if head is not None else 1000
    if units_per_em <= 0:
        units_per_em = 1000
    scale = 1000.0 / units_per_em

    if head is not None:
        bbox = COSArray()
        bbox.add(COSFloat(float(head.get_x_min()) * scale))
        bbox.add(COSFloat(float(head.get_y_min()) * scale))
        bbox.add(COSFloat(float(head.get_x_max()) * scale))
        bbox.add(COSFloat(float(head.get_y_max()) * scale))
        descriptor.set_font_b_box(bbox)

    hhea = ttf.get_horizontal_header()
    if hhea is not None:
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("Ascent"), int(hhea.get_ascender() * scale)
        )
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("Descent"), int(hhea.get_descender() * scale)
        )
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("CapHeight"), int(hhea.get_ascender() * scale)
        )

    descriptor.get_cos_object().set_int(COSName.get_pdf_name("ItalicAngle"), 0)
    descriptor.get_cos_object().set_int(COSName.get_pdf_name("StemV"), 80)


def _build_simple_widths(ttf: TrueTypeFont, encoding: Encoding) -> list[float]:
    """Return 256 advance widths (one per simple-font code) in 1/1000 em.

    Walks codes 0..255 through ``encoding.get_name`` to find the glyph
    name, looks the name up via the TTF's cmap to get a GID, then reads
    ``hmtx`` for the advance width. Unmapped codes get 0.
    """
    units_per_em = ttf.get_units_per_em()
    if units_per_em <= 0:
        units_per_em = 1000
    scale = 1000.0 / units_per_em
    widths: list[float] = []
    for code in range(256):
        try:
            name = encoding.get_name(code)
        except Exception:  # noqa: BLE001
            name = None
        if not name or name == ".notdef":
            widths.append(0.0)
            continue
        try:
            gid = ttf.name_to_gid(name)
        except Exception:  # noqa: BLE001
            gid = 0
        if gid <= 0:
            widths.append(0.0)
            continue
        try:
            advance = ttf.get_advance_width(gid)
        except Exception:  # noqa: BLE001
            advance = 0
        widths.append(float(advance) * scale)
    return widths


__all__ = ["PDTrueTypeFont"]
