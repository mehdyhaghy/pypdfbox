from __future__ import annotations

import io
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
        """Alias for :meth:`get_name` — mirrors upstream's split between
        ``getName()`` and ``getBaseFont()`` on simple fonts (both read
        ``/BaseFont``).
        """
        return self.get_name()

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

    def _generate_bounding_box(self) -> BoundingBox | None:
        """Build the font's :class:`BoundingBox` once.

        Mirrors upstream ``private BoundingBox generateBoundingBox()``.
        Descriptor ``/FontBBox`` wins when present (with non-zero corners);
        otherwise the embedded TTF's ``head`` table provides the rect.
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

        tag = prefix if prefix is not None else _random_subset_tag()
        subsetter = TTFSubsetter(ttf)
        subsetter.add_all(codepoints)
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
                return float(widths[idx])

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

    def read_code(self, stream: BinaryIO | bytes | bytearray | memoryview) -> int:
        """Read one byte from ``stream`` and return its integer code.

        Mirrors upstream ``PDTrueTypeFont.readCode(InputStream)`` —
        TrueType simple fonts use single-byte character codes, so the
        reader is just a one-byte pull. Accepts either a binary file
        object (anything with a ``.read(int)`` method) or a raw
        ``bytes`` / ``bytearray`` / ``memoryview`` for caller
        convenience. Returns ``-1`` at end-of-stream to mirror Java's
        ``InputStream.read`` contract.
        """
        if isinstance(stream, (bytes, bytearray, memoryview)):
            stream = io.BytesIO(bytes(stream))
        chunk = stream.read(1)
        if not chunk:
            return -1
        return chunk[0]

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
        """Resolve a one-byte character code to a TrueType glyph ID via
        the font's ``/Encoding`` and the embedded ``cmap``.

        Symbolic / no-Encoding fonts: treat ``code`` as the cmap key
        directly (matches the PDFBox behaviour for fonts without a
        meaningful PostScript encoding)."""
        encoding = self.get_encoding_typed()
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
        # Fallback: ask the cmap directly (symbolic fonts / no encoding).
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
        for sub in cmap_table.tables:
            platform_id = int(getattr(sub, "platformID", -1))
            encoding_id = int(getattr(sub, "platEncID", -1))
            if platform_id == CmapTable.PLATFORM_WINDOWS:
                if encoding_id == CmapTable.ENCODING_WIN_UNICODE_BMP:
                    self._cmap_win_unicode = _CmapPlatformView(sub)
                elif encoding_id == CmapTable.ENCODING_WIN_SYMBOL:
                    self._cmap_win_symbol = _CmapPlatformView(sub)
            elif (
                platform_id == CmapTable.PLATFORM_MACINTOSH
                and encoding_id == CmapTable.ENCODING_MAC_ROMAN
            ):
                self._cmap_mac_roman = _CmapPlatformView(sub)
            elif (
                platform_id == CmapTable.PLATFORM_UNICODE
                and encoding_id
                in (
                    CmapTable.ENCODING_UNICODE_1_0,
                    CmapTable.ENCODING_UNICODE_2_0_BMP,
                )
                and self._cmap_win_unicode is None
            ):
                # PDFBOX-4755 / PDF.js #5501 / PDFBOX-5484 — Unicode platform
                # entries promote to Win-Unicode when no explicit (3,1) is
                # present. ``putIfAbsent`` semantics: don't clobber a real
                # (3,1) subtable.
                self._cmap_win_unicode = _CmapPlatformView(sub)
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

        Returns ``None`` for the AFM-driven branch (we currently have no
        ``Type1Encoding`` port) — callers should fall through to their
        usual encoding-resolution path.
        """
        # Non-symbolic, non-embedded fonts: PDF spec defaults to Standard.
        if not self.is_embedded() and self.get_standard14_afm() is not None:
            # Upstream returns ``new Type1Encoding(getStandard14AFM())`` here.
            # We don't have a Type1Encoding-from-AFM port yet; fall through
            # to None and let the caller use its standard encoding chain.
            return None
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

    Mirrors enough of :class:`CmapSubtable` for :meth:`extract_cmap_table`
    callers to resolve glyphs through the (3,1) Win-Unicode, (3,0)
    Win-Symbol and (1,0) Mac-Roman tables independently of the
    priority-ordered Unicode subtable returned by
    :meth:`TrueTypeFont.get_unicode_cmap_subtable`.

    Only :meth:`get_glyph_id` is exposed because that is the single entry
    upstream's ``codeToGID`` reaches for. Materialises ``code -> name``
    once at construction so repeated lookups don't hit fontTools.
    """

    __slots__ = ("_chars",)

    def __init__(self, fonttools_subtable: Any) -> None:
        self._chars: dict[int, str] = dict(fonttools_subtable.cmap)

    def get_name(self, code: int) -> str | None:
        """Glyph name for ``code`` (``None`` when unmapped)."""
        return self._chars.get(code)


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
        from fontTools.pens.recordingPen import RecordingPen  # type: ignore[import-untyped]

        pen = RecordingPen()
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


def _random_subset_tag() -> str:
    """Return a fresh six-uppercase-letter PDF subset tag.

    Per PDF 32000-1 §9.6.4 the tag is six uppercase ASCII letters chosen
    arbitrarily. We use ``secrets`` so concurrent subsetters in the same
    process don't collide on a deterministic seed.
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


__all__ = ["PDTrueTypeFont"]
