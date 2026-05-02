from __future__ import annotations

import io
import logging
from typing import BinaryIO

from pypdfbox.cos import COSDictionary
from pypdfbox.fontbox.type1.type1_font import Type1Font

from .afm_loader import AfmMetrics
from .pd_simple_font import PDSimpleFont
from .standard14_fonts import Standard14Fonts

_LOG = logging.getLogger(__name__)

# Alternative glyph names commonly encountered in substitute fonts.
# Mirrors the ``ALT_NAMES`` table on upstream ``PDType1Font`` — when a
# requested ligature name is not present in the underlying program, we
# retry with these underscore-separated component spellings (e.g.
# ``ff`` -> ``f_f``). The misspelled ``ellipsis`` -> ``elipsis`` entry is
# load-bearing for some ArialMT-substituted Type 1 PDFs.
_ALT_NAMES: dict[str, str] = {
    "ff": "f_f",
    "ffi": "f_f_i",
    "ffl": "f_f_l",
    "fi": "f_i",
    "fl": "f_l",
    "st": "s_t",
    "IJ": "I_J",
    "ij": "i_j",
    "ellipsis": "elipsis",  # misspelled in ArialMT
}

# First byte of a PFB-wrapped Type 1 font program — see PDFBOX-2607.
# Upstream uses this constant to detect when an embedded ``/FontFile``
# stream contains the entire PFB envelope (header + segments) rather
# than the bare two binary segments specified by PDF 32000-1 §9.9.
_PFB_START_MARKER: int = 0x80


class PDType1Font(PDSimpleFont):
    """PDF Type 1 (PostScript) font. Mirrors PDFBox ``PDType1Font``.

    The embedded font program (``/FontFile`` on the ``/FontDescriptor``)
    is parsed lazily on first metric access via :class:`Type1Font` —
    itself a thin wrapper around ``fontTools.t1Lib``. Glyph widths and
    outlines are exposed through :meth:`get_glyph_width` and
    :meth:`get_glyph_path`.
    """

    SUB_TYPE = "Type1"

    # Re-exposed at class level so external callers can mirror the
    # ``PDType1Font.ALT_NAMES`` / ``PDType1Font.PFB_START_MARKER`` access
    # patterns from upstream.
    ALT_NAMES = _ALT_NAMES
    PFB_START_MARKER = _PFB_START_MARKER

    # PostScript names of the 14 Standard fonts (PDF 32000-1:2008 §9.6.2.2).
    # Mirror upstream ``Standard14Fonts.FontName`` enum values exactly so
    # callers can spell the canonical name with ``PDType1Font.HELVETICA``
    # rather than the verbose ``Standard14Fonts.HELVETICA``. The string
    # values match those of the upstream Java enum's ``getName()``.
    HELVETICA = "Helvetica"
    HELVETICA_BOLD = "Helvetica-Bold"
    HELVETICA_OBLIQUE = "Helvetica-Oblique"
    HELVETICA_BOLD_OBLIQUE = "Helvetica-BoldOblique"

    TIMES_ROMAN = "Times-Roman"
    TIMES_BOLD = "Times-Bold"
    TIMES_ITALIC = "Times-Italic"
    TIMES_BOLD_ITALIC = "Times-BoldItalic"

    COURIER = "Courier"
    COURIER_BOLD = "Courier-Bold"
    COURIER_OBLIQUE = "Courier-Oblique"
    COURIER_BOLD_OBLIQUE = "Courier-BoldOblique"

    SYMBOL = "Symbol"
    ZAPF_DINGBATS = "ZapfDingbats"

    # Default advance returned by :meth:`get_width_from_font` for the
    # ``.notdef`` glyph of a substituted (non-embedded) font. Mirrors the
    # ``return 250`` literal in upstream ``PDType1Font.getWidthFromFont``
    # and PDFBOX-1900 — picked to match the Adobe AFM ``.notdef`` advance
    # for Helvetica.
    SUBSTITUTE_NOTDEF_WIDTH: float = 250.0

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazily-loaded embedded Type 1 program. ``None`` means
        # "not yet attempted", ``False`` means "tried, no /FontFile or
        # parse failed".
        self._t1: Type1Font | None | bool = None

    # ---------- Type 1 program access ----------

    def _get_type1_font(self) -> Type1Font | None:
        """Return the parsed Type 1 program for this font's ``/FontFile``
        stream, or ``None`` if the font is not embedded or the stream
        cannot be parsed. Result is cached.

        Subclasses that read a different stream slot (e.g. ``PDType1CFont``
        which uses ``/FontFile3 /Subtype /Type1C``) override this to
        return ``None`` and supply their own program getter.
        """
        if self._t1 is not None:
            return self._t1 if isinstance(self._t1, Type1Font) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._t1 = False
            return None
        font_file = descriptor.get_font_file()
        if font_file is None:
            self._t1 = False
            return None
        try:
            raw = font_file.to_byte_array()
            self._t1 = Type1Font.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile for %s", self.get_name())
            self._t1 = False
            return None
        return self._t1

    def set_font_program(self, font: Type1Font | None) -> None:
        """Inject a pre-parsed :class:`Type1Font`. Mirrors the equivalent
        TTF-side injector — lets callers that already have the font
        program in hand bypass ``/FontFile`` parsing, and lets tests
        skip the byte-level fixture round-trip."""
        self._t1 = font if font is not None else False

    # ---------- per-glyph widths ----------

    def get_glyph_width(self, code: int) -> float:
        """Return the advance width for character code ``code`` in 1/1000 em.

        Per PDF 32000-1:2008 §9.6.6.4, when the font dictionary supplies a
        ``/Widths`` array (indexed from ``/FirstChar`` through ``/LastChar``),
        that table **wins over** every other source — including the Standard
        14 AFM widths for the canonical fonts.

        Lookup order:

        1. ``/Widths[code - /FirstChar]`` if the dict carries one and the
           code falls inside the ``/FirstChar``..``/LastChar`` window.
        2. Embedded font-program advance (``/FontFile`` for Type 1,
           ``/FontFile3 /Subtype /Type1C`` for the CFF subclass), scaled
           from font units to 1/1000 em.
        3. Standard 14 AFM fallback when ``/BaseFont`` resolves to one of
           the canonical fonts. The font dict's ``/Encoding`` (if any)
           selects the code → glyph-name mapping; otherwise the PostScript
           default encoding for the family is used (PDF 32000-1 §9.6.2.4).
        4. ``0.0`` (matches PDFBox's ``getWidth`` fallback for a
           non-Standard-14 font with no ``/Widths`` and no embedded program).
        """
        # 1. /Widths overrides every other source.
        widths = self.get_widths()
        first = self.get_first_char()
        last = self.get_last_char()
        if widths and 0 <= first <= code <= last:
            idx = code - first
            if idx < len(widths):
                return float(widths[idx])

        # 2. Embedded font program.
        program_width = self._program_width(code)
        if program_width is not None:
            return program_width

        # 3. Standard 14 fallback via the bundled AFM.
        base_font = self.get_name()
        if base_font is not None and Standard14Fonts.containsName(base_font):
            # If the PDF supplied an /Encoding, honour it for code -> name;
            # otherwise use the font's PostScript default encoding.
            typed_encoding = self.get_encoding_typed()
            if typed_encoding is not None:
                glyph_name = typed_encoding.get_name(code)
            else:
                # No /Encoding -> default per PDF 32000-1 §9.6.2.4. Resolved
                # internally by Standard14Fonts.get_average_widths which is
                # cached; for a single-code lookup we go through the AFM
                # directly via the standard default encoding.
                from .encoding.standard_encoding import StandardEncoding
                from .encoding.symbol_encoding import SymbolEncoding
                from .encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding

                canonical = Standard14Fonts.getMappedFontName(base_font)
                if canonical == "Symbol":
                    glyph_name = SymbolEncoding.INSTANCE.get_name(code)
                elif canonical == "ZapfDingbats":
                    glyph_name = ZapfDingbatsEncoding.INSTANCE.get_name(code)
                else:
                    glyph_name = StandardEncoding.INSTANCE.get_name(code)
            if glyph_name != ".notdef":
                return Standard14Fonts.get_glyph_width(base_font, glyph_name)

        return 0.0

    def get_width_from_font(self, code: int) -> float:
        """Return the glyph advance for ``code`` *as reported by the
        underlying font program* in 1/1000 em — bypassing the
        ``/Widths`` array. Mirrors upstream
        ``PDType1Font.getWidthFromFont``.

        Behaviour:

        * If the font is **not** embedded and ``code`` resolves to
          ``.notdef``, return :data:`SUBSTITUTE_NOTDEF_WIDTH` (250) —
          PDFBOX-1900: the substitute's ``.notdef`` advance is meaningless
          for the original font, so a fixed sentinel is used instead.
        * Otherwise return the embedded program's advance for the
          (encoding-resolved, ``ALT_NAMES``-remapped) glyph name. If no
          program is loaded or the glyph is absent, fall through to the
          Standard 14 AFM mean for the matching Standard 14 base font.
        * Returns ``0.0`` when nothing is resolvable.
        """
        name = self.code_to_name(code)
        if not self.is_embedded() and name == ".notdef":
            return self.SUBSTITUTE_NOTDEF_WIDTH
        program_width = self._program_width(code)
        if program_width is not None:
            return program_width
        # Standard 14 AFM fallback (matches the third tier of get_glyph_width).
        afm = self.get_standard_14_font_metrics()
        if afm is not None and name != ".notdef":
            return Standard14Fonts.get_glyph_width(self.get_name() or "", name)
        return 0.0

    def _program_width(self, code: int) -> float | None:
        """Look up an advance width in the embedded font program.

        Returns the scaled advance (1/1000 em) when found, ``None`` when
        the font is not embedded, the code does not resolve to a known
        glyph, or the program reports zero/unknown for the glyph.
        Subclasses (e.g. :class:`PDType1CFont`) override to substitute a
        different program kind.
        """
        program = self._get_type1_font()
        if program is None:
            return None
        name = self._code_to_glyph_name(code)
        if name is None or not program.has_glyph(name):
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        advance = program.get_width(name)
        if advance <= 0.0:
            return None
        return advance * 1000.0 / units_per_em

    # ---------- glyph paths ----------

    def get_glyph_path(self, code: int) -> list[tuple]:
        """Glyph outline for character ``code``, in *font units*.

        Returns an empty list when the font has no embedded program,
        when ``code`` does not resolve to a known glyph, or when the
        charstring cannot be drawn.
        """
        program = self._get_type1_font()
        if program is None:
            return []
        name = self._code_to_glyph_name(code)
        if name is None:
            return []
        return program.get_path(name)

    # ---------- code -> glyph name ----------

    def _code_to_glyph_name(self, code: int) -> str | None:
        """Resolve a 1-byte character code to a PostScript glyph name
        via the font's ``/Encoding`` (with ``/Differences`` overlay).

        Returns ``None`` for ``.notdef`` and unmapped codes — callers
        treat that as "no glyph available".
        """
        encoding = self.get_encoding_typed()
        if encoding is not None:
            name = encoding.get_name(code)
            if name and name != ".notdef":
                return name
        return None

    # ---------- upstream-parity accessors ----------

    # ``get_name`` is already defined on :class:`PDFont`; ``get_base_font``
    # is the upstream alias (PDFBox exposes both — ``getName`` and
    # ``getBaseFont``). We expose both names so callers porting from
    # ``org.apache.pdfbox.pdmodel.font.PDType1Font`` find the API they
    # expect.

    def get_base_font(self) -> str | None:
        """``/BaseFont`` — alias of :meth:`PDFont.get_name`. Mirrors
        upstream ``PDType1Font.getBaseFont``."""
        return self.get_name()

    def get_font_program(self) -> Type1Font | None:
        """Return the parsed embedded Type 1 program, or ``None`` when the
        font is not embedded or the program failed to parse. Mirrors
        upstream ``PDType1Font.getFontProgram`` — alias of the internal
        :meth:`_get_type1_font`."""
        return self._get_type1_font()

    def get_glyph_name_for_code(self, code: int) -> str | None:
        """Resolve a 1-byte character code to a PostScript glyph name via
        the font's ``/Encoding`` (with ``/Differences`` overlay).

        Returns ``None`` for ``.notdef`` and unmapped codes. Mirrors
        upstream ``PDType1Font.getGlyphNameForCode`` — alias of the
        internal :meth:`_code_to_glyph_name` so external callers don't
        have to reach for an underscore-prefixed name.
        """
        return self._code_to_glyph_name(code)

    def get_path(self, name: str) -> list[tuple]:
        """Return the glyph outline for the named glyph, in font units.

        Mirrors upstream ``PDType1Font.getPath(String name)`` — operates
        on a glyph *name* (not a character code; see
        :meth:`get_glyph_path` for the code-keyed variant).

        Edge-case handling parallels upstream:

        * ``.notdef`` for a non-embedded font returns ``[]`` — Acrobat
          does not draw ``.notdef`` for substituted Type 1 fonts (PDFBOX-2421).
        * For embedded programs (and when a substitute carries the glyph),
          the lookup goes through :meth:`get_name_in_font` so ligature
          fallbacks (``ff`` -> ``f_f``) and the ArialMT ``ellipsis``
          spelling are honoured.
        * Returns ``[]`` when no program is loaded or the resolved glyph
          name is absent from the program.
        """
        if name == ".notdef" and not self.is_embedded():
            return []
        program = self._get_type1_font()
        if program is None:
            return []
        resolved = self.get_name_in_font(name)
        return program.get_path(resolved)

    def get_path_for_code(self, code: int) -> list[tuple]:
        """Glyph outline for character ``code``, looked up via the font's
        ``/Encoding``. Mirrors upstream ``PDType1Font.getPath(int code)``.

        Returns ``[]`` when the font has no ``/Encoding`` or the code does
        not resolve to a known glyph.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return []
        return self.get_path(encoding.get_name(code))

    def get_normalized_path_for_code(self, code: int) -> list[tuple]:
        """Glyph outline for ``code``, falling back to ``.notdef`` when
        the primary lookup yields an empty path. Mirrors upstream
        ``PDType1Font.getNormalizedPath(int code)``.

        For non-embedded fonts the ``.notdef`` short-circuit in
        :meth:`get_path` still applies — falling back will itself yield
        ``[]``, matching upstream's "no path drawn" behaviour for
        substituted Type 1 fonts.
        """
        path = self.get_path_for_code(code)
        if path:
            return path
        return self.get_path(".notdef")

    def is_embedded(self) -> bool:
        """``True`` iff the font dictionary carries an embedded font
        program — ``/FontFile`` (Type 1) or ``/FontFile3`` (Type 1C /
        OpenType). Mirrors upstream ``PDFont.isEmbedded``."""
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        return (
            descriptor.get_font_file() is not None
            or descriptor.get_font_file3() is not None
        )

    def is_damaged(self) -> bool:
        """``True`` iff the embedded font program failed to parse.
        Mirrors upstream ``PDFont.isDamaged``. Returns ``False`` when
        the font is not embedded (nothing to parse, nothing to damage)
        or when parsing succeeded.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None or descriptor.get_font_file() is None:
            return False
        # Force the lazy parse and check whether it surfaced a real program.
        self._get_type1_font()
        return self._t1 is False

    def get_height(self, code: int) -> float:
        """Return the height of the glyph at ``code`` in font units.

        Computed from the glyph outline's bounding box (max-y minus
        min-y) when an embedded Type 1 program is available; otherwise
        ``0.0``. Mirrors upstream ``PDSimpleFont.getHeight`` for
        Type 1.
        """
        program = self._get_type1_font()
        if program is None:
            return 0.0
        name = self._code_to_glyph_name(code)
        if name is None:
            return 0.0
        path = program.get_path(name)
        if not path:
            return 0.0
        ys: list[float] = []
        for cmd in path:
            # Commands look like ("moveto", x, y), ("lineto", x, y),
            # ("curveto", x1, y1, x2, y2, x, y), ("closepath",). Skip the
            # closepath singleton; for everything else extract the y
            # coordinates (every odd-indexed numeric arg).
            if len(cmd) <= 1:
                continue
            for i in range(2, len(cmd), 2):
                ys.append(float(cmd[i]))
        if not ys:
            return 0.0
        return max(ys) - min(ys)

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Glyph displacement vector for ``code``, in *thousandths of an em*.

        For horizontal-writing-mode simple fonts (which all Type 1 fonts
        are) the displacement is ``(width / 1000, 0)`` — see PDF
        32000-1:2008 §9.2.4. ``width`` is the value
        :meth:`get_glyph_width` returns. Mirrors upstream
        ``PDSimpleFont.getDisplacement``.
        """
        return self.get_glyph_width(code) / 1000.0, 0.0

    def get_average_font_width(self) -> float:
        """Mean glyph advance for this font in 1/1000 em.

        Lookup order:

        1. Mean of positive entries in ``/Widths`` (matches
           :meth:`PDSimpleFont.get_average_font_width`).
        2. AFM mean for the matching Standard 14 font, when ``/BaseFont``
           resolves to one. Mirrors upstream ``PDType1Font`` falling back
           to its bundled ``FontMetrics`` when the dict has no widths.
        3. ``0.0``.
        """
        widths = self.get_widths()
        non_zero = [w for w in widths if w > 0.0]
        if non_zero:
            return sum(non_zero) / len(non_zero)
        afm = self.get_standard_14_font_metrics()
        if afm is not None:
            return afm.get_average_width()
        return 0.0

    def get_standard_14_font_metrics(self) -> AfmMetrics | None:
        """Return the bundled Adobe AFM metrics for this font when
        ``/BaseFont`` resolves to one of the 14 Standard fonts (or a
        known alias); ``None`` otherwise. Mirrors upstream
        ``PDType1Font.getStandard14AFM``.
        """
        base_font = self.get_name()
        if base_font is None or not Standard14Fonts.containsName(base_font):
            return None
        return Standard14Fonts.get_afm(base_font)

    # ---------- code / name resolution ----------

    def code_to_name(self, code: int) -> str:
        """Resolve a 1-byte character code to the glyph name *as it
        appears in the underlying font*. Mirrors upstream
        ``PDType1Font.codeToName``.

        Goes through ``/Encoding`` first (so ``/Differences`` overlays
        win, exactly like the encode path) and then through
        :meth:`get_name_in_font` to handle ligature spelling mismatches
        and AGL fallbacks. Returns ``".notdef"`` when the font has no
        ``/Encoding`` entry (matches upstream's null-encoding fallback).
        """
        encoding = self.get_encoding_typed()
        name = encoding.get_name(code) if encoding is not None else ".notdef"
        return self.get_name_in_font(name)

    def get_name_in_font(self, name: str) -> str:
        """Map a PostScript glyph name to the spelling actually present
        in the embedded program. Mirrors upstream
        ``PDType1Font.getNameInFont``.

        Resolution order:

        1. ``name`` itself when the font is embedded (upstream trusts
           the embedded program to round-trip its own names) or when the
           program already contains a glyph by that exact name.
        2. The :data:`ALT_NAMES` ligature spelling (``ff`` -> ``f_f``
           etc.) when the program lacks ``name`` but carries the
           component spelling.
        3. ``".notdef"`` when a program is loaded and lacks every
           candidate.

        When no embedded program is available at all (no /FontFile and
        we have nothing to substitute against), ``name`` is returned
        unchanged — we have no negative evidence to remap on. This
        deviates slightly from upstream, which always has a generic
        substitute font in hand and can therefore reach a real
        ``.notdef`` decision; see CHANGES.md.
        """
        program = self._get_type1_font()
        if self.is_embedded():
            return name
        if program is None:
            # No embedded program and no substitute loaded — pass
            # through unchanged.
            return name
        if program.has_glyph(name):
            return name
        alt = _ALT_NAMES.get(name)
        if alt is not None and name != ".notdef" and program.has_glyph(alt):
            return alt
        return ".notdef"

    # ---------- glyph existence probes ----------

    def has_glyph(self, name: str) -> bool:
        """``True`` iff the underlying font program carries a glyph for
        ``name`` (after ``ALT_NAMES`` remapping). Mirrors upstream
        ``PDType1Font.hasGlyph(String)``.
        """
        resolved = self.get_name_in_font(name)
        if resolved == ".notdef":
            return False
        program = self._get_type1_font()
        if program is None:
            # is_embedded() short-circuits get_name_in_font to return
            # ``name`` unchanged; without a parsed program we can't
            # confirm presence either way, so report False.
            return False
        return program.has_glyph(resolved)

    def has_glyph_for_code(self, code: int) -> bool:
        """``True`` iff ``/Encoding`` maps ``code`` to anything other
        than ``.notdef``. Mirrors upstream
        ``PDType1Font.hasGlyph(int)`` — the upstream overload is purely
        encoding-based; it does not consult the font program.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return False
        return encoding.get_name(code) != ".notdef"

    # ---------- byte-stream reader ----------

    def read_code(self, stream: BinaryIO | bytes) -> int:
        """Read one byte from ``stream`` and return its integer code.

        Mirrors upstream ``PDType1Font.readCode`` — Type 1 fonts always
        use single-byte character codes regardless of encoding, so the
        reader is just a one-byte pull. Accepts either a binary file
        object (anything with a ``.read(int)`` method) or a raw
        ``bytes``/``bytearray`` for caller convenience. Returns ``-1``
        at end-of-stream to mirror Java's ``InputStream.read`` contract.
        """
        if isinstance(stream, (bytes, bytearray, memoryview)):
            stream = io.BytesIO(bytes(stream))
        chunk = stream.read(1)
        if not chunk:
            return -1
        return chunk[0]

    # ---------- embedded program alias ----------

    def get_type1_font(self) -> Type1Font | None:
        """Return the embedded :class:`Type1Font` program, or ``None``
        when the font is not embedded / failed to parse. Mirrors
        upstream ``PDType1Font.getType1Font``. Distinct from
        :meth:`get_font_program` (which mirrors the upstream
        ``getFontProgram`` accessor on ``PDVectorFont``); both currently
        delegate to the same lazy parser, but we keep separate names so
        callers can match the upstream surface they were trained on.
        """
        return self._get_type1_font()


__all__ = ["PDType1Font"]
