from __future__ import annotations

import logging
from typing import TYPE_CHECKING, BinaryIO

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.type1.type1_font import Type1Font

from .afm_loader import AfmMetrics
from .pd_simple_font import PDSimpleFont
from .standard14_fonts import Standard14Fonts

# Cached COSName for the ``/BaseFont`` dict key — mirrors upstream
# ``COSName.BASE_FONT`` and avoids re-allocating the name on every
# :meth:`PDType1Font.get_name` call.
_BASE_FONT_KEY = COSName.get_pdf_name("BaseFont")

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    from .encoding.encoding import Encoding

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
        # Caches mirroring upstream's ``fontBBox`` and ``fontMatrix``
        # fields — populated on first access by :meth:`get_bounding_box`
        # / :meth:`get_font_matrix`.
        self._bbox_cache: PDRectangle | None = None
        self._font_matrix_cache: list[float] | None = None
        # Mirrors upstream ``codeToBytesMap`` — caches per-codepoint
        # encoded bytes so repeated :meth:`encode` calls for the same
        # unicode value don't re-walk the encoding's name->code table.
        self._code_to_bytes: dict[int, bytes] = {}

    @classmethod
    def load(
        cls,
        document: PDDocument,
        pfb_stream: BinaryIO | bytes,
        encoding: object | None = None,
    ) -> PDType1Font:
        """Build a :class:`PDType1Font` that embeds the Type 1 font program
        from ``pfb_stream``.

        Mirrors upstream PDFBox's
        ``PDType1Font(PDDocument, InputStream, Encoding)`` constructor —
        wires a new font dictionary through :class:`PDType1FontEmbedder`,
        then wraps the dict in a fresh :class:`PDType1Font`. ``encoding``
        may be ``None`` to take the font program's built-in encoding.
        """
        # Local import to avoid a circular dependency
        # (pd_type1_font_embedder imports from this module).
        from pypdfbox.pdmodel.font.pd_type1_font_embedder import (
            PDType1FontEmbedder,
        )

        font_dict = COSDictionary()
        PDType1FontEmbedder(document, font_dict, pfb_stream, encoding)
        return cls(font_dict)

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
                entry = widths[idx]
                return float(entry) if entry is not None else 0.0

        # 2. Embedded font program.
        program_width = self._program_width(code)
        if program_width is not None:
            return program_width

        # 3. Standard 14 fallback via the bundled AFM.
        base_font = self.get_name()
        if base_font is not None and Standard14Fonts.contains_name(base_font):
            # Resolve code -> glyph name. Family default PostScript
            # encoding (PDF 32000-1 §9.6.2.4) is the fall-through when
            # /Encoding is absent OR is a base-less DictionaryEncoding
            # whose /Differences didn't cover ``code`` (wave 1391 —
            # without the fall-through, AcroForm widget appearance text
            # on unembedded Helvetica with /Differences painted
            # nothing).
            from .encoding.dictionary_encoding import (  # noqa: PLC0415
                DictionaryEncoding,
            )
            from .encoding.standard_encoding import StandardEncoding  # noqa: PLC0415
            from .encoding.symbol_encoding import SymbolEncoding  # noqa: PLC0415
            from .encoding.zapf_dingbats_encoding import (  # noqa: PLC0415
                ZapfDingbatsEncoding,
            )

            canonical = Standard14Fonts.get_mapped_font_name(base_font)
            if canonical == "Symbol":
                default_encoding = SymbolEncoding.INSTANCE
            elif canonical == "ZapfDingbats":
                default_encoding = ZapfDingbatsEncoding.INSTANCE
            else:
                default_encoding = StandardEncoding.INSTANCE
            typed_encoding = self.get_encoding_typed()
            if typed_encoding is None:
                glyph_name = default_encoding.get_name(code)
            else:
                glyph_name = typed_encoding.get_name(code)
                if glyph_name == ".notdef" and isinstance(
                    typed_encoding, DictionaryEncoding
                ) and not typed_encoding.has_base_encoding():
                    glyph_name = default_encoding.get_name(code)
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

    # ---------- text -> bytes ----------

    def encode(self, text: str) -> bytes:
        """Encode a Python string to the font's raw byte representation.

        Mirrors upstream ``PDType1Font.encode``: a Type-1-specific
        override that adds (a) a per-codepoint cache identical to
        upstream's ``codeToBytesMap`` field, and (b) ``ALT_NAMES``
        ligature spelling fallback so a writer asking for ``ff`` still
        round-trips to a glyph the embedded program can render. Calls
        for which the cache misses delegate to
        :meth:`PDSimpleFont.encode`, which honours pypdfbox's documented
        divergence from upstream's throw-on-unmapped behaviour
        (CHANGES.md: simple-font writers fall back to ``b'?'`` rather
        than raising ``IllegalArgumentException`` — the round-trip
        contract that pypdfbox guarantees).
        """
        if not text:
            return b""
        out = bytearray()
        for ch in text:
            unicode_value = ord(ch)
            cached = self._code_to_bytes.get(unicode_value)
            if cached is not None:
                out.extend(cached)
                continue
            piece = super().encode(ch)
            # Cache the very first byte produced — Type-1 single-byte
            # encodings always yield exactly one byte per codepoint per
            # PDF 32000-1 §9.6.6.4. Mirrors upstream's ``new byte[] { code }``
            # cache shape.
            self._code_to_bytes[unicode_value] = bytes(piece)
            out.extend(piece)
        return bytes(out)

    # ---------- glyph paths ----------

    def get_glyph_path(self, code: int) -> list[tuple]:
        """Glyph outline for character ``code``, in *font units*.

        Resolution order:

        1. Embedded ``/FontFile`` program (the usual Type 1 path) — returns
           the program's outline for the encoding-resolved glyph name.
        2. **Bundled substitute** for non-embedded Standard 14 fonts —
           when ``/BaseFont`` resolves to one of the 14 canonical
           PostScript names (Helvetica, Times-Roman, Courier, … families,
           plus Symbol / ZapfDingbats) and the dict ships no font program,
           fall through to the bundled substitute TTF outline via
           :meth:`Standard14Fonts.get_glyph_path` — Liberation for the
           Latin branches and DejaVu Sans for Symbol / ZapfDingbats.

        Returns an empty list when ``code`` does not resolve to a known
        glyph, or when no outline source is available.
        """
        program = self._get_type1_font()
        if program is not None:
            name = self._code_to_glyph_name(code)
            if name is None:
                return []
            return program.get_path(name)
        # No embedded program — fall back to Liberation when the font is
        # one of the Standard 14.
        base_font = self.get_name()
        if base_font is None or not Standard14Fonts.contains_name(base_font):
            return []
        # Resolve code -> glyph name. Mirror the family default
        # PostScript encoding (PDF 32000-1 §9.6.2.4) when (a) the font
        # ships no /Encoding at all OR (b) /Encoding is a base-less
        # :class:`DictionaryEncoding` (the upstream Type 3 mode that
        # PDSimpleFont.get_encoding_typed historically built for every
        # dictionary encoding — wave 1391) whose /Differences overlay
        # didn't cover ``code``. Without (b) the AcroForm widget
        # appearance text on an unembedded Helvetica with a
        # /Differences encoding painted nothing.
        from .encoding.dictionary_encoding import (  # noqa: PLC0415
            DictionaryEncoding,
        )
        from .encoding.standard_encoding import (  # noqa: PLC0415
            StandardEncoding,
        )
        from .encoding.symbol_encoding import SymbolEncoding  # noqa: PLC0415
        from .encoding.zapf_dingbats_encoding import (  # noqa: PLC0415
            ZapfDingbatsEncoding,
        )

        canonical = Standard14Fonts.get_mapped_font_name(base_font)
        if canonical == "Symbol":
            default_encoding = SymbolEncoding.INSTANCE
        elif canonical == "ZapfDingbats":
            default_encoding = ZapfDingbatsEncoding.INSTANCE
        else:
            default_encoding = StandardEncoding.INSTANCE
        encoding = self.get_encoding_typed()
        if encoding is None:
            glyph_name = default_encoding.get_name(code)
        else:
            glyph_name = encoding.get_name(code)
            if glyph_name == ".notdef" and isinstance(
                encoding, DictionaryEncoding
            ) and not encoding.has_base_encoding():
                glyph_name = default_encoding.get_name(code)
        if glyph_name == ".notdef":
            return []
        return Standard14Fonts.get_glyph_path(base_font, glyph_name)

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
        return self._dict.get_name(_BASE_FONT_KEY)

    def get_name(self) -> str | None:
        """The font's lookup name (``/BaseFont``). Mirrors upstream
        ``PDType1Font.getName`` which is overridden to delegate to
        ``getBaseFont()`` — the two are effectively the same for Type 1
        fonts because the dictionary's ``/Name`` slot is purely a
        deprecated PDF 1.0 field while ``/BaseFont`` is the canonical
        PostScript identity. We read ``/BaseFont`` directly (rather than
        chaining through :meth:`get_base_font`) so subclasses that
        override one method but not the other don't end up in mutual
        recursion.
        """
        return self._dict.get_name(_BASE_FONT_KEY)

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

        Mirrors upstream ``PDType1Font.getHeight``:

        1. When the font is one of the Standard 14 (an AFM is bundled),
           consult the AFM's ``getCharacterHeight`` for the glyph name
           resolved through the typed encoding.
        2. Otherwise fall back to the glyph outline's bounding box height
           (max-y minus min-y) read from the embedded Type 1 program.
        3. ``0.0`` when neither source is resolvable.
        """
        afm = self.get_standard_14_font_metrics()
        if afm is not None:
            encoding = self.get_encoding_typed()
            if encoding is not None:
                glyph_name = encoding.get_name(code)
                # Upstream queries the AFM with whatever name the encoding
                # returns — including ``.notdef``. The AFM transparently
                # returns 0 for unknown names.
                return afm.get_character_height(glyph_name)
            return 0.0
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
        non_zero = [w for w in widths if w is not None and w > 0.0]
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
        if base_font is None or not Standard14Fonts.contains_name(base_font):
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

    def read_code(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> tuple[int, int]:
        """Read one character code from ``data`` starting at ``offset``.

        Mirrors upstream ``PDType1Font.readCode`` — Type 1 fonts always
        use single-byte character codes regardless of encoding, so the
        reader is just a one-byte pull. Returns ``(code, bytes_consumed)``
        to match the uniform pypdfbox renderer signature shared by
        composite (Type0) and simple fonts. At or past end-of-buffer
        returns ``(0, 0)`` so callers terminate the decode loop.
        """
        if offset < 0 or offset >= len(data):
            return (0, 0)
        return (data[offset] & 0xFF, 1)

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

    def get_font_box_font(self) -> Type1Font | None:
        """Return the parsed Type 1 program for rendering. Mirrors
        upstream ``PDType1Font.getFontBoxFont`` — Java's port returns the
        ``FontBoxFont`` interface (an embedded Type 1 or a substitute);
        in the Python port both code paths funnel through
        :class:`Type1Font` so this is an alias of :meth:`get_type1_font`.
        """
        return self._get_type1_font()

    # ---------- bounding box (PDFontLike override) ----------

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the font's bounding box.

        Mirrors upstream ``PDType1Font.getBoundingBox``: when the font
        descriptor carries a non-zero ``/FontBBox`` use it directly;
        otherwise fall through to :meth:`generate_bounding_box` which
        consults the embedded program. Result is cached for repeated
        access (matches upstream's ``fontBBox`` field).
        """
        if self._bbox_cache is not None:
            return self._bbox_cache
        self._bbox_cache = self.generate_bounding_box()
        return self._bbox_cache

    def generate_bounding_box(self) -> PDRectangle | None:
        """Compute the font bounding box from the descriptor or the
        embedded program. Mirrors upstream
        ``PDType1Font.generateBoundingBox``: prefer the
        ``/FontDescriptor /FontBBox`` when non-zero, else read the
        program's ``FontBBox``. Returns ``None`` when no source carries
        a usable bbox.
        """
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        descriptor = self.get_font_descriptor()
        if descriptor is not None:
            bbox = descriptor.get_font_bounding_box()
            if self.is_non_zero_bounding_box(bbox):
                return bbox
        program = self._get_type1_font()
        if program is None:
            return None
        program_bbox = program.get_font_bbox()
        if program_bbox is None:
            return None
        x0, y0, x1, y1 = program_bbox
        return PDRectangle(float(x0), float(y0), float(x1), float(y1))

    # ---------- font matrix (PDFontLike override) ----------

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element font matrix from the embedded program,
        falling back to the simple-font default ``[0.001, 0, 0, 0.001, 0, 0]``
        when no program is loaded or its matrix is malformed.

        Mirrors upstream ``PDType1Font.getFontMatrix``: PDF 32000-1
        §9.2.4 specifies the 1000-upem default for Type 1, but some
        fonts (e.g. PDFBOX-2298) carry a custom matrix in the program
        which wins over the default.
        """
        if self._font_matrix_cache is not None:
            return list(self._font_matrix_cache)
        program = self._get_type1_font()
        if program is not None:
            matrix = program.get_font_matrix()
            if matrix is not None and len(matrix) == 6:
                self._font_matrix_cache = [float(v) for v in matrix]
                return list(self._font_matrix_cache)
        # Fall back to the simple-font default from PDFont.
        self._font_matrix_cache = list(self.DEFAULT_FONT_MATRIX)
        return list(self._font_matrix_cache)

    # ---------- normalised path alias (code overload) ----------

    def get_normalized_path(self, code: int) -> list[tuple]:
        """Glyph outline for ``code``, falling back to ``.notdef`` when
        the primary lookup yields an empty path. Mirrors upstream
        ``PDType1Font.getNormalizedPath(int)`` — alias of
        :meth:`get_normalized_path_for_code` so callers porting from
        ``getNormalizedPath`` find the canonical name in addition to
        the underscore-suffixed variant we already expose.
        """
        return self.get_normalized_path_for_code(code)

    # ---------- embedded program length-field repair ----------

    def repair_length1(self, data: bytes | bytearray, length1: int) -> int:
        """Repair an invalid ``/Length1`` on a Type 1 ``/FontFile`` stream.

        Some Type 1 fonts carry a truncated or otherwise wrong
        ``/Length1`` such that the binary segment marker (``exec``) is
        misplaced — see PDFBOX-2350, PDFBOX-3677. This scans backwards
        from the declared boundary for the trailing ``exec`` token,
        skipping any CR/LF/space/tab whitespace that follows it, and
        returns the corrected offset. Returns ``length1`` unchanged when
        the scan does not find a credible boundary.
        """
        buf = bytes(data)
        offset = max(0, length1 - 4)
        if offset <= 0 or offset > len(buf) - 4:
            offset = max(0, len(buf) - 4)
        offset = self.find_binary_offset_after_exec(buf, offset)
        if offset == 0 and length1 > 0:
            # Brute-force second pass — start from end of the buffer.
            offset = self.find_binary_offset_after_exec(buf, len(buf) - 4)
        if length1 - offset != 0 and offset > 0:
            _LOG.warning(
                "Ignored invalid Length1 %d for Type 1 font %s",
                length1,
                self.get_name(),
            )
            return offset
        return length1

    def repair_length2(
        self, data: bytes | bytearray, length1: int, length2: int
    ) -> int:
        """Repair an invalid ``/Length2`` on a Type 1 ``/FontFile`` stream.

        Mirrors upstream ``PDType1Font.repairLength2`` (PDFBOX-3475): a
        negative ``/Length2`` would crash ``Arrays.copyOfRange``, a huge
        value bloats memory with padding. When ``length2`` is out of
        range, return ``len(data) - length1`` so the second segment runs
        to end-of-buffer.
        """
        if length2 < 0 or length2 > len(data) - length1:
            _LOG.warning(
                "Ignored invalid Length2 %d for Type 1 font %s",
                length2,
                self.get_name(),
            )
            return len(data) - length1
        return length2

    @staticmethod
    def find_binary_offset_after_exec(
        data: bytes | bytearray, start_offset: int
    ) -> int:
        """Scan backwards from ``start_offset`` for ``b"exec"`` and
        return the offset of the first non-whitespace byte after it.

        Mirrors upstream ``PDType1Font.findBinaryOffsetAfterExec`` — the
        helper that powers :meth:`repair_length1`. Returns ``0`` when no
        ``exec`` token is found between offset 0 and ``start_offset``.
        """
        buf = bytes(data)
        offset = start_offset
        while offset > 0:
            if (
                offset + 3 < len(buf)
                and buf[offset] == 0x65  # 'e'
                and buf[offset + 1] == 0x78  # 'x'
                and buf[offset + 2] == 0x65  # 'e'
                and buf[offset + 3] == 0x63  # 'c'
            ):
                offset += 4
                # Skip trailing CR / LF / space / tab.
                while offset < len(buf) and buf[offset] in (
                    0x0D,
                    0x0A,
                    0x20,
                    0x09,
                ):
                    offset += 1
                return offset
            offset -= 1
        return 0

    # ---------- encoding synthesis from the font program ----------

    def read_encoding_from_font(self) -> Encoding | None:
        """Synthesise an :class:`Encoding` from the embedded program or
        the bundled Standard 14 AFM.

        Mirrors upstream ``PDType1Font.readEncodingFromFont``:

        * Non-embedded Standard 14 fonts read the encoding from their
          AFM (built-in Type 1 encoding) — represented here as the
          font's PostScript default encoding (Standard / Symbol / Zapf).
        * Embedded fonts surface their program's built-in encoding when
          available.
        * Otherwise we fall back to :class:`StandardEncoding`.

        Returns ``None`` only when nothing is resolvable.
        """
        from .encoding.standard_encoding import StandardEncoding
        from .encoding.symbol_encoding import SymbolEncoding
        from .encoding.win_ansi_encoding import WinAnsiEncoding
        from .encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding

        # Non-embedded Standard 14: pick the family-default encoding.
        # The two FontSpecific fonts (Symbol / ZapfDingbats) use their own
        # built-in encodings; the twelve Latin text fonts default to
        # WinAnsiEncoding. This mirrors upstream PDFBox, whose standard-14
        # PDType1Font constructor assigns ``WinAnsiEncoding.INSTANCE`` for the
        # non-symbolic fonts even though the bundled Adobe AFM declares
        # ``EncodingScheme AdobeStandardEncoding`` — Acrobat treats the
        # unembedded core fonts as WinAnsi by default, so code 39 maps to
        # ``quotesingle`` (191) rather than ``quoteright`` (222), code 96 to
        # ``grave`` (333), code 128 to ``Euro`` (556), code 160 to
        # ``nbspace`` -> ``space`` (278), etc. Using StandardEncoding here
        # produced the wrong per-glyph AFM advance for every code that the
        # two encodings disagree on.
        afm = self.get_standard_14_font_metrics()
        if not self.is_embedded() and afm is not None:
            base = self.get_name() or ""
            canonical = Standard14Fonts.get_mapped_font_name(base)
            if canonical == "Symbol":
                return SymbolEncoding.INSTANCE
            if canonical == "ZapfDingbats":
                return ZapfDingbatsEncoding.INSTANCE
            return WinAnsiEncoding.INSTANCE

        # Embedded program: surface its built-in encoding when present.
        program = self._get_type1_font()
        if program is not None:
            encoding_map = program.get_encoding()
            if encoding_map:
                # Build a lightweight Encoding wrapper.
                from .encoding.built_in_encoding import BuiltInEncoding

                return BuiltInEncoding(dict(encoding_map))
        return StandardEncoding.INSTANCE

    # ---------- subsetting ----------
    #
    # Upstream ``PDSimpleFont.subset()`` raises ``UnsupportedOperationException``
    # ("only TTF subsetting via PDType0Font is currently supported"). PDFBox
    # has never implemented Type 1 / CFF subsetting at the PDDocument level
    # and fontTools' bundled t1Lib does not expose a subset entry point
    # either (its ``T1Font`` class has only parse/write/getGlyphSet, no
    # ``subset``); fontTools' ``Subsetter`` operates on OpenType /CFF
    # tables, not raw Type 1 streams. The inherited :meth:`subset` /
    # :meth:`add_to_subset` therefore continue to raise — overridden here
    # only to attach a Type 1-specific docstring.

    def will_be_subset(self) -> bool:
        """``False`` — Type 1 subsetting is not currently implemented."""
        return False

    def add_to_subset(self, code_point: int) -> None:
        """Type 1 subsetting is not currently implemented.

        Mirrors upstream ``PDSimpleFont.addToSubset`` which raises
        ``UnsupportedOperationException``; only TTF subsetting (via
        :class:`PDType0Font` + :class:`PDCIDFontType2Embedder`) is
        supported by PDFBox today. fontTools does not provide a Type 1
        subsetter either, so we keep parity with upstream rather than
        invent a divergent implementation.
        """
        raise NotImplementedError(
            "Type 1 font subsetting is not supported "
            "(only TTF subsetting via PDType0Font is currently implemented; "
            "fontTools t1Lib has no public subset entry point)"
        )

    def subset(self) -> None:
        """Type 1 subsetting is not currently implemented.

        See :meth:`add_to_subset` for the rationale.
        """
        raise NotImplementedError(
            "Type 1 font subsetting is not supported "
            "(only TTF subsetting via PDType0Font is currently implemented; "
            "fontTools t1Lib has no public subset entry point)"
        )


__all__ = ["PDType1Font"]
