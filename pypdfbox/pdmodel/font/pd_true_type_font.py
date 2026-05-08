from __future__ import annotations

import io
import logging
import secrets
import string
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, overload

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

from .pd_simple_font import PDSimpleFont

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

    # ---------- subsetting ----------

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
        the embedded font program. Falls back to the ``hmtx`` advance
        from the embedded TrueType, scaled by ``1000 / unitsPerEm``.
        Returns 0.0 when neither source can answer.
        """
        first_char = self.get_first_char()
        widths = self.get_widths()
        if first_char >= 0 and widths:
            idx = code - first_char
            if 0 <= idx < len(widths):
                return float(widths[idx])

        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0

        gid = self._code_to_gid(code, ttf)
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        advance = ttf.get_advance_width(gid)
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
