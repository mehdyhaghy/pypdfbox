"""
PDFDocEncoding — the 256-entry single-byte encoding used inside PDF "text
strings" (PDF 32000-1 §D.3, table D.2). Note that this is *not* a Type 1
font encoding; it is used only to store metadata strings, outline titles,
form-field values and similar text in the document.

Upstream lives at ``org.apache.pdfbox.cos.PDFDocEncoding`` (package-private,
``final class``). We expose it here in ``pypdfbox.pdmodel.common`` because
that package is the natural home for shared encoding helpers in our layout
and PDFBox itself uses the encoding from many ``pdmodel`` call sites.

The PDFDocEncoding shape mirrors upstream's static-method API. Module-level
functions are the primary surface; the ``PDFDocEncoding`` class with
classmethods is provided for upstream-name parity.
"""

from __future__ import annotations

from typing import Final

_REPLACEMENT_CHARACTER: Final[str] = "�"


def _build_tables() -> tuple[list[str], dict[str, int]]:
    # Upstream's CODE_TO_UNI is an ``int[]`` whose unset slots default to 0,
    # and ``toString`` casts each slot to ``(char)``. So any code that is
    # neither given an ISO-8859-1 identity below nor an explicit deviation
    # decodes to U+0000 (NUL) — not U+FFFD. The only such slot in practice
    # is 0xAD (SOFT HYPHEN), which PDFDocEncoding leaves undefined; matching
    # upstream's NUL default here keeps decode parity byte-for-byte
    # (PDFBOX named-destination strings carrying a raw 0xAD differ otherwise).
    code_to_uni: list[str] = ["\u0000"] * 256
    uni_to_code: dict[str, int] = {}

    def _set(code: int, unicode_char: str) -> None:
        code_to_uni[code] = unicode_char
        uni_to_code[unicode_char] = code

    # Initialize with basically ISO-8859-1, skipping codes that have no
    # Unicode counterpart in PDFDocEncoding.
    for i in range(256):
        # Skip entries not in the Unicode column of table D.2.
        if 0x17 < i < 0x20:
            continue
        if 0x7E < i < 0xA1:
            continue
        if i == 0xAD:
            continue
        _set(i, chr(i))

    # Then apply all deviations (based on the table in ISO 32000-1:2008).
    # Block 1
    _set(0x18, "˘")  # BREVE
    _set(0x19, "ˇ")  # CARON
    _set(0x1a, "ˆ")  # MODIFIER LETTER CIRCUMFLEX ACCENT
    _set(0x1b, "˙")  # DOT ABOVE
    _set(0x1c, "˝")  # DOUBLE ACUTE ACCENT
    _set(0x1d, "˛")  # OGONEK
    _set(0x1e, "˚")  # RING ABOVE
    _set(0x1f, "˜")  # SMALL TILDE
    # Block 2
    _set(0x7f, _REPLACEMENT_CHARACTER)  # undefined
    _set(0x80, "•")  # BULLET
    _set(0x81, "†")  # DAGGER
    _set(0x82, "‡")  # DOUBLE DAGGER
    _set(0x83, "…")  # HORIZONTAL ELLIPSIS
    _set(0x84, "—")  # EM DASH
    _set(0x85, "–")  # EN DASH
    _set(0x86, "ƒ")  # LATIN SMALL LETTER SCRIPT F
    _set(0x87, "⁄")  # FRACTION SLASH (solidus)
    _set(0x88, "‹")  # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    _set(0x89, "›")  # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    _set(0x8a, "−")  # MINUS SIGN
    _set(0x8b, "‰")  # PER MILLE SIGN
    _set(0x8c, "„")  # DOUBLE LOW-9 QUOTATION MARK (quotedblbase)
    _set(0x8d, "“")  # LEFT DOUBLE QUOTATION MARK (quotedblleft)
    _set(0x8e, "”")  # RIGHT DOUBLE QUOTATION MARK (quotedblright)
    _set(0x8f, "‘")  # LEFT SINGLE QUOTATION MARK (quoteleft)
    _set(0x90, "’")  # RIGHT SINGLE QUOTATION MARK (quoteright)
    _set(0x91, "‚")  # SINGLE LOW-9 QUOTATION MARK (quotesinglbase)
    _set(0x92, "™")  # TRADE MARK SIGN
    _set(0x93, "ﬁ")  # LATIN SMALL LIGATURE FI
    _set(0x94, "ﬂ")  # LATIN SMALL LIGATURE FL
    _set(0x95, "Ł")  # LATIN CAPITAL LETTER L WITH STROKE
    _set(0x96, "Œ")  # LATIN CAPITAL LIGATURE OE
    _set(0x97, "Š")  # LATIN CAPITAL LETTER S WITH CARON
    _set(0x98, "Ÿ")  # LATIN CAPITAL LETTER Y WITH DIAERESIS
    _set(0x99, "Ž")  # LATIN CAPITAL LETTER Z WITH CARON
    _set(0x9a, "ı")  # LATIN SMALL LETTER DOTLESS I
    _set(0x9b, "ł")  # LATIN SMALL LETTER L WITH STROKE
    _set(0x9c, "œ")  # LATIN SMALL LIGATURE OE
    _set(0x9d, "š")  # LATIN SMALL LETTER S WITH CARON
    _set(0x9e, "ž")  # LATIN SMALL LETTER Z WITH CARON
    _set(0x9f, _REPLACEMENT_CHARACTER)  # undefined
    _set(0xa0, "€")  # EURO SIGN
    # End of deviations.

    return code_to_uni, uni_to_code


_CODE_TO_UNI: list[str]
_UNI_TO_CODE: dict[str, int]
_CODE_TO_UNI, _UNI_TO_CODE = _build_tables()


def contains_char(character: str) -> bool:
    """Return ``True`` if the given UTF-16 character is available in
    PDFDocEncoding. Mirrors upstream ``containsChar(char)``.
    """
    if len(character) != 1:
        return False
    return character in _UNI_TO_CODE


def decode_bytes(data: bytes | bytearray | memoryview) -> str:
    """Decode the given PDFDocEncoded byte sequence to a Python string.

    Mirrors upstream ``toString(byte[])``. Bytes whose code is outside the
    256-entry table (cannot happen for ``bytes`` whose values are in
    ``0..255``, but the upstream loop guards against signed-byte oddities)
    map to ``"?"``; the two codes explicitly flagged "undefined" in the
    table (``0x7F``, ``0x9F``) map to ``U+FFFD`` REPLACEMENT CHARACTER, while
    any slot with no table entry at all (only ``0xAD``) maps to ``U+0000`` —
    matching upstream's ``int[]`` default-of-0 / ``(char)`` cast.
    """
    out: list[str] = []
    for b in data:
        if b >= len(_CODE_TO_UNI):
            out.append("?")
        else:
            out.append(_CODE_TO_UNI[b])
    return "".join(out)


def encode_bytes(text: str) -> bytes:
    """Encode the given string with PDFDocEncoding. Mirrors upstream
    ``getBytes(String)``.

    Characters not representable in PDFDocEncoding map to ``0x00``, exactly
    matching upstream's ``getOrDefault(c, 0)`` behaviour. Callers that need
    to detect unmappable characters should pre-check with
    :func:`contains_char`.
    """
    return bytes(_UNI_TO_CODE.get(c, 0) for c in text)


def get_char_code(character: str) -> int | None:
    """Return the PDFDocEncoded byte for the given Unicode character, or
    ``None`` if it is not representable. Pythonic helper that complements
    :func:`contains_char` (upstream relies on the underlying
    ``UNI_TO_CODE`` map being package-private).
    """
    if len(character) != 1:
        return None
    return _UNI_TO_CODE.get(character)


def set(code: int, unicode_char: str) -> None:  # noqa: A001 - mirror upstream name
    """Register a code → Unicode mapping in the PDFDocEncoding tables.

    Mirrors upstream ``PDFDocEncoding.set(int code, char unicode)`` —
    private in Java but exposed here under the upstream snake_case
    spelling for parity with code ported from PDFBox that calls it to
    register custom deviations. Both directions of the
    code↔Unicode mapping are updated.

    ``code`` must be in ``0..255`` (the size of the PDFDocEncoding
    table); ``unicode_char`` must be a single character.
    """
    if not (0 <= code < len(_CODE_TO_UNI)):
        raise ValueError(
            f"code must be in 0..{len(_CODE_TO_UNI) - 1}, got {code}"
        )
    if len(unicode_char) != 1:
        raise ValueError(
            f"unicode_char must be a single character, got len={len(unicode_char)}"
        )
    _CODE_TO_UNI[code] = unicode_char
    _UNI_TO_CODE[unicode_char] = code


class PDFDocEncoding:
    """Upstream-name parity wrapper around the module-level functions.

    Mirrors ``org.apache.pdfbox.cos.PDFDocEncoding``'s static surface so
    code ported from PDFBox can call ``PDFDocEncoding.toString(...)`` /
    ``PDFDocEncoding.getBytes(...)`` / ``PDFDocEncoding.containsChar(...)``
    with the snake_case pypdfbox conventions.
    """

    # Direct upstream-named static methods (with snake_case per the
    # project's "camelCase → snake_case only" rule).

    @staticmethod
    def to_string(data: bytes | bytearray | memoryview) -> str:
        """Mirrors upstream ``toString(byte[])``."""
        return decode_bytes(data)

    @staticmethod
    def get_bytes(text: str) -> bytes:
        """Mirrors upstream ``getBytes(String)``."""
        return encode_bytes(text)

    @staticmethod
    def contains_char(character: str) -> bool:
        """Mirrors upstream ``containsChar(char)``."""
        return contains_char(character)

    @staticmethod
    def get_char_code(character: str) -> int | None:
        """Pythonic accessor for the byte code of a given character."""
        return get_char_code(character)

    @staticmethod
    def set(code: int, unicode_char: str) -> None:  # noqa: A003 - mirror upstream name
        """Register a code → Unicode mapping in the PDFDocEncoding tables.

        Mirrors upstream ``PDFDocEncoding.set(int, char)`` (private static
        in Java, used internally by the table initializer). Exposed here
        under the same name so ported code can call ``PDFDocEncoding.set``
        directly without needing the module-level alias.
        """
        set(code, unicode_char)


__all__ = [
    "PDFDocEncoding",
    "contains_char",
    "decode_bytes",
    "encode_bytes",
    "get_char_code",
    "set",
]
