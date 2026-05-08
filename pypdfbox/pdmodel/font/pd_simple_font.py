from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList

from .encoding import (
    DictionaryEncoding,
    Encoding,
    MacRomanEncoding,
    StandardEncoding,
    WinAnsiEncoding,
    ZapfDingbatsEncoding,
)
from .pd_font import PDFont
from .pd_font_descriptor import (
    FLAG_ALL_CAP,
    FLAG_FIXED_PITCH,
    FLAG_FORCE_BOLD,
    FLAG_ITALIC,
    FLAG_SCRIPT,
    FLAG_SERIF,
    FLAG_SMALL_CAP,
    FLAG_SYMBOLIC,
)
from .standard14_fonts import Standard14Fonts

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")

# Per-encoding (unicode -> code) reverse cache. Keyed by the typed Encoding
# instance identity so the same singleton is shared across PDSimpleFont
# instances; DictionaryEncoding instances naturally get their own entry.
_REVERSE_CACHE: dict[int, dict[str, int]] = {}


def _glyph_list_for(encoding: Encoding) -> GlyphList:
    """Pick the glyph-list flavour matching the encoding (Zapf vs AGL)."""
    if isinstance(encoding, ZapfDingbatsEncoding):
        return GlyphList.ZAPF_DINGBATS
    return GlyphList.DEFAULT


def _build_unicode_to_code(encoding: Encoding) -> dict[str, int]:
    glyph_list = _glyph_list_for(encoding)
    out: dict[str, int] = {}
    # Iterate code -> name (rather than name -> code) so that the *first*
    # code wins when several names map to the same unicode point — this
    # matches the lowest-code-first behaviour expected by writers.
    for code, name in sorted(encoding.get_code_to_name_map().items()):
        unicode = glyph_list.to_unicode(name)
        if unicode is None:
            continue
        out.setdefault(unicode, code)
    return out


def _unicode_to_code_map(encoding: Encoding) -> dict[str, int]:
    key = id(encoding)
    cached = _REVERSE_CACHE.get(key)
    if cached is None:
        cached = _build_unicode_to_code(encoding)
        _REVERSE_CACHE[key] = cached
    return cached


class PDSimpleFont(PDFont):
    """Abstract intermediate base for Type1 / TrueType / Type3 fonts.

    Mirrors PDFBox ``PDSimpleFont``. Adds ``/FirstChar``, ``/LastChar``,
    ``/Widths``, and ``/Encoding`` accessors plus the ``encode`` / ``decode``
    helpers that round-trip Python ``str`` <-> raw byte strings via the
    typed ``Encoding`` and the Adobe glyph list.
    """

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        self._encoding_typed: Encoding | None = None
        self._encoding_resolved: bool = False

    # ---------- char-range / widths ----------

    def get_first_char(self) -> int:
        return self._dict.get_int(_FIRST_CHAR, -1)

    def get_last_char(self) -> int:
        return self._dict.get_int(_LAST_CHAR, -1)

    def get_widths(self) -> list[float]:
        arr = self._dict.get_dictionary_object(_WIDTHS)
        if not isinstance(arr, COSArray):
            return []
        widths: list[float] = []
        for item in arr:
            if isinstance(item, (COSInteger, COSFloat)):
                widths.append(float(item.value))
        return widths

    def set_first_char(self, value: int | None) -> None:
        """Set or clear ``/FirstChar`` on the font dictionary."""
        if value is None:
            self._dict.remove_item(_FIRST_CHAR)
            return
        self._dict.set_int(_FIRST_CHAR, int(value))

    def set_last_char(self, value: int | None) -> None:
        """Set or clear ``/LastChar`` on the font dictionary."""
        if value is None:
            self._dict.remove_item(_LAST_CHAR)
            return
        self._dict.set_int(_LAST_CHAR, int(value))

    def set_widths(self, values: list[float] | None) -> None:
        """Replace or clear the ``/Widths`` array."""
        if values is None:
            self._dict.remove_item(_WIDTHS)
            return
        self._dict.set_item(_WIDTHS, COSArray([COSFloat(float(v)) for v in values]))

    # ---------- /FontDescriptor /Flags accessors ----------
    #
    # Thin wrappers around ``get_font_descriptor()`` + the flag-bit constants
    # in :mod:`pd_font_descriptor`. Mirrors the convenience accessors on
    # upstream ``PDFontLike`` / ``PDFontDescriptor``. Each returns ``False``
    # when the font has no ``/FontDescriptor`` (i.e. defaults are absent =
    # nonsymbolic / non-italic / non-bold per PDF 32000-1 §9.8.2).
    #
    # ``is_symbolic`` is the only bit upstream documents as defaulting to
    # *True* when ambiguous (some viewers assume nonsymbolic when /Flags is
    # missing); we follow the user contract here and return False when no
    # descriptor is present.
    #
    # ``is_bold`` has no dedicated /Flags bit in PDF 32000-1 — boldness is
    # signalled via the font name (e.g. ``-Bold``) or ``/FontWeight >= 700``
    # on the descriptor. ``is_force_bold`` reads the dedicated bit 19
    # (1<<18 = 262144) which forces bold rendering at small sizes.

    def _flag(self, mask: int) -> bool:
        fd = self.get_font_descriptor()
        if fd is None:
            return False
        return bool(fd.get_flags() & mask)

    def is_symbolic(self) -> bool:
        return self._flag(FLAG_SYMBOLIC)

    def is_italic(self) -> bool:
        return self._flag(FLAG_ITALIC)

    def is_bold(self) -> bool:
        # No dedicated /Flags bit — derive from /FontWeight (>=700 = bold)
        # per PDF 32000-1 §9.8.1 Table 122.
        fd = self.get_font_descriptor()
        if fd is None:
            return False
        return fd.get_font_weight() >= 700

    def is_fixed_pitch(self) -> bool:
        return self._flag(FLAG_FIXED_PITCH)

    def is_serif(self) -> bool:
        return self._flag(FLAG_SERIF)

    def is_script(self) -> bool:
        return self._flag(FLAG_SCRIPT)

    def is_force_bold(self) -> bool:
        return self._flag(FLAG_FORCE_BOLD)

    def is_all_cap(self) -> bool:
        return self._flag(FLAG_ALL_CAP)

    def is_small_cap(self) -> bool:
        return self._flag(FLAG_SMALL_CAP)

    # ---------- Standard 14 ----------

    def is_standard_14(self) -> bool:
        """``True`` iff this font is one of the 14 PDF Standard fonts.

        Mirrors PDFBox ``PDSimpleFont.isStandard14``: in addition to the
        base ``PDFont`` check (not embedded + ``/BaseFont`` matches a
        canonical / alias name), an ``/Encoding`` carrying a non-trivial
        ``/Differences`` overlay disqualifies the font — see PDFBOX-2372,
        PDFBOX-1900, and the PDFBOX-2192 file. ``/Differences`` entries
        that simply restate the base encoding's mapping are ignored.
        """
        if not super().is_standard14():
            return False
        encoding = self.get_encoding_typed()
        if isinstance(encoding, DictionaryEncoding):
            differences = encoding.get_differences()
            if differences:
                base = encoding.get_base_encoding()
                if base is None:
                    return False
                for code, name in differences.items():
                    if name != base.get_name(code):
                        return False
        return True

    # Upstream's canonical name is ``isStandard14`` (no underscore between
    # 14 and the rest); expose both spellings so callers porting from
    # PDFBox find what they expect. Snake-cased per house style.
    def is_standard14(self) -> bool:
        return self.is_standard_14()

    def get_average_font_width(self) -> float:
        """Return the average glyph advance for this font in *thousandths
        of an em* (the same scale upstream's ``getAverageFontWidth``
        returns). Computed as the arithmetic mean of the entries in
        ``/Widths``; zero-width entries (typically ``.notdef`` slots) are
        skipped because they would otherwise drag the mean toward zero
        for sparsely-mapped fonts. Returns ``0.0`` when the font has no
        ``/Widths`` array or every entry is zero — callers should use
        their own fallback in that case.
        """
        widths = self.get_widths()
        non_zero = [w for w in widths if w > 0.0]
        if not non_zero:
            return 0.0
        return sum(non_zero) / len(non_zero)

    # ---------- encoding ----------

    def get_encoding(self) -> COSBase | None:
        """Raw ``/Encoding`` entry — a ``COSName`` for predefined encodings,
        a ``COSDictionary`` for ``/Differences``-style overrides, or ``None``."""
        return self._dict.get_dictionary_object(_ENCODING)

    def get_encoding_typed(self) -> Encoding | None:
        """Resolve ``/Encoding`` to a typed :class:`Encoding`.

        Returns ``None`` when the font has no ``/Encoding`` entry. The
        resolved instance is cached on first access.
        """
        if self._encoding_resolved:
            return self._encoding_typed
        raw = self.get_encoding()
        if isinstance(raw, COSName):
            self._encoding_typed = Encoding.get_instance(raw)
        elif isinstance(raw, COSDictionary):
            self._encoding_typed = DictionaryEncoding(font_encoding=raw)
        else:
            self._encoding_typed = None
        self._encoding_resolved = True
        return self._encoding_typed

    def get_glyph_list(self) -> GlyphList:
        """Return the glyph-list flavour the font should use.

        Mirrors upstream ``PDSimpleFont.getGlyphList`` together with
        ``assignGlyphList(FontName)``: ``ZapfDingbats`` (canonical name or
        alias) and a ``ZapfDingbatsEncoding`` both select the Zapf list,
        anything else uses the Adobe Glyph List (AGL). Returning the
        public AGL singleton when no encoding is resolved keeps callers
        from having to test for ``None``.
        """
        # Standard 14 ZapfDingbats wins regardless of /Encoding (matches
        # upstream's name-based ``assignGlyphList``).
        mapped = Standard14Fonts.get_mapped_font_name(self.get_name())
        if mapped == Standard14Fonts.ZAPF_DINGBATS:
            return GlyphList.ZAPF_DINGBATS
        encoding = self.get_encoding_typed()
        if isinstance(encoding, ZapfDingbatsEncoding):
            return GlyphList.ZAPF_DINGBATS
        return GlyphList.DEFAULT

    # ---------- symbolic detection ----------

    def get_symbolic_flag(self) -> bool | None:
        """Return the ``/Symbolic`` flag from ``/FontDescriptor`` or
        ``None`` when the font has no descriptor.

        Mirrors upstream ``PDSimpleFont.getSymbolicFlag``: the Java
        method returns ``Boolean`` (a tri-state) so callers can
        distinguish "definitely nonsymbolic" from "no descriptor at all"
        — the latter is a hint to inspect the encoding instead. The
        upstream comment notes the flag itself defaults to ``false`` when
        absent so a ``False`` result is not always trustworthy; that is a
        property of the descriptor, not this method.
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return None
        return fd.is_symbolic()

    def is_font_symbolic(self) -> bool | None:
        """Tri-state symbolic detection.

        Mirrors upstream ``PDSimpleFont.isFontSymbolic``: returns the
        descriptor's ``/Symbolic`` flag when present; otherwise inspects
        the font name (Standard 14 ``Symbol`` / ``ZapfDingbats`` are
        always symbolic) and the encoding (the three Latin encodings —
        WinAnsi, MacRoman, Standard — guarantee nonsymbolic; a
        ``DictionaryEncoding`` whose ``/Differences`` only references
        names from the Latin character sets is also nonsymbolic).
        Returns ``None`` when no determination can be made — the caller
        should default conservatively (upstream's ``isSymbolic``
        defaults to ``True``).
        """
        flag = self.get_symbolic_flag()
        if flag is not None:
            return flag
        if self.is_standard14():
            mapped = Standard14Fonts.get_mapped_font_name(self.get_name())
            return mapped in (Standard14Fonts.SYMBOL, Standard14Fonts.ZAPF_DINGBATS)
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        if isinstance(encoding, (WinAnsiEncoding, MacRomanEncoding, StandardEncoding)):
            return False
        if isinstance(encoding, DictionaryEncoding):
            for name in encoding.get_differences().values():
                if name == ".notdef":
                    continue
                if not (
                    WinAnsiEncoding.INSTANCE.contains_name(name)
                    and MacRomanEncoding.INSTANCE.contains_name(name)
                    and StandardEncoding.INSTANCE.contains_name(name)
                ):
                    return True
            return False
        return None

    # ---------- code -> unicode (per character) ----------

    def to_unicode(
        self, code: int, custom_glyph_list: GlyphList | None = None
    ) -> str | None:
        """Resolve a single character code to its unicode string.

        Mirrors upstream ``PDSimpleFont.toUnicode(int)`` and
        ``toUnicode(int, GlyphList)``: tries the font's ``/ToUnicode``
        CMap first (so explicit CMap overrides win), then maps the code
        to a glyph name via the font's encoding and looks the name up in
        the glyph list. ``custom_glyph_list`` overrides the AGL but is
        ignored when this font is bound to the Zapf glyph list (matches
        upstream's "don't break Zapf Dingbats" guard). Returns ``None``
        when no mapping can be produced.
        """
        # /ToUnicode CMap wins when present.
        cmap = self.get_to_unicode_cmap()
        if cmap is not None:
            mapped = cmap.to_unicode(code)
            if mapped is not None:
                return mapped
        # Don't override Zapf's glyph list — upstream guard.
        font_glyph_list = self.get_glyph_list()
        if custom_glyph_list is not None and font_glyph_list is GlyphList.DEFAULT:
            unicode_glyph_list = custom_glyph_list
        else:
            unicode_glyph_list = font_glyph_list
        encoding = self.get_encoding_typed()
        if encoding is None:
            return None
        name = encoding.get_name(code)
        return unicode_glyph_list.to_unicode(name)

    # ---------- text <-> bytes ----------

    def encode(self, text: str) -> bytes:
        """Encode a Python string to the font's raw byte representation.

        Per Unicode code point: glyph-list lookup gives the PostScript glyph
        name, the typed encoding gives the byte. Code points outside the
        encoding fall back to ``?`` (matches PDFBox's ``encode`` fallback
        for unmapped glyphs in simple-font writers). When the font has no
        ``/Encoding`` at all, encode as Latin-1.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return text.encode("latin-1", errors="replace")

        unicode_to_code = _unicode_to_code_map(encoding)
        glyph_list = _glyph_list_for(encoding)
        out = bytearray()
        for ch in text:
            code = unicode_to_code.get(ch)
            if code is None:
                # Try a glyph-list round-trip in case the unicode normalises
                # through one of the synthesised uniXXXX / .suffix entries.
                derived = glyph_list.to_unicode(ch)
                if derived is not None:
                    code = unicode_to_code.get(derived)
            if code is None:
                out.append(ord("?"))
            else:
                out.append(code & 0xFF)
        return bytes(out)

    # ---------- writing-mode / widths / subsetting (PDFontLike) ----------

    def is_vertical(self) -> bool:
        """Simple fonts never write vertically.

        Mirrors upstream ``PDSimpleFont.isVertical`` which is hard-coded
        to ``false`` — vertical writing in PDF is only available via
        Type0 / CIDFont (``PDType0Font``).
        """
        return False

    def has_explicit_width(self, code: int) -> bool:
        """``True`` when ``/Widths`` carries an explicit advance for ``code``.

        Mirrors upstream ``PDSimpleFont.hasExplicitWidth(int)``: the
        font dictionary must contain a ``/Widths`` key, and ``code`` must
        fall within ``[FirstChar, FirstChar + len(Widths))``. Default
        widths (the descriptor's ``/MissingWidth``) do not count.
        """
        if self._dict.get_dictionary_object(_WIDTHS) is None:
            return False
        first_char = self._dict.get_int(_FIRST_CHAR, -1)
        if code < first_char:
            return False
        return code - first_char < len(self.get_widths())

    def will_be_subset(self) -> bool:
        """``False`` for simple fonts.

        Mirrors upstream ``PDSimpleFont.willBeSubset``: only TrueType
        subsetting via ``PDType0Font`` is supported. ``PDTrueTypeFont``
        overrides this when subsetting has been requested.
        """
        return False

    def add_to_subset(self, code_point: int) -> None:
        """Register a codepoint for subsetting.

        Mirrors upstream ``PDSimpleFont.addToSubset(int)`` which raises
        ``UnsupportedOperationException``. Concrete subclasses that
        actually support subsetting (``PDTrueTypeFont``) override this.
        """
        raise NotImplementedError(
            "subsetting is not supported for this simple-font subtype"
        )

    def subset(self) -> None:
        """Run subsetting on this font.

        Mirrors upstream ``PDSimpleFont.subset()`` which raises
        ``UnsupportedOperationException``. Concrete subclasses that
        actually support subsetting (``PDTrueTypeFont``) override this.
        """
        raise NotImplementedError(
            "subsetting is not supported for this simple-font subtype"
        )

    @staticmethod
    def is_non_zero_bounding_box(bbox: PDRectangle | None) -> bool:
        """``True`` when ``bbox`` has at least one non-zero corner.

        Mirrors upstream ``PDSimpleFont.isNonZeroBoundingBox(PDRectangle)``
        — used by font-descriptor sanity checks: an all-zero bbox is the
        defaulted / unset case, any non-zero corner means a real bbox is
        present. Returns ``False`` for ``None``.
        """
        if bbox is None:
            return False
        return (
            bbox.get_lower_left_x() != 0.0
            or bbox.get_lower_left_y() != 0.0
            or bbox.get_upper_right_x() != 0.0
            or bbox.get_upper_right_y() != 0.0
        )

    def decode(self, data: bytes) -> str:
        """Decode the font's raw byte representation back to a Python string.

        Per byte: typed encoding gives the glyph name, glyph list gives the
        unicode string. Bytes mapped to ``.notdef`` (or to a glyph the
        glyph-list cannot resolve) are replaced with U+FFFD. When the font
        has no ``/Encoding`` at all, decode as Latin-1.
        """
        encoding = self.get_encoding_typed()
        if encoding is None:
            return data.decode("latin-1", errors="replace")

        glyph_list = _glyph_list_for(encoding)
        out: list[str] = []
        for byte in data:
            name = encoding.get_name(byte)
            unicode = glyph_list.to_unicode(name)
            out.append(unicode if unicode is not None else "�")
        return "".join(out)


__all__ = ["PDSimpleFont"]
