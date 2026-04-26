from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.fontbox.encoding.glyph_list import GlyphList

from .encoding import DictionaryEncoding, Encoding, ZapfDingbatsEncoding
from .pd_font import PDFont

_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")

# Per-encoding (unicode -> code) reverse cache. Keyed by the typed Encoding
# instance identity so the same singleton is shared across PDSimpleFont
# instances; DictionaryEncoding instances naturally get their own entry.
_REVERSE_CACHE: "dict[int, dict[str, int]]" = {}


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
