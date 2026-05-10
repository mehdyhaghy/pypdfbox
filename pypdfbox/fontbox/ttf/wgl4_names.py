from __future__ import annotations

# Windows Glyph List 4 (WGL4) names for Mac glyphs.
# Mirrors org.apache.fontbox.ttf.WGL4Names. Used by `post` table (formats 1 and 2).

NUMBER_OF_MAC_GLYPHS: int = 258

_MAC_GLYPH_NAMES: tuple[str, ...] = (
    ".notdef", ".null", "nonmarkingreturn", "space", "exclam", "quotedbl",
    "numbersign", "dollar", "percent", "ampersand", "quotesingle",
    "parenleft", "parenright", "asterisk", "plus", "comma", "hyphen",
    "period", "slash", "zero", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "colon", "semicolon", "less",
    "equal", "greater", "question", "at", "A", "B", "C", "D", "E", "F",
    "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S",
    "T", "U", "V", "W", "X", "Y", "Z", "bracketleft", "backslash",
    "bracketright", "asciicircum", "underscore", "grave", "a", "b",
    "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o",
    "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "braceleft",
    "bar", "braceright", "asciitilde", "Adieresis", "Aring",
    "Ccedilla", "Eacute", "Ntilde", "Odieresis", "Udieresis", "aacute",
    "agrave", "acircumflex", "adieresis", "atilde", "aring",
    "ccedilla", "eacute", "egrave", "ecircumflex", "edieresis",
    "iacute", "igrave", "icircumflex", "idieresis", "ntilde", "oacute",
    "ograve", "ocircumflex", "odieresis", "otilde", "uacute", "ugrave",
    "ucircumflex", "udieresis", "dagger", "degree", "cent", "sterling",
    "section", "bullet", "paragraph", "germandbls", "registered",
    "copyright", "trademark", "acute", "dieresis", "notequal", "AE",
    "Oslash", "infinity", "plusminus", "lessequal", "greaterequal",
    "yen", "mu", "partialdiff", "summation", "product", "pi",
    "integral", "ordfeminine", "ordmasculine", "Omega", "ae", "oslash",
    "questiondown", "exclamdown", "logicalnot", "radical", "florin",
    "approxequal", "Delta", "guillemotleft", "guillemotright",
    "ellipsis", "nonbreakingspace", "Agrave", "Atilde", "Otilde", "OE",
    "oe", "endash", "emdash", "quotedblleft", "quotedblright",
    "quoteleft", "quoteright", "divide", "lozenge", "ydieresis",
    "Ydieresis", "fraction", "currency", "guilsinglleft",
    "guilsinglright", "fi", "fl", "daggerdbl", "periodcentered",
    "quotesinglbase", "quotedblbase", "perthousand", "Acircumflex",
    "Ecircumflex", "Aacute", "Edieresis", "Egrave", "Iacute",
    "Icircumflex", "Idieresis", "Igrave", "Oacute", "Ocircumflex",
    "apple", "Ograve", "Uacute", "Ucircumflex", "Ugrave", "dotlessi",
    "circumflex", "tilde", "macron", "breve", "dotaccent", "ring",
    "cedilla", "hungarumlaut", "ogonek", "caron", "Lslash", "lslash",
    "Scaron", "scaron", "Zcaron", "zcaron", "brokenbar", "Eth", "eth",
    "Yacute", "yacute", "Thorn", "thorn", "minus", "multiply",
    "onesuperior", "twosuperior", "threesuperior", "onehalf",
    "onequarter", "threequarters", "franc", "Gbreve", "gbreve",
    "Idotaccent", "Scedilla", "scedilla", "Cacute", "cacute", "Ccaron",
    "ccaron", "dcroat",
)

assert len(_MAC_GLYPH_NAMES) == NUMBER_OF_MAC_GLYPHS

_MAC_GLYPH_NAMES_INDICES: dict[str, int] = {
    name: i for i, name in enumerate(_MAC_GLYPH_NAMES)
}


def get_glyph_index(name: str) -> int | None:
    """Return the index of ``name`` in the WGL4 list, or ``None`` if missing."""
    return _MAC_GLYPH_NAMES_INDICES.get(name)


def get_glyph_name(index: int) -> str | None:
    """Return the WGL4 name at ``index``, or ``None`` if out of range."""
    if 0 <= index < NUMBER_OF_MAC_GLYPHS:
        return _MAC_GLYPH_NAMES[index]
    return None


def get_all_names() -> list[str]:
    """Return a fresh list of all 258 names."""
    return list(_MAC_GLYPH_NAMES)


class WGL4Names:
    """Static container mirroring upstream's all-static ``WGL4Names`` API.

    Mirrors ``org.apache.fontbox.ttf.WGL4Names`` from upstream Apache
    PDFBox 3.0.x. Upstream is a final class with a private constructor
    and only static accessors. We expose the same surface as
    staticmethods so call sites that read like
    ``WGL4Names.getGlyphIndex(name)`` translate cleanly.
    """

    NUMBER_OF_MAC_GLYPHS = NUMBER_OF_MAC_GLYPHS

    @staticmethod
    def get_glyph_index(name: str) -> int | None:
        """Module-level alias of :func:`get_glyph_index`."""
        return get_glyph_index(name)

    @staticmethod
    def get_glyph_name(index: int) -> str | None:
        """Module-level alias of :func:`get_glyph_name`."""
        return get_glyph_name(index)

    @staticmethod
    def get_all_names() -> list[str]:
        """Module-level alias of :func:`get_all_names`."""
        return get_all_names()


__all__ = [
    "NUMBER_OF_MAC_GLYPHS",
    "WGL4Names",
    "get_all_names",
    "get_glyph_index",
    "get_glyph_name",
]
